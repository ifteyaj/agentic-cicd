import pytest


@pytest.mark.xfail(strict=True, reason="M1b: SQLite persistence not implemented")
def test_paused_run_survives_restart_and_completes(tmp_path) -> None:
    import hashlib
    import hmac
    import json

    from fastapi.testclient import TestClient

    from app.domain.status import RunStatus
    from app.main import create_app
    from app.services.runs import RunService

    secret = "test-secret-value"  # noqa: S105 - test fixture, not a real credential
    valid_sha = "0123456789abcdef0123456789abcdef01234567"
    payload = {
        "action": "completed",
        "workflow_run": {
            "id": 7654321,
            "run_attempt": 1,
            "head_sha": valid_sha,
            "conclusion": "failure",
        },
        "repository": {"clone_url": "https://github.com/example/repo.git"},
    }
    raw = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()

    db_path = tmp_path / "cicd.db"

    app1 = create_app(webhook_secret=secret, db_path=db_path)
    client1 = TestClient(app1)
    response = client1.post(
        "/webhooks/github",
        content=raw,
        headers={
            "X-GitHub-Delivery": "restart-gate-delivery",
            "X-Hub-Signature-256": signature,
            "X-GitHub-Event": "workflow_run",
        },
    )
    assert response.status_code == 202
    run_id = response.json()["run_id"]

    service1: RunService = app1.state.run_service
    for _ in range(10):
        run = service1.store.get(run_id)
        assert run is not None
        if run.status is RunStatus.AWAITING_APPROVAL:
            break
        service1.advance(run_id)
    else:
        raise AssertionError("run never reached awaiting_approval")

    run = service1.store.get(run_id)
    assert run is not None
    assert run.status is RunStatus.AWAITING_APPROVAL

    del app1
    del client1
    del service1

    app2 = create_app(webhook_secret=secret, db_path=db_path)
    service2: RunService = app2.state.run_service

    run = service2.store.get(run_id)
    assert run is not None
    assert run.status is RunStatus.AWAITING_APPROVAL
