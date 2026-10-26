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
    FAILED = "failed"
    CANCELLED = "cancelled"
