from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=512)


class PasswordRequest(BaseModel):
    password: str = Field(min_length=8, max_length=256)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1, max_length=512)
    new_password: str = Field(min_length=8, max_length=256)


class ProfileUpdate(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr | None = None
    mobile: str | None = Field(default=None, max_length=30)


class ProfileResponse(BaseModel):
    id: int
    username: str
    email: str | None
    mobile: str | None
    full_name: str
    roles: list[str]
    permissions: list[str]


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    email: EmailStr | None = None
    mobile: str | None = Field(default=None, max_length=30)
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=256)
    role_ids: list[int] = Field(default_factory=list)


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    mobile: str | None = Field(default=None, max_length=30)
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    role_ids: list[int] | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str | None
    mobile: str | None
    full_name: str
    is_active: bool
    last_login_at: datetime | None
    roles: list[str]


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    permission_ids: list[int] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    permission_ids: list[int] | None = None


class RoleResponse(BaseModel):
    id: int
    name: str
    description: str | None
    is_active: bool
    permission_ids: list[int]
    permission_codes: list[str]


class PermissionResponse(BaseModel):
    id: int
    code: str
    module: str
    description: str | None


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    entity_type: str
    entity_id: str
    action: str
    before_json: dict[str, object] | None
    after_json: dict[str, object] | None
    ip: str | None
    created_at: datetime
