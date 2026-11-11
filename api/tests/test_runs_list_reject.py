"""M1c-2 phase 1 (red): contract tests for listing and rejecting runs.

Two endpoints are specified but not implemented yet: ``GET /api/runs`` lists
runs newest first with a response count, and ``POST /api/runs/{run_id}/reject``
rejects a run that is waiting at the approval gate. Every test here is a strict
xfail and must fail on the missing route (404/405), never on an import or
fixture error. An unexpected pass means the route landed: drop the marker in
the same change that implements it.

The rejection note is deliberately out of scope until approval persistence
lands: the reject route must accept only an absent or empty body for now.
"""

import pytest


@pytest.mark.xfail(strict=True, reason="M1c-2: list and reject not implemented")
def test_list_returns_newest_first_with_count() -> None:
    """Newest first by created_at; ``count`` counts the runs in this response."""
    import hashlib
    import hmac
    import json
    from dataclasses import replace

    from fastapi.testclient import TestClient

    from app.main import create_app

    secret = "test-secret-value"  # noqa: S105 - test fixture, not a real credential
    valid_sha = "0123456789abcdef0123456789abcdef01234567"
    client = TestClient(create_app(webhook_secret=secret, allowed_repos=["example/repo"]))

    def create_run(workflow_run_id: int, delivery_id: str) -> str:
        payload = {
            "action": "completed",
            "workflow_run": {
                "id": workflow_run_id,
                "run_attempt": 1,
                "head_sha": valid_sha,
                "conclusion": "failure",
            },
            "repository": {"clone_url": "https://github.com/example/repo.git"},
        }
        raw = json.dumps(payload).encode()
        signature = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        response = client.post(
            "/api/webhooks/github",
            content=raw,
            headers={
                "X-GitHub-Delivery": delivery_id,
                "X-Hub-Signature-256": signature,
                "X-GitHub-Event": "workflow_run",
            },
        )
        assert response.status_code == 202, response.text
        return str(response.json()["run_id"])

    first = create_run(1001, "list-delivery-1")
    second = create_run(1002, "list-delivery-2")
    third = create_run(1003, "list-delivery-3")

    service = client.app.state.run_service
    # Pin created_at so the expected order is set by the field, not insertion.
    for run_id, created_at in (
        (first, "2026-01-01T00:00:02+00:00"),
        (second, "2026-01-01T00:00:03+00:00"),
        (third, "2026-01-01T00:00:01+00:00"),
    ):
        run = service.store.get(run_id)
        assert run is not None
        service.store.update(replace(run, created_at=created_at))

    response = client.get("/api/runs")
    assert response.status_code == 200, response.text
    assert response.json() == {
        "runs": [
            {"run_id": second, "status": "queued"},
            {"run_id": first, "status": "queued"},
            {"run_id": third, "status": "queued"},
        ],
        "count": 3,
    }

    # Unknown query parameters are ignored, not rejected.
    unknown = client.get("/api/runs?status=queued&unknown=1")
    assert unknown.status_code == 200, unknown.text
    assert unknown.json() == response.json()


@pytest.mark.xfail(strict=True, reason="M1c-2: list and reject not implemented")
def test_list_limit_default_is_50_and_max_is_200() -> None:
    import hashlib
    import hmac
    import json

    from fastapi.testclient import TestClient

    from app.main import create_app

    secret = "test-secret-value"  # noqa: S105 - test fixture, not a real credential
    valid_sha = "0123456789abcdef0123456789abcdef01234567"
    client = TestClient(create_app(webhook_secret=secret, allowed_repos=["example/repo"]))

    def create_run(workflow_run_id: int, delivery_id: str) -> str:
        payload = {
            "action": "completed",
            "workflow_run": {
                "id": workflow_run_id,
                "run_attempt": 1,
                "head_sha": valid_sha,
                "conclusion": "failure",
            },
            "repository": {"clone_url": "https://github.com/example/repo.git"},
        }
        raw = json.dumps(payload).encode()
        signature = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        response = client.post(
            "/api/webhooks/github",
            content=raw,
            headers={
                "X-GitHub-Delivery": delivery_id,
                "X-Hub-Signature-256": signature,
                "X-GitHub-Event": "workflow_run",
            },
        )
        assert response.status_code == 202, response.text
        return str(response.json()["run_id"])

    run_ids = [create_run(5000 + index, f"limit-delivery-{index}") for index in range(201)]

    default_response = client.get("/api/runs")
    assert default_response.status_code == 200, default_response.text
    default_body = default_response.json()
    assert len(default_body["runs"]) == 50
    assert default_body["count"] == 50
    assert default_body["runs"][0]["run_id"] == run_ids[-1]

    max_response = client.get("/api/runs?limit=200")
    assert max_response.status_code == 200, max_response.text
    max_body = max_response.json()
    assert len(max_body["runs"]) == 200
    assert max_body["count"] == 200
    assert max_body["runs"][0]["run_id"] == run_ids[-1]
    # The default list is exactly the newest page of the maximum list.
    assert max_body["runs"][:50] == default_body["runs"]


