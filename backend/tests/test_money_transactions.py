from collections.abc import Generator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.modules.auth.models import AuditLog, User
from app.modules.money_accounts.models import MoneyAccount, MoneyAccountType
from app.modules.money_accounts.service import update_money_account
from app.modules.money_transactions.models import MoneyTransaction, MoneyTransactionType
from app.modules.money_transactions.service import get_account_balance, post_money_transaction
from app.modules.payment_methods.models import PaymentMethod


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            AuditLog.__table__,
            PaymentMethod.__table__,
            MoneyAccount.__table__,
            MoneyTransaction.__table__,
        ],
    )
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        yield session
    engine.dispose()


@pytest.fixture
def account_and_actor(db_session: Session) -> tuple[MoneyAccount, User]:
    actor = User(
        username="money-operator",
        full_name="Money Operator",
        password_hash="test-hash",
    )
    account = MoneyAccount(
        name="Main Cash",
        type=MoneyAccountType.CASH,
        opening_balance=Decimal("100.00"),
        allow_overdraft=False,
    )
    db_session.add_all([actor, account])
    db_session.commit()
    return account, actor


def test_money_postings_preserve_balance_and_write_audit(
    db_session: Session, account_and_actor: tuple[MoneyAccount, User]
) -> None:
    account, actor = account_and_actor
    collection = post_money_transaction(
        db_session,
        account_id=account.id,
        amount_signed=Decimal("25.00"),
        txn_type=MoneyTransactionType.COLLECTION,
        actor=actor,
        txn_date=datetime(2026, 10, 15, tzinfo=UTC),
        source_type="CUSTOMER_COLLECTION",
        source_id=12,
        party_type="CUSTOMER",
        party_id=8,
    )
    post_money_transaction(
        db_session,
        account_id=account.id,
        amount_signed=Decimal("-40.00"),
        txn_type=MoneyTransactionType.PAYMENT,
        actor=actor,
    )
    db_session.commit()

    assert collection.id > 0
    assert get_account_balance(db_session, account.id) == Decimal("85.00")
    transactions = list(
        db_session.scalars(
            select(MoneyTransaction).where(MoneyTransaction.account_id == account.id)
        )
    )
    audits = list(
        db_session.scalars(select(AuditLog).where(AuditLog.entity_type == "money_transaction"))
    )
    assert len(transactions) == 2
    assert len(audits) == 2
    assert all(audit.action == "CREATE" for audit in audits)


def test_money_posting_rejects_wrong_sign_and_insufficient_funds(
    db_session: Session, account_and_actor: tuple[MoneyAccount, User]
) -> None:
    account, actor = account_and_actor

    with pytest.raises(HTTPException) as wrong_sign:
        post_money_transaction(
            db_session,
            account_id=account.id,
            amount_signed=Decimal("5.00"),
            txn_type=MoneyTransactionType.EXPENSE,
            actor=actor,
        )
    assert wrong_sign.value.status_code == 422

    with pytest.raises(HTTPException) as insufficient:
        post_money_transaction(
            db_session,
            account_id=account.id,
            amount_signed=Decimal("-100.01"),
            txn_type=MoneyTransactionType.PAYMENT,
            actor=actor,
        )
    assert insufficient.value.status_code == 409
    assert insufficient.value.detail == "MONEY_ACCOUNT_INSUFFICIENT"
    assert get_account_balance(db_session, account.id) == Decimal("100.00")
    assert db_session.scalar(select(MoneyTransaction.id)) is None


def test_overdraft_setting_allows_negative_balance(
    db_session: Session, account_and_actor: tuple[MoneyAccount, User]
) -> None:
    account, actor = account_and_actor
    account.allow_overdraft = True
    db_session.commit()

    post_money_transaction(
        db_session,
        account_id=account.id,
        amount_signed=Decimal("-150.00"),
        txn_type=MoneyTransactionType.SALARY,
        actor=actor,
    )
    db_session.commit()

    assert get_account_balance(db_session, account.id) == Decimal("-50.00")
    with pytest.raises(HTTPException) as error:
        update_money_account(db_session, account, {"allow_overdraft": False}, actor)
    assert error.value.status_code == 409
    assert error.value.detail == "MONEY_ACCOUNT_OVERDRAFT_REQUIRED"


def test_opening_adjustment_is_counted_against_the_account_baseline(
    db_session: Session, account_and_actor: tuple[MoneyAccount, User]
) -> None:
    account, actor = account_and_actor
    post_money_transaction(
        db_session,
        account_id=account.id,
        amount_signed=Decimal("-20.00"),
        txn_type=MoneyTransactionType.OPENING,
        actor=actor,
    )
    db_session.commit()

    assert get_account_balance(db_session, account.id) == Decimal("80.00")


def test_opening_balance_is_immutable_after_first_transaction(
    db_session: Session, account_and_actor: tuple[MoneyAccount, User]
) -> None:
    account, actor = account_and_actor
    post_money_transaction(
        db_session,
        account_id=account.id,
        amount_signed=Decimal("10.00"),
        txn_type=MoneyTransactionType.INCOME,
        actor=actor,
    )
    db_session.commit()

    with pytest.raises(HTTPException) as error:
        update_money_account(
            db_session,
            account,
            {"opening_balance": Decimal("200.00")},
            actor,
        )
    assert error.value.status_code == 409
    assert error.value.detail == "MONEY_ACCOUNT_OPENING_BALANCE_LOCKED"

    updated = update_money_account(db_session, account, {"name": "Main Till"}, actor)
    assert updated.name == "Main Till"
    assert updated.opening_balance == Decimal("100.00")


def test_non_finite_and_overprecision_amounts_are_rejected(
    db_session: Session, account_and_actor: tuple[MoneyAccount, User]
) -> None:
    account, actor = account_and_actor
    for amount in (Decimal("NaN"), Decimal("1.001")):
        with pytest.raises(HTTPException) as error:
            post_money_transaction(
                db_session,
                account_id=account.id,
                amount_signed=amount,
                txn_type=MoneyTransactionType.INCOME,
                actor=actor,
            )
        assert error.value.status_code == 422


def test_requires_timezone_aware_transaction_dates(
    db_session: Session, account_and_actor: tuple[MoneyAccount, User]
) -> None:
    account, actor = account_and_actor
    with pytest.raises(HTTPException) as error:
        post_money_transaction(
            db_session,
            account_id=account.id,
            amount_signed=Decimal("1.00"),
            txn_type=MoneyTransactionType.INCOME,
            actor=actor,
            txn_date=datetime(2026, 10, 15),
        )
    assert error.value.status_code == 422
