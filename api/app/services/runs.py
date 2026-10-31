"""Run creation, validation, and in-memory idempotency.

No HTTP imports: this module owns domain validation and the duplicate
boundary. The store keeps two indexes over the same runs and evicts the
oldest run from both when the cap is reached.
"""

import hashlib
import re
import sqlite3
import threading
from collections import OrderedDict
from dataclasses import dataclass, replace
from typing import Literal
from urllib.parse import urlsplit
from uuid import uuid4

from app.domain.attempt import FIXED_FAKE_PATCH, Attempt
from app.domain.run import Run, run_key
from app.domain.status import RunStatus, transition


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


class RunStore:
    """Common interface for run stores."""

    def count(self) -> int:
        raise NotImplementedError

    def get(self, run_id: str) -> Run | None:
        raise NotImplementedError

    def get_by_delivery(self, delivery_id: str) -> Run | None:
        raise NotImplementedError

    def get_by_run_key(self, key: str) -> Run | None:
        raise NotImplementedError

    def insert(self, run: Run) -> None:
        raise NotImplementedError

    def create_if_absent(self, run: Run) -> tuple[Run, bool]:
        raise NotImplementedError

    def update(self, run: Run) -> None:
        raise NotImplementedError

    def record_attempt(self, attempt: Attempt) -> None:
        raise NotImplementedError

    def get_attempt(self, attempt_id: str) -> Attempt | None:
        raise NotImplementedError

    def list_attempts(self, run_id: str) -> list[Attempt]:
        raise NotImplementedError


class InMemoryRunStore(RunStore):
    """Process-local store with delivery-ID and run-key indexes."""

    def __init__(self, max_runs: int = 10_000) -> None:
        if max_runs < 1:
            raise ValueError("max_runs must be at least 1")
        self._max_runs = max_runs
        self._lock = threading.Lock()
        self._runs: OrderedDict[str, Run] = OrderedDict()
        self._by_delivery: dict[str, str] = {}
        self._by_run_key: dict[str, str] = {}
        self._attempts: dict[str, Attempt] = {}
        self._attempts_by_run: dict[str, list[str]] = {}

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

    def update(self, run: Run) -> None:
        """Replace an existing run without changing its keys."""
        with self._lock:
            if run.run_id not in self._runs:
                raise ValueError(f"unknown run_id: {run.run_id}")
            self._runs[run.run_id] = run
            self._by_delivery[run.delivery_id] = run.run_id
            self._by_run_key[run.run_key] = run.run_id

    def record_attempt(self, attempt: Attempt) -> None:
        with self._lock:
            self._attempts[attempt.attempt_id] = attempt
            attempt_ids = self._attempts_by_run.setdefault(attempt.run_id, [])
            if attempt.attempt_id not in attempt_ids:
                attempt_ids.append(attempt.attempt_id)

    def get_attempt(self, attempt_id: str) -> Attempt | None:
        with self._lock:
            return self._attempts.get(attempt_id)

    def list_attempts(self, run_id: str) -> list[Attempt]:
        with self._lock:
            return [
                self._attempts[attempt_id]
                for attempt_id in self._attempts_by_run.get(run_id, [])
                if attempt_id in self._attempts
            ]

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


