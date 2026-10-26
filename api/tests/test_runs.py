import threading

import pytest

from app.domain.run import run_key
from app.domain.status import RunStatus
from app.services.runs import (
    CreateResult,
    InMemoryRunStore,
    InvalidRunInput,
    RunService,
    normalize_repo_url,
    validate_commit_sha,
    validate_delivery_id,
    validate_workflow_identity,
)


def _create(
    service: RunService,
    delivery_id: str = "delivery-1",
    *,
    run_id: int = 123,
    attempt: int = 1,
    repo_url: str = "https://github.com/example/repo",
    commit_sha: str = "a" * 40,
) -> CreateResult:
    return service.create_from_delivery(
        delivery_id,
        repo_url=repo_url,
        commit_sha=commit_sha,
        workflow_run_id=run_id,
        run_attempt=attempt,
    )


def test_same_run_key_with_new_delivery_returns_original() -> None:
    service = RunService(InMemoryRunStore())
    first = _create(service, "delivery-1")
    second = _create(service, "delivery-2")
    assert first.run_id == second.run_id
    assert second.created is False
    assert service.store.count() == 1


def test_different_attempts_create_two_runs() -> None:
    service = RunService(InMemoryRunStore())
    first = _create(service, "delivery-1", attempt=1)
    second = _create(service, "delivery-2", attempt=2)
    assert first.run_id != second.run_id
    assert second.created is True
    assert service.store.count() == 2


def test_run_starts_queued_and_normalizes_dot_git() -> None:
    service = RunService(InMemoryRunStore())
    result = _create(service, repo_url="https://github.com/example/repo.git")
    run = result.run
    assert run.status is RunStatus.QUEUED
    assert run.repo_url == "https://github.com/example/repo"
    assert run.run_key == run_key(123, 1)
    assert run.workflow_run_id == 123
    assert run.run_attempt == 1


def test_create_result_exposes_run_id() -> None:
    result = _create(RunService(InMemoryRunStore()))
    assert result.run_id == result.run.run_id


@pytest.mark.parametrize("delivery_id", ["", " ", "abc_def", "a" * 129, "abc/def", None])
def test_invalid_delivery_id_is_rejected(delivery_id: object) -> None:
    with pytest.raises(InvalidRunInput):
        validate_delivery_id(delivery_id)


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/example/repo",
        "https://gitlab.com/example/repo",
        "https://user:pass@github.com/example/repo",
        "https://github.com:443/example/repo",
        "https://github.com/example/repo?ref=main",
        "https://github.com/example/repo#readme",
        "https://github.com/example/repo/",
        "https://github.com/example/repo/extra",
        "https://github.com/example",
        "https://github.com/../repo",
        "https://github.com/example/..",
        "https://github.com/example/repo%20name",
        "",
    ],
)
def test_invalid_repo_urls_are_rejected(url: str) -> None:
    with pytest.raises(InvalidRunInput):
        normalize_repo_url(url)


def test_repo_url_dot_git_is_removed_once() -> None:
    assert (
        normalize_repo_url("https://github.com/example/repo.git")
        == "https://github.com/example/repo"
    )


@pytest.mark.parametrize(
    "sha",
    ["", "a" * 39, "a" * 41, "A" * 40, "g" * 40, "0" * 40, "0" * 64, None, 1],
)
def test_invalid_commit_sha_is_rejected(sha: object) -> None:
    with pytest.raises(InvalidRunInput):
        validate_commit_sha(sha)


@pytest.mark.parametrize("sha", ["a" * 40, "a" * 64])
def test_valid_commit_sha_is_accepted(sha: str) -> None:
    assert validate_commit_sha(sha) == sha


@pytest.mark.parametrize(
    ("workflow_run_id", "run_attempt"),
    [
        (0, 1),
        (-1, 1),
        (True, 1),
        (1.0, 1),
        ("1", 1),
        (1, 0),
        (1, -1),
        (1, True),
        (1, 1.0),
        (1, "1"),
        (None, 1),
        (1, None),
    ],
)
def test_invalid_workflow_identity_is_rejected(
    workflow_run_id: object, run_attempt: object
) -> None:
    with pytest.raises(InvalidRunInput):
        validate_workflow_identity(workflow_run_id, run_attempt)


def test_store_cap_evicts_oldest_from_both_indexes() -> None:
    store = InMemoryRunStore(max_runs=2)
    service = RunService(store)
    first = _create(service, "delivery-1", run_id=1)
    _create(service, "delivery-2", run_id=2)
    _create(service, "delivery-3", run_id=3)

    assert store.count() == 2
    assert store.get_by_delivery("delivery-1") is None
    assert store.get_by_run_key(first.run.run_key) is None
    assert store.get_by_delivery("delivery-2") is not None
    assert store.get_by_delivery("delivery-3") is not None


def test_store_rejects_non_positive_cap() -> None:
    with pytest.raises(ValueError):
        InMemoryRunStore(max_runs=0)


def test_concurrent_same_delivery_creates_one_run() -> None:
    service = RunService(InMemoryRunStore())
    results = []
    lock = threading.Lock()

    def worker() -> None:
        result = _create(service)
        with lock:
            results.append(result)

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(results) == 20
    assert sum(result.created for result in results) == 1
    assert len({result.run_id for result in results}) == 1
    assert service.store.count() == 1
