import hashlib
import hmac
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.runs import InMemoryRunStore, RunService

SECRET = "test-secret-value"  # noqa: S105 - test fixture, not a real credential
VALID_SHA = "0123456789abcdef0123456789abcdef01234567"
_COMPUTE_SIGNATURE = object()


def _sign(body: bytes, secret: str = SECRET) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return "sha256=" + digest


def _payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "action": "completed",
        "workflow_run": {
            "id": 123456789,
            "run_attempt": 1,
            "head_sha": VALID_SHA,
            "conclusion": "failure",
        },
        "repository": {"clone_url": "https://github.com/example/repo.git"},
    }
    for key, value in overrides.items():
        if key in {"workflow_run", "repository"} and isinstance(value, dict):
            payload[key] = {**payload[key], **value}
        else:
            payload[key] = value
    return payload


def _client(
    *, secret: str | None = SECRET, store: InMemoryRunStore | None = None
) -> tuple[TestClient, InMemoryRunStore]:
    store = store if store is not None else InMemoryRunStore()
    service = RunService(store)
    return TestClient(create_app(run_service=service, webhook_secret=secret)), store


def _post(
    client: TestClient,
    payload: dict[str, Any] | None = None,
    *,
    body: bytes | None = None,
    delivery: str = "delivery-1",
    event: str | None = "workflow_run",
    secret: str = SECRET,
    signature: str | None | object = _COMPUTE_SIGNATURE,
) -> Any:
    raw = (
        body
        if body is not None
        else json.dumps(payload if payload is not None else _payload()).encode()
    )
    headers = {"X-GitHub-Delivery": delivery}
    if signature is _COMPUTE_SIGNATURE:
        headers["X-Hub-Signature-256"] = _sign(raw, secret)
    elif isinstance(signature, str):
        headers["X-Hub-Signature-256"] = signature
    if event is not None:
        headers["X-GitHub-Event"] = event
    return client.post("/webhooks/github", content=raw, headers=headers)


def test_valid_delivery_creates_run() -> None:
    client, store = _client()
    response = _post(client, _payload())
    assert response.status_code == 202
    body = response.json()
    assert body["duplicate"] is False
    assert store.count() == 1

    run = store.get(body["run_id"])
    assert run is not None
    assert run.repo_url == "https://github.com/example/repo"
    assert run.commit_sha == VALID_SHA
    assert run.delivery_id == "delivery-1"
    assert run.workflow_run_id == 123456789
    assert run.run_attempt == 1


def test_repeated_delivery_returns_original_run() -> None:
    client, store = _client()
    first = _post(client, _payload())
    second = _post(client, _payload())

    assert first.status_code == 202
    assert second.status_code == 200
    assert second.json() == {"run_id": first.json()["run_id"], "duplicate": True}
    assert store.count() == 1


def test_same_run_key_with_new_delivery_returns_original_run() -> None:
    client, store = _client()
    first = _post(client, _payload(), delivery="delivery-1")
    second = _post(client, _payload(), delivery="delivery-2")

    assert first.status_code == 202
    assert second.status_code == 200
    assert second.json()["run_id"] == first.json()["run_id"]
    assert store.count() == 1


def test_replay_with_new_run_attempt_creates_another_run() -> None:
    client, store = _client()
    first = _post(client, _payload(), delivery="delivery-1")
    second = _post(client, _payload(workflow_run={"run_attempt": 2}), delivery="delivery-2")

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["run_id"] != second.json()["run_id"]
    assert store.count() == 2


def test_duplicate_delivery_with_malformed_json_returns_original_run() -> None:
    client, store = _client()
    first = _post(client, _payload())
    second = _post(client, body=b"{not json", delivery="delivery-1")

    assert first.status_code == 202
    assert second.status_code == 200
    assert second.json()["run_id"] == first.json()["run_id"]
    assert store.count() == 1


def test_duplicate_delivery_with_ignored_body_returns_original_run() -> None:
    client, store = _client()
    first = _post(client, _payload())
    second = _post(client, _payload(workflow_run={"conclusion": "success"}), delivery="delivery-1")

    assert first.status_code == 202
    assert second.status_code == 200
    assert second.json()["run_id"] == first.json()["run_id"]
    assert store.count() == 1


