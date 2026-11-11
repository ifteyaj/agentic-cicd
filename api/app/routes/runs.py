"""Run listing, detail, approval, and rejection endpoints."""

import hmac
from dataclasses import replace
from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from app.domain.status import RunStatus, transition
from app.services.runs import RunService

router = APIRouter()


class ApproveRequest(BaseModel):
    attempt_id: str
    patch_sha256: str


def _error(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail})


@router.get("/api/runs")
async def list_runs(
    request: Request, limit: Annotated[int, Query(ge=1, le=200)] = 50
) -> JSONResponse:
    service: RunService = request.app.state.run_service
    # Stable two-pass sort: run_id ascending first, then created_at descending,
    # so equal timestamps keep run_id ascending order.
    by_run_id = sorted(service.store.list_runs(), key=lambda run: run.run_id)
    runs = sorted(by_run_id, key=lambda run: run.created_at, reverse=True)[:limit]
    return JSONResponse(
        status_code=200,
        content={
            "runs": [{"run_id": run.run_id, "status": run.status.value} for run in runs],
            "count": len(runs),
        },
    )


@router.get("/api/runs/{run_id}")
async def get_run(run_id: str, request: Request) -> JSONResponse:
    service: RunService = request.app.state.run_service
    run = service.store.get(run_id)
    if run is None:
        return _error(404, "run not found")
    attempts = [
        {"attempt_id": attempt.attempt_id, "patch_sha256": attempt.patch_sha256}
        for attempt in service.store.list_attempts(run_id)
    ]
    return JSONResponse(
        status_code=200,
        content={
            "run_id": run.run_id,
            "status": run.status.value,
            "attempts": attempts,
        },
    )


@router.post("/api/runs/{run_id}/approve")
async def approve_run(run_id: str, body: ApproveRequest, request: Request) -> JSONResponse:
    service: RunService = request.app.state.run_service
    run = service.store.get(run_id)
    if run is None:
        return _error(404, "run not found")
    if run.status is not RunStatus.AWAITING_APPROVAL:
        return _error(409, "run is not awaiting approval")

    attempt = service.store.get_attempt(body.attempt_id)
    if attempt is None or attempt.run_id != run_id:
        return _error(404, "attempt not found")
    if not hmac.compare_digest(attempt.patch_sha256, body.patch_sha256):
        return _error(409, "patch hash mismatch")

    return _error(501, "approval not implemented in this milestone")


@router.post("/api/runs/{run_id}/reject")
async def reject_run(run_id: str, request: Request) -> JSONResponse:
    service: RunService = request.app.state.run_service
    # The rejection note is deferred to the approval-persistence step: reject
    # accepts an absent or empty body only, before any state check.
    if (await request.body()).strip():
        return _error(422, "reject does not accept a request body")

    run = service.store.get(run_id)
    if run is None:
        return _error(404, "run not found")
    if run.status is not RunStatus.AWAITING_APPROVAL:
        return _error(409, "run is not awaiting approval")

    service.store.update(replace(run, status=transition(run.status, RunStatus.REJECTED)))
    return JSONResponse(status_code=200, content={"run_id": run_id, "status": "rejected"})


@router.get("/api/runs/{run_id}/events")
async def get_events(run_id: str, request: Request) -> Response:
    service: RunService = request.app.state.run_service
    run = service.store.get(run_id)
    if run is None:
        return _error(404, "run not found")

    last_event_id_header = request.headers.get("Last-Event-ID")
    after_event_id = 0
    if last_event_id_header is not None:
        if not last_event_id_header.isdigit():
            return _error(400, "invalid Last-Event-ID")
        after_event_id = int(last_event_id_header)

    lines: list[str] = []
    for event in service.list_events(run_id, after_event_id):
        lines.append(f"id: {event.event_id}\nevent: {event.type}\ndata: {event.payload}\n\n")
    return Response(content="".join(lines), media_type="text/event-stream")
