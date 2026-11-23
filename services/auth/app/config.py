import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SERVICE_NAME: str = "auth-service"
    PORT: int = int(os.getenv("AUTH_SERVICE_PORT", "8001"))
    DATABASE_URL: str = os.getenv(
        "AUTH_DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres_password_dev@postgres:5432/auth_db"
    )
    # Compose sets JWT_SECRET (single source of truth in .env). Keep the old
    # name as a fallback so existing .env files keep working.
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET") or os.getenv("JWT_SECRET_KEY", "dev_only_change_me")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("JWT_EXPIRE_MINUTES") or os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    )

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
