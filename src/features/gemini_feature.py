import google.genai as genai
from google.genai import types, errors
from discord.ext import commands
from discord import Message
from config import ConfigManager
from collections import OrderedDict
from typing import List
from datetime import datetime, timezone, timedelta


class GeminiFeature:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = ConfigManager()
        self.gemini_api_key = self.config.get_gemini_key()
        self.gemini_model_name = "gemini-2.5-flash"
        self.client = genai.Client(api_key=self.gemini_api_key)

        self.conversations: OrderedDict[int, list[types.Content]] = OrderedDict()
        self.MAX_ACTIVE_CONVERSATIONS = 50
        self.MAX_CONVERSATION_HISTORY_MESSAGES = 50

    def _make_gemini_request(
        self,
        conversation_contents: list[types.Content],
        system_instruction_text: str | None,
    ) -> str | None:
        """
        Makes a request to the Gemini API with the given conversation history and system instruction.
        Returns the text response or an error message string.
        """
        if not conversation_contents:
            print("Gemini Feature: Conversation contents list is empty.")
            return "Sorry, there's no conversation to continue with."

        gen_config_params = {}
        if system_instruction_text:
            gen_config_params["system_instruction"] = system_instruction_text

        generation_config = (
            types.GenerateContentConfig(**gen_config_params)
            if gen_config_params
            else None
        )

        # Explicitly create a new list to help the type checker
        # recognize the elements as compatible with ContentUnion,
        # addressing the list invariance issue.
        contents_for_api: List[types.ContentUnion] = [
            item for item in conversation_contents
        ]

        try:
            response = self.client.models.generate_content(
                model=self.gemini_model_name,
                contents=contents_for_api,  # Use the new list
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
                        and rating.probability.value
                        >= types.HarmProbability.LOW.value  # Added checks for rating.probability and rating.category
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
            # Removed the check for resource_exhausted as it's not a valid attribute per error message and documentation
            else:
                # This block will now also handle potential resource exhaustion errors if they come as a general APIError
                print(
                    f"Gemini Feature: Google API error: {e.code if hasattr(e, 'code') else 'Unknown code'} - {e.message}"
                )
                return f"Sorry, a Google API error occurred: {e.message}"
        except Exception as e:
            print(f"Gemini Feature: An unexpected error occurred: {e}")
            return "Sorry, an unexpected error occurred while communicating with the AI service."

    def _cleanup_old_conversations(self):
        """Removes the oldest conversation histories if exceeding MAX_ACTIVE_CONVERSATIONS."""
        while len(self.conversations) > self.MAX_ACTIVE_CONVERSATIONS:
            self.conversations.popitem(last=False)

    async def setup(self):
        """Registers the !gemini command."""

        @commands.command(name="rundown")
        async def rundown_command(ctx: commands.Context, minutes: int = 10):
            """Fetches all messages in the current channel from the past x minutes and asks Gemini for a summary and what each person argued for."""
            minutes = max(1, min(minutes, 2000))
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)

            messages_2d: list[list[str]] = []

            async for msg in ctx.channel.history(limit=1000, oldest_first=True):
                if msg.created_at >= cutoff:
                    username = msg.author.display_name
                    if username in ("ChatArchive", "BNBD"):
                        continue
                    messages_2d.append([username, msg.content])

            print(f"Total messages included: {len(messages_2d)}")

            # Prepare prompt for Gemini
            prompt = (
                "Here is a list of messages from a Discord channel. "
                "Each entry is a list of two items: [sender, message]. "
                "The list is ordered from earliest to latest. "
                "Please provide an overall summary of what the conversation was about, "
                "and summarize what each person argued for or contributed. "
                "Keep your response concise and brief."
                f"{messages_2d}"
            )

            system_instruction = "Summarize the conversation and each participant's arguments based on the provided message list."
            async with ctx.typing():
                summary = self._make_gemini_request(
                    [types.Content(role="user", parts=[types.Part(text=prompt)])],
                    system_instruction,
                )

            if not summary:
                await ctx.reply("Sorry, Gemini did not return a summary.")
                return

            if len(summary) > 1900:
                summary = summary[:1900] + "..."

            await ctx.reply(
                f"Rundown summary for the {len(messages_2d)} messages from the past {minutes} minutes:\n{summary}"
            )

        self.bot.add_command(rundown_command)

        @commands.command(name="gemini")
        async def gemini_command(ctx: commands.Context, *, prompt: str):
            """Talk to the Gemini AI. Reply to the bot's previous messages to continue a conversation."""
            if not prompt:
                await ctx.reply("Please provide a prompt for Gemini!")
                return

            user_current_prompt_text = prompt
            system_instruction = "Please keep your response concise and brief."
            current_conversation_history: list[types.Content] = []

            if ctx.message.reference and ctx.message.reference.resolved:
                replied_message: Message = ctx.message.reference.resolved  # type: ignore
                if replied_message.author == self.bot.user:
                    retrieved_history = self.conversations.get(replied_message.id)
                    if retrieved_history:
                        current_conversation_history = list(replied_message)
                        self.conversations.move_to_end(replied_message.id)

            current_conversation_history.append(
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=user_current_prompt_text)],
                )
            )

            if (
                len(current_conversation_history)
                > self.MAX_CONVERSATION_HISTORY_MESSAGES
            ):
                current_conversation_history = current_conversation_history[
                    -self.MAX_CONVERSATION_HISTORY_MESSAGES :
                ]

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

            sent_discord_messages: list[Message] = []
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
                    msg_obj = await ctx.reply(
                        message_to_send_discord
                    )  # Changed from ctx.send
                    sent_discord_messages.append(msg_obj)
                except Exception as e:
                    print(f"Error sending Discord message part: {e}")
                    await ctx.reply(
                        f"Error sending part of the response: {e}"
                    )  # Changed from ctx.send

            if sent_discord_messages and not is_error_response:
                final_sent_message_id = sent_discord_messages[-1].id

                history_to_store = list(current_conversation_history)
                history_to_store.append(
                    types.Content(
                        role="model",
                        parts=[types.Part.from_text(text=raw_ai_response_text)],
                    )
                )

                if len(history_to_store) > self.MAX_CONVERSATION_HISTORY_MESSAGES:
                    history_to_store = history_to_store[
                        -self.MAX_CONVERSATION_HISTORY_MESSAGES :
                    ]

                self.conversations[final_sent_message_id] = history_to_store
                self._cleanup_old_conversations()

        self.bot.add_command(gemini_command)
        print("Gemini feature loaded and command registered with conversation context.")
