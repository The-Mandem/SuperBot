import requests
from discord.ext import commands
from config import ConfigManager

class GeminiFeature:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = ConfigManager()
        self.gemini_api_key = self.config.get_gemini_key()
        self.gemini_model = "gemini-2.0-flash"
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent?key={self.gemini_api_key}"


    def _make_gemini_request(self, prompt: str) -> str | None:
        """Makes a request to the Gemini API and returns the text response."""
        headers = {"Content-Type": "application/json"}
        data = {"contents": [{"parts": [{"text": prompt}]}]}
        response = None

        try:
            response = requests.post(self.api_url, headers=headers, json=data, timeout=120) # 120-second timeout
            response.raise_for_status()  # Raises HTTPError for bad responses (4XX or 5XX)

            response_json = response.json()

            # Defensive parsing of the response
            candidates = response_json.get("candidates")
            if not candidates or not isinstance(candidates, list) or not candidates[0].get("content"):
                print(f"Gemini Feature: Unexpected response structure: {response_json}")
                return "Sorry, I received an unexpected response format from the AI."

            parts = candidates[0]["content"].get("parts")
            if not parts or not isinstance(parts, list) or not parts[0].get("text"):
                print(f"Gemini Feature: Text part missing in response: {response_json}")
                return "Sorry, I couldn't extract a text response from the AI."

            return parts[0]["text"]

        except requests.exceptions.HTTPError as e:
            error_details = e.response.json() if e.response else str(e)
            print(f"Gemini Feature: HTTP Error {e.response.status_code if e.response else 'N/A'} - {error_details}")
            # Try to extract a more user-friendly error from Gemini's response if available
            gemini_error_message = "An internal error occurred with the AI service."
            if e.response is not None:
                try:
                    error_data = e.response.json()
                    if "error" in error_data and "message" in error_data["error"]:
                        gemini_error_message = error_data["error"]["message"]
                except ValueError:
                    pass
            return f"Sorry, I encountered an error with the AI service (HTTP {e.response.status_code if e.response else 'N/A'}). Details: {gemini_error_message}"
        except requests.exceptions.RequestException as e:
            print(f"Gemini Feature: Request failed: {e}")
            return "Sorry, I couldn't connect to the AI service. Please try again later."
        except (IndexError, KeyError, TypeError) as e:
            response_text = response.text if response is not None else 'N/A'
            print(f"Gemini Feature: Error parsing Gemini response: {e}. Response: {response_text}")
            return "Sorry, I received an unparseable response from the AI."


    async def setup(self):
        """Registers the !gemini command."""

        @commands.command(name="gemini")
        async def gemini_command(ctx: commands.Context, *, prompt: str):
            """Talk to the Gemini AI."""
            if not prompt:
                await ctx.send("Please provide a prompt for Gemini!")
                return

            # Append instruction to keep the response short
            modified_prompt = f"{prompt}\n\nInstruction: Please keep your response concise and brief."

            async with ctx.typing(): # Shows "Bot is typing..."
                response_text = await self.bot.loop.run_in_executor(
                    None, self._make_gemini_request, modified_prompt
                )

            if response_text:
                # Handle long messages by splitting them
                # Even with the instruction to be brief, the model might still generate long text.
                if len(response_text) > 2000: # Discord character limit per message
                    parts = []
                    current_part = ""
                    for line in response_text.splitlines(keepends=True):
                        if len(current_part) + len(line) > 1990: # Leave some buffer
                            parts.append(current_part.strip())
                            current_part = line
                        else:
                            current_part += line
                    if current_part.strip(): # Add the last part
                        parts.append(current_part.strip())

                    for i, part_text in enumerate(parts):
                        if i == 0 and not part_text.startswith("```"): # Add code blocks if not already present for first part
                             await ctx.send(f"```{part_text}```")
                        elif part_text.strip(): # Send subsequent parts, ensuring they are not empty
                             await ctx.send(f"```{part_text}```") # Enclose all parts in code blocks for consistency
                else:
                    await ctx.send(response_text)
            else:
                # _make_gemini_request should return an error message string if it fails.
                # If it returns None truly (should not happen with current logic), provide a generic error.
                await ctx.send("Sorry, an unknown error occurred while getting a response from Gemini.")

        self.bot.add_command(gemini_command)
        print("Gemini feature loaded and command registered.")