from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.parties.models import PartyContact


def list_contacts(db: Session, party_type: str, party_id: int) -> list[PartyContact]:
    statement = (
        select(PartyContact)
        .where(PartyContact.party_type == party_type, PartyContact.party_id == party_id)
        .order_by(PartyContact.name, PartyContact.id)
    )
    return list(db.scalars(statement))


def get_contact(db: Session, contact_id: int) -> PartyContact | None:
    return db.get(PartyContact, contact_id)
