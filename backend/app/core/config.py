from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Sabuj Pran API"
    app_env: str = "development"
    database_url: str = (
        "mysql+pymysql://sabuj_pran:local-dev-password@localhost:3306/sabuj_pran?charset=utf8mb4"
    )
    secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    password_reset_expire_minutes: int = 30
    login_max_failed_attempts: int = 5
    login_lockout_minutes: int = 15
    frontend_origin: str = "http://localhost:3000"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    smtp_timeout_seconds: int = 10

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