@pytest.mark.xfail(strict=True, reason="M1c-2: list and reject not implemented")
def test_list_rejects_limit_outside_range_with_422() -> None:
    """The range is 1..200 inclusive; outside it is 422 and the body is unread."""
    from fastapi.testclient import TestClient

    from app.main import create_app

    secret = "test-secret-value"  # noqa: S105 - test fixture, not a real credential
    client = TestClient(create_app(webhook_secret=secret, allowed_repos=["example/repo"]))

    for limit in ("0", "-1", "201", "1000", "abc", "1.5", ""):
        response = client.get(f"/api/runs?limit={limit}")
        assert response.status_code == 422, (limit, response.text)
        assert "detail" in response.json()

    # The request body is never parsed: an out-of-range limit still wins.
    junk_body = client.request("GET", "/api/runs?limit=0", content=b"{not json")
    assert junk_body.status_code == 422, junk_body.text


@pytest.mark.xfail(strict=True, reason="M1c-2: list and reject not implemented")
def test_reject_awaiting_run_returns_200_and_status_rejected() -> None:
    """A rejection writes no attempt, no approval record, and no branch."""
    import hashlib
    import hmac
    import json

    from fastapi.testclient import TestClient

    from app.domain.status import RunStatus
    from app.main import create_app

    secret = "test-secret-value"  # noqa: S105 - test fixture, not a real credential
    valid_sha = "0123456789abcdef0123456789abcdef01234567"
    payload = {
        "action": "completed",
        "workflow_run": {
            "id": 3001,
            "run_attempt": 1,
            "head_sha": valid_sha,
            "conclusion": "failure",
        },
        "repository": {"clone_url": "https://github.com/example/repo.git"},
    }
    raw = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()

    client = TestClient(create_app(webhook_secret=secret, allowed_repos=["example/repo"]))
    created = client.post(
        "/api/webhooks/github",
        content=raw,
        headers={
            "X-GitHub-Delivery": "reject-awaiting-delivery",
            "X-Hub-Signature-256": signature,
            "X-GitHub-Event": "workflow_run",
        },
    )
    assert created.status_code == 202, created.text
    run_id = str(created.json()["run_id"])

    service = client.app.state.run_service
    for _ in range(10):  # safety bound, not the expected step count
        run = service.store.get(run_id)
        assert run is not None
        if run.status is RunStatus.AWAITING_APPROVAL:
            break
        service.advance(run_id)
    else:
        raise AssertionError("run never reached awaiting_approval")

    attempts_before = [attempt.attempt_id for attempt in service.store.list_attempts(run_id)]
    runs_before = service.store.count()

    rejected = client.post(f"/api/runs/{run_id}/reject")
    assert rejected.status_code == 200, rejected.text
    assert rejected.json() == {"run_id": run_id, "status": "rejected"}

    stored = service.store.get(run_id)
    assert stored is not None
    assert stored.status is RunStatus.REJECTED

    after_attempts = [attempt.attempt_id for attempt in service.store.list_attempts(run_id)]
    assert after_attempts == attempts_before
    assert service.store.count() == runs_before


@pytest.mark.xfail(strict=True, reason="M1c-2: list and reject not implemented")
def test_reject_unknown_run_returns_404() -> None:
    from fastapi.testclient import TestClient

    from app.main import create_app

    secret = "test-secret-value"  # noqa: S105 - test fixture, not a real credential
    client = TestClient(create_app(webhook_secret=secret, allowed_repos=["example/repo"]))

    run_id = "00000000-0000-4000-8000-000000000000"
    response = client.post(f"/api/runs/{run_id}/reject")
    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "run not found"}
    assert client.app.state.run_service.store.count() == 0


