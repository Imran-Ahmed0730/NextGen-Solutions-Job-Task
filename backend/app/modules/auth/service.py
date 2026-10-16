import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.mail import (
    MailDeliveryError,
    send_password_reset_email,
    validate_email_configuration,
)
from app.core.security import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.modules.auth.audit import record_audit
from app.modules.auth.models import AuditLog, PasswordReset, Permission, RefreshToken, Role, User
from app.modules.auth.repository import (
    get_permissions,
    get_role,
    get_roles,
    get_user,
    user_has_active_admin_role,
)
from app.modules.employees import service as employee_service

settings = get_settings()


def issue_session(
    db: Session,
    user: User,
    ip: str | None = None,
    audit_login: bool = True,
) -> dict[str, object]:
    refresh_token, expires_at = create_refresh_token()
    refresh_session = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_token),
        expires_at=expires_at,
    )
    db.add(refresh_session)
    db.flush()
    if audit_login:
        record_audit(
            db,
            actor_id=user.id,
            entity_type="auth_session",
            entity_id=user.id,
            action="LOGIN",
            after={"username": user.username},
            ip=ip,
        )
    db.commit()
    return {
        "access_token": create_access_token(user, refresh_session.id),
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.jwt_access_token_expire_minutes * 60,
    }


def login(db: Session, identifier: str, password: str, ip: str | None = None) -> dict[str, object]:
    user = authenticate_user(db, identifier, password)
    return issue_session(db, user, ip)


def rotate_refresh_token(
    db: Session, token: str, ip: str | None = None
) -> dict[str, object]:
    now = datetime.now(UTC)
    stored = db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == hash_token(token))
        .with_for_update()
    )
    if stored is None or stored.revoked_at is not None or _as_utc(stored.expires_at) <= now:
        raise _invalid_refresh_token()
    user = get_user(db, stored.user_id)
    if (
        user is None
        or not user.is_active
        or (user.locked_until is not None and _as_utc(user.locked_until) > now)
    ):
        raise _invalid_refresh_token()

    stored.revoked_at = now
    next_token, expires_at = create_refresh_token()
    next_session = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(next_token),
        expires_at=expires_at,
    )
    db.add(next_session)
    db.flush()
    record_audit(
        db,
        actor_id=user.id,
        entity_type="auth_session",
        entity_id=user.id,
        action="UPDATE",
        after={"event": "refresh"},
        ip=ip,
    )
    db.commit()
    return {
        "access_token": create_access_token(user, next_session.id),
        "refresh_token": next_token,
        "token_type": "bearer",
        "expires_in": settings.jwt_access_token_expire_minutes * 60,
    }


def logout(
    db: Session,
    user: User,
    session_id: int,
    ip: str | None = None,
) -> None:
    stored = db.get(RefreshToken, session_id)
    if stored is None or stored.user_id != user.id or stored.revoked_at is not None:
        raise HTTPException(status_code=400, detail="Authenticated session is no longer active")
    stored.revoked_at = datetime.now(UTC)
    record_audit(
        db,
        actor_id=user.id,
        entity_type="auth_session",
        entity_id=user.id,
        action="UPDATE",
        after={"event": "logout"},
        ip=ip,
    )
    db.commit()


def request_password_reset(db: Session, email: str, ip: str | None = None) -> str:
    try:
        validate_email_configuration()
    except MailDeliveryError as error:
        raise HTTPException(
            status_code=503,
            detail="Password reset email service is unavailable",
        ) from error

    user = db.scalar(
        select(User).where(func.lower(User.email) == email.lower(), User.is_active.is_(True))
    )
    if user is None:
        return "If an account exists for this email, a password reset link will be sent."

    now = datetime.now(UTC)
    previous = list(
        db.scalars(
            select(PasswordReset)
            .where(PasswordReset.user_id == user.id, PasswordReset.used_at.is_(None))
            .with_for_update()
        )
    )
    for item in previous:
        item.used_at = now
    token = secrets.token_urlsafe(48)
    reset = PasswordReset(
        user_id=user.id,
        token_hash=hash_token(token),
        expires_at=now + timedelta(minutes=settings.password_reset_expire_minutes),
    )
    db.add(reset)
    record_audit(
        db,
        actor_id=None,
        entity_type="user",
        entity_id=user.id,
        action="UPDATE",
        after={"event": "password_reset_requested"},
        ip=ip,
    )
    db.commit()
    try:
        send_password_reset_email(email, token)
    except MailDeliveryError as error:
        reset.used_at = datetime.now(UTC)
        db.commit()
        raise HTTPException(
            status_code=503,
            detail="Password reset email could not be delivered",
        ) from error
    return "If an account exists for this email, a password reset link will be sent."


