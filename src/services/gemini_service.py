import requests
import google.genai as genai
from google.genai import types, errors
from config.manager import ConfigManager
from typing import List


class LLMFallbackError(Exception):
    """Raised when the Gemini API fails, signaling a need to fallback to a local LLM."""

    pass


class GeminiService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GeminiService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.config = ConfigManager()
        gemini_api_key = self.config.get_gemini_key()
        if not gemini_api_key:
            raise ValueError("Gemini API key is not configured.")

        self.gemini_model_name = "gemini-3.1-flash-lite-preview"
        self.client = genai.Client(api_key=gemini_api_key)
        self._initialized = True

    def make_ollama_request(
        self,
        conversation_contents: list[types.Content],
        system_instruction_text: str | None,
    ) -> str | None:
        """
        Fallback mechanism that uses a local Ollama instance running llama3.2
        """
        print("Gemini Service: Executing local Ollama fallback (llama3.2)...")
        messages = []

        if system_instruction_text:
            messages.append({"role": "system", "content": system_instruction_text})

        for content in conversation_contents:
            # Convert Gemini roles to Ollama roles (user, assistant, system)
            role = content.role
            if role == "model":
                role = "assistant"
            elif role not in ["user", "system", "assistant"]:
                role = "user"  # Default fallback role

            text = ""
            if hasattr(content, "parts") and content.parts:
                for part in content.parts:
                    if hasattr(part, "text") and part.text:
                        text += part.text

            messages.append({"role": role, "content": text})

        try:
            response = requests.post(
                "http://localhost:11434/api/chat",
                json={"model": "llama3.2", "messages": messages, "stream": False},
                timeout=180,  # Generous timeout since 3b models on a Pi are slow
            )
            response.raise_for_status()
            result = response.json()
            return result.get("message", {}).get(
                "content", "Sorry, local AI returned an empty response."
            )
        except Exception as e:
            print(f"Gemini Service: Ollama fallback error: {e}")
            return "Sorry, both Gemini and the local fallback AI encountered an error."

    def make_gemini_request(
        self,
        conversation_contents: list[types.Content],
        system_instruction_text: str | None,
    ) -> str | None:
        """
        Makes a request to the Gemini API. Raises LLMFallbackError if the API request fails.
        """
        if not conversation_contents:
            print("Gemini Service: Conversation contents list is empty.")
            return "Sorry, there's no conversation to continue with."

        gen_config_params = {}
        if system_instruction_text:
            gen_config_params["system_instruction"] = system_instruction_text

        generation_config = (
            types.GenerateContentConfig(**gen_config_params)
            if gen_config_params
            else None
        )

        contents_for_api: List[types.ContentUnion] = [
            item for item in conversation_contents
        ]

        try:
            response = self.client.models.generate_content(
                model=self.gemini_model_name,
                contents=contents_for_api,
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
                        and rating.probability.value >= types.HarmProbability.LOW.value
                    ]
                    if problematic_ratings:
                        safety_ratings_info = (
                            f" due to: {', '.join(problematic_ratings)}"
                        )

                print(
                    f"Gemini Service: Content blocked. Reason: {block_reason}{safety_ratings_info}. Full response: {response}"
                )
                return f"Sorry, your request was blocked by the AI's safety filters (Reason: {block_reason.name}{safety_ratings_info}). Please rephrase your prompt."
            else:
                print(
                    f"Gemini Service: No text response or block reason. Response: {response}"
                )
                raise LLMFallbackError(
                    "Empty or unrecognized response from Gemini API."
                )

        except errors.APIError as e:
            print(f"Gemini Service: API Error: {e}")
            raise LLMFallbackError(str(e))
        except Exception as e:
            print(f"Gemini Service: Unexpected error: {e}")
            raise LLMFallbackError(str(e))
