import re
from discord.ext import commands
from datetime import datetime, timezone, timedelta
from services.litellm_service import LiteLLMService, LLMFallbackError


class RundownCog(commands.Cog, name="Rundown"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.llm_service = LiteLLMService()

    _DURATION_RE = re.compile(r"^\s*(\d+)\s*([mMhH]?)\s*$")

    @staticmethod
    def _parse_duration_to_timedelta(duration_raw: str):
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
            try:
                summary = await self.bot.loop.run_in_executor(
                    None,
                    self.llm_service.make_gemini_request,
                    [{"role": "user", "content": prompt}],
                    system_instruction,
                )
            except LLMFallbackError:
                await ctx.reply(
                    "⚠️ **Gemini API failed.** Falling back to local `llama3.2` to summarize. This runs locally on the Raspberry Pi and may take a moment..."
                )
                summary = await self.bot.loop.run_in_executor(
                    None,
                    self.llm_service.make_ollama_request,
                    [{"role": "user", "content": prompt}],
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
