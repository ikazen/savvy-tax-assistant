from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://savvy:savvy@localhost:5432/savvy",
    )

    llm_provider: Literal["ollama", "gemini"] = "ollama"
    embedding_provider: Literal["ollama", "gemini"] = "ollama"
    vector_store: Literal["pgvector", "qdrant", "milvus"] = "pgvector"

    embed_dimension: int = 1024

    ollama_base_url: str = "http://localhost:11434"
    ollama_api_key: str = ""
    ollama_chat_model: str = "qwen2.5:14b"
    ollama_embed_model: str = "bge-m3"

    gemini_api_key: str = ""
    gemini_chat_model: str = "gemini-2.0-flash"
    gemini_embed_model: str = "text-embedding-004"

    default_tenant_id: str = "default"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
