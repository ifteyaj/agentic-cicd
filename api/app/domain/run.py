"""Core run domain types.

This module has no framework imports.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.domain.status import RunStatus


def run_key(workflow_run_id: int, run_attempt: int) -> str:
    """Return the signed, stable identity of one workflow attempt."""
    return f"{workflow_run_id}:{run_attempt}"


@dataclass(frozen=True, slots=True)
class Run:
    run_id: str
    delivery_id: str
    run_key: str
    workflow_run_id: int
    run_attempt: int
    repo_url: str
    commit_sha: str
    status: RunStatus = RunStatus.QUEUED
    source: str = "webhook"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
