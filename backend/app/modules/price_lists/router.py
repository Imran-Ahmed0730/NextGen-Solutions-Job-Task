from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.price_lists import service
from app.modules.price_lists.models import PriceList, ProductPrice
from app.modules.price_lists.schemas import (
    PriceListCreate,
    PriceListResponse,
    PriceListUpdate,
    ProductPriceCreate,
    ProductPriceResponse,
    ProductPriceUpdate,
)

router = APIRouter(prefix="/api/v1/price-lists", tags=["price-lists"])


def _price_list_or_404(db: Session, price_list_id: int) -> PriceList:
    price_list = service.get_price_list(db, price_list_id)
    if price_list is None:
        raise HTTPException(status_code=404, detail="Price list not found")
    return price_list


def _product_price_or_404(db: Session, price_id: int) -> ProductPrice:
    product_price = service.get_product_price(db, price_id)
    if product_price is None:
        raise HTTPException(status_code=404, detail="Product price not found")
    return product_price


@router.get("", response_model=list[PriceListResponse])
def list_price_lists(
    include_inactive: bool = False,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master_data.price_lists.read")),
) -> list[PriceList]:
    return service.list_price_lists(
        db, include_inactive=include_inactive, offset=offset, limit=limit
    )


@router.post("", response_model=PriceListResponse, status_code=status.HTTP_201_CREATED)
def create_price_list(
    payload: PriceListCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.price_lists.create")),
) -> PriceList:
    return service.create_price_list(db, payload.model_dump(), actor, _ip(request))


@router.get("/{price_list_id}", response_model=PriceListResponse)
def get_price_list(
    price_list_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master_data.price_lists.read")),
) -> PriceList:
    return _price_list_or_404(db, price_list_id)


@router.patch("/{price_list_id}", response_model=PriceListResponse)
def update_price_list(
    price_list_id: int,
    payload: PriceListUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.price_lists.update")),
) -> PriceList:
    price_list = _price_list_or_404(db, price_list_id)
    return service.update_price_list(
        db, price_list, payload.model_dump(exclude_unset=True), actor, _ip(request)
    )


@router.delete("/{price_list_id}", response_model=PriceListResponse)
def delete_price_list(
    price_list_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.price_lists.delete")),
) -> PriceList:
    price_list = _price_list_or_404(db, price_list_id)
    return service.delete_price_list(db, price_list, actor, _ip(request))


@router.post("/{price_list_id}/activate", response_model=PriceListResponse)
def activate_price_list(
    price_list_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.price_lists.update")),
) -> PriceList:
    price_list = _price_list_or_404(db, price_list_id)
    return service.activate_price_list(db, price_list, actor, _ip(request))


@router.get("/{price_list_id}/prices", response_model=list[ProductPriceResponse])
def list_product_prices(
    price_list_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master_data.price_lists.read")),
) -> list[ProductPrice]:
    _price_list_or_404(db, price_list_id)
    return service.list_product_prices(db, price_list_id)


@router.post(
    "/{price_list_id}/prices",
    response_model=ProductPriceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_product_price(
    price_list_id: int,
    payload: ProductPriceCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.price_lists.create")),
) -> ProductPrice:
    _price_list_or_404(db, price_list_id)
    return service.create_product_price(
        db, price_list_id, payload.model_dump(), actor, _ip(request)
    )


@router.patch("/{price_list_id}/prices/{price_id}", response_model=ProductPriceResponse)
def update_product_price(
    price_list_id: int,
    price_id: int,
    payload: ProductPriceUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.price_lists.update")),
) -> ProductPrice:
    _price_list_or_404(db, price_list_id)
    product_price = _product_price_or_404(db, price_id)
    if product_price.price_list_id != price_list_id:
        raise HTTPException(status_code=404, detail="Product price not found")
    return service.update_product_price(
        db, product_price, payload.model_dump(exclude_unset=True), actor, _ip(request)
    )


@router.delete("/{price_list_id}/prices/{price_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product_price(
    price_list_id: int,
    price_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.price_lists.delete")),
) -> None:
    _price_list_or_404(db, price_list_id)
    product_price = _product_price_or_404(db, price_id)
    if product_price.price_list_id != price_list_id:
        raise HTTPException(status_code=404, detail="Product price not found")
    service.delete_product_price(db, product_price, actor, _ip(request))


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None
