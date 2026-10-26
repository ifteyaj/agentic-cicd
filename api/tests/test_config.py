import pytest

from app.config import Settings, is_usable_webhook_secret


def test_settings_reads_secret_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "from-environment")
    settings = Settings()
    assert settings.github_webhook_secret is not None
    assert settings.github_webhook_secret.get_secret_value() == "from-environment"


def test_settings_secret_is_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_WEBHOOK_SECRET", raising=False)
    settings = Settings(_env_file=None)
    assert settings.github_webhook_secret is None


@pytest.mark.parametrize("secret", [None, "", " ", "\t\n", "change-me"])
def test_unusable_secrets_are_rejected(secret: str | None) -> None:
    assert is_usable_webhook_secret(secret) is False


@pytest.mark.parametrize("secret", ["a", "change-me-please", "x" * 16])
def test_usable_secrets_are_accepted(secret: str) -> None:
    assert is_usable_webhook_secret(secret) is True
