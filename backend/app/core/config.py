from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: SecretStr
    api_key: SecretStr
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = Field(min_length=1)
    ollama_timeout: float = Field(default=120, gt=0, le=600)
    ai_requests_per_minute: int = Field(default=6, ge=1, le=100)
    cors_origins: list[str] = ["http://localhost:3000"]

    @field_validator("api_key")
    @classmethod
    def validate_key(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("API_KEY must contain at least 32 characters")
        return value

    @field_validator("database_url")
    @classmethod
    def validate_database(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().startswith("postgresql+asyncpg://"):
            raise ValueError("Use postgresql+asyncpg://")
        return value

    @field_validator("ollama_base_url")
    @classmethod
    def validate_ollama(cls, value: str) -> str:
        from urllib.parse import urlsplit
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.query or parsed.fragment:
            raise ValueError("Invalid Ollama URL")
        return value.rstrip("/")
