"""集中配置：全部来自环境变量，默认值与 .env.example 保持一致。"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_name: str = "tracknorm"
    brand: str = "tracknorm"

    db_host: str = "localhost"
    db_port: int = 3306
    db_name: str = "tracknorm"
    db_user: str = "tracknorm"
    db_password: str = "tracknorm_pw_2026"

    jwt_secret: str = "tracknorm-jwt-secret-change-me-2026"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 480

    redis_url: str = "redis://localhost:6379/0"
    seed_demo: bool = True

    rate_limit_per_minute: int = 300
    rate_limit_pull_per_minute: int = 20

    mock_429_budget: int = 2
    pull_batch_size: int = 60
    mapping_default_version: int = 1

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
