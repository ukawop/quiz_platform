from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from enum import Enum


class LLMProvider(str, Enum):
    OPENAI = "openai"
    YANDEXGPT = "yandexgpt"
    G4F = "g4f"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    API_DEBUG: bool = False

    DATABASE_URL: str

    LLM_PROVIDER: LLMProvider = LLMProvider.G4F

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    YANDEX_API_KEY: str = ""
    YANDEX_FOLDER_ID: str = ""
    YANDEX_MODEL: str = "yandexgpt-lite"


settings = Settings()
