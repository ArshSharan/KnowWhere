from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str
    extraction_model: str = "gpt-5.6-luna"
    reconciliation_model: str = "gpt-5.6-sol"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # Database
    database_url: str = ""

    # Cloudflare R2
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = "knowwhere-pdfs"
    r2_endpoint_url: str = ""

    # App
    env: str = "development"
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
