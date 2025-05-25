import google.genai as genai
from discord.ext import commands
from config import ConfigManager
from google.api_core import exceptions


class GeminiFeature:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = ConfigManager()
        self.gemini_api_key = self.config.get_gemini_key()
        self.gemini_model_name = "gemini-2.5-flash-preview-04-17-thinking"
        self.client = genai.Client(api_key=self.gemini_api_key)

    def _make_gemini_request(self, prompt: str) -> str | None:
        """Makes a request to the Gemini API using the SDK and returns the text response."""
        response = None

        try:
            response = self.client.models.generate_content(
                model=self.gemini_model_name, contents=[prompt]
            )

            # Check if response and text exist
            if response and response.text:
                return response.text
            else:
                print(f"Gemini Feature: No text response returned: {response}")
                return "Sorry, the AI did not return a text response."

        except exceptions.NotFound as e:
            print(f"Gemini Feature: Model not found: {e}")
            return (
                "Sorry, the specified Gemini model was not found or is not available."
            )
        except exceptions.GoogleAPIError as e:
            print(f"Gemini Feature: Google API error: {e}")
            return f"Sorry, a Google API error occurred: {e}"
        except Exception as e:
            print(f"Gemini Feature: An unexpected error occurred: {e}")
            return "Sorry, an unexpected error occurred while communicating with the AI service."

    async def setup(self):
        """Registers the !gemini command."""

        @commands.command(name="gemini")
        async def gemini_command(ctx: commands.Context, *, prompt: str):
            """Talk to the Gemini AI."""
            if not prompt:
                await ctx.send("Please provide a prompt for Gemini!")
                return

            # Append instruction to keep the response short
            modified_prompt = (
                f"{prompt}\n\nInstruction: Please keep your response concise and brief."
            )

            async with ctx.typing():  # Shows "Bot is typing..."
                response_text = await self.bot.loop.run_in_executor(
                    None, self._make_gemini_request, modified_prompt
                )

            if response_text:
                # Handle long messages by splitting them
                # Even with the instruction to be brief, the model might still generate long text.
                if len(response_text) > 2000:  # Discord character limit per message
                    parts = []
                    current_part = ""
                    for line in response_text.splitlines(keepends=True):
                        if len(current_part) + len(line) > 1990:  # Leave some buffer
                            parts.append(current_part.strip())
                            current_part = line
                        else:
                            current_part += line
                    if current_part.strip():  # Add the last part
                        parts.append(current_part.strip())

                    for i, part_text in enumerate(parts):
                        if i == 0 and not part_text.startswith(
                            "```"
                        ):  # Add code blocks if not already present for first part
                            await ctx.send(f"```{part_text}```")
                        elif (
                            part_text.strip()
                        ):  # Send subsequent parts, ensuring they are not empty
                            await ctx.send(
                                f"```{part_text}```"
                            )  # Enclose all parts in code blocks for consistency
                else:
                    await ctx.send(response_text)
            else:
                # _make_gemini_request should return an error message string if it fails.
                # If it returns None truly (should not happen with current logic), provide a generic error.
                await ctx.send(
                    "Sorry, an unknown error occurred while getting a response from Gemini."
                )

        self.bot.add_command(gemini_command)
        print("Gemini feature loaded and command registered.")