def reset_password(db: Session, token: str, new_password: str, ip: str | None = None) -> None:
    reset = db.scalar(
        select(PasswordReset)
        .where(PasswordReset.token_hash == hash_token(token))
        .with_for_update()
    )
    now = datetime.now(UTC)
    if (
        reset is None
        or reset.used_at is not None
        or _as_utc(reset.expires_at) <= now
    ):
        raise HTTPException(status_code=400, detail="Reset token is invalid or expired")
    user = get_user(db, reset.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=400, detail="Reset token is invalid or expired")

    reset.used_at = now
    user.password_hash = hash_password(new_password)
    user.failed_attempts = 0
    setattr(user, "locked_until", None)
    _revoke_user_refresh_tokens(db, user.id, now)
    record_audit(
        db,
        actor_id=user.id,
        entity_type="user",
        entity_id=user.id,
        action="UPDATE",
        after={"event": "password_reset"},
        ip=ip,
    )
    db.commit()


def change_password(
    db: Session,
    user: User,
    current_password: str,
    new_password: str,
    ip: str | None = None,
) -> dict[str, object]:
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if current_password == new_password:
        raise HTTPException(status_code=400, detail="New password must be different")
    user.password_hash = hash_password(new_password)
    now = datetime.now(UTC)
    _revoke_user_refresh_tokens(db, user.id, now)
    record_audit(
        db,
        actor_id=user.id,
        entity_type="user",
        entity_id=user.id,
        action="UPDATE",
        after={"event": "password_changed"},
        ip=ip,
    )
    return issue_session(db, user, ip, audit_login=False)


def get_profile(user: User) -> dict[str, object]:
    permission_codes = {
        permission.code
        for role in user.roles
        if role.is_active
        for permission in role.permissions
    }
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "mobile": user.mobile,
        "full_name": user.full_name,
        "roles": sorted(role.name for role in user.roles if role.is_active),
        "permissions": sorted(permission_codes),
    }


def update_profile(
    db: Session,
    user: User,
    data: dict[str, object],
    ip: str | None = None,
) -> User:
    before = _user_snapshot(user)
    _ensure_unique_contact(db, data, user.id)
    for field in ("full_name", "email", "mobile"):
        if field in data:
            setattr(user, field, data[field])
    record_audit(
        db,
        actor_id=user.id,
        entity_type="user",
        entity_id=user.id,
        action="UPDATE",
        before=before,
        after=_user_snapshot(user),
        ip=ip,
    )
    db.commit()
    db.refresh(user)
    return user


def list_users(db: Session, offset: int, limit: int) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .options(selectinload(User.roles))
            .order_by(User.id)
            .offset(offset)
            .limit(limit)
        )
    )


def create_user(
    db: Session, data: dict[str, object], actor: User, ip: str | None = None
) -> User:
    _ensure_unique_contact(db, data)
    employee_id = data.get("employee_id")
    if employee_id is not None and (
        not isinstance(employee_id, int) or isinstance(employee_id, bool) or employee_id <= 0
    ):
        raise HTTPException(status_code=422, detail="Employee must be active")
    employee = (
        employee_service.get_active_employee(db, employee_id)
        if isinstance(employee_id, int)
        else None
    )
    role_ids = data.get("role_ids", [])
    roles = get_roles(db, role_ids if isinstance(role_ids, list) else [])
    if len(roles) != len(set(role_ids if isinstance(role_ids, list) else [])):
        raise HTTPException(status_code=422, detail="One or more roles do not exist")
    if any(not role.is_active for role in roles):
        raise HTTPException(status_code=422, detail="Inactive roles cannot be assigned")
    user = User(
        username=str(data["username"]).strip(),
        email=data.get("email"),
        mobile=data.get("mobile"),
        full_name=str(data["full_name"]).strip(),
        password_hash=hash_password(str(data["password"])),
        roles=roles,
        employee_id=employee.id if employee else None,
    )
    if not user.username or not user.full_name:
        raise HTTPException(status_code=422, detail="Username and full name are required")
    db.add(user)
    db.flush()
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="user",
        entity_id=user.id,
        action="CREATE",
        after=_user_snapshot(user),
        ip=ip,
    )
    db.commit()
    db.refresh(user)
    return user


