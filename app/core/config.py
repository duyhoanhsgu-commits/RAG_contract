from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Contract RAG API"
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    vector_store_path: str = "data/vector_store"
    vector_store_collection: str = "contract_chunks"
    model_name: str = "gpt-4o-mini"
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
