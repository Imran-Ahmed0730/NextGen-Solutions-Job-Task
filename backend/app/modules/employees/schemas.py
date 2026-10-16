from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

EmployeeCode = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)
]
EmployeeName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)
]
OptionalMobile = Annotated[str, StringConstraints(strip_whitespace=True, max_length=30)] | None
OptionalDesignation = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=100)
] | None
OptionalDepartment = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=100)
] | None
BaseSalary = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2)]


class EmployeeCreate(BaseModel):
    code: EmployeeCode
    name: EmployeeName
    mobile: OptionalMobile = None
    email: EmailStr | None = None
    designation: OptionalDesignation = None
    department: OptionalDepartment = None
    join_date: date
    base_salary: BaseSalary


class EmployeeUpdate(BaseModel):
    code: EmployeeCode | None = None
    name: EmployeeName | None = None
    mobile: OptionalMobile = None
    email: EmailStr | None = None
    designation: OptionalDesignation = None
    department: OptionalDepartment = None
    join_date: date | None = None
    base_salary: BaseSalary | None = None


class EmployeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    mobile: str | None
    email: str | None
    designation: str | None
    department: str | None
    join_date: date
    base_salary: Decimal
    is_active: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime
