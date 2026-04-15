import time
import discord
from discord import Message
from langchain_litellm import ChatLiteLLM
from config.manager import ConfigManager


class LiteLLMService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LiteLLMService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.config = ConfigManager()
        self.gemini_api_key = self.config.get_gemini_key()
        if not self.gemini_api_key:
            raise ValueError("Gemini API key is not configured.")

        self.gemini_model_name = "gemini/gemini-3.1-flash-lite-preview"

        # Primary LLM via LangChain (Gemini)
        self.primary_llm = ChatLiteLLM(
            model=self.gemini_model_name, api_key=self.gemini_api_key
        )

        # Fallback LLM via LangChain (Local Ollama on Raspberry Pi)
        self.fallback_llm = ChatLiteLLM(
            model="ollama_chat/llama3.2",
            api_base="http://localhost:11434",
            model_kwargs={"timeout": 180},
        )

        self._initialized = True

    async def stream_to_discord(
        self, messageable, llm, prompt_value, prefix: str = "", **kwargs
    ) -> tuple[str, list[Message]]:
        """
        Streams the LLM response to Discord, returning the full text and sent messages.
        Handles message character limits and API rate-limit delays organically.
        """
        full_text = ""
        current_part = prefix
        sent_messages = []
        current_message = None
        last_edit_time = 0.0
        EDIT_DELAY = 1.25  # Safe edit delay for Discord rate limits

        async for chunk in llm.astream(prompt_value):
            text = chunk.content
            if not text:
                continue

            full_text += text
            current_part += text

            # Prevent hitting the 2000 character limit by creating a new message at ~1950 characters
            if len(current_part) > 1950:
                # Try splitting cleanly near the end
                split_index = current_part.rfind("\n", 0, 1950)
                if split_index == -1 or split_index < 1000:
                    split_index = 1950

                chunk_to_send = current_part[:split_index]

                if not current_message:
                    current_message = await messageable.reply(chunk_to_send, **kwargs)
                else:
                    try:
                        await current_message.edit(content=chunk_to_send)
                    except discord.HTTPException:
                        pass  # Rate limits/identical content triggers exception safely

                if current_message not in sent_messages:
                    sent_messages.append(current_message)

                # Keep the remainder for the next text chunk
                current_part = current_part[split_index:].lstrip("\n")
                current_message = None
                last_edit_time = time.time()
                continue

            # Update the message periodically
            now = time.time()
            if now - last_edit_time >= EDIT_DELAY:
                display_text = current_part + " █"
                if not current_message:
                    current_message = await messageable.reply(display_text, **kwargs)
                else:
                    try:
                        await current_message.edit(content=display_text)
                    except discord.HTTPException:
                        pass
                last_edit_time = now

        # Flush final stream state cleanly
        if current_message:
            try:
                final_text = current_part if current_part.strip() else " "
                await current_message.edit(content=final_text)
            except discord.HTTPException:
                pass
            if current_message not in sent_messages:
                sent_messages.append(current_message)
        elif current_part.strip():
            # Catch case if stream is so incredibly fast it never ticked over the DELAY threshold
            current_message = await messageable.reply(current_part, **kwargs)
            sent_messages.append(current_message)

        return full_text, sent_messages
