"""Run creation, validation, and in-memory idempotency.

No HTTP imports: this module owns domain validation and the duplicate
boundary. The store keeps two indexes over the same runs and evicts the
oldest run from both when the cap is reached.
"""

import re
import threading
from collections import OrderedDict
from dataclasses import dataclass
from urllib.parse import urlsplit
from uuid import uuid4

from app.domain.run import Run, run_key
from app.domain.status import RunStatus


class InvalidRunInput(ValueError):
    """Raised when a delivery carries a field that fails domain validation."""


_DELIVERY_RE = re.compile(r"[A-Za-z0-9-]{1,128}")
_SHA_RE = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
_SEGMENT_RE = re.compile(r"[A-Za-z0-9_.-]+")


def validate_delivery_id(delivery_id: object) -> None:
    """Validate the unsigned delivery header before using it as a key."""
    if not isinstance(delivery_id, str) or _DELIVERY_RE.fullmatch(delivery_id) is None:
        raise InvalidRunInput("invalid delivery id")


def normalize_repo_url(url: object) -> str:
    """Return a canonical ``https://github.com/owner/repo`` URL or raise."""
    if not isinstance(url, str):
        raise InvalidRunInput("invalid repository url")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as exc:  # malformed port, invalid IPv6, etc.
        raise InvalidRunInput("invalid repository url") from exc

    if parts.scheme != "https":
        raise InvalidRunInput("repository url must use https")
    if parts.username is not None or parts.password is not None:
        raise InvalidRunInput("repository url must not contain credentials")
    if parts.hostname != "github.com":
        raise InvalidRunInput("repository host must be github.com")
    if port is not None:
        raise InvalidRunInput("repository url must not contain a port")
    if parts.query or parts.fragment:
        raise InvalidRunInput("repository url must not contain a query or fragment")

    path = parts.path
    if path.endswith(".git"):
        path = path[:-4]
    if not path.startswith("/"):
        raise InvalidRunInput("repository url must contain an owner and repository")
    segments = path[1:].split("/")
    if len(segments) != 2:
        raise InvalidRunInput("repository url must contain exactly owner/repo")
    for segment in segments:
        if segment in {".", ".."} or _SEGMENT_RE.fullmatch(segment) is None:
            raise InvalidRunInput("repository url contains an invalid path segment")
    return f"https://github.com/{segments[0]}/{segments[1]}"


def validate_commit_sha(commit_sha: object) -> str:
    """Accept a 40- or 64-character lowercase hex SHA that is not all zeros."""
    if (
        not isinstance(commit_sha, str)
        or _SHA_RE.fullmatch(commit_sha) is None
        or set(commit_sha) == {"0"}
    ):
        raise InvalidRunInput("invalid commit sha")
    return commit_sha


def validate_workflow_identity(workflow_run_id: object, run_attempt: object) -> tuple[int, int]:
    """Require JSON integers: bool, float, and str are rejected."""
    if isinstance(workflow_run_id, bool) or not isinstance(workflow_run_id, int):
        raise InvalidRunInput("workflow_run.id must be an integer")
    if workflow_run_id <= 0:
        raise InvalidRunInput("workflow_run.id must be positive")
    if isinstance(run_attempt, bool) or not isinstance(run_attempt, int):
        raise InvalidRunInput("workflow_run.run_attempt must be an integer")
    if run_attempt < 1:
        raise InvalidRunInput("workflow_run.run_attempt must be positive")
    return workflow_run_id, run_attempt


class InMemoryRunStore:
    """Process-local store with delivery-ID and run-key indexes."""

    def __init__(self, max_runs: int = 10_000) -> None:
        if max_runs < 1:
            raise ValueError("max_runs must be at least 1")
        self._max_runs = max_runs
        self._lock = threading.Lock()
        self._runs: OrderedDict[str, Run] = OrderedDict()
        self._by_delivery: dict[str, str] = {}
        self._by_run_key: dict[str, str] = {}

    def count(self) -> int:
        with self._lock:
            return len(self._runs)

    def get_by_delivery(self, delivery_id: str) -> Run | None:
        with self._lock:
            run_id = self._by_delivery.get(delivery_id)
            return self._runs.get(run_id) if run_id is not None else None

    def get_by_run_key(self, key: str) -> Run | None:
        with self._lock:
            run_id = self._by_run_key.get(key)
            return self._runs.get(run_id) if run_id is not None else None

    def get(self, run_id: str) -> Run | None:
        with self._lock:
            return self._runs.get(run_id)

    def insert(self, run: Run) -> None:
        with self._lock:
            self._insert_locked(run)

    def create_if_absent(self, run: Run) -> tuple[Run, bool]:
        """Atomically return the existing run for either key, or insert ``run``."""
        with self._lock:
            existing_id = self._by_delivery.get(run.delivery_id)
            if existing_id is None:
                existing_id = self._by_run_key.get(run.run_key)
            if existing_id is not None:
                return self._runs[existing_id], False
            self._insert_locked(run)
            return run, True

    def _insert_locked(self, run: Run) -> None:
        self._runs[run.run_id] = run
        self._by_delivery[run.delivery_id] = run.run_id
        self._by_run_key[run.run_key] = run.run_id
        while len(self._runs) > self._max_runs:
            _, evicted = self._runs.popitem(last=False)
            if self._by_delivery.get(evicted.delivery_id) == evicted.run_id:
                del self._by_delivery[evicted.delivery_id]
            if self._by_run_key.get(evicted.run_key) == evicted.run_id:
                del self._by_run_key[evicted.run_key]


@dataclass(frozen=True)
class CreateResult:
    run: Run
    created: bool

    @property
    def run_id(self) -> str:
        return self.run.run_id


class RunService:
    """Validate inputs and create at most one run per delivery or run key."""

    def __init__(self, store: InMemoryRunStore) -> None:
        self._store = store

    @property
    def store(self) -> InMemoryRunStore:
        return self._store

    def get_by_delivery(self, delivery_id: str) -> Run | None:
        return self._store.get_by_delivery(delivery_id)

    def get_by_run_key(self, key: str) -> Run | None:
        return self._store.get_by_run_key(key)

    def create_from_delivery(
        self,
        delivery_id: str,
        *,
        repo_url: str,
        commit_sha: str,
        workflow_run_id: int,
        run_attempt: int,
        source: str = "webhook",
    ) -> CreateResult:
        validate_delivery_id(delivery_id)
        normalized_url = normalize_repo_url(repo_url)
        validated_sha = validate_commit_sha(commit_sha)
        workflow_run_id, run_attempt = validate_workflow_identity(workflow_run_id, run_attempt)
        run = Run(
            run_id=str(uuid4()),
            delivery_id=delivery_id,
            run_key=run_key(workflow_run_id, run_attempt),
            workflow_run_id=workflow_run_id,
            run_attempt=run_attempt,
            repo_url=normalized_url,
            commit_sha=validated_sha,
            status=RunStatus.QUEUED,
            source=source,
        )
        stored, created = self._store.create_if_absent(run)
        return CreateResult(run=stored, created=created)
