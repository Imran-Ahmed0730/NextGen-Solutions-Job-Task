from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.money_collections import service
from app.modules.money_collections.models import CustomerCollection
from app.modules.money_collections.schemas import (
    CustomerCollectionCreate,
    CustomerCollectionOptionsResponse,
    CustomerCollectionResponse,
)

router = APIRouter(prefix="/api/v1/money/collections", tags=["money-collections"])


@router.get("/options", response_model=CustomerCollectionOptionsResponse)
def get_collection_options(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("money.collections.read")),
) -> CustomerCollectionOptionsResponse:
    return service.get_collection_options(db)


@router.get("", response_model=list[CustomerCollectionResponse])
def list_collections(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("money.collections.read")),
) -> list[CustomerCollection]:
    return service.list_collections(db, offset=offset, limit=limit)


@router.post("", response_model=CustomerCollectionResponse, status_code=status.HTTP_201_CREATED)
def create_collection(
    payload: CustomerCollectionCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("money.collections.create")),
) -> CustomerCollection:
    ip = request.client.host if request.client else None
    return service.create_collection(db, payload, actor, ip)
