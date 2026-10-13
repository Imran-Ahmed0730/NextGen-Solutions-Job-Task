"""Seed common company settings from environment/configuration defaults."""

import argparse
import os

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.modules.company_settings import repository
from app.modules.company_settings.models import CompanySetting


def _default_settings() -> dict[str, str]:
    settings = get_settings()
    return {
        "company_name": os.getenv("COMPANY_NAME", "Sabuj Pran").strip() or "Sabuj Pran",
        "company_address": os.getenv("COMPANY_ADDRESS", "").strip(),
        "company_phone": os.getenv("COMPANY_PHONE", "").strip(),
        "company_email": (
            os.getenv("COMPANY_EMAIL") or settings.smtp_from_email or ""
        ).strip(),
        "currency_code": os.getenv("CURRENCY_CODE", "BDT").strip() or "BDT",
        "timezone": os.getenv("TIMEZONE", "Asia/Dhaka").strip() or "Asia/Dhaka",
        "invoice_footer": os.getenv("INVOICE_FOOTER", "").strip(),
        "credit_limit_mode": os.getenv("CREDIT_LIMIT_MODE", "WARN").strip() or "WARN",
        "receipt_tolerance_pct": os.getenv("RECEIPT_TOLERANCE_PCT", "0").strip() or "0",
    }


def seed_company_settings(*, overwrite: bool = False) -> int:
    inserted = 0
    with SessionLocal() as session:
        for key, value in _default_settings().items():
            existing = repository.get_setting(session, key)
            if existing is None:
                session.add(CompanySetting(key=key, value=value))
                inserted += 1
            elif overwrite:
                existing.value = value
        session.commit()
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed common company settings.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite values for settings that already exist.",
    )
    args = parser.parse_args()

    inserted = seed_company_settings(overwrite=args.overwrite)
    print(f"Company settings seeded. Inserted {inserted} missing setting(s).")


if __name__ == "__main__":
    main()