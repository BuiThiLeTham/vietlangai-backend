from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./data/dev.db"
    jwt_secret: str = "dev-only-change-me"
    jwt_access_minutes: int = 15
    jwt_refresh_days: int = 14
    ml_base_url: str = "http://127.0.0.1:8100"
    cors_origins: str = "*"
    auto_seed: bool = True
    demo_email: str = "demo@ngonsacviet.example.com"
    demo_password: str = "Demo1234"
    demo_name: str = "Demo"


@lru_cache
def get_settings() -> Settings:
    return Settings()
