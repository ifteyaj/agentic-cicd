import pytest


@pytest.mark.xfail(strict=True, reason="M1b: SSE replay not implemented")
def test_reconnect_with_last_event_id_replays_only_missed_events(tmp_path) -> None:
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
            "id": 11223344,
            "run_attempt": 1,
            "head_sha": valid_sha,
            "conclusion": "failure",
        },
        "repository": {"clone_url": "https://github.com/example/repo.git"},
    }
    raw = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()

    db_path = tmp_path / "events.db"
    client = TestClient(create_app(webhook_secret=secret, db_path=str(db_path)))
    response = client.post(
        "/webhooks/github",
        content=raw,
        headers={
            "X-GitHub-Delivery": "sse-replay-delivery",
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

    first_response = client.get(events_url)
    assert first_response.status_code == 200
    events = parse_events(first_response.text)
    assert len(events) >= 3
    ids = [int(event["id"]) for event in events]
    assert ids == list(range(1, len(ids) + 1))
    assert all(ids[index] < ids[index + 1] for index in range(len(ids) - 1))

    reconnect_response = client.get(events_url, headers={"Last-Event-ID": str(ids[1])})
    assert reconnect_response.status_code == 200
    missed = parse_events(reconnect_response.text)
    missed_ids = [int(event["id"]) for event in missed]
    assert missed_ids == ids[2:]
    assert missed_ids[0] == ids[2]
    assert all(event_id > ids[1] for event_id in missed_ids)
