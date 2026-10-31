"""Command-line entry point for cicd-agent."""

from __future__ import annotations

import os
import sys
import urllib.request
from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer(help="cicd-agent command line")

_STDOUT = sys.stdout
_DEFAULT_CONFIG_DIR = Path.home() / ".cicd-agent"
_DEFAULT_API_URL = "http://127.0.0.1:8000"
_SEEN_FLAG_NAME = "welcome-seen"
_PLAIN_ENV = "NO_COLOR"


def _is_tty() -> bool:
    try:
        return bool(_STDOUT.isatty())
    except (AttributeError, OSError):
        try:
            return bool(sys.stdout.isatty())
        except (AttributeError, OSError):
            return False


def _ascii_only(plain: bool) -> bool:
    return plain or os.environ.get(_PLAIN_ENV) is not None


def _config_dir() -> Path:
    configured = os.environ.get("CICD_AGENT_CONFIG_DIR")
    path = Path(configured) if configured else _DEFAULT_CONFIG_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _seen_flag_path() -> Path:
    return _config_dir() / _SEEN_FLAG_NAME


def _api_url() -> str:
    return os.environ.get("CICD_AGENT_API_URL", _DEFAULT_API_URL)


def _status_line(plain: bool) -> str:
    try:
        with urllib.request.urlopen(_api_url().rstrip("/") + "/healthz", timeout=2) as response:  # noqa: S310
            if response.status == 200:
                return "API reachable"
    except (OSError, urllib.error.URLError, TimeoutError, ValueError):
        pass
    return "o unreachable" if plain else "○ unreachable"


def _render(full: bool, plain: bool, *, prompt: bool, write_seen: bool) -> None:
    ascii_only = _ascii_only(plain)
    console = Console(color_system=None if ascii_only else "auto", force_terminal=False)

    if not full:
        console.print("cicd-agent")
        console.print(_status_line(ascii_only))
        return

    console.print("cicd-agent")
    console.print("Before you begin")
    console.print(f"API: {_status_line(ascii_only)}")

    if prompt and _is_tty():
        try:
            answer = input("Press Enter to continue (q to quit): ")
        except EOFError:
            answer = ""
        if answer.strip().lower() == "q":
            raise typer.Exit(code=0)

    if write_seen and _is_tty():
        try:
            _seen_flag_path().write_text("1", encoding="utf-8")
        except OSError:
            pass


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context, plain: bool = typer.Option(False, "--plain")) -> None:
    if ctx.invoked_subcommand is not None:
        return
    seen = _seen_flag_path().exists()
    if not seen:
        _render(full=True, plain=plain, prompt=_is_tty(), write_seen=_is_tty())
    else:
        _render(full=False, plain=plain, prompt=False, write_seen=False)


@app.command("welcome")
def welcome(plain: bool = typer.Option(False, "--plain")) -> None:
    _render(
        full=True,
        plain=plain,
        prompt=_is_tty(),
        write_seen=_seen_flag_path().exists() is False,
    )
