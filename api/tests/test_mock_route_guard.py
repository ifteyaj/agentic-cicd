import pytest


@pytest.mark.xfail(strict=True, reason="M1b: mock route not implemented")
def test_mock_route_accepts_requests_when_env_is_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "dev")

    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    body = {
        "repo_url": "https://github.com/example/repo",
        "commit_sha": "0123456789abcdef0123456789abcdef01234567",
    }
    response = client.post("/webhooks/mock", json=body)

    assert response.status_code == 202
    assert "run_id" in response.json()


# Guard test: passes today because the route is undefined (404). It must
# keep passing after M1b, so it is not an xfail.
def test_mock_route_is_unavailable_when_env_is_not_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "production")

    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    body = {
        "repo_url": "https://github.com/example/repo",
        "commit_sha": "0123456789abcdef0123456789abcdef01234567",
    }
    response = client.post("/webhooks/mock", json=body)

    assert response.status_code == 404
