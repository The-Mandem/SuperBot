import google.genai as genai
import re
from google.genai import types, errors
from discord.ext import commands
from config import ConfigManager
from typing import List
from datetime import datetime, timezone, timedelta


class RundownFeature:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = ConfigManager()
        self.gemini_api_key = self.config.get_gemini_key()
        self.gemini_model_name = "gemini-2.5-flash"
        self.client = genai.Client(api_key=self.gemini_api_key)

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

    _DURATION_RE = re.compile(r"^\s*(\d+)\s*([mMhH]?)\s*$")

    @staticmethod
    def _parse_duration_to_timedelta(duration_raw: str):
        """
        Accepts: '60m', '12h', '45' (defaults to minutes)
        Returns: (timedelta, amount_int, unit_str) where unit_str is 'minute(s)' or 'hour(s)'
        Raises: ValueError on invalid/too-large input
        """
        match = RundownFeature._DURATION_RE.match(duration_raw or "")
        if not match:
            raise ValueError("Invalid duration. Try `!rundown 60m` or `!rundown 2h`.")

        value = int(match.group(1))
        suffix = (match.group(2) or "m").lower()

        # sane upper bound — tweak as you like
        MAX_HOURS = 24 * 7  # 7 days
        if suffix == "h":
            if value > MAX_HOURS:
                raise ValueError(f"Duration too large. Max is {MAX_HOURS}h.")
            amount = value
            unit = "hour" if value == 1 else "hours"
            delta = timedelta(hours=value)
        else:
            # minutes path
            if value > MAX_HOURS * 60:
                raise ValueError(f"Duration too large. Max is {MAX_HOURS * 60}m.")
            amount = value
            unit = "minute" if value == 1 else "minutes"
            delta = timedelta(minutes=value)

        return delta, amount, unit

    async def setup(self):
        """Registers the !rundown command."""

        @commands.command(name="rundown")
        async def rundown_command(ctx: commands.Context, duration: str = "10m"):
            """
            Fetch messages from the past <duration> and summarize.
            Examples: !rundown 60m, !rundown 2h, !rundown 45  (45 defaults to minutes)
            """
            try:
                delta, amount, unit = RundownFeature._parse_duration_to_timedelta(
                    duration
                )
            except ValueError as e:
                await ctx.reply(str(e))
                return

            cutoff = datetime.now(timezone.utc) - delta

            messages_2d: list[list[str]] = []

            async for msg in ctx.channel.history(limit=1000):
                # We process newest messages first. If a message is older than the cutoff,
                # all subsequent messages will also be older, so we can stop early.
                if msg.created_at < cutoff:
                    break

                username = msg.author.display_name
                if username in ("ChatArchive", "BNBD"):
                    continue
                messages_2d.append([username, msg.content])

            # Since we fetched newest-to-oldest, we must reverse the list
            # so it's in chronological order (oldest-to-newest) for the AI.
            messages_2d.reverse()

            print(f"Total messages included: {len(messages_2d)}")

            # Prepare prompt for Gemini
            prompt = (
                "Here is a list of messages from a Discord channel. "
                "Each entry is a list of two items: [sender, message]. "
                "The list is ordered from earliest to latest. "
                "Please provide a short overall summary of what the conversation was about, "
                "and summarize what each person argued for or contributed. "
                "Keep your response concise and brief, it MUST be under 2000 characters in total. Sacrifice detail if needed to stay under this limit. This limit is non negotiable."
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
                f"Ts da runDown :3 for the {len(messages_2d)} messages from the past {amount} {unit}:\n{summary}"
            )

        self.bot.add_command(rundown_command)
        print("Rundown feature loaded and command registered.")
