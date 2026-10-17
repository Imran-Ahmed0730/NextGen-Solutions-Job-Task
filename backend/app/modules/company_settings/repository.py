from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.company_settings.models import CompanySetting


def list_settings(db: Session) -> list[CompanySetting]:
    return list(db.scalars(select(CompanySetting).order_by(CompanySetting.key)))


def get_setting(db: Session, key: str) -> CompanySetting | None:
    return db.get(CompanySetting, key)
