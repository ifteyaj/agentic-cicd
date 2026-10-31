# ADR 0006: Non-TTY first run does not consume the welcome screen

Status: Accepted
Date: 2026-10-31

## Context
The CLI shows a welcome screen once per install, tracked by the
welcome-seen file in CICD_AGENT_CONFIG_DIR. Scripts and CI runs also call
the CLI without a terminal. If a non-terminal run wrote the flag, the
first interactive user would never see the welcome.

## Options considered
A. Any first run writes the flag, terminal or not.
B. Only an interactive first run writes the flag (chosen).
C. Never write the flag; show the welcome on every run.

## Decision
Option B. A first run writes welcome-seen only when stdout is a terminal
and the user pressed Enter. A non-terminal run prints the welcome, does
not prompt, and does not write the flag. Evidence:
api/tests/test_cli_welcome.py (W1, W4) and the write_text call in
api/app/cli.py, which is guarded by the terminal check.

## Consequences
- CI and piped runs never consume the first-run screen.
- Output in non-terminal runs is the full welcome every time. This is
  noisier for scripts, which is accepted.
- The rule is tested for the first run (W1) and for non-terminal output
  (W4). It is not tested for a non-terminal first run that is followed by
  an interactive run; add that test if the owner wants the rule proven
  end to end.
