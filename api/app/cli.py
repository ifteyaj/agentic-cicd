"""Command-line entry point for cicd-agent."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

import typer
from rich.console import Console

os.environ.setdefault("COLUMNS", "120")

app = typer.Typer(help="cicd-agent command line")

_STDOUT = sys.stdout
_DEFAULT_CONFIG_DIR = Path.home() / ".cicd-agent"
_DEFAULT_API_URL = "http://127.0.0.1:8000"
_SEEN_FLAG_NAME = "welcome-seen"
_PLAIN_ENV = "NO_COLOR"
_COMMIT_SHA_RE = re.compile(r"[0-9a-f]{40}")
_MOCK_ROUTE = "/api/webhooks/mock"


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


def _post_mock_run(repo_url: str, commit_sha: str) -> tuple[int, dict[str, object]]:
    """POST one run request to the dev-only mock route.

    Returns the status code and JSON object for every response, including 4xx.
    Only transport and malformed-response errors propagate to the caller.
    """
    body = json.dumps({"repo_url": repo_url, "commit_sha": commit_sha}).encode()
    request = urllib.request.Request(  # noqa: S310
        _api_url().rstrip("/") + _MOCK_ROUTE,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310
            decoded = json.loads(response.read() or b"{}")
            status = response.status
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            decoded = json.loads(raw) if raw else {}
        except ValueError:
            decoded = {}
        payload: dict[str, object] = decoded if isinstance(decoded, dict) else {}
        return exc.code, payload

    if not isinstance(decoded, dict):
        raise ValueError("response must be a JSON object")
    return status, decoded


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


@app.command("trigger")
def trigger(
    repo: str = typer.Option(..., "--repo"),
    sha: str = typer.Option(..., "--sha"),
    label: str | None = typer.Option(None, "--label"),
) -> None:
    if _COMMIT_SHA_RE.fullmatch(sha) is None:
        typer.echo("--sha must be exactly 40 lowercase hex characters", err=True)
        raise typer.Exit(code=2)

    repo_url = "https://github.com/" + repo
    try:
        status, payload = _post_mock_run(repo_url, sha)
    except ValueError:
        typer.echo("server returned an unexpected response", err=True)
        raise typer.Exit(code=5) from None
    except (OSError, urllib.error.URLError, TimeoutError):
        typer.echo("○ unreachable", err=True)
        raise typer.Exit(code=5) from None

    if status == 202:
        typer.echo(str(payload.get("run_id", "")))
        if label is not None:
            typer.echo(label)
        return
    if status == 404:
        typer.echo("trigger needs the dev server (ENV=dev)", err=True)
        raise typer.Exit(code=3)
    if status == 403:
        typer.echo("repository not on the allowlist", err=True)
        raise typer.Exit(code=4)
    if status == 422:
        typer.echo(str(payload.get("detail", "")), err=True)
        raise typer.Exit(code=2)

    typer.echo(f"trigger failed with status {status}", err=True)
    raise typer.Exit(code=2)


def _get_run(run_id: str) -> tuple[int, dict[str, object]]:
    """GET one run's detail from the API.

    Returns the status code and JSON object for every response, including 4xx.
    Only transport and malformed-response errors propagate to the caller.
    """
    request = urllib.request.Request(  # noqa: S310
        _api_url().rstrip("/") + "/api/runs/" + run_id,
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310
            decoded = json.loads(response.read() or b"{}")
            status = response.status
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            decoded = json.loads(raw) if raw else {}
        except ValueError:
            decoded = {}
        payload: dict[str, object] = decoded if isinstance(decoded, dict) else {}
        return exc.code, payload

    if not isinstance(decoded, dict):
        raise ValueError("response must be a JSON object")
    return status, decoded


@app.command("show")
def show(run_id: str) -> None:
    try:
        status, payload = _get_run(run_id)
    except ValueError:
        typer.echo("server returned an unexpected response", err=True)
        raise typer.Exit(code=5) from None
    except (OSError, urllib.error.URLError, TimeoutError):
        typer.echo("○ unreachable", err=True)
        raise typer.Exit(code=5) from None

    if status == 200:
        typer.echo(str(payload.get("run_id", "")))
        typer.echo(str(payload.get("status", "")))
        attempts = payload.get("attempts", [])
        if isinstance(attempts, list):
            for i, attempt in enumerate(attempts, start=1):
                if isinstance(attempt, dict):
                    typer.echo(
                        f"attempt {i} {attempt.get('attempt_id', '')} "
                        f"{attempt.get('patch_sha256', '')}"
                    )
        return
    if status == 404:
        typer.echo("run not found", err=True)
        raise typer.Exit(code=6)

    typer.echo(f"show failed with status {status}", err=True)
    raise typer.Exit(code=2)


if __name__ == "__main__":
    app()