def test_duplicate_delivery_without_event_header_returns_original_run() -> None:
    client, store = _client()
    first = _post(client, _payload())
    second = _post(client, _payload(), event=None)

    assert first.status_code == 202
    assert second.status_code == 200
    assert second.json()["run_id"] == first.json()["run_id"]
    assert store.count() == 1


def test_non_canonical_raw_body_is_verified_as_sent() -> None:
    client, store = _client()
    body = (
        b'{ "repository" : {"clone_url":"https://github.com/example/repo.git"},'
        b' "action":"completed", "workflow_run": {"run_attempt":1,"id":42,'
        b'"head_sha":"' + VALID_SHA.encode() + b'","conclusion":"timed_out"} }'
    )
    response = _post(client, body=body)
    assert response.status_code == 202
    assert store.count() == 1


@pytest.mark.parametrize(
    "signature",
    [
        None,
        "sha256=" + "0" * 64,
        "sha1=" + "0" * 40,
        "sha256=" + "A" * 64,
        "sha256=" + "z" * 64,
        "sha256=",
        "",
    ],
)
def test_invalid_signatures_are_rejected(signature: str | None) -> None:
    client, store = _client()
    response = _post(client, _payload(), signature=signature)
    assert response.status_code == 401
    assert store.count() == 0


def test_tampered_body_is_rejected() -> None:
    client, store = _client()
    raw = json.dumps(_payload()).encode()
    signature = _sign(raw)
    tampered = raw + b" "
    response = _post(client, body=tampered, signature=signature)
    assert response.status_code == 401
    assert store.count() == 0


def test_invalid_signature_wins_over_malformed_json() -> None:
    client, store = _client()
    response = _post(client, body=b"{not json", signature="sha256=" + "0" * 64)
    assert response.status_code == 401
    assert store.count() == 0


@pytest.mark.parametrize("secret", ["", "   ", "change-me"])
def test_unusable_secret_returns_503(secret: str) -> None:
    client, store = _client(secret=secret)
    response = _post(client, _payload())
    assert response.status_code == 503
    assert response.json() == {"detail": "webhook secret is not configured"}
    assert store.count() == 0


def test_missing_secret_via_settings_returns_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_WEBHOOK_SECRET", raising=False)
    store = InMemoryRunStore()
    client = TestClient(create_app(run_service=RunService(store)))
    response = _post(client, _payload())
    assert response.status_code == 503
    assert store.count() == 0


@pytest.mark.parametrize(
    ("event", "payload"),
    [
        ("ping", {"zen": "Keep it logically awesome."}),
        ("push", {"ref": "refs/heads/main"}),
        ("issues", {"action": "opened"}),
    ],
)
def test_non_workflow_run_events_are_ignored(event: str, payload: dict[str, Any]) -> None:
    client, store = _client()
    response = _post(client, payload, event=event)
    assert response.status_code == 204
    assert response.content == b""
    assert store.count() == 0


@pytest.mark.parametrize(
    "conclusion",
    ["success", "cancelled", "skipped", "neutral", "stale", "action_required"],
)
def test_non_failure_conclusions_are_ignored(conclusion: str) -> None:
    client, store = _client()
    response = _post(client, _payload(workflow_run={"conclusion": conclusion}))
    assert response.status_code == 204
    assert store.count() == 0


@pytest.mark.parametrize("action", ["requested", "in_progress", "completed_extra"])
def test_non_completed_actions_are_ignored(action: str) -> None:
    client, store = _client()
    response = _post(client, _payload(action=action))
    assert response.status_code == 204
    assert store.count() == 0


def test_malformed_json_on_new_delivery_returns_400() -> None:
    client, store = _client()
    response = _post(client, body=b"{not json")
    assert response.status_code == 400
    assert store.count() == 0


def test_empty_body_returns_400() -> None:
    client, store = _client()
    response = _post(client, body=b"")
    assert response.status_code == 400
    assert store.count() == 0


@pytest.mark.parametrize(
    "payload",
    [
        [],
        "string",
        1,
        None,
    ],
)
def test_non_object_json_returns_422(payload: Any) -> None:
    client, store = _client()
    response = _post(client, body=json.dumps(payload).encode())
    assert response.status_code == 422
    assert store.count() == 0


