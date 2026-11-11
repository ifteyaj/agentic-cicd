"""M1c-3 phase 1 (red): the rejection decision must appear in the trace.

``POST /api/runs/{run_id}/reject`` currently moves the run to REJECTED with
``store.update``, which writes nothing to the events table, so SSE replay never
shows the decision. ``test_rejection_writes_status_changed_event`` is strict
xfail and must be dropped in the change that records the event.

``test_rejection_conflict_writes_no_event`` is not xfail: the invariant it
asserts (a 409 conflict writes no event) already holds and must keep holding
after the fix, so it is a normal regression test.
"""

import pytest


@pytest.mark.xfail(strict=True, reason="reject event not implemented")
def test_rejection_writes_status_changed_event() -> None:
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
            "id": 66778899,
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
            "X-GitHub-Delivery": "reject-event-delivery",
            "X-Hub-Signature-256": signature,
            "X-GitHub-Event": "workflow_run",
        },
    )
    assert created.status_code == 202, created.text
    run_id = created.json()["run_id"]

    service: RunService = client.app.state.run_service
    for _ in range(10):  # safety bound, not the expected step count
        run = service.store.get(run_id)
        assert run is not None
        if run.status is RunStatus.AWAITING_APPROVAL:
            break
        service.advance(run_id)
    else:
        raise AssertionError("run never reached awaiting_approval")

    events_url = f"/api/runs/{run_id}/events"

    def parse_events(text: str) -> list[dict[str, object]]:
        events: list[dict[str, object]] = []
        event: dict[str, object] = {}
        for line in text.splitlines():
            if line == "":
                if event:
                    events.append(event)
                    event = {}
            elif line.startswith("id:"):
                event["id"] = int(line[4:].strip())
            elif line.startswith("data:"):
                event["data"] = line[5:].strip()
        if event:
            events.append(event)
        return events

    before_response = client.get(events_url)
    assert before_response.status_code == 200
    before_events = parse_events(before_response.text)
    assert len(before_events) >= 3

    rejected = client.post(f"/api/runs/{run_id}/reject")
    assert rejected.status_code == 200, rejected.text

    # Same route and parser; replay only what was written after the last event
    # seen before the rejection.
    last_before_id = int(before_events[-1]["id"])
    after_response = client.get(events_url, headers={"Last-Event-ID": str(last_before_id)})
    assert after_response.status_code == 200
    new_events = parse_events(after_response.text)

    assert len(new_events) == 1, after_response.text
    # parse_events records id and data only, so the frame's event line is
    # checked directly; this response carries exactly one frame.
    event_lines = [line for line in after_response.text.splitlines() if line.startswith("event:")]
    assert event_lines == ["event: run.status_changed"]
    assert json.loads(str(new_events[0]["data"])) == {
        "from": "awaiting_approval",
        "to": "rejected",
    }


def test_rejection_conflict_writes_no_event() -> None:
    import hashlib
    import hmac
    import json

    from fastapi.testclient import TestClient

    from app.main import create_app

    secret = "test-secret-value"  # noqa: S105 - test fixture, not a real credential
    valid_sha = "0123456789abcdef0123456789abcdef01234567"
    payload = {
        "action": "completed",
        "workflow_run": {
            "id": 66778898,
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
            "X-GitHub-Delivery": "reject-conflict-delivery",
            "X-Hub-Signature-256": signature,
            "X-GitHub-Event": "workflow_run",
        },
    )
    assert created.status_code == 202, created.text
    run_id = created.json()["run_id"]  # left queued: nothing advanced

    events_url = f"/api/runs/{run_id}/events"

    def parse_events(text: str) -> list[dict[str, object]]:
        events: list[dict[str, object]] = []
        event: dict[str, object] = {}
        for line in text.splitlines():
            if line == "":
                if event:
                    events.append(event)
                    event = {}
            elif line.startswith("id:"):
                event["id"] = int(line[4:].strip())
            elif line.startswith("data:"):
                event["data"] = line[5:].strip()
        if event:
            events.append(event)
        return events

    before_response = client.get(events_url)
    assert before_response.status_code == 200
    before_events = parse_events(before_response.text)

    rejected = client.post(f"/api/runs/{run_id}/reject")
    assert rejected.status_code == 409, rejected.text
    assert rejected.json() == {"detail": "run is not awaiting approval"}

    after_response = client.get(events_url)
    assert after_response.status_code == 200
    assert len(parse_events(after_response.text)) == len(before_events)
