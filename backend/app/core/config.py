from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Sabuj Pran API"
    app_env: str = "development"
    database_url: str = (
        "mysql+pymysql://sabuj_pran:local-dev-password@db:3306/sabuj_pran?charset=utf8mb4"
    )
    secret_key: str = "change-me"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
