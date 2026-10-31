def test_stub_forced_to_fail_three_times_ends_in_escalated_with_three_attempts() -> None:
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
            "id": 86420975,
            "run_attempt": 1,
            "head_sha": valid_sha,
            "conclusion": "failure",
        },
        "repository": {"clone_url": "https://github.com/example/repo.git"},
    }
    raw = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()

    client = TestClient(create_app(webhook_secret=secret, stub_mode="fail"))
    response = client.post(
        "/webhooks/github",
        content=raw,
        headers={
            "X-GitHub-Delivery": "escalation-delivery",
            "X-Hub-Signature-256": signature,
            "X-GitHub-Event": "workflow_run",
        },
    )
    assert response.status_code == 202
    run_id = response.json()["run_id"]

    service: RunService = client.app.state.run_service
    for _ in range(20):
        run = service.store.get(run_id)
        assert run is not None
        if run.status is RunStatus.ESCALATED:
            break
        service.advance(run_id)
    else:
        raise AssertionError("run never reached escalated")

    run = service.store.get(run_id)
    assert run is not None
    assert run.status is RunStatus.ESCALATED

    attempts = service.store.list_attempts(run_id)
    assert len(attempts) == 3
    assert [attempt.n for attempt in attempts] == [1, 2, 3]
