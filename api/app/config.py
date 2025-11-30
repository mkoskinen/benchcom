from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    """Application settings and configuration"""

    # Database
    POSTGRES_USER: str = "benchcom"
    POSTGRES_PASSWORD: str = "benchcom"
    POSTGRES_DB: str = "benchcom"
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Authentication modes: "anonymous", "authenticated", "both"
    AUTH_MODE: Literal["anonymous", "authenticated", "both"] = "both"

    # JWT settings
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # API
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "BENCHCOM API"

    # CORS
    CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:5173"]

    class Config:
        env_file = ".env"


settings = Settings()
