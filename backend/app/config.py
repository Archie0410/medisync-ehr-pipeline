from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://medisync:medisync_dev@localhost:5432/medisync"
    database_url_sync: str = "postgresql://medisync:medisync_dev@localhost:5432/medisync"
    api_key: str = "dev-api-key-change-in-prod"
    storage_path: str = "./storage/documents"
    extractions_path: str = "./storage/extractions"
    app_name: str = "MediSync"

    gemini_api_key: str = ""
    openai_api_key: str = ""
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_deployment_name: str = ""
    azure_openai_api_version: str = "2024-02-15-preview"
    extraction_provider: str = "gemini"
    extraction_model: str = "gemini-2.0-flash"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
