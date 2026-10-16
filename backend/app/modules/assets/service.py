from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.assets import repository
from app.modules.assets.models import Asset, AssetAssignment, AssetMaintenance
from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.employees import service as employee_service


def list_assets(
    db: Session, *, include_inactive: bool = False, offset: int = 0, limit: int = 50
) -> list[Asset]:
    return repository.list_assets(
        db, include_inactive=include_inactive, offset=offset, limit=limit
    )


def get_asset(db: Session, asset_id: int, *, for_update: bool = False) -> Asset | None:
    return repository.get_asset(db, asset_id, for_update=for_update)


def create_asset(
    db: Session, payload: dict[str, object], actor: User, ip: str | None = None
) -> Asset:
    asset_code = _text(payload.get("asset_code"), "Asset code", 50)
    _ensure_code_available(db, asset_code)
    asset = Asset(
        asset_code=asset_code,
        name=_text(payload.get("name"), "Asset name", 150),
        category=_text(payload.get("category"), "Asset category", 100),
        purchase_date=_date(payload.get("purchase_date"), "Purchase date"),
        purchase_cost=_money(payload.get("purchase_cost")),
        location=_text(payload.get("location"), "Location", 150),
        status=_status(payload.get("status", "IN_STORE")),
        created_by=actor.id,
    )
    db.add(asset)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Asset code is already in use") from exc
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="asset",
        entity_id=asset.id,
        action="CREATE",
        after=_asset_snapshot(asset),
        ip=ip,
    )
    db.commit()
    return repository.get_asset(db, asset.id) or asset


def update_asset(
    db: Session,
    asset_id: int,
    payload: dict[str, object],
    actor: User,
    ip: str | None = None,
) -> Asset:
    try:
        asset = _active_asset(db, asset_id, for_update=True)
        before = _asset_snapshot(asset)
        for field, label, maximum in (
            ("asset_code", "Asset code", 50),
            ("name", "Asset name", 150),
            ("category", "Asset category", 100),
            ("location", "Location", 150),
        ):
            if field in payload:
                value = _text(payload[field], label, maximum)
                if field == "asset_code" and value != asset.asset_code:
                    _ensure_code_available(db, value, exclude_id=asset.id)
                setattr(asset, field, value)
        if "purchase_date" in payload:
            asset.purchase_date = _date(payload["purchase_date"], "Purchase date")
        if "purchase_cost" in payload:
            asset.purchase_cost = _money(payload["purchase_cost"])
        if "status" in payload:
            new_status = _status(payload["status"])
            if new_status != "IN_USE" and any(
                assignment.returned_on is None for assignment in asset.assignments
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Return the active assignment before changing asset status",
                )
            asset.status = new_status
        db.flush()
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="asset",
            entity_id=asset.id,
            action="UPDATE",
            before=before,
            after=_asset_snapshot(asset),
            ip=ip,
        )
        db.commit()
        return repository.get_asset(db, asset.id) or asset
    except Exception:
        db.rollback()
        raise


def delete_asset(
    db: Session, asset_id: int, actor: User, ip: str | None = None
) -> Asset:
    try:
        asset = _active_asset(db, asset_id, for_update=True)
        before = _asset_snapshot(asset)
        asset.is_active = False
        asset.deleted_at = datetime.now(UTC)
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="asset",
            entity_id=asset.id,
            action="DELETE",
            before=before,
            after=_asset_snapshot(asset),
            ip=ip,
        )
        db.commit()
        return repository.get_asset(db, asset.id) or asset
    except Exception:
        db.rollback()
        raise


def restore_asset(
    db: Session, asset_id: int, actor: User, ip: str | None = None
) -> Asset:
    try:
        asset = repository.get_asset(db, asset_id, for_update=True)
        if asset is None:
            raise HTTPException(status_code=404, detail="Asset not found")
        if asset.deleted_at is None and asset.is_active:
            return asset
        before = _asset_snapshot(asset)
        asset.is_active = True
        setattr(asset, "deleted_at", None)
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="asset",
            entity_id=asset.id,
            action="STATUS",
            before=before,
            after=_asset_snapshot(asset),
            ip=ip,
        )
        db.commit()
        return repository.get_asset(db, asset.id) or asset
    except Exception:
        db.rollback()
        raise


def assign_asset(
    db: Session,
    asset_id: int,
    payload: dict[str, object],
    actor: User,
    ip: str | None = None,
) -> Asset:
    try:
        asset = _active_asset(db, asset_id, for_update=True)
        if asset.status in {"DISPOSED", "UNDER_MAINTENANCE"}:
            raise HTTPException(
                status_code=409,
                detail="Disposed or under-maintenance assets cannot be assigned",
            )
        if any(assignment.returned_on is None for assignment in asset.assignments):
            raise HTTPException(status_code=409, detail="ASSET_ALREADY_ASSIGNED")
        employee_id = payload.get("employee_id")
        if employee_id is not None and (
            not isinstance(employee_id, int) or isinstance(employee_id, bool) or employee_id <= 0
        ):
            raise HTTPException(status_code=422, detail="Employee must be active")
        employee = (
            employee_service.get_active_employee(db, employee_id)
            if isinstance(employee_id, int)
            else None
        )
        assignment = AssetAssignment(
            asset_id=asset.id,
            employee_id=employee.id if employee else None,
            location=_text(payload.get("location"), "Location", 150),
            assigned_on=_date(payload.get("assigned_on"), "Assigned date"),
        )
        asset.location = assignment.location
        asset.status = "IN_USE"
        db.add(assignment)
        db.flush()
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="asset_assignment",
            entity_id=assignment.id,
            action="CREATE",
            after=_assignment_snapshot(assignment),
            ip=ip,
        )
        db.commit()
        return repository.get_asset(db, asset.id) or asset
    except Exception:
        db.rollback()
        raise


