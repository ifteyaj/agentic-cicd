import pytest


@pytest.mark.xfail(strict=True, reason="M1b: approval endpoint not implemented")
def test_approve_with_wrong_patch_hash_returns_409_and_stays_paused() -> None:
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
            "id": 24681012,
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
            "X-GitHub-Delivery": "approve-wrong-hash-delivery",
            "X-Hub-Signature-256": signature,
            "X-GitHub-Event": "workflow_run",
        },
    )
    assert response.status_code == 202
    run_id = response.json()["run_id"]

    service: RunService = client.app.state.run_service
    for _ in range(10):
        run = service.store.get(run_id)
        assert run is not None
        if run.status is RunStatus.AWAITING_APPROVAL:
            break
        service.advance(run_id)
    else:
        raise AssertionError("run never reached awaiting_approval")

    run_detail = client.get(f"/api/runs/{run_id}")
    assert run_detail.status_code == 200
    attempt = run_detail.json()["attempts"][-1]
    attempt_id = attempt["attempt_id"]
    correct_hash = attempt["patch_sha256"]

    approve_response = client.post(
        f"/api/runs/{run_id}/approve",
        json={"attempt_id": attempt_id, "patch_sha256": "0" * 64},
    )
    assert approve_response.status_code == 409

    run = service.store.get(run_id)
    assert run is not None
    assert run.status is RunStatus.AWAITING_APPROVAL
    assert correct_hash != "0" * 64
