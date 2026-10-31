def test_approve_on_a_terminal_run_returns_409() -> None:
    import hashlib
    import hmac
    import json
    from dataclasses import replace

    from fastapi.testclient import TestClient

    from app.domain.status import RunStatus, transition
    from app.main import create_app
    from app.services.runs import RunService

    secret = "test-secret-value"  # noqa: S105 - test fixture, not a real credential
    valid_sha = "0123456789abcdef0123456789abcdef01234567"
    payload = {
        "action": "completed",
        "workflow_run": {
            "id": 13579246,
            "run_attempt": 1,
            "head_sha": valid_sha,
            "conclusion": "failure",
        },
        "repository": {"clone_url": "https://github.com/example/repo.git"},
    }
    raw = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()

    client = TestClient(create_app(webhook_secret=secret))
    response = client.post(
        "/webhooks/github",
        content=raw,
        headers={
            "X-GitHub-Delivery": "approve-terminal-delivery",
            "X-Hub-Signature-256": signature,
            "X-GitHub-Event": "workflow_run",
        },
    )
    assert response.status_code == 202
    run_id = response.json()["run_id"]

    service: RunService = client.app.state.run_service
    run = service.store.get(run_id)
    assert run is not None

    terminal = replace(run, status=transition(run.status, RunStatus.FAILED))
    service.store.update(terminal)

    approve_response = client.post(
        f"/api/runs/{run_id}/approve",
        json={"attempt_id": "no-attempt", "patch_sha256": "0" * 64},
    )
    assert approve_response.status_code == 409

    stored = service.store.get(run_id)
    assert stored is not None
    assert stored.status is RunStatus.FAILED
