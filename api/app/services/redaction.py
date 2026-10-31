"""Pure redaction helpers for event and log payloads."""

import re

_GITHUB_CLASSIC_TOKEN = re.compile(r"ghp_[A-Za-z0-9]{36,}")
_GITHUB_FINE_GRAINED_TOKEN = re.compile(r"github_pat_[A-Za-z0-9_]{22,}")
_API_KEY = re.compile(r"\bsk-[A-Za-z0-9]{20,}")
_BEARER_HEADER = re.compile(r"Bearer \S+")
_SECRET_ASSIGNMENT = re.compile(r"(?i)\b((?:[A-Za-z0-9_]+_)?(?:TOKEN|SECRET|KEY|PASSWORD))=(\S+)")


def redact(text: str) -> str:
    """Return ``text`` with well-known secret shapes replaced."""
    redacted = _GITHUB_CLASSIC_TOKEN.sub("[REDACTED]", text)
    redacted = _GITHUB_FINE_GRAINED_TOKEN.sub("[REDACTED]", redacted)
    redacted = _API_KEY.sub("[REDACTED]", redacted)
    redacted = _BEARER_HEADER.sub("[REDACTED]", redacted)
    redacted = _SECRET_ASSIGNMENT.sub(r"\1=[REDACTED]", redacted)
    return redacted
