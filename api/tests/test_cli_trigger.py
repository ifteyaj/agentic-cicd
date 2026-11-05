import json
import urllib.error

import pytest

VALID_SHA = "0123456789abcdef0123456789abcdef01234567"
_POST_MOCK_RUN = "app.cli._post_mock_run"


def _stderr(result: object) -> str:
    return getattr(result, "stderr", "") or ""


def _combined(result: object) -> str:
    return (getattr(result, "output", "") or "") + _stderr(result)


def test_trigger_prints_run_id_and_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_post_mock_run(repo_url: str, commit_sha: str) -> tuple[int, dict[str, object]]:
        captured["repo_url"] = repo_url
        captured["commit_sha"] = commit_sha
        return 202, {"run_id": "abc123", "duplicate": False}

    monkeypatch.setenv("CICD_AGENT_API_URL", "http://127.0.0.1:8000")
    monkeypatch.setattr(_POST_MOCK_RUN, fake_post_mock_run, raising=False)

    from typer.testing import CliRunner

    from app.cli import app

    result = CliRunner().invoke(
        app,
        [
            "trigger",
            "--repo",
            "example/repo",
            "--sha",
            VALID_SHA,
            "--label",
            "logic-01-mean",
        ],
    )

    assert result.exit_code == 0
    assert captured == {
        "repo_url": "https://github.com/example/repo",
        "commit_sha": VALID_SHA,
    }
    assert "abc123" in result.output
    assert "logic-01-mean" in result.output


def test_trigger_exits_3_when_mock_route_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post_mock_run(repo_url: str, commit_sha: str) -> tuple[int, dict[str, object]]:
        return 404, {"detail": "Not Found"}

    monkeypatch.setenv("CICD_AGENT_API_URL", "http://127.0.0.1:8000")
    monkeypatch.setattr(_POST_MOCK_RUN, fake_post_mock_run, raising=False)

    from typer.testing import CliRunner

    from app.cli import app

    result = CliRunner().invoke(
        app,
        ["trigger", "--repo", "example/repo", "--sha", VALID_SHA],
    )

    assert result.exit_code == 3
    assert "trigger needs the dev server (ENV=dev)" in _stderr(result)


def test_trigger_exits_4_when_repository_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post_mock_run(repo_url: str, commit_sha: str) -> tuple[int, dict[str, object]]:
        return 403, {"detail": "repository not allowed"}

    monkeypatch.setenv("CICD_AGENT_API_URL", "http://127.0.0.1:8000")
    monkeypatch.setattr(_POST_MOCK_RUN, fake_post_mock_run, raising=False)

    from typer.testing import CliRunner

    from app.cli import app

    result = CliRunner().invoke(
        app,
        ["trigger", "--repo", "example/repo", "--sha", VALID_SHA],
    )

    assert result.exit_code == 4
    assert "repository not on the allowlist" in _stderr(result)


def test_trigger_reports_unreachable_and_exits_5(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post_mock_run(repo_url: str, commit_sha: str) -> tuple[int, dict[str, object]]:
        raise urllib.error.URLError("connection refused")

    monkeypatch.setenv("CICD_AGENT_API_URL", "http://127.0.0.1:8000")
    monkeypatch.setattr(_POST_MOCK_RUN, fake_post_mock_run, raising=False)

    from typer.testing import CliRunner

    from app.cli import app

    result = CliRunner().invoke(
        app,
        ["trigger", "--repo", "example/repo", "--sha", VALID_SHA],
    )

    assert result.exit_code == 5
    assert "○ unreachable" in _stderr(result)
    assert "Traceback" not in _stderr(result)


class _FakeResponse:
    status = 202

    def read(self) -> bytes:
        return json.dumps({"run_id": "abc123", "duplicate": False}).encode()

    def getcode(self) -> int:
        return self.status

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False


def test_trigger_posts_exact_body_to_mock_route(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[object] = []

    def fake_urlopen(request: object, timeout: float | None = None) -> _FakeResponse:
        calls.append(request)
        return _FakeResponse()

    monkeypatch.setenv("CICD_AGENT_API_URL", "http://127.0.0.1:8000")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    from typer.testing import CliRunner

    from app.cli import app

    result = CliRunner().invoke(
        app,
        ["trigger", "--repo", "example/repo", "--sha", VALID_SHA],
    )

    assert result.exit_code == 0
    assert len(calls) == 1
    request = calls[0]
    assert request.full_url == "http://127.0.0.1:8000/api/webhooks/mock"
    assert request.get_method() == "POST"
    assert json.loads(request.data.decode()) == {
        "repo_url": "https://github.com/example/repo",
        "commit_sha": VALID_SHA,
    }


def test_trigger_rejects_malformed_sha_without_http_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []

    def fake_urlopen(request: object, timeout: float | None = None) -> _FakeResponse:
        calls.append(request)
        return _FakeResponse()

    monkeypatch.setenv("CICD_AGENT_API_URL", "http://127.0.0.1:8000")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    from typer.testing import CliRunner

    from app.cli import app

    result = CliRunner().invoke(
        app,
        ["trigger", "--repo", "example/repo", "--sha", VALID_SHA[:39]],
    )

    assert result.exit_code == 2
    assert calls == []
    assert "No such command" not in _combined(result)


def test_trigger_rejects_positional_repo_without_http_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []

    def fake_urlopen(request: object, timeout: float | None = None) -> _FakeResponse:
        calls.append(request)
        return _FakeResponse()

    monkeypatch.setenv("CICD_AGENT_API_URL", "http://127.0.0.1:8000")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    from typer.testing import CliRunner

    from app.cli import app

    result = CliRunner().invoke(
        app,
        ["trigger", "example/repo", "--sha", VALID_SHA],
    )

    assert result.exit_code == 2
    assert calls == []
    assert "No such command" not in _combined(result)


def test_trigger_rejects_uppercase_sha_without_http_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []

    def fake_urlopen(request: object, timeout: float | None = None) -> _FakeResponse:
        calls.append(request)
        return _FakeResponse()

    monkeypatch.setenv("CICD_AGENT_API_URL", "http://127.0.0.1:8000")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    from typer.testing import CliRunner

    from app.cli import app

    result = CliRunner().invoke(
        app,
        ["trigger", "--repo", "example/repo", "--sha", VALID_SHA.upper()],
    )

    assert result.exit_code == 2
    assert calls == []


def test_trigger_reports_unexpected_response_separately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post_mock_run(repo_url: str, commit_sha: str) -> tuple[int, dict[str, object]]:
        raise ValueError("response must be a JSON object")

    monkeypatch.setenv("CICD_AGENT_API_URL", "http://127.0.0.1:8000")
    monkeypatch.setattr(_POST_MOCK_RUN, fake_post_mock_run, raising=False)

    from typer.testing import CliRunner

    from app.cli import app

    result = CliRunner().invoke(
        app,
        ["trigger", "--repo", "example/repo", "--sha", VALID_SHA],
    )

    assert result.exit_code == 5
    assert "server returned an unexpected response" in _stderr(result)
    assert "unreachable" not in _stderr(result)