def test_oversized_body_returns_413() -> None:
    client, store = _client()
    raw = b"x" * (1024 * 1024 + 1)
    response = _post(client, body=raw)
    assert response.status_code == 413
    assert store.count() == 0


@pytest.mark.parametrize(
    "delivery",
    ["", "has space", "under_score", "a" * 129, "slash/segment"],
)
def test_invalid_delivery_headers_return_422(delivery: str) -> None:
    client, store = _client()
    response = _post(client, _payload(), delivery=delivery)
    assert response.status_code == 422
    assert store.count() == 0


def test_missing_delivery_header_returns_422() -> None:
    client, store = _client()
    raw = json.dumps(_payload()).encode()
    response = client.post(
        "/webhooks/github",
        content=raw,
        headers={
            "X-Hub-Signature-256": _sign(raw),
            "X-GitHub-Event": "workflow_run",
        },
    )
    assert response.status_code == 422
    assert store.count() == 0


def test_missing_event_header_returns_422() -> None:
    client, store = _client()
    response = _post(client, _payload(), event=None)
    assert response.status_code == 422
    assert store.count() == 0


@pytest.mark.parametrize(
    "payload",
    [
        _payload(action=None),
        _payload(workflow_run={"conclusion": None}),
        _payload(workflow_run={"conclusion": 1}),
        _payload(workflow_run={"id": None}),
        _payload(workflow_run={"id": 0}),
        _payload(workflow_run={"id": -1}),
        _payload(workflow_run={"id": True}),
        _payload(workflow_run={"id": 1.0}),
        _payload(workflow_run={"id": "1"}),
        _payload(workflow_run={"run_attempt": None}),
        _payload(workflow_run={"run_attempt": 0}),
        _payload(workflow_run={"run_attempt": True}),
        _payload(workflow_run={"run_attempt": 1.0}),
        _payload(workflow_run={"run_attempt": "1"}),
        _payload(workflow_run={"head_sha": None}),
        _payload(workflow_run={"head_sha": "a" * 39}),
        _payload(workflow_run={"head_sha": "A" * 40}),
        _payload(workflow_run={"head_sha": "0" * 40}),
        _payload(repository={"clone_url": None}),
        _payload(repository={"clone_url": "http://github.com/example/repo"}),
        _payload(repository={"clone_url": "https://gitlab.com/example/repo"}),
        _payload(repository={"clone_url": "https://user:pass@github.com/o/r"}),
        _payload(repository={"clone_url": "https://github.com:443/o/r"}),
        _payload(repository={"clone_url": "https://github.com/o/r?x=1"}),
        _payload(repository={"clone_url": "https://github.com/o/r#x"}),
        _payload(repository={"clone_url": "https://github.com/o/r/"}),
        _payload(repository={"clone_url": "https://github.com/o"}),
        _payload(repository={"clone_url": "https://github.com/o/r/s"}),
    ],
)
def test_invalid_payload_fields_return_422(payload: Any) -> None:
    client, store = _client()
    response = _post(client, payload)
    assert response.status_code == 422, response.text
    assert store.count() == 0


@pytest.mark.parametrize("missing", ["action", "workflow_run", "repository"])
def test_missing_payload_sections_return_422(missing: str) -> None:
    client, store = _client()
    payload = _payload()
    del payload[missing]
    response = _post(client, payload)
    assert response.status_code == 422
    assert store.count() == 0


def test_concurrent_duplicates_create_one_run() -> None:
    store = InMemoryRunStore()
    application = create_app(run_service=RunService(store), webhook_secret=SECRET)
    payload = json.dumps(_payload()).encode()
    signature = _sign(payload)
    headers = {
        "X-Hub-Signature-256": signature,
        "X-GitHub-Delivery": "delivery-race",
        "X-GitHub-Event": "workflow_run",
    }

    def call() -> Any:
        return TestClient(application).post("/webhooks/github", content=payload, headers=headers)

    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(lambda _: call(), range(8)))

    statuses = sorted(response.status_code for response in responses)
    assert statuses == [200] * 7 + [202]
    run_ids = {response.json()["run_id"] for response in responses}
    assert len(run_ids) == 1
    assert store.count() == 1
