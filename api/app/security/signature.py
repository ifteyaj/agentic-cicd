"""GitHub webhook signature verification.

The verifier is total: any malformed input returns ``False`` and it never
raises. Only HMAC-SHA256 with a lowercase hex digest is accepted.
"""

import hashlib
import hmac
import re

_SIGNATURE_RE = re.compile(r"sha256=([0-9a-f]{64})")


def verify_github_signature(body: bytes, header: str | None, secret: str) -> bool:
    """Return whether ``header`` is a valid SHA-256 HMAC of ``body``."""
    try:
        if not isinstance(header, str) or not isinstance(secret, str) or not secret:
            return False
        match = _SIGNATURE_RE.fullmatch(header)
        if match is None:
            return False
        expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(match.group(1), expected)
    except (TypeError, ValueError, UnicodeError):
        return False
