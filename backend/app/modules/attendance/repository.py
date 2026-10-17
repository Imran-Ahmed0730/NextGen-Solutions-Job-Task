from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.modules.attendance.models import Attendance
from app.modules.employees.models import Employee


def list_attendance_for_range(db: Session, from_date: date, to_date: date) -> list[Attendance]:
    statement = (
        select(Attendance)
        .options(joinedload(Attendance.employee))
        .where(Attendance.att_date >= from_date, Attendance.att_date <= to_date)
        .join(Attendance.employee)
        .order_by(Employee.name, Attendance.id)
    )
    return list(db.scalars(statement))


def list_employee_options(db: Session) -> list[Employee]:
    statement = (
        select(Employee)
        .where(Employee.is_active.is_(True), Employee.deleted_at.is_(None))
        .order_by(Employee.name, Employee.id)
    )
    return list(db.scalars(statement))


def get_attendance(
    db: Session, attendance_id: int, *, for_update: bool = False
) -> Attendance | None:
    statement = (
        select(Attendance)
        .options(joinedload(Attendance.employee))
        .where(Attendance.id == attendance_id)
    )
    if for_update:
        statement = statement.with_for_update()
    return db.scalar(statement)


def get_employee(db: Session, employee_id: int) -> Employee | None:
    return db.get(Employee, employee_id)


def get_employee_attendance(db: Session, employee_id: int, att_date: date) -> Attendance | None:
    statement = select(Attendance).where(
        Attendance.employee_id == employee_id,
        Attendance.att_date == att_date,
    )
    return db.scalar(statement)


def get_employee_by_code(db: Session, code: str) -> Employee | None:
    statement = select(Employee).where(func.lower(Employee.code) == code.lower())
    return db.scalar(statement)
