from __future__ import annotations

from savvy.config import Settings
from savvy.llm.base import LLMProvider
from savvy.llm.ollama import OllamaLLM


def make_llm(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "ollama":
        return OllamaLLM(
            model=settings.ollama_chat_model,
            base_url=settings.ollama_base_url,
            api_key=settings.ollama_api_key or None,
        )
    if settings.llm_provider == "gemini":
        raise NotImplementedError("Gemini LLM provider not yet implemented")
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")