def update_user(
    db: Session,
    target: User,
    data: dict[str, object],
    actor: User,
    ip: str | None = None,
) -> User:
    before = _user_snapshot(target)
    _ensure_unique_contact(db, data, target.id)
    if "employee_id" in data:
        employee_id = data["employee_id"]
        if employee_id is None:
            setattr(target, "employee_id", None)
        elif (
            not isinstance(employee_id, int)
            or isinstance(employee_id, bool)
            or employee_id <= 0
        ):
            raise HTTPException(status_code=422, detail="Employee must be active")
        elif employee_id != target.employee_id:
            target.employee_id = employee_service.get_active_employee(db, employee_id).id
    for field in ("email", "mobile", "full_name"):
        if field in data:
            setattr(target, field, data[field])
    if data.get("role_ids") is not None:
        role_ids = data["role_ids"]
        if not isinstance(role_ids, list):
            raise HTTPException(status_code=422, detail="role_ids must be a list")
        roles = get_roles(db, role_ids)
        if len(roles) != len(set(role_ids)):
            raise HTTPException(status_code=422, detail="One or more roles do not exist")
        if any(not role.is_active for role in roles):
            raise HTTPException(status_code=422, detail="Inactive roles cannot be assigned")
        removes_admin = user_has_active_admin_role(target) and not any(
            role.name.casefold() == "administrator" for role in roles
        )
        if removes_admin and _other_active_admin_count(db, target.id) == 0:
            raise HTTPException(
                status_code=409,
                detail="Cannot remove the last administrator role",
            )
        target.roles = roles

    record_audit(
        db,
        actor_id=actor.id,
        entity_type="user",
        entity_id=target.id,
        action="UPDATE",
        before=before,
        after=_user_snapshot(target),
        ip=ip,
    )
    db.commit()
    return get_user(db, target.id) or target


def set_user_active(
    db: Session,
    target: User,
    is_active: bool,
    actor: User,
    ip: str | None = None,
) -> User:
    if not is_active:
        if user_has_active_admin_role(target) and _other_active_admin_count(db, target.id) == 0:
            raise HTTPException(status_code=409, detail="Cannot deactivate the last administrator")
    before = _user_snapshot(target)
    target.is_active = is_active
    if not is_active:
        _revoke_user_refresh_tokens(db, target.id, datetime.now(UTC))
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="user",
        entity_id=target.id,
        action="STATUS",
        before=before,
        after=_user_snapshot(target),
        ip=ip,
    )
    db.commit()
    return get_user(db, target.id) or target


def list_roles(db: Session) -> list[Role]:
    return list(
        db.scalars(
            select(Role)
            .options(selectinload(Role.permissions))
            .order_by(Role.name)
        )
    )


def create_role(
    db: Session, data: dict[str, object], actor: User, ip: str | None = None
) -> Role:
    name = str(data["name"]).strip()
    if not name:
        raise HTTPException(status_code=422, detail="Role name is required")
    _ensure_unique_role_name(db, name)
    permission_ids = data.get("permission_ids", [])
    permissions = get_permissions(db, permission_ids if isinstance(permission_ids, list) else [])
    if len(permissions) != len(set(permission_ids if isinstance(permission_ids, list) else [])):
        raise HTTPException(status_code=422, detail="One or more permissions do not exist")
    role = Role(
        name=name,
        description=data.get("description"),
        permissions=permissions,
    )
    db.add(role)
    db.flush()
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="role",
        entity_id=role.id,
        action="CREATE",
        after=_role_snapshot(role),
        ip=ip,
    )
    db.commit()
    return get_role(db, role.id) or role


