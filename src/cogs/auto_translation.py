import re
from discord.ext import commands
from discord import Message
from services.litellm_service import LiteLLMService, LLMFallbackError


class AutoTranslationCog(commands.Cog, name="ArabicTranslate"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.llm_service = LiteLLMService()
        self.arabic_pattern = re.compile(r"[\u0600-\u06FF]")

    def _get_translation_args(self, text: str):
        """Helper to generate conversation history and instruction."""
        system_instruction = (
            "Translate the following Arabic text into English. "
            "Only return the translation, no explanations."
        )
        conversation_history = [{"role": "user", "content": text}]
        return conversation_history, system_instruction

    def _translate_with_gemini(self, text: str) -> str | None:
        """Send Arabic text to Gemini and return English translation."""
        history, instr = self._get_translation_args(text)
        translation = self.llm_service.make_gemini_request(history, instr)

        if not translation or translation.startswith("Sorry,"):
            print(f"ArabicTranslateFeature: Translation error: {translation}")
            return None
        return translation

    def _translate_with_ollama(self, text: str) -> str | None:
        """Fallback translation method using local Ollama model."""
        history, instr = self._get_translation_args(text)
        translation = self.llm_service.make_ollama_request(history, instr)

        if not translation or translation.startswith("Sorry,"):
            print(f"ArabicTranslateFeature: Ollama translation error: {translation}")
            return None
        return translation

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        """Hook into on_message to auto-translate Arabic text."""
        if message.author.bot or message.content.startswith(self.bot.command_prefix):  # type: ignore
            return

        if self.arabic_pattern.search(message.content):
            try:
                translated_text = await self.bot.loop.run_in_executor(
                    None, self._translate_with_gemini, message.content
                )
            except LLMFallbackError:
                await message.reply(
                    "⚠️ **Translation API failed.** Falling back to local `llama3.2`. This may take a moment...",
                    mention_author=False,
                )
                translated_text = await self.bot.loop.run_in_executor(
                    None, self._translate_with_ollama, message.content
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