class SQLiteRunStore(RunStore):
    """SQLite-backed run store, one row per run."""

    def __init__(self, db_path: str, max_runs: int = 10_000) -> None:
        self._db_path = db_path
        self._max_runs = max_runs
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, timeout=30.0, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    delivery_id TEXT NOT NULL UNIQUE,
                    run_key TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    source TEXT NOT NULL,
                    repo_url TEXT NOT NULL,
                    commit_sha TEXT NOT NULL,
                    workflow_run_id INTEGER NOT NULL,
                    run_attempt INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS attempts (
                    attempt_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES runs (run_id),
                    n INTEGER NOT NULL,
                    patch_sha256 TEXT NOT NULL,
                    patch_diff TEXT NOT NULL
                )
                """
            )
            self._conn.commit()

    def count(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) FROM runs").fetchone()
            return int(row[0]) if row is not None else 0

    def get(self, run_id: str) -> Run | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            return self._row_to_run(row) if row is not None else None

    def get_by_delivery(self, delivery_id: str) -> Run | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM runs WHERE delivery_id = ?", (delivery_id,)
            ).fetchone()
            return self._row_to_run(row) if row is not None else None

    def get_by_run_key(self, key: str) -> Run | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM runs WHERE run_key = ?", (key,)).fetchone()
            return self._row_to_run(row) if row is not None else None

    def insert(self, run: Run) -> None:
        self._insert_row(run)

    def create_if_absent(self, run: Run) -> tuple[Run, bool]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM runs WHERE delivery_id = ? OR run_key = ?",
                (run.delivery_id, run.run_key),
            ).fetchone()
            if row is not None:
                return self._row_to_run(row), False
            self._insert_row(run)
            return run, True

    def update(self, run: Run) -> None:
        with self._lock:
            cursor = self._conn.execute(
                """
                UPDATE runs
                SET delivery_id = ?, run_key = ?, status = ?, source = ?,
                    repo_url = ?, commit_sha = ?, workflow_run_id = ?,
                    run_attempt = ?, created_at = ?
                WHERE run_id = ?
                """,
                (
                    run.delivery_id,
                    run.run_key,
                    run.status.value,
                    run.source,
                    run.repo_url,
                    run.commit_sha,
                    run.workflow_run_id,
                    run.run_attempt,
                    run.created_at,
                    run.run_id,
                ),
            )
            self._conn.commit()
            if cursor.rowcount != 1:
                raise ValueError(f"unknown run_id: {run.run_id}")

    def record_attempt(self, attempt: Attempt) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO attempts "
                "(attempt_id, run_id, n, patch_sha256, patch_diff) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    attempt.attempt_id,
                    attempt.run_id,
                    attempt.n,
                    attempt.patch_sha256,
                    attempt.patch_diff,
                ),
            )
            self._conn.commit()

    def get_attempt(self, attempt_id: str) -> Attempt | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM attempts WHERE attempt_id = ?", (attempt_id,)
            ).fetchone()
            return self._row_to_attempt(row) if row is not None else None

    def list_attempts(self, run_id: str) -> list[Attempt]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM attempts WHERE run_id = ? ORDER BY n", (run_id,)
            ).fetchall()
            return [self._row_to_attempt(row) for row in rows]

    def _row_to_attempt(self, row: sqlite3.Row) -> Attempt:
        return Attempt(
            attempt_id=row["attempt_id"],
            run_id=row["run_id"],
            n=row["n"],
            patch_sha256=row["patch_sha256"],
            patch_diff=row["patch_diff"],
        )

    def _insert_row(self, run: Run) -> None:
        self._conn.execute(
            """
            INSERT INTO runs (
                run_id, delivery_id, run_key, status, source, repo_url,
                commit_sha, workflow_run_id, run_attempt, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run.run_id,
                run.delivery_id,
                run.run_key,
                run.status.value,
                run.source,
                run.repo_url,
                run.commit_sha,
                run.workflow_run_id,
                run.run_attempt,
                run.created_at,
            ),
        )
        self._conn.commit()

    def _row_to_run(self, row: sqlite3.Row) -> Run:
        return Run(
            run_id=row["run_id"],
            delivery_id=row["delivery_id"],
            run_key=row["run_key"],
            workflow_run_id=row["workflow_run_id"],
            run_attempt=row["run_attempt"],
            repo_url=row["repo_url"],
            commit_sha=row["commit_sha"],
            status=RunStatus(row["status"]),
            source=row["source"],
            created_at=row["created_at"],
        )


@dataclass(frozen=True)
class CreateResult:
    run: Run
    created: bool

    @property
    def run_id(self) -> str:
        return self.run.run_id


class RunService:
    """Validate inputs and create at most one run per delivery or run key."""

    def __init__(self, store: RunStore, stub_mode: Literal["pass", "fail"] = "pass") -> None:
        self._store = store
        self.stub_mode = stub_mode

    @property
    def store(self) -> RunStore:
        return self._store

    def get_by_delivery(self, delivery_id: str) -> Run | None:
        return self._store.get_by_delivery(delivery_id)

    def get_by_run_key(self, key: str) -> Run | None:
        return self._store.get_by_run_key(key)

    def advance(self, run_id: str) -> Run:
        """Move a run one fake step, leaving it paused at approval."""
        run = self._store.get(run_id)
        if run is None:
            raise ValueError(f"unknown run_id: {run_id}")
        if run.status is RunStatus.AWAITING_APPROVAL:
            return run

        next_status = {
            RunStatus.QUEUED: RunStatus.TRIAGING,
            RunStatus.TRIAGING: RunStatus.REPAIRING,
            RunStatus.REPAIRING: RunStatus.VALIDATING,
        }.get(run.status)
        if run.status is RunStatus.VALIDATING:
            if self.stub_mode == "fail":
                attempts = len(self._store.list_attempts(run.run_id))
                next_status = RunStatus.REPAIRING if attempts < 3 else RunStatus.ESCALATED
            else:
                next_status = RunStatus.AWAITING_APPROVAL
        if next_status is None:
            return run

        if next_status is RunStatus.VALIDATING:
            attempt_number = len(self._store.list_attempts(run.run_id)) + 1
            self._store.record_attempt(
                Attempt(
                    attempt_id=str(uuid4()),
                    run_id=run.run_id,
                    n=attempt_number,
                    patch_sha256=hashlib.sha256(FIXED_FAKE_PATCH.encode()).hexdigest(),
                    patch_diff=FIXED_FAKE_PATCH,
                )
            )

        updated = replace(run, status=transition(run.status, next_status))
        self._store.update(updated)
        return updated

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
