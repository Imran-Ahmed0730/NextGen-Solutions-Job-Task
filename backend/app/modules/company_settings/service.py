from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.company_settings import repository
from app.modules.company_settings.models import CompanySetting


def list_settings(db: Session) -> list[CompanySetting]:
    return repository.list_settings(db)


def get_setting(db: Session, key: str) -> CompanySetting | None:
    return repository.get_setting(db, key)


def save_setting(
    db: Session, key: str, value: str, actor: User, ip: str | None = None
) -> CompanySetting:
    key = key.strip()
    if not key:
        raise HTTPException(status_code=422, detail="Setting key is required")
    if len(key) > 100:
        raise HTTPException(status_code=422, detail="Setting key is too long")

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