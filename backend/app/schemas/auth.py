from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AuthCredentials(BaseModel):
    email: str = Field(..., min_length=3, max_length=320, description="Account email address")
    password: str = Field(..., min_length=8, max_length=128, description="Account password")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        local, separator, domain = normalized.partition("@")
        if not separator or not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
            raise ValueError("Enter a valid email address")
        return normalized


class RegisterRequest(AuthCredentials):
    """Credentials used to create a new authentication account."""

    display_name: str | None = Field(default=None, min_length=1, max_length=150)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Display name cannot be empty")
        return normalized


class LoginRequest(AuthCredentials):
    """Credentials used to authenticate an existing account."""


class AuthUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: str | None = None
    avatar_url: str | None = None
    created_at: datetime
    updated_at: datetime
    financial_user_id: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProfileUpdateRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=150)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320, description="Account email address")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        local, separator, domain = normalized.partition("@")
        if not separator or not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
            raise ValueError("Enter a valid email address")
        return normalized


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=16, max_length=256, description="Opaque password reset token")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")

    @field_validator("token")
    @classmethod
    def normalize_token(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Reset token is required")
        return normalized


class MessageResponse(BaseModel):
    message: str


class VerifyOtpRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320, description="Account email address")
    otp: str = Field(..., min_length=6, max_length=6, description="6-digit verification code")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        local, separator, domain = normalized.partition("@")
        if not separator or not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
            raise ValueError("Enter a valid email address")
        return normalized

    @field_validator("otp")
    @classmethod
    def validate_otp(cls, value: str) -> str:
        clean = value.strip()
        if not clean.isdigit() or len(clean) != 6:
            raise ValueError("Verification code must be exactly 6 digits")
        return clean


class VerifyOtpResponse(BaseModel):
    reset_token: str
    message: str
