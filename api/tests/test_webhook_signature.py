import hashlib
import hmac

import pytest


def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.mark.xfail(strict=True, reason="M1: signature verification not implemented")
def test_valid_signature_is_accepted() -> None:
    from app.security.signature import verify_github_signature

    body = b'{"action":"completed"}'
    assert verify_github_signature(body, _sign(body, "s3cret"), "s3cret") is True


@pytest.mark.xfail(strict=True, reason="M1: signature verification not implemented")
def test_tampered_body_is_rejected() -> None:
    from app.security.signature import verify_github_signature

    body = b'{"action":"completed"}'
    assert verify_github_signature(body + b" ", _sign(body, "s3cret"), "s3cret") is False


@pytest.mark.xfail(strict=True, reason="M1: signature verification not implemented")
def test_missing_header_is_rejected() -> None:
    from app.security.signature import verify_github_signature

    assert verify_github_signature(b"{}", None, "s3cret") is False


@pytest.mark.xfail(strict=True, reason="M1: signature verification not implemented")
def test_wrong_algorithm_prefix_is_rejected() -> None:
    from app.security.signature import verify_github_signature

    body = b"{}"
    digest = hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()
    assert verify_github_signature(body, "sha1=" + digest, "s3cret") is False
