from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.employees import service
from app.modules.employees.models import Employee
from app.modules.employees.repository import get_employee
from app.modules.employees.schemas import EmployeeCreate, EmployeeResponse, EmployeeUpdate

router = APIRouter(prefix="/api/v1/employees", tags=["employees"])


def _employee_or_404(db: Session, employee_id: int) -> Employee:
    employee = get_employee(db, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


@router.get("", response_model=list[EmployeeResponse])
def list_employees(
    search: str | None = None,
    include_inactive: bool = False,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("employees.read")),
) -> list[Employee]:
    return service.list_employees(
        db,
        search=search,
        include_inactive=include_inactive,
        offset=offset,
        limit=limit,
    )


@router.post("", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
def create_employee(
    payload: EmployeeCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("employees.create")),
) -> Employee:
    return service.create_employee(db, payload.model_dump(), actor, _ip(request))


@router.patch("/{employee_id}", response_model=EmployeeResponse)
def update_employee(
    employee_id: int,
    payload: EmployeeUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("employees.update")),
) -> Employee:
    return service.update_employee(
        db,
        _employee_or_404(db, employee_id),
        payload.model_dump(exclude_unset=True),
        actor,
        _ip(request),
    )


@router.delete("/{employee_id}", response_model=EmployeeResponse)
def delete_employee(
    employee_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("employees.delete")),
) -> Employee:
    return service.delete_employee(db, _employee_or_404(db, employee_id), actor, _ip(request))


@router.post("/{employee_id}/restore", response_model=EmployeeResponse)
def restore_employee(
    employee_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("employees.update")),
) -> Employee:
    return service.restore_employee(db, _employee_or_404(db, employee_id), actor, _ip(request))


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None
