"""Run detail and approval endpoints."""

import hmac

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from app.domain.status import RunStatus
from app.services.runs import RunService

router = APIRouter()


class ApproveRequest(BaseModel):
    attempt_id: str
    patch_sha256: str


def _error(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail})


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
