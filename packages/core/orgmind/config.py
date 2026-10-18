"""Configuration management for OrgMind platform via pydantic-settings."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Determine project root to locate .env reliably
_project_root = Path(__file__).resolve().parent.parent.parent.parent
_env_path = _project_root / ".env"


class Settings(BaseSettings):
    """Central configuration validated from environment variables and .env file."""

    # Environment
    ENV: str = "development"
    DEBUG: bool = False
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # FalkorDB Graph Database
    FALKORDB_HOST: str = "localhost"
    FALKORDB_PORT: int = 6379
    FALKORDB_PASSWORD: str | None = None
    FALKORDB_GRAPH_NAME: str = "northwind_labs"
    FALKORDB_DEFAULT_READONLY: bool = False

    # Application Relational Database (SQLAlchemy)
    # Defaults to local SQLite file for zero-setup local dev; PostgreSQL in production
    DATABASE_URL: str = "sqlite:///./orgmind.db"

    # Background Job Queue (Dedicated Redis instance on port 6380, separate from FalkorDB)
    REDIS_JOBS_URL: str = "redis://localhost:6380/0"
    REDIS_URL: str = "redis://localhost:6380/0"

    # Authentication & Session Security (OWASP: 600,000 PBKDF2 iterations, reasonable JWT expiry)
    JWT_SECRET_KEY: str | None = None
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120  # 2 hours default
    PBKDF2_ITERATIONS: int = 600_000

    def get_jwt_secret(self) -> str:
        """Returns the JWT secret or raises in production if not set."""
        if self.JWT_SECRET_KEY:
            return self.JWT_SECRET_KEY
        if self.ENV.lower() in ("development", "test", "dev"):
            return "orgmind-dev-insecure-secret-key-32bytes-minimum"
        raise ValueError("CRITICAL: JWT_SECRET_KEY environment variable MUST be set in production mode.")

    # LLM Model Configuration
    LLM_MODEL: str = "ollama/qwen2.5-coder:14b"
    LLM_FALLBACK_MODEL: str | None = "ollama/qwen2.5-coder:14b"
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None

    model_config = SettingsConfigDict(
        env_file=str(_env_path) if _env_path.exists() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Global singleton instance
settings = Settings()
