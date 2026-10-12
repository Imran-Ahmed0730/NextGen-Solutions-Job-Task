from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.modules.auth.models import Permission, Role, User


def get_user(db: Session, user_id: int) -> User | None:
    return db.scalar(
        select(User)
        .options(selectinload(User.roles).selectinload(Role.permissions))
        .where(User.id == user_id)
    )


def get_role(db: Session, role_id: int) -> Role | None:
    return db.scalar(
        select(Role)
        .options(selectinload(Role.permissions), selectinload(Role.users))
        .where(Role.id == role_id)
    )


def get_roles(db: Session, role_ids: list[int]) -> list[Role]:
    if not role_ids:
        return []
    return list(db.scalars(select(Role).where(Role.id.in_(set(role_ids)))))


def get_permissions(db: Session, permission_ids: list[int]) -> list[Permission]:
    if not permission_ids:
        return []
    return list(db.scalars(select(Permission).where(Permission.id.in_(set(permission_ids)))))


def user_has_active_admin_role(user: User) -> bool:
    return any(role.is_active and role.name.casefold() == "administrator" for role in user.roles)
