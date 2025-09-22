import google.genai as genai
from google.genai import types, errors
from discord.ext import commands
from discord import Message
from config import ConfigManager
from typing import List


class GeminiFeature:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = ConfigManager()
        self.gemini_api_key = self.config.get_gemini_key()
        self.gemini_model_name = "gemini-2.5-flash"
        self.client = genai.Client(api_key=self.gemini_api_key)

        self.MAX_CONVERSATION_HISTORY_MESSAGES = 50

    def _make_gemini_request(
        self,
        conversation_contents: list[types.Content],
        system_instruction_text: str | None,
    ) -> str | None:
        """
        Makes a request to the Gemini API with the given conversation history and system instruction,
        with grounding enabled.
        Returns the text response or an error message string.
        """
        if not conversation_contents:
            print("Gemini Feature: Conversation contents list is empty.")
            return "Sorry, there's no conversation to continue with."

        google_search_tool = types.Tool(google_search=types.GoogleSearch())

        gen_config_params = {"tools": [google_search_tool]}
        if system_instruction_text:
            gen_config_params["system_instruction"] = system_instruction_text

        generation_config = types.GenerateContentConfig(**gen_config_params)

        contents_for_api: List[types.ContentUnion] = [
            item for item in conversation_contents
        ]

        try:
            response = self.client.models.generate_content(
                model=self.gemini_model_name,
                contents=contents_for_api,
                config=generation_config,
            )

            if response and response.text:
                return response.text
            elif (
                response
                and response.prompt_feedback
                and response.prompt_feedback.block_reason
            ):
                block_reason = response.prompt_feedback.block_reason
                safety_ratings_info = ""
                if response.candidates and response.candidates[0].safety_ratings:
                    problematic_ratings = [
                        f"{rating.category.name} ({rating.probability.name})"
                        for rating in response.candidates[0].safety_ratings
                        if rating.probability
                        and rating.category
                        and rating.probability.value >= types.HarmProbability.LOW.value
                    ]
                    if problematic_ratings:
                        safety_ratings_info = (
                            f" due to: {', '.join(problematic_ratings)}"
                        )

                print(
                    f"Gemini Feature: Content blocked. Reason: {block_reason}{safety_ratings_info}. Full response: {response}"
                )
                return f"Sorry, your request was blocked by the AI's safety filters (Reason: {block_reason.name}{safety_ratings_info}). Please rephrase your prompt."
            else:
                print(
                    f"Gemini Feature: No text response or block reason. Response: {response}"
                )
                return "Sorry, the AI did not return a recognizable text response."

        except errors.APIError as e:
            if e.code == 404:
                print(
                    f"Gemini Feature: Model not found or API endpoint issue: {e.message}"
                )
                return "Sorry, the specified Gemini model was not found or there's an issue with the API endpoint."
            else:
                print(
                    f"Gemini Feature: Google API error: {e.code if hasattr(e, 'code') else 'Unknown code'} - {e.message}"
                )
                return f"Sorry, a Google API error occurred: {e.message}"
        except Exception as e:
            print(f"Gemini Feature: An unexpected error occurred: {e}")
            return "Sorry, an unexpected error occurred while communicating with the AI service."

    async def setup(self):
        """Registers the !ask command with conversation context."""

        @commands.command(name="ask", aliases=["gemini", "miku"])
        async def gemini_command(ctx: commands.Context, *, prompt: str):
            """Talk to the Gemini AI. Reply to the bot's previous messages to continue a conversation."""
            if not prompt:
                await ctx.reply("Please provide a prompt for Gemini!")
                return

            user_current_prompt_text = prompt
            system_instruction = "Please keep your response concise and brief."
            current_conversation_history: list[types.Content] = []

            # Dynamically build conversation history from the reply chain
            if ctx.message.reference and ctx.message.reference.resolved:
                print(
                    "Gemini Feature: Found a reply. Building conversation history from the chain."
                )
                current_message = ctx.message.reference.resolved

                # The resolved attribute can be a Message or a DeletedReferencedMessage.
                # We only care about actual messages.
                while isinstance(current_message, Message):
                    # Determine the role based on the author of the message
                    author_role = (
                        "model" if current_message.author == self.bot.user else "user"
                    )

                    print(
                        f"Gemini Feature: Adding message from '{author_role}' with content: '{current_message.content[:70]}...'"
                    )

                    current_conversation_history.insert(
                        0,
                        types.Content(
                            role=author_role,
                            parts=[types.Part.from_text(text=current_message.content)],
                        ),
                    )

                    # Traverse up the reply chain.
                    if current_message.reference and isinstance(
                        current_message.reference.resolved, Message
                    ):
                        current_message = current_message.reference.resolved
                    else:
                        # End of the chain
                        print("Gemini Feature: Reached the end of the reply chain.")
                        break

            # Add the user's current prompt as the last message in the history
            current_conversation_history.append(
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=user_current_prompt_text)],
                )
            )

            # Trim the history if it exceeds the maximum length
            if (
                len(current_conversation_history)
                > self.MAX_CONVERSATION_HISTORY_MESSAGES
            ):
                current_conversation_history = current_conversation_history[
                    -self.MAX_CONVERSATION_HISTORY_MESSAGES :
                ]
                print(
                    f"Gemini Feature: Conversation history trimmed to the last {self.MAX_CONVERSATION_HISTORY_MESSAGES} messages."
                )

            print(
                f"Gemini Feature: Sending {len(current_conversation_history)} message(s) to the Gemini API."
            )

            async with ctx.typing():
                raw_ai_response_text = await self.bot.loop.run_in_executor(
                    None,
                    self._make_gemini_request,
                    current_conversation_history,
                    system_instruction,
                )

            if not raw_ai_response_text:
                await ctx.reply(
                    "Sorry, an unknown error occurred and no response was generated from Gemini."
                )
                return

            is_error_response = raw_ai_response_text.startswith("Sorry,")

            display_text_parts = []
            if not is_error_response and len(raw_ai_response_text) > 2000:
                current_part = ""
                for line in raw_ai_response_text.splitlines(keepends=True):
                    if len(current_part) + len(line) > 1980:
                        display_text_parts.append(current_part.strip())
                        current_part = line
                    else:
                        current_part += line
                if current_part.strip():
                    display_text_parts.append(current_part.strip())
            else:
                display_text_parts.append(raw_ai_response_text)

            for i, text_content_for_part in enumerate(display_text_parts):
                if not text_content_for_part.strip():
                    continue

                message_to_send_discord: str
                if is_error_response:
                    # Error messages are always sent as plain text.
                    message_to_send_discord = text_content_for_part
                else:
                    # Check if the AI's response part is already formatted as a full code block.
                    # We trim to ensure leading/trailing whitespace doesn't break the check.
                    trimmed_content = text_content_for_part.strip()
                    is_already_formatted_as_code_block = trimmed_content.startswith(
                        "```"
                    ) and trimmed_content.endswith("```")

                    if is_already_formatted_as_code_block:
                        # If the AI already provided a full code block, send it as is.
                        # Using the original text_content_for_part to preserve any original formatting/spacing.
                        message_to_send_discord = text_content_for_part
                    else:
                        # If it's not an error response and not an explicit, full-part code block,
                        # send it as a normal Discord message. Discord will still parse
                        # any inline or block code within the text_content_for_part.
                        message_to_send_discord = text_content_for_part

                try:
                    # Reply to the user's command to allow for easy continuation of the conversation chain
                    await ctx.reply(message_to_send_discord)
                except Exception as e:
                    print(f"Error sending Discord message part: {e}")
                    await ctx.reply(f"Error sending part of the response: {e}")

        self.bot.add_command(gemini_command)
        print(
            "Gemini feature loaded and command registered with dynamic conversation context."
        )
