import pytest

from app import main as app_main

# The mock route validates commit_sha before the allowlist check, and
# validate_commit_sha rejects an all-zero SHA with 422. Payloads here must use
# a real non-zero hex SHA so a refusal test cannot pass for the wrong reason.


@pytest.fixture(autouse=True)
def _fresh_env_apps(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rebuild the cached per-env app so each test reads the allowlist env var."""
    monkeypatch.setattr(app_main, "_env_apps", {})


def test_mock_route_accepts_requests_when_env_is_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "dev")

    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.setenv("CICD_AGENT_ALLOWED_REPOS", "example/repo")
    client = TestClient(app)
    body = {
        "repo_url": "https://github.com/example/repo",
        "commit_sha": "0123456789abcdef0123456789abcdef01234567",
    }
    response = client.post("/api/webhooks/mock", json=body)

    assert response.status_code == 202
    assert "run_id" in response.json()


# Guard test: passes today because the route is undefined (404). It must
# keep passing after M1b, so it is not an xfail.
def test_mock_route_is_unavailable_when_env_is_not_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "production")

    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.setenv("CICD_AGENT_ALLOWED_REPOS", "example/repo")
    client = TestClient(app)
    body = {
        "repo_url": "https://github.com/example/repo",
        "commit_sha": "0123456789abcdef0123456789abcdef01234567",
    }
    response = client.post("/api/webhooks/mock", json=body)

    assert response.status_code == 404


def test_mock_route_rejects_repo_not_on_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("CICD_AGENT_ALLOWED_REPOS", "example/other")

    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    body = {
        "repo_url": "https://github.com/example/repo",
        "commit_sha": "0123456789abcdef0123456789abcdef01234567",
    }
    response = client.post("/api/webhooks/mock", json=body)

    assert response.status_code == 403
    assert response.json() == {"detail": "repository not allowed"}
