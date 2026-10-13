from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.audit import record_audit
from app.modules.auth.models import User
from app.modules.document_numbering import repository
from app.modules.document_numbering.models import DocumentSequence


def list_sequences(db: Session, *, limit: int = 100, offset: int = 0):
    return repository.list_sequences(db, limit=limit, offset=offset)


def get_sequence(db: Session, sequence_id: int) -> DocumentSequence | None:
    return repository.get_sequence(db, sequence_id)


def _validate_doc_type(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=422, detail="Document type is required")
    value = value.strip()
    if len(value) > 50:
        raise HTTPException(status_code=422, detail="Document type is too long")
    return value


def _validate_prefix(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=422, detail="Document prefix is required")
    value = value.strip()
    if len(value) > 30:
        raise HTTPException(status_code=422, detail="Document prefix is too long")
    return value


def _validate_year(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise HTTPException(status_code=422, detail="Document year must be an integer")
    if value < 1900 or value > 9999:
        raise HTTPException(status_code=422, detail="Document year is out of range")
    return value


def _validate_last_number(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise HTTPException(status_code=422, detail="Last number must be an integer")
    if value < 0:
        raise HTTPException(status_code=422, detail="Last number cannot be negative")
    return value


def _validate_padding(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise HTTPException(status_code=422, detail="Padding must be an integer")
    if value < 1 or value > 10:
        raise HTTPException(status_code=422, detail="Padding must be between 1 and 10")
    return value


def create_sequence(
    db: Session, data: dict[str, object], actor: User, ip: str | None = None
) -> DocumentSequence:
    doc_type = _validate_doc_type(data.get("doc_type"))
    prefix = _validate_prefix(data.get("prefix"))
    year = _validate_year(data.get("year", datetime.now(timezone.utc).year))
    last_number = _validate_last_number(data.get("last_number", 0))
    padding = _validate_padding(data.get("padding", 4))

    existing = repository.get_sequence_by_type_and_year(db, doc_type, year)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Document sequence already exists")

    sequence = DocumentSequence(
        doc_type=doc_type,
        prefix=prefix,
        year=year,
        last_number=last_number,
        padding=padding,
    )
    db.add(sequence)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Document sequence already exists") from exc

    record_audit(
        db,
        actor_id=actor.id,
        entity_type="document_sequence",
        entity_id=sequence.id,
        action="CREATE",
        after=_snapshot(sequence),
        ip=ip,
    )
    db.commit()
    db.refresh(sequence)
    return sequence


def update_sequence(
    db: Session,
    sequence: DocumentSequence,
    data: dict[str, object],
    actor: User,
    ip: str | None = None,
) -> DocumentSequence:
    doc_type = sequence.doc_type
    if "doc_type" in data:
        doc_type = _validate_doc_type(data["doc_type"])

    prefix = sequence.prefix
    if "prefix" in data:
        prefix = _validate_prefix(data["prefix"])

    year = sequence.year
    if "year" in data:
        year = _validate_year(data["year"])

    last_number = sequence.last_number
    if "last_number" in data:
        last_number = _validate_last_number(data["last_number"])

    padding = sequence.padding
    if "padding" in data:
        padding = _validate_padding(data["padding"])

    if doc_type != sequence.doc_type or year != sequence.year:
        existing = repository.get_sequence_by_type_and_year(db, doc_type, year)
        if existing is not None and existing.id != sequence.id:
            raise HTTPException(status_code=409, detail="Document sequence already exists")

    before = _snapshot(sequence)
    sequence.doc_type = doc_type
    sequence.prefix = prefix
    sequence.year = year
    sequence.last_number = last_number
    sequence.padding = padding
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Document sequence already exists") from exc

    record_audit(
        db,
        actor_id=actor.id,
        entity_type="document_sequence",
        entity_id=sequence.id,
        action="UPDATE",
        before=before,
        after=_snapshot(sequence),
        ip=ip,
    )
    db.commit()
    db.refresh(sequence)
    return sequence


def delete_sequence(
    db: Session, sequence: DocumentSequence, actor: User, ip: str | None = None
) -> None:
    record_audit(
        db,
        actor_id=actor.id,
        entity_type="document_sequence",
        entity_id=sequence.id,
        action="DELETE",
        before=_snapshot(sequence),
        after=None,
        ip=ip,
    )
    db.delete(sequence)
    db.commit()


def format_number(sequence: DocumentSequence) -> str:
    return f"{sequence.prefix}{sequence.year}{str(sequence.last_number).zfill(sequence.padding)}"


def preview_next_number(db: Session, doc_type: str, year: int | None = None) -> str:
    if year is None:
        year = datetime.now(timezone.utc).year
    sequence = repository.get_sequence_by_type_and_year(db, doc_type, year)
    if sequence is None:
        raise HTTPException(status_code=404, detail="Document sequence not configured")
    sequence.last_number += 0
    next_value = sequence.last_number + 1
    return f"{sequence.prefix}{sequence.year}{str(next_value).zfill(sequence.padding)}"


def generate_next_number(db: Session, doc_type: str, year: int | None = None) -> str:
    if year is None:
        year = datetime.now(timezone.utc).year
    sequence = repository.get_sequence_by_type_and_year(db, doc_type, year, for_update=True)
    if sequence is None:
        raise HTTPException(status_code=404, detail="Document sequence not configured")
    sequence.last_number += 1
    db.flush()
    return format_number(sequence)


def _snapshot(sequence: DocumentSequence) -> dict[str, object]:
    return {
        "doc_type": sequence.doc_type,
        "prefix": sequence.prefix,
        "year": sequence.year,
        "last_number": sequence.last_number,
        "padding": sequence.padding,
    }


# Compatibility aliases used by document modules.
generate_document_number = generate_next_number
next_document_number = generate_next_number
peek_next_number = preview_next_number