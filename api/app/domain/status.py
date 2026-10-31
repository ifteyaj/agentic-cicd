"""Run lifecycle states.

The full lifecycle is declared here so later milestones can add transitions
without moving types. M1 only creates ``QUEUED`` runs.
"""

from enum import StrEnum


class RunStatus(StrEnum):
    QUEUED = "queued"
    TRIAGING = "triaging"
    REPAIRING = "repairing"
    VALIDATING = "validating"
    AWAITING_APPROVAL = "awaiting_approval"
    PUBLISHING = "publishing"
    COMPLETED = "completed"
    ESCALATED = "escalated"
    REJECTED = "rejected"
    FAILED = "failed"


class IllegalTransition(Exception):
    """Raised when a run is asked to move through a non-legal transition."""


_TERMINAL_STATUSES = frozenset(
    {
        RunStatus.COMPLETED,
        RunStatus.ESCALATED,
        RunStatus.REJECTED,
        RunStatus.FAILED,
    }
)

_LEGAL_TRANSITIONS: frozenset[tuple[RunStatus, RunStatus]] = frozenset(
    {
        (RunStatus.QUEUED, RunStatus.TRIAGING),
        (RunStatus.TRIAGING, RunStatus.REPAIRING),
        (RunStatus.REPAIRING, RunStatus.VALIDATING),
        (RunStatus.VALIDATING, RunStatus.REPAIRING),
        (RunStatus.VALIDATING, RunStatus.AWAITING_APPROVAL),
        (RunStatus.VALIDATING, RunStatus.ESCALATED),
        (RunStatus.AWAITING_APPROVAL, RunStatus.PUBLISHING),
        (RunStatus.AWAITING_APPROVAL, RunStatus.REJECTED),
        (RunStatus.PUBLISHING, RunStatus.COMPLETED),
    }
    | {(current, RunStatus.FAILED) for current in RunStatus if current not in _TERMINAL_STATUSES}
)


def transition(current: RunStatus, nxt: RunStatus) -> RunStatus:
    """Return ``nxt`` if the transition is legal, otherwise raise."""
    if (current, nxt) not in _LEGAL_TRANSITIONS:
        raise IllegalTransition(f"{current} -> {nxt} is not a legal transition")
    return nxt