def update_role(
    db: Session,
    role: Role,
    data: dict[str, object],
    actor: User,
    ip: str | None = None,
) -> Role:
    before = _role_snapshot(role)
    if data.get("name") is not None:
        name = str(data["name"]).strip()
        if not name:
            raise HTTPException(status_code=422, detail="Role name is required")
        if role.name.casefold() == "administrator" and name.casefold() != "administrator":
            raise HTTPException(status_code=409, detail="The Administrator role cannot be renamed")
        _ensure_unique_role_name(db, name, role.id)
        role.name = name
    if "description" in data:
        setattr(role, "description", data["description"])
    if data.get("permission_ids") is not None:
        permission_ids = data["permission_ids"]
        if not isinstance(permission_ids, list):
            raise HTTPException(status_code=422, detail="permission_ids must be a list")
        permissions = get_permissions(db, permission_ids)
        if len(permissions) != len(set(permission_ids)):
            raise HTTPException(status_code=422, detail="One or more permissions do not exist")
        role.permissions = permissions
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="role",
        entity_id=role.id,
        action="UPDATE",
        before=before,
        after=_role_snapshot(role),
        ip=ip,
    )
    db.commit()
    return get_role(db, role.id) or role


def activate_role(
    db: Session, role: Role, actor: User, ip: str | None = None
) -> Role:
    if role.is_active:
        return role
    before = _role_snapshot(role)
    role.is_active = True
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="role",
        entity_id=role.id,
        action="STATUS",
        before=before,
        after=_role_snapshot(role),
        ip=ip,
    )
    db.commit()
    return get_role(db, role.id) or role


def deactivate_role(
    db: Session, role: Role, actor: User, ip: str | None = None
) -> Role:
    if not role.is_active:
        return role
    if role.name.casefold() == "administrator":
        assigned_active_admins = sum(user.is_active for user in role.users)
        if assigned_active_admins > 0:
            raise HTTPException(
                status_code=409,
                detail="Reassign administrators before deactivating this role",
            )
    before = _role_snapshot(role)
    role.is_active = False
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="role",
        entity_id=role.id,
        action="STATUS",
        before=before,
        after=_role_snapshot(role),
        ip=ip,
    )
    db.commit()
    return get_role(db, role.id) or role


def list_permissions(db: Session) -> list[Permission]:
    return list(db.scalars(select(Permission).order_by(Permission.module, Permission.code)))


def list_audit_logs(db: Session, offset: int, limit: int) -> list[AuditLog]:
    return list(
        db.scalars(
            select(AuditLog)
            .order_by(AuditLog.id.desc())
            .offset(offset)
            .limit(limit)
        )
    )


def _ensure_unique_contact(
    db: Session, data: dict[str, object], exclude_user_id: int | None = None
) -> None:
    for field in ("username", "email", "mobile"):
        value = data.get(field)
        if value is None:
            continue
        column = getattr(User, field)
        condition = column == value
        if field in {"username", "email"}:
            condition = func.lower(column) == str(value).casefold()
        statement = select(User.id).where(condition)
        if exclude_user_id is not None:
            statement = statement.where(User.id != exclude_user_id)
        if db.scalar(statement) is not None:
            raise HTTPException(status_code=409, detail=f"{field} is already in use")


def _ensure_unique_role_name(
    db: Session, name: str, exclude_role_id: int | None = None
) -> None:
    statement = select(Role.id).where(func.lower(Role.name) == name.casefold())
    if exclude_role_id is not None:
        statement = statement.where(Role.id != exclude_role_id)
    if db.scalar(statement) is not None:
        raise HTTPException(status_code=409, detail="Role name is already in use")


def _user_snapshot(user: User) -> dict[str, object]:
    return {
        "username": user.username,
        "email": user.email,
        "mobile": user.mobile,
        "full_name": user.full_name,
        "employee_id": user.employee_id,
        "is_active": user.is_active,
        "role_ids": sorted(role.id for role in user.roles),
    }


def _role_snapshot(role: Role) -> dict[str, object]:
    return {
        "name": role.name,
        "description": role.description,
        "is_active": role.is_active,
        "permission_ids": sorted(permission.id for permission in role.permissions),
    }


def _other_active_admin_count(db: Session, user_id: int) -> int:
    return int(
        db.scalar(
            select(func.count(func.distinct(User.id)))
            .join(User.roles)
            .where(
                User.id != user_id,
                User.is_active.is_(True),
                Role.is_active.is_(True),
                func.lower(Role.name) == "administrator",
            )
        )
        or 0
    )


def _revoke_user_refresh_tokens(db: Session, user_id: int, at: datetime) -> None:
    for refresh in db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
    ):
        refresh.revoked_at = at


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _invalid_refresh_token() -> HTTPException:
    return HTTPException(status_code=401, detail="Refresh token is invalid or expired")
