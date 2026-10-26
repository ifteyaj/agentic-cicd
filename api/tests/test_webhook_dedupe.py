import pytest


@pytest.mark.xfail(strict=True, reason="M1: run service not implemented")
def test_same_delivery_id_creates_one_run() -> None:
    from app.services.runs import InMemoryRunStore, RunService

    store = InMemoryRunStore()
    service = RunService(store)
    first = service.create_from_delivery(
        "delivery-1", repo_url="https://github.com/example/repo", commit_sha="a" * 40
    )
    second = service.create_from_delivery(
        "delivery-1", repo_url="https://github.com/example/repo", commit_sha="a" * 40
    )
    assert first.run_id == second.run_id
    assert store.count() == 1
