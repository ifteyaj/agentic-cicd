from app.services.runs import InMemoryRunStore, RunService


def test_same_delivery_id_creates_one_run() -> None:
    store = InMemoryRunStore()
    service = RunService(store)
    first = service.create_from_delivery(
        "delivery-1",
        repo_url="https://github.com/example/repo",
        commit_sha="a" * 40,
        workflow_run_id=123,
        run_attempt=1,
    )
    second = service.create_from_delivery(
        "delivery-1",
        repo_url="https://github.com/example/repo",
        commit_sha="a" * 40,
        workflow_run_id=123,
        run_attempt=1,
    )
    assert first.run_id == second.run_id
    assert first.created is True
    assert second.created is False
    assert store.count() == 1
