import hashlib
import hmac

import pytest

from app.security.signature import verify_github_signature


def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_valid_signature_is_accepted() -> None:
    body = b'{"action":"completed"}'
    assert verify_github_signature(body, _sign(body, "s3cret"), "s3cret") is True


def test_tampered_body_is_rejected() -> None:
    body = b'{"action":"completed"}'
    assert verify_github_signature(body + b" ", _sign(body, "s3cret"), "s3cret") is False


def test_missing_header_is_rejected() -> None:
    assert verify_github_signature(b"{}", None, "s3cret") is False


def test_wrong_algorithm_prefix_is_rejected() -> None:
    body = b"{}"
    digest = hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()
    assert verify_github_signature(body, "sha1=" + digest, "s3cret") is False


def test_valid_sha1_hmac_is_rejected() -> None:
    body = b"{}"
    digest = hmac.new(b"s3cret", body, hashlib.sha1).hexdigest()
    assert verify_github_signature(body, "sha1=" + digest, "s3cret") is False


def test_valid_sha512_hmac_is_rejected() -> None:
    body = b"{}"
    digest = hmac.new(b"s3cret", body, hashlib.sha512).hexdigest()
    assert verify_github_signature(body, "sha512=" + digest, "s3cret") is False


@pytest.mark.parametrize(
    "header",
    [
        "",
        "sha256=",
        "sha256=deadbeef",
        "sha256=" + "A" * 64,
        "sha256=" + "g" * 64,
        "sha256=" + "a" * 63,
        "sha256=" + "a" * 65,
        " SHA256=" + "a" * 64,
        "sha256 =" + "a" * 64,
        "sha256=" + "é" * 64,
        "md5=" + "a" * 32,
        "sha256= " + "a" * 64,
    ],
)
def test_malformed_signature_headers_are_rejected(header: str) -> None:
    assert verify_github_signature(b"{}", header, "s3cret") is False


def test_empty_secret_is_rejected() -> None:
    body = b"{}"
    assert verify_github_signature(body, _sign(body, ""), "") is False


def test_verifier_never_raises_on_unexpected_types() -> None:
    assert verify_github_signature(b"{}", 123, "s3cret") is False  # type: ignore[arg-type]
    assert verify_github_signature(b"{}", None, None) is False  # type: ignore[arg-type]
    assert verify_github_signature(b"{}", "sha256=" + "a" * 64, "s3cret") is False
