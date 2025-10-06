import re
from google.genai import types
from discord.ext import commands
from discord import Message
from utils import ignore_channel_in_prod
from gemini_service import GeminiService


class AutoTranslationCog(commands.Cog, name="ArabicTranslate"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.gemini_service = GeminiService()
        self.arabic_pattern = re.compile(r"[\u0600-\u06FF]")

    def _translate_with_gemini(self, text: str) -> str | None:
        """Send Arabic text to Gemini and return English translation."""
        system_instruction = (
            "Translate the following Arabic text into English. "
            "Only return the translation, no explanations."
        )

        conversation_history = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=text)],
            )
        ]

        translation = self.gemini_service.make_gemini_request(
            conversation_history, system_instruction
        )

        if not translation or translation.startswith("Sorry,"):
            print(f"ArabicTranslateFeature: Translation error: {translation}")
            return None

        return translation

    @commands.Cog.listener()
    @ignore_channel_in_prod()
    async def on_message(self, message: Message):
        """Hook into on_message to auto-translate Arabic text."""
        if message.author.bot or message.content.startswith(self.bot.command_prefix):  # type: ignore
            return

        if self.arabic_pattern.search(message.content):
            translated_text = await self.bot.loop.run_in_executor(
                None, self._translate_with_gemini, message.content
            )

            if translated_text is None:
                print("Translation failed")
                return

            try:
                await message.reply(f"🌍 Translation:\n{translated_text}")
            except Exception as e:
                print(f"ArabicTranslateFeature: Error replying: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoTranslationCog(bot))
