from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_permission
from app.modules.auth.models import User
from app.modules.document_numbering import service
from app.modules.document_numbering.models import DocumentSequence
from app.modules.document_numbering.schemas import (
    DocumentSequenceCreate,
    DocumentSequenceResponse,
    DocumentSequenceUpdate,
    NextDocumentNumberResponse,
)

router = APIRouter(prefix="/api/v1/document-numbering", tags=["document-numbering"])


def _sequence_or_404(db: Session, sequence_id: int) -> DocumentSequence:
    sequence = service.get_sequence(db, sequence_id)
    if sequence is None:
        raise HTTPException(status_code=404, detail="Document sequence not found")
    return sequence


@router.get("", response_model=list[DocumentSequenceResponse])
def list_sequences(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master_data.document_numbering.read")),
) -> list[DocumentSequence]:
    return service.list_sequences(db, limit=limit, offset=offset)


@router.post("", response_model=DocumentSequenceResponse, status_code=status.HTTP_201_CREATED)
def create_sequence(
    payload: DocumentSequenceCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.document_numbering.create")),
) -> DocumentSequence:
    return service.create_sequence(db, payload.model_dump(), actor, _ip(request))


@router.get("/{sequence_id}", response_model=DocumentSequenceResponse)
def get_sequence(
    sequence_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master_data.document_numbering.read")),
) -> DocumentSequence:
    return _sequence_or_404(db, sequence_id)


@router.patch("/{sequence_id}", response_model=DocumentSequenceResponse)
def update_sequence(
    sequence_id: int,
    payload: DocumentSequenceUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.document_numbering.update")),
) -> DocumentSequence:
    sequence = _sequence_or_404(db, sequence_id)
    return service.update_sequence(
        db, sequence, payload.model_dump(exclude_unset=True), actor, _ip(request)
    )


@router.delete("/{sequence_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sequence(
    sequence_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("master_data.document_numbering.delete")),
) -> None:
    sequence = _sequence_or_404(db, sequence_id)
    service.delete_sequence(db, sequence, actor, _ip(request))


@router.get(
    "/{doc_type}/next", response_model=NextDocumentNumberResponse
)
def preview_next_number(
    doc_type: str,
    year: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master_data.document_numbering.read")),
) -> NextDocumentNumberResponse:
    from datetime import datetime, timezone

    resolved_year = year if year is not None else datetime.now(timezone.utc).year
    number = service.preview_next_number(db, doc_type, resolved_year)
    return NextDocumentNumberResponse(
        doc_type=doc_type, year=resolved_year, number=number
    )


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None