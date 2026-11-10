from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_name: str = "Ngôn Sắc Việt"
    database_url: str = "sqlite+aiosqlite:///./data/dev.db"
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_ssl_require: bool = True
    db_statement_cache_size: int = 0
    auto_create_tables: bool = True

    jwt_secret: str = "dev-only-change-me-at-least-32-bytes-long"
    jwt_access_minutes: int = 15
    jwt_refresh_days: int = 14

    ml_base_url: str = "http://127.0.0.1:8100"
    ml_api_key: str = ""
    ml_text_timeout: float = 60.0
    ml_file_timeout: float = 180.0

    max_image_mb: int = 8
    max_audio_mb: int = 20

    cors_origins: str = "*"
    auto_seed: bool = True
    seed_demo_user: bool = True
    allow_self_review: bool = True
    demo_email: str = "demo@ngonsacviet.example.com"
    demo_password: str = "Demo1234"
    demo_name: str = "Demo"

    rate_limit_enabled: bool = False
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60

    def validate_security(self) -> None:
        if self.app_env.lower() == "production":
            if len(self.jwt_secret.encode("utf-8")) < 32 or self.jwt_secret.startswith("dev-only"):
                raise RuntimeError(
                    "Production environment requires a strong JWT_SECRET of at least 32 bytes."
                )


@lru_cache
def get_settings() -> Settings:
    return Settings()
