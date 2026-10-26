"""Environment-backed settings.

Importing this module never raises: settings are instantiated on demand.
"""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

UNUSABLE_WEBHOOK_SECRETS = frozenset({"change-me"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    github_webhook_secret: SecretStr | None = None


def is_usable_webhook_secret(secret: str | None) -> bool:
    """A secret is usable only if it is non-blank and not the placeholder."""
    if secret is None:
        return False
    if not secret.strip():
        return False
    return secret not in UNUSABLE_WEBHOOK_SECRETS
