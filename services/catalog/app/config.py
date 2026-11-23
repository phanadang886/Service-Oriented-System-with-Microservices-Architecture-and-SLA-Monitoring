import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SERVICE_NAME: str = "catalog-service"
    PORT: int = int(os.getenv("CATALOG_SERVICE_PORT", "8002"))
    DATABASE_URL: str = os.getenv(
        "CATALOG_DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres_password_dev@postgres:5432/catalog_db"
    )
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    CACHE_TTL_SECONDS: int = 300  # 5 phút theo quy định kiến trúc

    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "dev_super_secret_jwt_key_medical_booking_system_2026")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
