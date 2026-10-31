"""GitHub webhook intake.

The processing order is an invariant: check the secret and signature presence,
enforce the body cap, verify the raw bytes, validate the delivery ID, return a
known delivery before parsing, then parse and filter. No unauthenticated bytes
are ever parsed.
"""

import hashlib
import json
import logging
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from app.config import is_usable_webhook_secret
from app.domain.run import run_key
from app.security.signature import verify_github_signature
from app.services.runs import (
    InvalidRunInput,
    RunService,
    normalize_repo_url,
    validate_commit_sha,
    validate_delivery_id,
    validate_workflow_identity,
)

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_BODY_BYTES = 1024 * 1024
_ACCEPTED_CONCLUSIONS = frozenset({"failure", "timed_out"})

mock_router = APIRouter()


def _error(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail})


def _duplicate(run_id: str) -> JSONResponse:
    return JSONResponse(status_code=200, content={"run_id": run_id, "duplicate": True})


def _content_hash(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _extract(payload: dict[str, object]) -> tuple[str, str, str, str, object, object]:
    action = payload.get("action")
    workflow_run = payload.get("workflow_run")
    repository = payload.get("repository")
    if not isinstance(workflow_run, dict) or not isinstance(repository, dict):
        raise InvalidRunInput("invalid payload shape")

    conclusion = workflow_run.get("conclusion")
    clone_url = repository.get("clone_url")
    head_sha = workflow_run.get("head_sha")
    workflow_run_id = workflow_run.get("id")
    run_attempt = workflow_run.get("run_attempt")

    if not isinstance(action, str) or not isinstance(conclusion, str):
        raise InvalidRunInput("invalid action or conclusion")
    if not isinstance(clone_url, str) or not isinstance(head_sha, str):
        raise InvalidRunInput("invalid repository or commit")
    return action, conclusion, clone_url, head_sha, workflow_run_id, run_attempt


@router.post("/webhooks/github")
async def github_webhook(request: Request) -> Response:
    secret = request.app.state.webhook_secret
    if not is_usable_webhook_secret(secret):
        return _error(503, "webhook secret is not configured")

    signature = request.headers.get("X-Hub-Signature-256")
    if signature is None:
        return _error(401, "invalid signature")

    declared_length = request.headers.get("content-length")
    if declared_length is not None:
        try:
            if int(declared_length) > MAX_BODY_BYTES:
                return _error(413, "payload too large")
        except ValueError:
            # Malformed Content-Length: the streaming cap below still applies.
            pass

    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_BODY_BYTES:
            return _error(413, "payload too large")
    raw = bytes(body)

    if not verify_github_signature(raw, signature, secret):
        return _error(401, "invalid signature")

    delivery_id = request.headers.get("X-GitHub-Delivery")
    if delivery_id is None:
        return _error(422, "missing X-GitHub-Delivery header")
    try:
        validate_delivery_id(delivery_id)
    except InvalidRunInput:
        return _error(422, "invalid X-GitHub-Delivery header")

    service: RunService = request.app.state.run_service
    existing = service.get_by_delivery(delivery_id)
    if existing is not None:
        logger.info(
            "duplicate delivery delivery_id=%s run_id=%s content_sha256=%s",
            delivery_id,
            existing.run_id,
            _content_hash(raw),
        )
        return _duplicate(existing.run_id)

    event = request.headers.get("X-GitHub-Event")
    if event is None:
        return _error(422, "missing X-GitHub-Event header")

    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _error(400, "malformed JSON")

    if event != "workflow_run":
        return Response(status_code=204)
    if not isinstance(payload, dict):
        return _error(422, "payload must be a JSON object")

    try:
        action, conclusion, clone_url, head_sha, workflow_run_id, run_attempt = _extract(payload)
    except InvalidRunInput as exc:
        return _error(422, str(exc))

    if action != "completed" or conclusion not in _ACCEPTED_CONCLUSIONS:
        return Response(status_code=204)

    try:
        repo_url = normalize_repo_url(clone_url)
        commit_sha = validate_commit_sha(head_sha)
        workflow_run_id, run_attempt = validate_workflow_identity(workflow_run_id, run_attempt)
    except InvalidRunInput as exc:
        return _error(422, str(exc))

    existing = service.get_by_run_key(run_key(workflow_run_id, run_attempt))
    if existing is not None:
        logger.info(
            "duplicate run key delivery_id=%s run_id=%s content_sha256=%s",
            delivery_id,
            existing.run_id,
            _content_hash(raw),
        )
        return _duplicate(existing.run_id)

    try:
        result = service.create_from_delivery(
            delivery_id,
            repo_url=repo_url,
            commit_sha=commit_sha,
            workflow_run_id=workflow_run_id,
            run_attempt=run_attempt,
        )
    except InvalidRunInput as exc:
        return _error(422, str(exc))

    if not result.created:
        return _duplicate(result.run_id)

    service.record_event(
        result.run_id,
        "run.created",
        {"run_id": result.run_id, "source": result.run.source},
    )

    logger.info(
        "created run delivery_id=%s repo_url=%s run_id=%s content_sha256=%s",
        delivery_id,
        result.run.repo_url,
        result.run_id,
        _content_hash(raw),
    )
    return JSONResponse(status_code=202, content={"run_id": result.run_id, "duplicate": False})


@mock_router.post("/webhooks/mock", status_code=202)
async def mock_webhook(request: Request) -> Response:
    try:
        payload = await request.json()
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return _error(400, "malformed JSON")
    if not isinstance(payload, dict):
        return _error(422, "payload must be a JSON object")

    repo_url_raw = payload.get("repo_url")
    commit_sha_raw = payload.get("commit_sha")
    try:
        repo_url = normalize_repo_url(repo_url_raw)
        commit_sha = validate_commit_sha(commit_sha_raw)
    except InvalidRunInput as exc:
        return _error(422, str(exc))

    service: RunService = request.app.state.run_service
    mock_id = uuid4()
    workflow_run_id = mock_id.int >> 65
    while workflow_run_id == 0:
        mock_id = uuid4()
        workflow_run_id = mock_id.int >> 65
    try:
        result = service.create_from_delivery(
            str(mock_id),
            repo_url=repo_url,
            commit_sha=commit_sha,
            workflow_run_id=workflow_run_id,
            run_attempt=1,
            source="mock",
        )
    except InvalidRunInput as exc:
        return _error(422, str(exc))

    if not result.created:
        return _duplicate(result.run_id)

    logger.info(
        "created mock run repo_url=%s run_id=%s",
        result.run.repo_url,
        result.run_id,
    )
    return JSONResponse(status_code=202, content={"run_id": result.run_id, "duplicate": False})
