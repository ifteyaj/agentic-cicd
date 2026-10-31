def test_first_run_shows_full_welcome_and_writes_seen_flag(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CICD_AGENT_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr("sys.stdout.isatty", lambda: True, raising=False)

    from typer.testing import CliRunner

    from app.cli import app

    runner = CliRunner()
    result = runner.invoke(app, input="\n")
    assert result.exit_code == 0
    assert "cicd-agent" in result.output
    assert "Before you begin" in result.output
    assert (tmp_path / "welcome-seen").exists()


def test_second_run_shows_compact_header_only(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CICD_AGENT_CONFIG_DIR", str(tmp_path))
    (tmp_path / "welcome-seen").write_text("1", encoding="utf-8")

    from typer.testing import CliRunner

    from app.cli import app

    runner = CliRunner()
    result = runner.invoke(app)
    assert "Before you begin" not in result.output
    assert "cicd-agent" in result.output


def test_welcome_command_replays_regardless_of_flag(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CICD_AGENT_CONFIG_DIR", str(tmp_path))
    (tmp_path / "welcome-seen").write_text("1", encoding="utf-8")

    from typer.testing import CliRunner

    from app.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["welcome"])
    assert "Before you begin" in result.output


def test_non_tty_prints_and_exits_without_prompt() -> None:
    from typer.testing import CliRunner

    from app.cli import app

    runner = CliRunner()
    result = runner.invoke(app)
    assert result.exit_code == 0
    assert "cicd-agent" in result.output
    assert "Press Enter" not in result.output


def test_plain_mode_is_ascii_only(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CICD_AGENT_CONFIG_DIR", str(tmp_path))

    from typer.testing import CliRunner

    from app.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["--plain"])
    assert all(ord(char) < 128 for char in result.output)


def test_unreachable_api_shows_marker_and_exits_zero(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CICD_AGENT_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("CICD_AGENT_API_URL", "http://127.0.0.1:1")

    from typer.testing import CliRunner

    from app.cli import app

    runner = CliRunner()
    result = runner.invoke(app)
    assert result.exit_code == 0
    assert "○ unreachable" in result.output
