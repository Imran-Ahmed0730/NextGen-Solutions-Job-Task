from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

ID_TYPE = (
    BigInteger().with_variant(BIGINT(unsigned=True), "mysql").with_variant(Integer(), "sqlite")
)


class DocumentSequence(Base):
    __tablename__ = "document_sequences"
    __table_args__ = (
        UniqueConstraint("doc_type", "year", name="uq_document_sequences_type_year"),
        Index("ix_document_sequences_doc_type", "doc_type"),
        Index("ix_document_sequences_year", "year"),
    )

    id: Mapped[int] = mapped_column(ID_TYPE, primary_key=True, autoincrement=True)
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False)
    prefix: Mapped[str] = mapped_column(String(30), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    last_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    padding: Mapped[int] = mapped_column(
        Integer, nullable=False, default=4, server_default=text("4")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )
