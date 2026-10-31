import pytest


@pytest.mark.xfail(strict=True, reason="M1b: pause at gate not implemented")
def test_run_reaches_awaiting_approval_and_stops() -> None:
    import hashlib
    import hmac
    import json

    from fastapi.testclient import TestClient

    from app.domain.status import RunStatus
    from app.main import app
    from app.services.runs import RunService

    secret = "test-secret-value"  # noqa: S105 - test fixture, not a real credential
    valid_sha = "0123456789abcdef0123456789abcdef01234567"
    payload = {
        "action": "completed",
        "workflow_run": {
            "id": 987654321,
            "run_attempt": 1,
            "head_sha": valid_sha,
            "conclusion": "failure",
        },
        "repository": {"clone_url": "https://github.com/example/repo.git"},
    }
    raw = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()

    client = TestClient(app)
    response = client.post(
        "/webhooks/github",
        content=raw,
        headers={
            "X-GitHub-Delivery": "pause-gate-delivery",
            "X-Hub-Signature-256": signature,
            "X-GitHub-Event": "workflow_run",
        },
    )
    assert response.status_code == 202
    run_id = response.json()["run_id"]

    service: RunService = app.state.run_service
    service.advance(run_id)

    run = service.store.get(run_id)
    assert run is not None
    assert run.status is RunStatus.AWAITING_APPROVAL

    service.advance(run_id)

    run = service.store.get(run_id)
    assert run is not None
    assert run.status is RunStatus.AWAITING_APPROVAL
