import re
from discord.ext import commands
from discord import Message
from services.litellm_service import LiteLLMService
from langchain_core.prompts import ChatPromptTemplate


class AutoTranslationCog(commands.Cog, name="ArabicTranslate"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.llm_service = LiteLLMService()
        self.arabic_pattern = re.compile(r"[\u0600-\u06FF]")

        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "Translate the following Arabic text into English. Only return the translation, no explanations.",
                ),
                ("human", "{text}"),
            ]
        )

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        """Hook into on_message to auto-translate Arabic text."""
        if message.author.bot or message.content.startswith(self.bot.command_prefix):  # type: ignore
            return

        if self.arabic_pattern.search(message.content):
            prompt_value = await self.prompt.ainvoke({"text": message.content})
            translated_text = None
            prefix = "🌍 Translation:\n"
            warning_msg = None

            async with message.channel.typing():
                try:
                    translated_text, _ = await self.llm_service.stream_to_discord(
                        message,
                        self.llm_service.primary_llm,
                        prompt_value,
                        prefix=prefix,
                    )
                except Exception as e:
                    print(f"ArabicTranslateFeature: API Error: {e}")
                    warning_msg = await message.reply(
                        "⚠️ **Translation API failed.** Falling back to local `llama3.2`. This may take a moment...",
                        mention_author=False,
                    )
                    try:
                        translated_text, _ = await self.llm_service.stream_to_discord(
                            message,
                            self.llm_service.fallback_llm,
                            prompt_value,
                            prefix=prefix,
                        )
                    except Exception as fallback_e:
                        print(f"ArabicTranslateFeature: Fallback error: {fallback_e}")
                        return
                    finally:
                        if warning_msg:
                            try:
                                await warning_msg.delete()
                            except Exception as delete_e:
                                print(
                                    f"ArabicTranslateFeature: Failed to delete warning message: {delete_e}"
                                )

            if not translated_text or translated_text.startswith("Sorry,"):
                print("Translation failed")
                return


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoTranslationCog(bot))
