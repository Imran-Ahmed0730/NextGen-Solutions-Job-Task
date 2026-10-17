import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_accepts_a_sufficiently_long_secret_key() -> None:
    secret = "a" * 32

    settings = Settings(secret_key=secret, _env_file=None)

    assert settings.secret_key == secret


@pytest.mark.parametrize(
    "secret",
    [
        "change-me",
        "change-me-in-production",
        "short-secret",
        " " * 40,
    ],
)
def test_settings_rejects_placeholder_or_short_secret_keys(secret: str) -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(secret_key=secret, _env_file=None)


def test_settings_requires_secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(ValidationError, match="secret_key"):
        Settings(_env_file=None)
