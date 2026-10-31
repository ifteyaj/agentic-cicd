import pytest


@pytest.mark.xfail(strict=True, reason="M1b: CLI welcome not implemented")
def test_first_run_shows_full_welcome_and_writes_seen_flag(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CICD_AGENT_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr("sys.stdout.isatty", lambda: True, raising=False)

    from app.cli import app
    from typer.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(app, input="\n")
    assert result.exit_code == 0
    assert "cicd-agent" in result.output
    assert "Before you begin" in result.output
    assert (tmp_path / "welcome-seen").exists()


@pytest.mark.xfail(strict=True, reason="M1b: CLI welcome not implemented")
def test_second_run_shows_compact_header_only(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CICD_AGENT_CONFIG_DIR", str(tmp_path))
    (tmp_path / "welcome-seen").write_text("1", encoding="utf-8")

    from app.cli import app
    from typer.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(app)
    assert "Before you begin" not in result.output
    assert "cicd-agent" in result.output


@pytest.mark.xfail(strict=True, reason="M1b: CLI welcome not implemented")
def test_welcome_command_replays_regardless_of_flag(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CICD_AGENT_CONFIG_DIR", str(tmp_path))
    (tmp_path / "welcome-seen").write_text("1", encoding="utf-8")

    from app.cli import app
    from typer.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(app, ["welcome"])
    assert "Before you begin" in result.output


@pytest.mark.xfail(strict=True, reason="M1b: CLI welcome not implemented")
def test_non_tty_prints_and_exits_without_prompt() -> None:
    from app.cli import app
    from typer.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(app)
    assert result.exit_code == 0
    assert "cicd-agent" in result.output
    assert "Press Enter" not in result.output


@pytest.mark.xfail(strict=True, reason="M1b: CLI welcome not implemented")
def test_plain_mode_is_ascii_only(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CICD_AGENT_CONFIG_DIR", str(tmp_path))

    from app.cli import app
    from typer.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(app, ["--plain"])
    assert all(ord(char) < 128 for char in result.output)


@pytest.mark.xfail(strict=True, reason="M1b: CLI welcome not implemented")
def test_unreachable_api_shows_marker_and_exits_zero(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CICD_AGENT_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("CICD_AGENT_API_URL", "http://127.0.0.1:1")

    from app.cli import app
    from typer.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(app)
    assert result.exit_code == 0
    assert "○ unreachable" in result.output
