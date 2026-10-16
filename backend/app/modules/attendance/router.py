from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.attendance import service
from app.modules.attendance.models import Attendance
from app.modules.attendance.schemas import (
    AttendanceCreate,
    AttendanceImportResult,
    AttendanceResponse,
    AttendanceUpdate,
    EmployeeOption,
)
from app.modules.auth.models import User
from app.modules.employees.models import Employee

router = APIRouter(prefix="/api/v1/attendance", tags=["attendance"])
WORKBOOK_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MAX_WORKBOOK_SIZE = 5 * 1024 * 1024


@router.get("/template")
def attendance_template(
    _: User = Depends(require_permission("employees.attendance.read")),
) -> Response:
    return Response(
        content=service.build_attendance_workbook(),
        media_type=WORKBOOK_MIME,
        headers={"Content-Disposition": 'attachment; filename="attendance_template.xlsx"'},
    )


@router.get("/export")
def export_attendance(
    from_date: date = Query(),
    to_date: date = Query(),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("employees.attendance.read")),
) -> Response:
    records = service.list_attendance_for_range(db, from_date, to_date)
    filename = f"attendance_{from_date.isoformat()}_to_{to_date.isoformat()}.xlsx"
    return Response(
        content=service.build_attendance_workbook(records),
        media_type=WORKBOOK_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/options", response_model=list[EmployeeOption])
def list_employee_options(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("employees.attendance.read")),
) -> list[Employee]:
    return service.list_employee_options(db)


@router.get("", response_model=list[AttendanceResponse])
def list_attendance(
    from_date: date = Query(),
    to_date: date = Query(),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("employees.attendance.read")),
) -> list[Attendance]:
    return service.list_attendance_for_range(db, from_date, to_date)


@router.post(
    "",
    response_model=AttendanceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_attendance(
    payload: AttendanceCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("employees.attendance.create")),
) -> Attendance:
    return service.create_attendance(db, payload.model_dump(), actor, _ip(request))


@router.post("/import", response_model=AttendanceImportResult)
async def import_attendance(
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("employees.attendance.create")),
) -> dict[str, object]:
    content_type = request.headers.get("content-type", "").split(";", maxsplit=1)[0].strip()
    if content_type != WORKBOOK_MIME:
        raise HTTPException(status_code=415, detail="Upload an .xlsx attendance workbook")
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_WORKBOOK_SIZE:
            raise HTTPException(status_code=413, detail="Workbook exceeds the 5 MB size limit")
        chunks.append(chunk)
    rows = service.parse_attendance_workbook(b"".join(chunks))
    return service.import_attendance(db, rows, actor, _ip(request))


@router.patch("/{attendance_id}", response_model=AttendanceResponse)
def update_attendance(
    attendance_id: int,
    payload: AttendanceUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("employees.attendance.update")),
) -> Attendance:
    return service.update_attendance(
        db,
        attendance_id,
        payload.model_dump(exclude_unset=True),
        actor,
        _ip(request),
    )


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None