def return_asset(
    db: Session,
    asset_id: int,
    assignment_id: int,
    returned_on: date,
    actor: User,
    ip: str | None = None,
) -> Asset:
    try:
        asset = _active_asset(db, asset_id, for_update=True)
        assignment = next(
            (item for item in asset.assignments if item.id == assignment_id), None
        )
        if assignment is None or assignment.returned_on is not None:
            raise HTTPException(status_code=404, detail="Active asset assignment not found")
        if returned_on < assignment.assigned_on:
            raise HTTPException(status_code=422, detail="Return date cannot precede assigned date")
        before = _assignment_snapshot(assignment)
        assignment.returned_on = returned_on
        asset.status = "IN_STORE"
        db.flush()
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="asset_assignment",
            entity_id=assignment.id,
            action="STATUS",
            before=before,
            after=_assignment_snapshot(assignment),
            ip=ip,
        )
        db.commit()
        return repository.get_asset(db, asset.id) or asset
    except Exception:
        db.rollback()
        raise


def add_maintenance(
    db: Session,
    asset_id: int,
    payload: dict[str, object],
    actor: User,
    ip: str | None = None,
) -> Asset:
    try:
        asset = _active_asset(db, asset_id, for_update=True)
        maintenance_date = _date(payload.get("maintenance_date"), "Maintenance date")
        next_due = payload.get("next_due_date")
        next_due_date = _date(next_due, "Next due date") if next_due is not None else None
        if next_due_date is not None and next_due_date < maintenance_date:
            raise HTTPException(
                status_code=422, detail="Next due date cannot precede maintenance date"
            )
        maintenance = AssetMaintenance(
            asset_id=asset.id,
            maintenance_date=maintenance_date,
            description=_text(payload.get("description"), "Description", 2000),
            cost=_money(payload.get("cost")),
            next_due_date=next_due_date,
            created_by=actor.id,
        )
        db.add(maintenance)
        db.flush()
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="asset_maintenance",
            entity_id=maintenance.id,
            action="CREATE",
            after=_maintenance_snapshot(maintenance),
            ip=ip,
        )
        db.commit()
        return repository.get_asset(db, asset.id) or asset
    except Exception:
        db.rollback()
        raise


def _active_asset(db: Session, asset_id: int, *, for_update: bool = False) -> Asset:
    asset = repository.get_asset(db, asset_id, for_update=for_update)
    if asset is None or not asset.is_active or asset.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


def _ensure_code_available(db: Session, code: str, *, exclude_id: int | None = None) -> None:
    if repository.get_asset_by_code(db, code, exclude_id=exclude_id) is not None:
        raise HTTPException(status_code=409, detail="Asset code is already in use")


def _text(value: object, label: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=422, detail=f"{label} is required")
    result = value.strip()
    if len(result) > maximum:
        raise HTTPException(status_code=422, detail=f"{label} is too long")
    return result


def _date(value: object, label: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if not isinstance(value, date):
        raise HTTPException(status_code=422, detail=f"{label} is required")
    return value


def _money(value: object) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Cost must be a number") from exc
    if not result.is_finite() or result < 0 or result != result.quantize(Decimal("0.01")):
        raise HTTPException(
            status_code=422, detail="Cost must be nonnegative with at most 2 decimals"
        )
    if result > Decimal("9999999999999999.99"):
        raise HTTPException(status_code=422, detail="Cost exceeds supported amount")
    return result


def _status(value: object) -> str:
    statuses = {"IN_USE", "IN_STORE", "UNDER_MAINTENANCE", "DISPOSED"}
    if not isinstance(value, str) or value not in statuses:
        raise HTTPException(status_code=422, detail="Invalid asset status")
    return value


def _asset_snapshot(asset: Asset) -> dict[str, object]:
    return {
        "asset_code": asset.asset_code,
        "name": asset.name,
        "category": asset.category,
        "purchase_date": asset.purchase_date.isoformat(),
        "purchase_cost": str(asset.purchase_cost),
        "location": asset.location,
        "status": asset.status,
        "is_active": asset.is_active,
        "deleted_at": asset.deleted_at.isoformat() if asset.deleted_at else None,
    }


def _assignment_snapshot(assignment: AssetAssignment) -> dict[str, object]:
    return {
        "asset_id": assignment.asset_id,
        "employee_id": assignment.employee_id,
        "location": assignment.location,
        "assigned_on": assignment.assigned_on.isoformat(),
        "returned_on": (
            assignment.returned_on.isoformat() if assignment.returned_on else None
        ),
    }


def _maintenance_snapshot(maintenance: AssetMaintenance) -> dict[str, object]:
    return {
        "asset_id": maintenance.asset_id,
        "maintenance_date": maintenance.maintenance_date.isoformat(),
        "description": maintenance.description,
        "cost": str(maintenance.cost),
        "next_due_date": (
            maintenance.next_due_date.isoformat() if maintenance.next_due_date else None
        ),
    }
