from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

DocType = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
Prefix = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]
PositiveInt = Annotated[int, Field(strict=True, ge=1)]


class DocumentSequenceCreate(BaseModel):
    doc_type: DocType
    prefix: Prefix
    year: int = Field(ge=1900, le=9999)
    last_number: int = Field(default=0, ge=0)
    padding: int = Field(default=4, ge=1, le=10)


class DocumentSequenceUpdate(BaseModel):
    prefix: Prefix | None = None
    year: int | None = Field(default=None, ge=1900, le=9999)
    last_number: int | None = Field(default=None, ge=0)
    padding: int | None = Field(default=None, ge=1, le=10)


class DocumentSequenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doc_type: str
    prefix: str
    year: int
    last_number: int
    padding: int
    created_at: datetime
    updated_at: datetime


class NextDocumentNumberResponse(BaseModel):
    doc_type: str
    year: int
    number: str