import re
from google.genai import types
from discord.ext import commands
from datetime import datetime, timezone, timedelta
from services.gemini_service import GeminiService


class RundownCog(commands.Cog, name="Rundown"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.gemini_service = GeminiService()

    _DURATION_RE = re.compile(r"^\s*(\d+)\s*([mMhH]?)\s*$")

    @staticmethod
    def _parse_duration_to_timedelta(duration_raw: str):
        """
        Accepts: '60m', '12h', '45' (defaults to minutes)
        Returns: (timedelta, amount_int, unit_str) where unit_str is 'minute(s)' or 'hour(s)'
        Raises: ValueError on invalid/too-large input
        """
        match = RundownCog._DURATION_RE.match(duration_raw or "")
        if not match:
            raise ValueError("Invalid duration. Try `!rundown 60m` or `!rundown 2h`.")

        value = int(match.group(1))
        suffix = (match.group(2) or "m").lower()

        MAX_HOURS = 24 * 7
        if suffix == "h":
            if value > MAX_HOURS:
                raise ValueError(f"Duration too large. Max is {MAX_HOURS}h.")
            amount = value
            unit = "hour" if value == 1 else "hours"
            delta = timedelta(hours=value)
        else:
            if value > MAX_HOURS * 60:
                raise ValueError(f"Duration too large. Max is {MAX_HOURS * 60}m.")
            amount = value
            unit = "minute" if value == 1 else "minutes"
            delta = timedelta(minutes=value)

        return delta, amount, unit

    @commands.command(name="rundown")
    async def rundown_command(self, ctx: commands.Context, duration: str = "10m"):
        """
        Fetch messages from the past <duration> and summarize.
        Examples: !rundown 60m, !rundown 2h, !rundown 45 (defaults to minutes)
        """
        try:
            delta, amount, unit = self._parse_duration_to_timedelta(duration)
        except ValueError as e:
            await ctx.reply(str(e))
            return

        cutoff = datetime.now(timezone.utc) - delta
        messages_2d: list[list[str]] = []

        async for msg in ctx.channel.history(limit=1000):
            if msg.created_at < cutoff:
                break

            if msg.content.strip().lower().startswith(
                "!rundown"
            ) or msg.author.display_name in ("ChatArchive", "BNBD"):
                continue

            messages_2d.append([msg.author.display_name, msg.content])

        messages_2d.reverse()

        if not messages_2d:
            await ctx.reply(
                f"No messages found in the last {amount} {unit} to summarize."
            )
            return

        print(f"Total messages included: {len(messages_2d)}")

        prompt = (
            "You are a Discord summarization bot. Provide a concise summary of the conversation, "
            "highlighting the main topics discussed and who contributed to each. "
            "Keep the overall summary brief, aiming for readability. "
            "Use bullet points to mention key speakers and their main points. "
            "The entire response should be under 1200 characters. "
            f"Here is the conversation history, where each item is [sender, message]:\n\n{messages_2d}"
        )

        system_instruction = (
            "Summarize the key topics and associated speakers from the provided Discord messages concisely. "
            "Prioritize readability with a brief overview and bulleted speaker contributions."
        )

        async with ctx.typing():
            summary = self.gemini_service.make_gemini_request(
                [types.Content(role="user", parts=[types.Part(text=prompt)])],
                system_instruction,
            )

        if not summary:
            await ctx.reply("Sorry, the AI did not return a summary.")
            return

        if len(summary) > 1900:
            summary = summary[:1900] + "..."

        await ctx.reply(
            f"Ts da runDown :3 for the {len(messages_2d)} messages from the past {amount} {unit}:\n{summary}"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(RundownCog(bot))
