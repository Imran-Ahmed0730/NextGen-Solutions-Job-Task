from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from pydantic.types import StringConstraints

Username = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    ),
]
FullName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
RoleName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
MobileNumber = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=11,
        max_length=11,
        pattern=r"^01[3-9]\d{8}$",
    ),
]
EmailAddress = Annotated[EmailStr, Field(max_length=255)]
PositiveId = Annotated[int, Field(strict=True, gt=0)]


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
    email: EmailAddress


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1, max_length=512)
    new_password: str = Field(min_length=8, max_length=256)


class ProfileUpdate(BaseModel):
    full_name: FullName
    email: EmailAddress | None = None
    mobile: MobileNumber | None = None


class ProfileResponse(BaseModel):
    id: int
    username: str
    email: str | None
    mobile: str | None
    full_name: str
    roles: list[str]
    permissions: list[str]


class UserCreate(BaseModel):
    username: Username
    email: EmailAddress | None = None
    mobile: MobileNumber | None = None
    full_name: FullName
    password: str = Field(min_length=8, max_length=256)
    role_ids: list[PositiveId] = Field(default_factory=list)
    employee_id: PositiveId | None = None


class UserUpdate(BaseModel):
    email: EmailAddress | None = None
    mobile: MobileNumber | None = None
    full_name: FullName | None = None
    role_ids: list[PositiveId] | None = None
    employee_id: PositiveId | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str | None
    mobile: str | None
    full_name: str
    employee_id: int | None
    is_active: bool
    last_login_at: datetime | None
    roles: list[str]


class RoleCreate(BaseModel):
    name: RoleName
    description: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None
    ) = None
    permission_ids: list[PositiveId] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    name: RoleName | None = None
    description: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None
    ) = None
    permission_ids: list[PositiveId] | None = None


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
