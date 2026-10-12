import logging
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urlencode

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class MailDeliveryError(Exception):
    pass


def validate_email_configuration() -> None:
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_from_email:
        raise MailDeliveryError("Email delivery is not configured")
    if bool(settings.smtp_username) != bool(settings.smtp_password):
        raise MailDeliveryError("SMTP username and password must be configured together")
    if settings.smtp_use_tls and settings.smtp_use_ssl:
        raise MailDeliveryError("Configure either SMTP STARTTLS or implicit SSL, not both")


def send_password_reset_email(email: str, token: str) -> None:
    settings = get_settings()
    validate_email_configuration()
    smtp_host = settings.smtp_host
    from_email = settings.smtp_from_email
    if smtp_host is None or from_email is None:
        raise MailDeliveryError("Email delivery is not configured")
    reset_url = (
        f"{settings.frontend_origin.rstrip('/')}/reset-password?"
        f"{urlencode({'token': token})}"
    )
    message = EmailMessage()
    message["Subject"] = "Reset your Sabuj Pran password"
    message["From"] = from_email
    message["To"] = email
    message.set_content(
        "A password reset was requested for your Sabuj Pran account.\n\n"
        f"Use this one-time link within {settings.password_reset_expire_minutes} minutes:\n"
        f"{reset_url}\n\n"
        "If you did not request this reset, you can ignore this email."
    )

    try:
        if settings.smtp_use_ssl:
            with smtplib.SMTP_SSL(
                smtp_host,
                settings.smtp_port,
                timeout=settings.smtp_timeout_seconds,
                context=ssl.create_default_context(),
            ) as server:
                _authenticate_and_send(
                    server, settings.smtp_username, settings.smtp_password, message
                )
        else:
            with smtplib.SMTP(
                smtp_host,
                settings.smtp_port,
                timeout=settings.smtp_timeout_seconds,
            ) as server:
                if settings.smtp_use_tls:
                    server.starttls(context=ssl.create_default_context())
                _authenticate_and_send(
                    server, settings.smtp_username, settings.smtp_password, message
                )
    except (OSError, smtplib.SMTPException):
        logger.exception("Password reset email delivery failed")
        raise MailDeliveryError("Password reset email could not be delivered") from None


def _authenticate_and_send(
    server: smtplib.SMTP,
    username: str | None,
    password: str | None,
    message: EmailMessage,
) -> None:
    if username and password:
        server.login(username, password)
    server.send_message(message)
