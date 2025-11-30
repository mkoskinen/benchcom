import secrets
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Literal, List, Union


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
    # (deprecated, use ALLOW_ANONYMOUS_SUBMISSIONS and ALLOW_ANONYMOUS_BROWSING instead)
    AUTH_MODE: Literal["anonymous", "authenticated", "both"] = "both"

    # Allow submissions without authentication
    ALLOW_ANONYMOUS_SUBMISSIONS: bool = True

    # Allow browsing/reading data without authentication
    ALLOW_ANONYMOUS_BROWSING: bool = True

    # Whether anonymous users have admin privileges (for development/private instances)
    ANONYMOUS_ADMIN: bool = False

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

    # CORS - override via CORS_ORIGINS env var (comma-separated, e.g. "http://localhost:3000,http://192.168.1.15:3000")
    # For development/private instances, set CORS_ORIGINS=* to allow all origins
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:3000", "http://localhost:5173"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS_ORIGINS from comma-separated string or list"""
        if isinstance(v, str):
            if v == "*":
                return ["*"]
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    class Config:
        env_file = ".env"


settings = Settings()
