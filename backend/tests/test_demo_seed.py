from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.demo_seed import DOCUMENT_SEQUENCES, seed_demo_data
from app.main import app  # noqa: F401  # Register all mapped models for create_all.
from app.modules.auth.models import AuditLog, User
from app.modules.auth.seed import seed_initial_admin
from app.modules.document_numbering.models import DocumentSequence
from app.modules.inventory.models import StockTransaction
from app.modules.money_transactions.models import MoneyTransaction


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        yield session
    engine.dispose()


def test_demo_seed_is_idempotent_and_leaves_ledgers_untouched(db_session: Session) -> None:
    seeded_admin = seed_initial_admin(db_session)
    actor = db_session.scalar(select(User).where(User.username == seeded_admin.username))
    assert actor is not None

    first_run_created = seed_demo_data(db_session, actor)
    purchase_order_sequence = db_session.scalar(
        select(DocumentSequence).where(DocumentSequence.doc_type == "PURCHASE_ORDER")
    )
    assert purchase_order_sequence is not None
    purchase_order_sequence.last_number = 7
    db_session.commit()
    first_audit_count = db_session.scalar(select(func.count(AuditLog.id)))
    second_run_created = seed_demo_data(db_session, actor)

    assert first_run_created == 12 + len(DOCUMENT_SEQUENCES)
    assert second_run_created == 0
    assert db_session.scalar(select(func.count(AuditLog.id))) == first_audit_count
    assert db_session.scalar(select(func.count(DocumentSequence.id))) == len(DOCUMENT_SEQUENCES)
    assert purchase_order_sequence.last_number == 7
    assert db_session.scalar(select(func.count(StockTransaction.id))) == 0
    assert db_session.scalar(select(func.count(MoneyTransaction.id))) == 0
