from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.employees.models import Employee


def list_employees(
    db: Session,
    *,
    search: str | None,
    include_inactive: bool,
    offset: int,
    limit: int,
) -> list[Employee]:
    statement = select(Employee)
    if not include_inactive:
        statement = statement.where(Employee.is_active.is_(True), Employee.deleted_at.is_(None))
    if search:
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                Employee.name.ilike(pattern),
                Employee.code.ilike(pattern),
                Employee.mobile.ilike(pattern),
                Employee.email.ilike(pattern),
            )
        )
    return list(
        db.scalars(statement.order_by(Employee.name, Employee.id).offset(offset).limit(limit))
    )


def get_employee(db: Session, employee_id: int) -> Employee | None:
    return db.get(Employee, employee_id)


def get_employee_by_code(
    db: Session, code: str, *, exclude_id: int | None = None
) -> Employee | None:
    statement = select(Employee).where(func.lower(Employee.code) == code.lower())
    if exclude_id is not None:
        statement = statement.where(Employee.id != exclude_id)
    return db.scalar(statement)
