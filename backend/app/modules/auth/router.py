from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth import service
from app.modules.auth.models import AuditLog, Role, User
from app.modules.auth.repository import get_role, get_user
from app.modules.auth.schemas import (
    AuditLogResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    PermissionResponse,
    ProfileResponse,
    ProfileUpdate,
    RefreshRequest,
    ResetPasswordRequest,
    RoleCreate,
    RoleResponse,
    RoleUpdate,
    TokenResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _user_response(user: User) -> dict[str, object]:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "mobile": user.mobile,
        "full_name": user.full_name,
        "employee_id": user.employee_id,
        "is_active": user.is_active,
        "last_login_at": user.last_login_at,
        "roles": sorted(role.name for role in user.roles),
    }


def _role_response(role: Role) -> dict[str, object]:
    return {
        "id": role.id,
        "name": role.name,
        "description": role.description,
        "is_active": role.is_active,
        "permission_ids": sorted(permission.id for permission in role.permissions),
        "permission_codes": sorted(permission.code for permission in role.permissions),
    }


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return service.login(db, payload.username, payload.password, _ip(request))


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    payload: RefreshRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return service.rotate_refresh_token(db, payload.refresh_token, _ip(request))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("auth.session.logout")),
) -> None:
    session_id = getattr(request.state, "auth_session_id", None)
    if not isinstance(session_id, int):
        raise HTTPException(status_code=401, detail="Authenticated session is missing")
    service.logout(db, current_user, session_id, _ip(request))


@router.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    return {"message": service.request_password_reset(db, str(payload.email), _ip(request))}


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> None:
    service.reset_password(db, payload.token, payload.new_password, _ip(request))


@router.get("/me", response_model=ProfileResponse)
def read_profile(
    current_user: User = Depends(require_permission("auth.profile.read")),
) -> dict[str, object]:
    return service.get_profile(current_user)


@router.patch("/me", response_model=ProfileResponse)
def update_profile(
    payload: ProfileUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("auth.profile.update")),
) -> dict[str, object]:
    user = service.update_profile(
        db, current_user, payload.model_dump(exclude_unset=True), _ip(request)
    )
    return service.get_profile(user)


@router.post("/change-password", response_model=TokenResponse)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("auth.password.change")),
) -> dict[str, object]:
    return service.change_password(
        db,
        current_user,
        payload.current_password,
        payload.new_password,
        _ip(request),
    )


@router.get("/users", response_model=list[UserResponse])
def list_users(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("auth.users.read")),
) -> list[dict[str, object]]:
    return [_user_response(user) for user in service.list_users(db, offset, limit)]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("auth.users.create")),
) -> dict[str, object]:
    user = service.create_user(db, payload.model_dump(), actor, _ip(request))
    return _user_response(user)


@router.get("/users/{user_id}", response_model=UserResponse)
def read_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("auth.users.read")),
) -> dict[str, object]:
    user = get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_response(user)


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("auth.users.update")),
) -> dict[str, object]:
    user = get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    updated = service.update_user(
        db, user, payload.model_dump(exclude_unset=True), actor, _ip(request)
    )
    return _user_response(updated)


@router.post("/users/{user_id}/deactivate", response_model=UserResponse)
def deactivate_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("auth.users.delete")),
) -> dict[str, object]:
    user = get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_response(service.set_user_active(db, user, False, actor, _ip(request)))


@router.post("/users/{user_id}/activate", response_model=UserResponse)
def activate_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("auth.users.update")),
) -> dict[str, object]:
    user = get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_response(service.set_user_active(db, user, True, actor, _ip(request)))


@router.get("/roles", response_model=list[RoleResponse])
def list_roles(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("auth.roles.read")),
) -> list[dict[str, object]]:
    return [_role_response(role) for role in service.list_roles(db)]


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
def create_role(
    payload: RoleCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("auth.roles.create")),
) -> dict[str, object]:
    role = service.create_role(db, payload.model_dump(), actor, _ip(request))
    return _role_response(role)


@router.patch("/roles/{role_id}", response_model=RoleResponse)
def update_role(
    role_id: int,
    payload: RoleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("auth.roles.update")),
) -> dict[str, object]:
    role = get_role(db, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")
    updated = service.update_role(
        db, role, payload.model_dump(exclude_unset=True), actor, _ip(request)
    )
    return _role_response(updated)


@router.post("/roles/{role_id}/deactivate", response_model=RoleResponse)
def deactivate_role(
    role_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("auth.roles.delete")),
) -> dict[str, object]:
    role = get_role(db, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")
    updated = service.deactivate_role(db, role, actor, _ip(request))
    return _role_response(updated)


@router.post("/roles/{role_id}/activate", response_model=RoleResponse)
def activate_role(
    role_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("auth.roles.update")),
) -> dict[str, object]:
    role = get_role(db, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")
    updated = service.activate_role(db, role, actor, _ip(request))
    return _role_response(updated)


@router.get("/permissions", response_model=list[PermissionResponse])
def list_permissions(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("auth.permissions.read")),
) -> list[dict[str, object]]:
    return [
        {
            "id": permission.id,
            "code": permission.code,
            "module": permission.module,
            "description": permission.description,
        }
        for permission in service.list_permissions(db)
    ]


@router.get("/audit-logs", response_model=list[AuditLogResponse])
def list_audit_logs(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("auth.audit_logs.read")),
) -> list[AuditLog]:
    return service.list_audit_logs(db, offset, limit)
