from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.boms import repository
from app.modules.boms.models import BOM, BOMLine
from app.modules.boms.schemas import BOMCreate, BOMOptionsResponse, BOMProductOption
from app.modules.products import service as product_service
from app.modules.products.models import Product, ProductType


def list_boms(
    db: Session, *, include_inactive: bool = False, offset: int = 0, limit: int = 50
) -> list[BOM]:
    return repository.list_boms(db, include_inactive=include_inactive, offset=offset, limit=limit)


def get_bom(db: Session, bom_id: int, *, active_only: bool = False) -> BOM | None:
    bom = repository.get_bom(db, bom_id)
    if bom is None or (active_only and (not bom.is_active or bom.deleted_at is not None)):
        return None
    return bom


def get_bom_options(db: Session) -> BOMOptionsResponse:
    raw_products = product_service.list_products(db, product_type=ProductType.RAW, limit=200)
    finished_products = product_service.list_products(
        db, product_type=ProductType.FINISHED, limit=200
    )
    return BOMOptionsResponse(
        raw_products=[_product_option(product) for product in raw_products],
        finished_products=[_product_option(product) for product in finished_products],
    )


def create_bom(db: Session, payload: BOMCreate, actor: User, ip: str | None = None) -> BOM:
    try:
        code = payload.code.strip()
        _ensure_code_available(db, code)
        finished_product = _validate_finished_product(db, payload.finished_product_id)
        if (
            not finished_product.unit.allow_decimal
            and payload.output_qty != payload.output_qty.to_integral_value()
        ):
            raise HTTPException(status_code=422, detail="BOM_OUTPUT_REQUIRES_WHOLE_QTY")
        _validate_raw_products(db, payload)
        bom = BOM(
            code=code,
            finished_product_id=finished_product.id,
            output_qty=payload.output_qty,
            labor_cost_default=payload.labor_cost_default,
            overhead_cost_default=payload.overhead_cost_default,
            lines=[
                BOMLine(raw_product_id=line.raw_product_id, qty=line.qty) for line in payload.lines
            ],
        )
        db.add(bom)
        db.flush()
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="bom",
            entity_id=bom.id,
            action="CREATE",
            after=_snapshot(bom),
            ip=ip,
        )
        db.commit()
        return repository.get_bom(db, bom.id) or bom
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="BOM_CODE_ALREADY_EXISTS") from exc
    except Exception:
        db.rollback()
        raise


def update_bom(
    db: Session, bom_id: int, payload: BOMCreate, actor: User, ip: str | None = None
) -> BOM:
    try:
        bom = repository.get_bom(db, bom_id, for_update=True)
        if bom is None or bom.deleted_at is not None:
            raise HTTPException(status_code=404, detail="BOM not found")
        code = payload.code.strip()
        _ensure_code_available(db, code, exclude_id=bom.id)
        finished_product = _validate_finished_product(db, payload.finished_product_id)
        if (
            not finished_product.unit.allow_decimal
            and payload.output_qty != payload.output_qty.to_integral_value()
        ):
            raise HTTPException(status_code=422, detail="BOM_OUTPUT_REQUIRES_WHOLE_QTY")
        _validate_raw_products(db, payload)
        before = _snapshot(bom)
        bom.code = code
        bom.finished_product_id = finished_product.id
        bom.output_qty = payload.output_qty
        bom.labor_cost_default = payload.labor_cost_default
        bom.overhead_cost_default = payload.overhead_cost_default
        bom.lines = [
            BOMLine(raw_product_id=line.raw_product_id, qty=line.qty) for line in payload.lines
        ]
        bom.updated_at = datetime.now(UTC)
        db.flush()
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="bom",
            entity_id=bom.id,
            action="UPDATE",
            before=before,
            after=_snapshot(bom),
            ip=ip,
        )
        db.commit()
        return repository.get_bom(db, bom.id) or bom
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="BOM_CODE_ALREADY_EXISTS") from exc
    except Exception:
        db.rollback()
        raise


def set_bom_active(
    db: Session, bom_id: int, *, active: bool, actor: User, ip: str | None = None
) -> BOM:
    try:
        bom = repository.get_bom(db, bom_id, for_update=True)
        if bom is None:
            raise HTTPException(status_code=404, detail="BOM not found")
        if active:
            if bom.is_active and bom.deleted_at is None:
                return bom
        elif bom.deleted_at is not None:
            return bom
        before = _snapshot(bom)
        bom.is_active = active
        setattr(bom, "deleted_at", None if active else datetime.now(UTC))
        bom.updated_at = datetime.now(UTC)
        db.flush()
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="bom",
            entity_id=bom.id,
            action="STATUS" if active else "DELETE",
            before=before,
            after=_snapshot(bom),
            ip=ip,
        )
        db.commit()
        return repository.get_bom(db, bom.id) or bom
    except Exception:
        db.rollback()
        raise


def _validate_finished_product(db: Session, product_id: int) -> Product:
    product = product_service.get_product(db, product_id)
    if (
        product is None
        or product.type != ProductType.FINISHED
        or not product.is_stocked
        or not product.is_active
        or product.deleted_at is not None
    ):
        raise HTTPException(status_code=422, detail="BOM_FINISHED_PRODUCT_INVALID")
    return product


def _validate_raw_products(db: Session, payload: BOMCreate) -> None:
    if len({line.raw_product_id for line in payload.lines}) != len(payload.lines):
        raise HTTPException(status_code=422, detail="BOM_COMPONENTS_MUST_BE_UNIQUE")
    if payload.finished_product_id in {line.raw_product_id for line in payload.lines}:
        raise HTTPException(status_code=422, detail="BOM_PRODUCT_CANNOT_BE_ITS_OWN_COMPONENT")
    for product_id in {line.raw_product_id for line in payload.lines}:
        product = product_service.get_product(db, product_id)
        if (
            product is None
            or product.type != ProductType.RAW
            or not product.is_stocked
            or not product.is_active
            or product.deleted_at is not None
        ):
            raise HTTPException(status_code=422, detail="BOM_RAW_PRODUCT_INVALID")
        if not product.unit.allow_decimal and any(
            line.raw_product_id == product_id and line.qty != line.qty.to_integral_value()
            for line in payload.lines
        ):
            raise HTTPException(status_code=422, detail="BOM_COMPONENT_REQUIRES_WHOLE_QTY")


def _ensure_code_available(db: Session, code: str, *, exclude_id: int | None = None) -> None:
    if repository.get_bom_by_code(db, code, exclude_id=exclude_id) is not None:
        raise HTTPException(status_code=409, detail="BOM_CODE_ALREADY_EXISTS")


def _product_option(product: Product) -> BOMProductOption:
    return BOMProductOption(
        id=product.id,
        sku=product.sku,
        name=product.name,
        unit_code=product.unit.code,
        type=product.type,
    )


def _snapshot(bom: BOM) -> dict[str, object]:
    return {
        "code": bom.code,
        "finished_product_id": bom.finished_product_id,
        "output_qty": str(bom.output_qty),
        "labor_cost_default": str(bom.labor_cost_default),
        "overhead_cost_default": str(bom.overhead_cost_default),
        "is_active": bom.is_active,
        "deleted_at": bom.deleted_at.isoformat() if bom.deleted_at else None,
        "lines": [
            {"raw_product_id": line.raw_product_id, "qty": str(line.qty)} for line in bom.lines
        ],
    }
