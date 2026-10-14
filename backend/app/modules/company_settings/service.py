import re
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.company_settings import repository
from app.modules.company_settings.models import CompanySetting
from app.modules.company_settings.storage import DEFAULT_BRAND_ASSETS


def _validate_setting_value(key: str, value: str) -> str:
    if key == "invoice_footer":
        if len(value) > 1000:
            raise HTTPException(status_code=422, detail="Invoice footer is too long")
        return value
    value = value.strip()
    if key == "company_name":
        if not value:
            raise HTTPException(status_code=422, detail="Company name is required")
        if len(value) > 255:
            raise HTTPException(status_code=422, detail="Company name is too long")
    elif key == "company_email":
        if value and (
            len(value) > 255
            or re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value) is None
        ):
            raise HTTPException(status_code=422, detail="Company email is invalid")
    elif key == "company_phone":
        if value and (
            len(value) > 30
            or re.fullmatch(r"\+?[0-9][0-9 ()-]{5,28}[0-9]", value) is None
        ):
            raise HTTPException(status_code=422, detail="Company phone is invalid")
    elif key == "company_address" and len(value) > 1000:
        raise HTTPException(status_code=422, detail="Company address is too long")
    elif key == "currency_code":
        value = value.upper()
        if re.fullmatch(r"[A-Z]{3}", value) is None:
            raise HTTPException(status_code=422, detail="Currency code must be 3 letters")
    elif key == "timezone":
        if len(value) > 100 or (
            value != "UTC"
            and re.fullmatch(r"[A-Za-z][A-Za-z0-9._+-]*(?:/[A-Za-z0-9._+-]+)+", value)
            is None
        ):
            raise HTTPException(status_code=422, detail="Timezone must be an IANA-style name")
    elif key == "credit_limit_mode":
        value = value.upper()
        if value not in {"WARN", "BLOCK"}:
            raise HTTPException(
                status_code=422, detail="Credit limit mode must be WARN or BLOCK"
            )
    elif key == "receipt_tolerance_pct":
        try:
            percentage = Decimal(value)
        except InvalidOperation as exc:
            raise HTTPException(
                status_code=422, detail="Receiving tolerance must be a number"
            ) from exc
        if not percentage.is_finite() or percentage < 0:
            raise HTTPException(
                status_code=422, detail="Receiving tolerance must be non-negative"
            )
        value = str(percentage)
    return value


def list_settings(db: Session) -> list[CompanySetting]:
    return repository.list_settings(db)


def get_setting(db: Session, key: str) -> CompanySetting | None:
    return repository.get_setting(db, key)


def get_branding(db: Session) -> dict[str, str]:
    branding = {
        "company_name": "Sabuj Pran",
        "company_logo_path": DEFAULT_BRAND_ASSETS["logo"],
        "company_favicon_path": DEFAULT_BRAND_ASSETS["favicon"],
    }
    for key in branding:
        setting = repository.get_setting(db, key)
        if setting is not None:
            branding[key] = setting.value
    return branding


def save_setting(
    db: Session, key: str, value: str, actor: User, ip: str | None = None
) -> CompanySetting:
    key = key.strip()
    if not key:
        raise HTTPException(status_code=422, detail="Setting key is required")
    if len(key) > 100:
        raise HTTPException(status_code=422, detail="Setting key is too long")
    value = _validate_setting_value(key, value)

    setting = repository.get_setting(db, key)
    if setting is None:
        setting = CompanySetting(key=key, value=value)
        db.add(setting)
        db.flush()
        record_audit(
            db,
            actor_id=actor.id,
            entity_type="company_setting",
            entity_id=key,
            action="CREATE",
            after={"key": key, "value": value},
            ip=ip,
        )
        db.commit()
        db.refresh(setting)
        return setting

    before: dict[str, object] = {"key": setting.key, "value": setting.value}
    setting.value = value
    db.flush()
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="company_setting",
        entity_id=key,
        action="UPDATE",
        before=before,
        after={"key": key, "value": value},
        ip=ip,
    )
    db.commit()
    db.refresh(setting)
    return setting


def create_setting_from_payload(
    db: Session, data: dict[str, object], actor: User, ip: str | None = None
) -> CompanySetting:
    key = data.get("key")
    if not isinstance(key, str) or not key.strip():
        raise HTTPException(status_code=422, detail="Setting key is required")
    key = key.strip()
    if len(key) > 100:
        raise HTTPException(status_code=422, detail="Setting key is too long")

    if "value" not in data:
        raise HTTPException(status_code=422, detail="Setting value is required")
    raw_value = data.get("value")
    if raw_value is None:
        value = ""
    elif isinstance(raw_value, str):
        value = raw_value
    else:
        value = str(raw_value)
    value = _validate_setting_value(key, value)

    if repository.get_setting(db, key) is not None:
        raise HTTPException(status_code=409, detail="Company setting already exists")

    setting = CompanySetting(key=key, value=value)
    db.add(setting)
    db.flush()
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="company_setting",
        entity_id=key,
        action="CREATE",
        after={"key": key, "value": value},
        ip=ip,
    )
    db.commit()
    db.refresh(setting)
    return setting


def save_setting_from_payload(
    db: Session, data: dict[str, object], actor: User, ip: str | None = None
) -> CompanySetting:
    key = data.get("key")
    if not isinstance(key, str) or not key.strip():
        raise HTTPException(status_code=422, detail="Setting key is required")
    key = key.strip()
    if len(key) > 100:
        raise HTTPException(status_code=422, detail="Setting key is too long")

    if "value" not in data:
        raise HTTPException(status_code=422, detail="Setting value is required")
    raw_value = data.get("value")
    if raw_value is None:
        value = ""
    elif isinstance(raw_value, str):
        value = raw_value
    else:
        value = str(raw_value)

    return save_setting(db, key, value, actor, ip)


def delete_setting(
    db: Session, key: str, actor: User, ip: str | None = None
) -> None:
    setting = repository.get_setting(db, key)
    if setting is None:
        raise HTTPException(status_code=404, detail="Company setting not found")
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="company_setting",
        entity_id=key,
        action="DELETE",
        before={"key": setting.key, "value": setting.value},
        after=None,
        ip=ip,
    )
    db.delete(setting)
    db.commit()