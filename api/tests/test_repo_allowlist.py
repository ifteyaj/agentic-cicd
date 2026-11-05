import pytest


def _payload() -> dict[str, object]:
    return {
        "action": "completed",
        "workflow_run": {
            "id": 123456789,
            "run_attempt": 1,
            "head_sha": "0123456789abcdef0123456789abcdef01234567",
            "conclusion": "failure",
        },
        "repository": {"clone_url": "https://github.com/example/repo.git"},
    }


@pytest.mark.xfail(strict=True, reason="M1c: repo allowlist not implemented")
def test_repo_not_on_allowlist_is_rejected_with_403() -> None:
    import hashlib
    import hmac
    import json

    from fastapi.testclient import TestClient

    from app.main import create_app

    secret = "test-secret-value"  # noqa: S105 - test fixture, not a real credential
    raw = json.dumps(_payload()).encode()
    signature = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    client = TestClient(create_app(webhook_secret=secret, allowed_repos=["example/other"]))
    response = client.post(
        "/api/webhooks/github",
        content=raw,
        headers={
            "X-GitHub-Delivery": "allowlist-denied-delivery",
            "X-GitHub-Event": "workflow_run",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 403
    assert client.app.state.run_service.store.count() == 0


@pytest.mark.xfail(strict=True, reason="M1c: repo allowlist not implemented")
def test_repo_on_allowlist_is_accepted() -> None:
    import hashlib
    import hmac
    import json

    from fastapi.testclient import TestClient

    from app.main import create_app

    secret = "test-secret-value"  # noqa: S105 - test fixture, not a real credential
    raw = json.dumps(_payload()).encode()
    signature = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    client = TestClient(create_app(webhook_secret=secret, allowed_repos=["example/repo"]))
    response = client.post(
        "/api/webhooks/github",
        content=raw,
        headers={
            "X-GitHub-Delivery": "allowlist-accepted-delivery",
            "X-GitHub-Event": "workflow_run",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 202


@pytest.mark.xfail(strict=True, reason="M1c: repo allowlist not implemented")
def test_empty_allowlist_rejects_every_repo() -> None:
    import hashlib
    import hmac
    import json

    from fastapi.testclient import TestClient

    from app.main import create_app

    secret = "test-secret-value"  # noqa: S105 - test fixture, not a real credential
    raw = json.dumps(_payload()).encode()
    signature = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    client = TestClient(create_app(webhook_secret=secret, allowed_repos=[]))
    response = client.post(
        "/api/webhooks/github",
        content=raw,
        headers={
            "X-GitHub-Delivery": "allowlist-empty-delivery",
            "X-GitHub-Event": "workflow_run",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 403