@pytest.mark.xfail(strict=True, reason="M1c-2: list and reject not implemented")
def test_reject_run_not_awaiting_returns_409_and_is_unchanged() -> None:
    import hashlib
    import hmac
    import json
    from dataclasses import replace

    from fastapi.testclient import TestClient

    from app.domain.status import RunStatus, transition
    from app.main import create_app

    secret = "test-secret-value"  # noqa: S105 - test fixture, not a real credential
    valid_sha = "0123456789abcdef0123456789abcdef01234567"
    client = TestClient(create_app(webhook_secret=secret, allowed_repos=["example/repo"]))

    def create_run(workflow_run_id: int, delivery_id: str) -> str:
        payload = {
            "action": "completed",
            "workflow_run": {
                "id": workflow_run_id,
                "run_attempt": 1,
                "head_sha": valid_sha,
                "conclusion": "failure",
            },
            "repository": {"clone_url": "https://github.com/example/repo.git"},
        }
        raw = json.dumps(payload).encode()
        signature = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        response = client.post(
            "/api/webhooks/github",
            content=raw,
            headers={
                "X-GitHub-Delivery": delivery_id,
                "X-Hub-Signature-256": signature,
                "X-GitHub-Event": "workflow_run",
            },
        )
        assert response.status_code == 202, response.text
        return str(response.json()["run_id"])

    queued_run_id = create_run(4001, "reject-queued-delivery")
    failed_run_id = create_run(4002, "reject-failed-delivery")

    service = client.app.state.run_service
    failed = service.store.get(failed_run_id)
    assert failed is not None
    service.store.update(replace(failed, status=transition(failed.status, RunStatus.FAILED)))

    cases = (
        (queued_run_id, RunStatus.QUEUED),
        (failed_run_id, RunStatus.FAILED),
    )
    for run_id, expected_status in cases:
        attempts_before = [attempt.attempt_id for attempt in service.store.list_attempts(run_id)]
        response = client.post(f"/api/runs/{run_id}/reject")
        assert response.status_code == 409, response.text
        assert response.json() == {"detail": "run is not awaiting approval"}

        stored = service.store.get(run_id)
        assert stored is not None
        assert stored.status is expected_status
        after_attempts = [attempt.attempt_id for attempt in service.store.list_attempts(run_id)]
        assert after_attempts == attempts_before


@pytest.mark.xfail(strict=True, reason="M1c-2: list and reject not implemented")
def test_reject_with_body_returns_422() -> None:
    """The rejection note is deferred to the approval-persistence step.

    Until then only an absent or empty body is accepted: any JSON object,
    including ``{}``, must be a 422 and must leave the run untouched.
    """
    import hashlib
    import hmac
    import json

    from fastapi.testclient import TestClient

    from app.domain.status import RunStatus
    from app.main import create_app

    secret = "test-secret-value"  # noqa: S105 - test fixture, not a real credential
    valid_sha = "0123456789abcdef0123456789abcdef01234567"
    payload = {
        "action": "completed",
        "workflow_run": {
            "id": 5001,
            "run_attempt": 1,
            "head_sha": valid_sha,
            "conclusion": "failure",
        },
        "repository": {"clone_url": "https://github.com/example/repo.git"},
    }
    raw = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()

    client = TestClient(create_app(webhook_secret=secret, allowed_repos=["example/repo"]))
    created = client.post(
        "/api/webhooks/github",
        content=raw,
        headers={
            "X-GitHub-Delivery": "reject-body-delivery",
            "X-Hub-Signature-256": signature,
            "X-GitHub-Event": "workflow_run",
        },
    )
    assert created.status_code == 202, created.text
    run_id = str(created.json()["run_id"])

    service = client.app.state.run_service
    for _ in range(10):  # safety bound, not the expected step count
        run = service.store.get(run_id)
        assert run is not None
        if run.status is RunStatus.AWAITING_APPROVAL:
            break
        service.advance(run_id)
    else:
        raise AssertionError("run never reached awaiting_approval")

    attempts_before = [attempt.attempt_id for attempt in service.store.list_attempts(run_id)]

    for body in ({"note": "this belongs to the approval record"}, {}):
        response = client.post(f"/api/runs/{run_id}/reject", json=body)
        assert response.status_code == 422, response.text

    stored = service.store.get(run_id)
    assert stored is not None
    assert stored.status is RunStatus.AWAITING_APPROVAL
    after_attempts = [attempt.attempt_id for attempt in service.store.list_attempts(run_id)]
    assert after_attempts == attempts_before
