import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SERVICE_NAME: str = "auth-service"
    PORT: int = int(os.getenv("AUTH_SERVICE_PORT", "8001"))
    DATABASE_URL: str = os.getenv(
        "AUTH_DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres_password_dev@postgres:5432/auth_db"
    )
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "dev_super_secret_jwt_key_medical_booking_system_2026")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
