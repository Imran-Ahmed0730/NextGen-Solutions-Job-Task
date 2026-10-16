from datetime import date, time
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

AttendanceStatus = Literal["PRESENT", "ABSENT", "LEAVE", "LATE"]
PositiveEmployeeId = Annotated[int, Field(gt=0)]


class AttendanceCreate(BaseModel):
    employee_id: PositiveEmployeeId
    att_date: date
    status: AttendanceStatus
    in_time: time | None = None
    out_time: time | None = None


class AttendanceUpdate(BaseModel):
    status: AttendanceStatus
    in_time: time | None = None
    out_time: time | None = None


class AttendanceImportError(BaseModel):
    row_number: int
    message: str


class AttendanceImportResult(BaseModel):
    created: int
    rejected: int
    errors: list[AttendanceImportError]


class AttendanceImportLine(BaseModel):
    employee_code: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)
    ]
    att_date: date
    status: AttendanceStatus
    in_time: time | None = None
    out_time: time | None = None


class EmployeeOption(BaseModel):
    id: int
    code: str
    name: str


class AttendanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    employee: EmployeeOption
    att_date: date
    status: AttendanceStatus
    in_time: time | None
    out_time: time | None
