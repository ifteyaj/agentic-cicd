import subprocess
import sys
from pathlib import Path


def test_module_runs_the_cli_when_executed() -> None:
    api_dir = Path(__file__).resolve().parents[1]
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "app.cli", "trigger", "--help"],
        cwd=api_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr

    assert result.returncode == 0
    assert "--repo" in output
    assert "--sha" in output
