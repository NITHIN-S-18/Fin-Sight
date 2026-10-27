from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "FinSight"
    app_description: str = "Financial Exposure Intelligence System backend"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    data_source: str = "csv"
    ml_reference_data_dir: str = ""
    database_url: str = "sqlite:///./finsight.db"
    cors_allow_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:5173"]
    )
    cors_allow_methods: list[str] = Field(default_factory=lambda: ["*"])
    cors_allow_headers: list[str] = Field(default_factory=lambda: ["*"])
    cors_allow_credentials: bool = True
    log_level: str = "INFO"
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"
    openapi_url: str = "/openapi.json"
    auth_jwt_secret: str = "change-this-development-secret-with-at-least-32-bytes"
    auth_jwt_algorithm: str = "HS256"
    auth_access_token_expire_minutes: int = 30
    auth_password_reset_token_expire_minutes: int = 30
    auth_password_reset_otp_expire_minutes: int = 5
    frontend_base_url: str = "http://localhost:5173"
    copilot_llm_enabled: bool = True
    copilot_llm_provider: str = "auto"
    copilot_llm_timeout_seconds: float = 8.0
    copilot_ollama_base_url: str = "http://localhost:11434"
    copilot_ollama_model: str = "llama3.2"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    email_delivery_provider: str = "console"
    resend_api_key: str = ""
    resend_from_email: str = ""
    resend_from_name: str = "FinSight"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_from_email: str = ""

    @field_validator("cors_allow_origins", "cors_allow_methods", "cors_allow_headers", mode="before")
    @classmethod
    def _parse_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def _validate_auth_secret(self) -> "Settings":
        if self.environment.lower() in {"production", "prod"}:
            if (
                self.auth_jwt_secret == "change-this-development-secret-with-at-least-32-bytes"
                or len(self.auth_jwt_secret) < 32
            ):
                raise ValueError("AUTH_JWT_SECRET must be a unique value of at least 32 characters in production")
            if self.email_delivery_provider.lower().strip() == "console":
                raise ValueError("EMAIL_DELIVERY_PROVIDER cannot be 'console' in production")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
