from datetime import date, time

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy import (
    Time as SQLTime,
)
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.modules.employees.models import Employee

ID_TYPE = (
    BigInteger().with_variant(BIGINT(unsigned=True), "mysql").with_variant(Integer(), "sqlite")
)


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("employee_id", "att_date", name="uq_attendance_employee_date"),
        CheckConstraint(
            "status IN ('PRESENT', 'ABSENT', 'LEAVE', 'LATE')",
            name="ck_attendance_status",
        ),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(
        ID_TYPE, ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    att_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    in_time: Mapped[time] = mapped_column(SQLTime, nullable=True)
    out_time: Mapped[time] = mapped_column(SQLTime, nullable=True)

    employee: Mapped[Employee] = relationship(lazy="joined")
