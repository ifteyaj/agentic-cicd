import json
import urllib.error

import pytest

RUN_ID = "run-123"
STATUS = "awaiting_approval"
ATTEMPT_ID = "attempt-42"
PATCH_SHA = "a" * 64
_GET_RUN = "app.cli._get_run"


def _stderr(result: object) -> str:
    return getattr(result, "stderr", "") or ""


class _FakeResponse:
    status = 200

    def read(self) -> bytes:
        return json.dumps({"run_id": RUN_ID, "status": STATUS, "attempts": []}).encode()

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False


def test_show_prints_run_and_attempts_and_exits_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "run_id": RUN_ID,
        "status": STATUS,
        "attempts": [
            {"attempt_id": ATTEMPT_ID, "patch_sha256": PATCH_SHA},
        ],
    }

    def fake_get_run(run_id: str) -> tuple[int, dict[str, object]]:
        return 200, payload

    monkeypatch.setenv("CICD_AGENT_API_URL", "http://127.0.0.1:8000")
    monkeypatch.setattr(_GET_RUN, fake_get_run, raising=False)

    from typer.testing import CliRunner

    from app.cli import app

    result = CliRunner().invoke(app, ["show", RUN_ID])

    assert result.exit_code == 0
    assert RUN_ID in result.output
    assert STATUS in result.output
    assert PATCH_SHA in result.output


def test_show_requests_the_exact_get_url(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[object] = []

    def fake_urlopen(request: object, timeout: float | None = None) -> _FakeResponse:
        calls.append(request)
        return _FakeResponse()

    monkeypatch.setenv("CICD_AGENT_API_URL", "http://127.0.0.1:8000")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    from typer.testing import CliRunner

    from app.cli import app

    result = CliRunner().invoke(app, ["show", RUN_ID])

    assert result.exit_code == 0
    assert len(calls) == 1
    request = calls[0]
    assert request.get_method() == "GET"
    assert request.full_url == "http://127.0.0.1:8000/api/runs/" + RUN_ID
    assert request.data is None


def test_show_exits_6_when_run_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get_run(run_id: str) -> tuple[int, dict[str, object]]:
        return 404, {"detail": "run not found"}

    monkeypatch.setenv("CICD_AGENT_API_URL", "http://127.0.0.1:8000")
    monkeypatch.setattr(_GET_RUN, fake_get_run, raising=False)

    from typer.testing import CliRunner

    from app.cli import app

    result = CliRunner().invoke(app, ["show", RUN_ID])

    assert result.exit_code == 6
    assert "run not found" in _stderr(result)


def test_show_reports_unreachable_and_exits_5(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_get_run(run_id: str) -> tuple[int, dict[str, object]]:
        raise urllib.error.URLError("connection refused")

    monkeypatch.setenv("CICD_AGENT_API_URL", "http://127.0.0.1:8000")
    monkeypatch.setattr(_GET_RUN, fake_get_run, raising=False)

    from typer.testing import CliRunner

    from app.cli import app

    result = CliRunner().invoke(app, ["show", RUN_ID])

    assert result.exit_code == 5
    assert "○ unreachable" in _stderr(result)
    assert "Traceback" not in _stderr(result)


def test_show_rejects_diff_flag_without_http_call(
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

    result = CliRunner().invoke(app, ["show", RUN_ID, "--diff"])

    assert result.exit_code == 2
    assert calls == []
    assert "No such command" not in (result.output + _stderr(result))
