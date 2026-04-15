import litellm
from litellm import completion
from config.manager import ConfigManager
from typing import List, Dict, Optional


class LLMFallbackError(Exception):
    """Raised when the Gemini API fails, signaling a need to fallback to a local LLM."""

    pass


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

        # LiteLLM routing prefix for Gemini
        self.gemini_model_name = "gemini/gemini-3.1-flash-lite-preview"
        self._initialized = True

    def _prepare_messages(
        self,
        conversation_contents: List[Dict[str, str]],
        system_instruction: Optional[str],
    ) -> List[Dict[str, str]]:
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.extend(conversation_contents)
        return messages

    def make_ollama_request(
        self,
        conversation_contents: List[Dict[str, str]],
        system_instruction_text: Optional[str],
    ) -> Optional[str]:
        """
        Fallback mechanism that uses a local Ollama instance running llama3.2 via LiteLLM
        """
        print("LiteLLM Service: Executing local Ollama fallback (llama3.2)...")
        messages = self._prepare_messages(
            conversation_contents, system_instruction_text
        )

        try:
            response = completion(
                model="ollama/llama3.2",
                messages=messages,
                api_base="http://localhost:11434",
                timeout=180,  # Generous timeout since 3b models on a Pi are slow
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"LiteLLM Service: Ollama fallback error: {e}")
            return "Sorry, both Gemini and the local fallback AI encountered an error."

    def make_gemini_request(
        self,
        conversation_contents: List[Dict[str, str]],
        system_instruction_text: Optional[str],
    ) -> Optional[str]:
        """
        Makes a request to the Gemini API using LiteLLM. Raises LLMFallbackError if the API request fails.
        """
        if not conversation_contents:
            print("LiteLLM Service: Conversation contents list is empty.")
            return "Sorry, there's no conversation to continue with."

        messages = self._prepare_messages(
            conversation_contents, system_instruction_text
        )

        try:
            response = completion(
                model=self.gemini_model_name,
                messages=messages,
                api_key=self.gemini_api_key,
            )
            return response.choices[0].message.content

        except litellm.exceptions.APIError as e:
            print(f"LiteLLM Service: API Error: {e}")
            raise LLMFallbackError(str(e))
        except Exception as e:
            print(f"LiteLLM Service: Unexpected error: {e}")
            raise LLMFallbackError(str(e))
