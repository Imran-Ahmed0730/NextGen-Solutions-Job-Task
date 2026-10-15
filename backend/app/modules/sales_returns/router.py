from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.sales_returns import service
from app.modules.sales_returns.models import SalesReturn
from app.modules.sales_returns.schemas import (
    SalesReturnCreate,
    SalesReturnOptionsResponse,
    SalesReturnResponse,
)

router = APIRouter(prefix="/api/v1/sales/returns", tags=["sales-returns"])


@router.get("/options", response_model=SalesReturnOptionsResponse)
def get_sales_return_options(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("sales.returns.read")),
) -> SalesReturnOptionsResponse:
    return service.get_sales_return_options(db)


@router.get("", response_model=list[SalesReturnResponse])
def list_sales_returns(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("sales.returns.read")),
) -> list[SalesReturn]:
    return service.list_sales_returns(db, offset=offset, limit=limit)


@router.post("", response_model=SalesReturnResponse, status_code=status.HTTP_201_CREATED)
def create_sales_return(
    payload: SalesReturnCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("sales.returns.create")),
) -> SalesReturn:
    ip = request.client.host if request.client else None
    return service.create_sales_return(db, payload, actor, ip)


@router.get("/{return_id}", response_model=SalesReturnResponse)
def get_sales_return(
    return_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("sales.returns.read")),
) -> SalesReturn:
    sales_return = service.get_sales_return(db, return_id)
    if sales_return is None:
        raise HTTPException(status_code=404, detail="Sales return not found")
    return sales_return
