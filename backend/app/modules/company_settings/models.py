from sqlalchemy import (
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

ID_TYPE = None


class CompanySetting(Base):
    __tablename__ = "company_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
