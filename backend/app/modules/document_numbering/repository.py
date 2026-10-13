from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.document_numbering.models import DocumentSequence


def list_sequences(
    db: Session, *, limit: int = 100, offset: int = 0
) -> list[DocumentSequence]:
    return list(
        db.scalars(
            select(DocumentSequence)
            .order_by(DocumentSequence.doc_type, DocumentSequence.year)
            .offset(offset)
            .limit(limit)
        )
    )


def get_sequence(db: Session, sequence_id: int) -> DocumentSequence | None:
    return db.get(DocumentSequence, sequence_id)


def get_sequence_by_type_and_year(
    db: Session, doc_type: str, year: int, *, for_update: bool = False
) -> DocumentSequence | None:
    statement = select(DocumentSequence).where(
        DocumentSequence.doc_type == doc_type,
        DocumentSequence.year == year,
    )
    if for_update:
        statement = statement.with_for_update()
    return db.scalar(statement)