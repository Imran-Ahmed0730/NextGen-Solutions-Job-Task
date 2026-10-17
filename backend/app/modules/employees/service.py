import re
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.employees import repository
from app.modules.employees.models import Employee


def list_employees(
    db: Session,
    *,
    search: str | None = None,
    include_inactive: bool = False,
    offset: int = 0,
    limit: int = 50,
) -> list[Employee]:
    return repository.list_employees(
        db,
        search=search,
        include_inactive=include_inactive,
        offset=offset,
        limit=limit,
    )


def get_active_employee(db: Session, employee_id: int) -> Employee:
    employee = repository.get_employee(db, employee_id)
    if employee is None or not employee.is_active or employee.deleted_at is not None:
        raise HTTPException(status_code=422, detail="Employee must be active")
    return employee


def create_employee(
    db: Session, data: dict[str, object], actor: User, ip: str | None = None
) -> Employee:
    code = _required_text(data.get("code"), "Employee code", 50)
    _ensure_code_available(db, code)
    employee = Employee(
        code=code,
        name=_required_text(data.get("name"), "Employee name", 150),
        mobile=_required_mobile(data.get("mobile")),
        email=_optional_text(data.get("email"), "Email", 255),
        designation=_optional_text(data.get("designation"), "Designation", 100),
        department=_optional_text(data.get("department"), "Department", 100),
        join_date=_date(data.get("join_date")),
        base_salary=_money(data.get("base_salary")),
    )
    db.add(employee)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise _duplicate_code_error() from exc
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="employee",
        entity_id=employee.id,
        action="CREATE",
        after=_snapshot(employee),
        ip=ip,
    )
    db.commit()
    db.refresh(employee)
    return employee


def update_employee(
    db: Session,
    employee: Employee,
    data: dict[str, object],
    actor: User,
    ip: str | None = None,
) -> Employee:
    if employee.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Employee not found")
    before = _snapshot(employee)
    updates: dict[str, object] = {}
    for field, label, maximum in (
        ("code", "Employee code", 50),
        ("name", "Employee name", 150),
    ):
        if field in data:
            updates[field] = _required_text(data[field], label, maximum)
    for field, label, maximum in (
        ("mobile", "Mobile", 30),
        ("email", "Email", 255),
        ("designation", "Designation", 100),
        ("department", "Department", 100),
    ):
        if field in data:
            updates[field] = (
                _required_mobile(data[field])
                if field == "mobile"
                else _optional_text(data[field], label, maximum)
            )
    if "mobile" not in updates:
        updates["mobile"] = _required_mobile(employee.mobile)
    if "join_date" in data:
        updates["join_date"] = _date(data["join_date"])
    if "base_salary" in data:
        updates["base_salary"] = _money(data["base_salary"])
    code = updates.get("code", employee.code)
    if code != employee.code:
        _ensure_code_available(db, str(code), exclude_id=employee.id)
    for field, value in updates.items():
        setattr(employee, field, value)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise _duplicate_code_error() from exc
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="employee",
        entity_id=employee.id,
        action="UPDATE",
        before=before,
        after=_snapshot(employee),
        ip=ip,
    )
    db.commit()
    db.refresh(employee)
    return employee


def delete_employee(
    db: Session, employee: Employee, actor: User, ip: str | None = None
) -> Employee:
    if employee.deleted_at is not None:
        return employee
    before = _snapshot(employee)
    employee.is_active = False
    employee.deleted_at = datetime.now(UTC)
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="employee",
        entity_id=employee.id,
        action="DELETE",
        before=before,
        after=_snapshot(employee),
        ip=ip,
    )
    db.commit()
    db.refresh(employee)
    return employee


def restore_employee(
    db: Session, employee: Employee, actor: User, ip: str | None = None
) -> Employee:
    if employee.is_active and employee.deleted_at is None:
        return employee
    before = _snapshot(employee)
    employee.is_active = True
    setattr(employee, "deleted_at", None)
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="employee",
        entity_id=employee.id,
        action="STATUS",
        before=before,
        after=_snapshot(employee),
        ip=ip,
    )
    db.commit()
    db.refresh(employee)
    return employee


def _required_text(value: object, label: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=422, detail=f"{label} is required")
    result = value.strip()
    if len(result) > maximum:
        raise HTTPException(status_code=422, detail=f"{label} is too long")
    return result


def _optional_text(value: object, label: str, maximum: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise HTTPException(status_code=422, detail=f"{label} must be text")
    result = value.strip()
    if not result:
        return None
    if len(result) > maximum:
        raise HTTPException(status_code=422, detail=f"{label} is too long")
    return result


def _required_mobile(value: object) -> str:
    if not isinstance(value, str):
        raise HTTPException(status_code=422, detail="Mobile number is required")
    result = value.strip()
    if re.fullmatch(r"01[3-9]\d{8}", result) is None:
        raise HTTPException(
            status_code=422,
            detail="Use a valid Bangladesh mobile number, e.g. 01712345678",
        )
    return result


def _date(value: object) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    raise HTTPException(status_code=422, detail="Join date is required")


def _money(value: object) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Base salary must be a number") from exc
    if not result.is_finite() or result < 0 or result != result.quantize(Decimal("0.01")):
        raise HTTPException(
            status_code=422, detail="Base salary must be nonnegative with at most 2 decimals"
        )
    if result > Decimal("9999999999999999.99"):
        raise HTTPException(status_code=422, detail="Base salary exceeds supported amount")
    return result


def _ensure_code_available(db: Session, code: str, *, exclude_id: int | None = None) -> None:
    if repository.get_employee_by_code(db, code, exclude_id=exclude_id) is not None:
        raise _duplicate_code_error()


def _duplicate_code_error() -> HTTPException:
    return HTTPException(status_code=409, detail="Employee code is already in use")


def _snapshot(employee: Employee) -> dict[str, object]:
    return {
        "code": employee.code,
        "name": employee.name,
        "mobile": employee.mobile,
        "email": employee.email,
        "designation": employee.designation,
        "department": employee.department,
        "join_date": employee.join_date.isoformat(),
        "base_salary": str(employee.base_salary),
        "is_active": employee.is_active,
        "deleted_at": employee.deleted_at.isoformat() if employee.deleted_at else None,
    }
