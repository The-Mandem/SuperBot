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
