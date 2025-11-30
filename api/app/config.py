import secrets
from pydantic_settings import BaseSettings
from typing import Literal, List


class Settings(BaseSettings):
    """Application settings and configuration"""

    # Database - no defaults for password in production
    POSTGRES_USER: str = "benchcom"
    POSTGRES_PASSWORD: str = "benchcom"  # Override in .env for production
    POSTGRES_DB: str = "benchcom"
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Authentication modes: "anonymous", "authenticated", "both"
    AUTH_MODE: Literal["anonymous", "authenticated", "both"] = "both"

    # JWT settings - generate random key if not set
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    @property
    def jwt_secret_key(self) -> str:
        """Get JWT secret key, generate if not set"""
        if self.SECRET_KEY and self.SECRET_KEY != "your-secret-key-change-in-production":
            return self.SECRET_KEY
        # Generate a random key for development (not persistent across restarts)
        if not hasattr(self, "_generated_key"):
            self._generated_key = secrets.token_urlsafe(32)
        return self._generated_key

    # API
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "BENCHCOM API"

    # CORS - can be overridden via environment
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    class Config:
        env_file = ".env"


settings = Settings()
