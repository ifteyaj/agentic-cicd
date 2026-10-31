# Current status

**Last updated:** 2026-10-31\
**Current milestone:** M1 walking skeleton. M1b complete on the code side; gate review not yet passed.\
**Branch:** `main` (PRs #4, #5, #6, #7 merged).

## What works

- `GET /healthz` returns `{"status":"ok"}`.
- Signed GitHub webhook: 202 new, 200 duplicate, 204 ignored, 401 bad signature,
  422 invalid headers, 503 unusable secret, 413 oversized
- Dev-only mock route, enabled only when ENV=dev
- Run states, enforced by transition(): 15 legal transitions
- Pause at AWAITING_APPROVAL; a run survives a restart (SQLite run row)
- Approval endpoint: wrong patch hash returns 409, run stays paused; terminal
  run returns 409 and is unchanged; a valid approval returns 501
- Three failed attempts end ESCALATED with exact attempt numbers
- Events table with database-assigned IDs; SSE replay with Last-Event-ID;
  payloads redacted before write
- Redaction function for token and assignment shapes
- CLI welcome screen: first run, replay, non-TTY, --plain, unreachable API
- Tests: 182 passed, 0 xfailed
- All four quality gates pass: ruff, format, mypy strict, and pytest.
- `AGENTS.md` at the repository root so OpenCode auto-loads harness global
  rules and project-specific constraints (AGENTS.md adapter; source is
  `config/global-rules.md`). Kept locally and not published (untracked).

## In progress

None for M1. Gate review is the owner's decision.

## Known issues

- Persistence covers the run row and events only. No LangGraph checkpoint
  tables; no index on status.
- Valid approval returns 501. Publish and completion are not implemented.
- The in-memory store is a test double; it is not used for the restart claim.
- SSE closes after the backlog. No live streaming.
- Store cap of 10,000 runs in memory (from M1a); still true for the
  in-memory path.
- Single process only.
- No sandbox yet.

## Next concrete action (M2, not M1)

1. Merge PR #4 after review.
2. M2 sandbox: real containers with hardening; hostile-input suite.

## Recently verified

| Date | Check | Result |
| --- | --- | --- |
| 2026-10-26 | `uv run pytest -q` | 161 passed, 4 xfailed |
| 2026-10-26 | `uv run ruff check .` | Pass |
| 2026-10-26 | `uv run ruff format --check .` | 20 files formatted |
| 2026-10-26 | `uv run mypy` | Pass (12 source files) |
| 2026-10-26 | Live uvicorn smoke test | health 200; new 202; duplicate 200; replay 200; ping 204; malformed 400; bad signature 401; missing event 422 |
| 2026-10-26 | `graphify extract . --code-only` | 53 nodes, 55 edges |
| 2026-10-31 | `uv run pytest -q` | 182 passed, 0 xfailed |
| 2026-10-31 | ruff check, ruff format --check, mypy | pass |

## Not verified / residual risk

- The Docker image and `docker compose up` were not built in this session.
- No GitHub webhook has been delivered from a real repository; verification
  uses signed synthetic payloads.
- Independent reviews used fresh-context subagents, because the Claude Code review
  runtime was unavailable. Reports are in `docs/designs/reviews/`.
- Live uvicorn smoke test not re-run after M1b
- Docker not re-run after M1b
- Redaction covers token and assignment shapes only, not every secret format
- Non-TTY first run does not write the welcome-seen flag (design decision,
  not yet an ADR)
