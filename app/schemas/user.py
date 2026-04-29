from datetime import datetime
import re
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)
    name: str = Field(..., min_length=1, max_length=120)
    phone: str = Field(..., min_length=7, max_length=32)
    pan: str = Field(..., min_length=10, max_length=16)
    city: str = Field(..., min_length=2, max_length=120)
    photo: str | None = Field(default=None, max_length=4096)
    risk_level: str = Field(default="medium", pattern="^(low|medium|high)$")

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if not re.search(r"[A-Z]", value):
            raise ValueError("Password must include at least one uppercase letter")
        if not re.search(r"[a-z]", value):
            raise ValueError("Password must include at least one lowercase letter")
        if not re.search(r"\d", value):
            raise ValueError("Password must include at least one number")
        if not re.search(r"[^A-Za-z0-9]", value):
            raise ValueError("Password must include at least one symbol")
        return value

    @field_validator("pan")
    @classmethod
    def normalize_pan(cls, value: str) -> str:
        return value.strip().upper()


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: str
    auth_provider: str
    is_active: bool
    is_verified: bool
    created_at: datetime
