from email.message import EmailMessage
from types import SimpleNamespace
from typing import Any

from app.core import mail


def test_password_reset_email_uses_configured_tls_and_link(monkeypatch: Any) -> None:
    settings = SimpleNamespace(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username="mailer",
        smtp_password="secret",
        smtp_from_email="noreply@example.com",
        smtp_use_tls=True,
        smtp_use_ssl=False,
        smtp_timeout_seconds=10,
        frontend_origin="https://erp.example.com/",
        password_reset_expire_minutes=30,
    )
    monkeypatch.setattr(mail, "get_settings", lambda: settings)
    sent_messages: list[EmailMessage] = []
    calls: list[str] = []

    class FakeSMTP:
        def __init__(self, host: str, port: int, timeout: int) -> None:
            assert (host, port, timeout) == ("smtp.example.com", 587, 10)

        def __enter__(self) -> "FakeSMTP":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def starttls(self, **_: object) -> None:
            calls.append("starttls")

        def login(self, username: str, password: str) -> None:
            assert (username, password) == ("mailer", "secret")
            calls.append("login")

        def send_message(self, message: EmailMessage) -> None:
            sent_messages.append(message)

    monkeypatch.setattr(mail.smtplib, "SMTP", FakeSMTP)
    mail.send_password_reset_email("user@example.com", "one-time-token")

    assert calls == ["starttls", "login"]
    assert sent_messages[0]["To"] == "user@example.com"
    assert (
        "https://erp.example.com/reset-password?token=one-time-token"
        in sent_messages[0].get_content()
    )
