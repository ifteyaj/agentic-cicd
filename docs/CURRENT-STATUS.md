# Current status

**Last updated:** 2026-11-11\
**Current milestone:** M1 walking skeleton. M1b complete on the code side; gate review not yet passed. M1c: repository allowlist, `trigger`, `show`, and the runs list + reject endpoints merged; `watch`, the CLI `runs`/`reject`/`approve` commands, and the rejection trace event remain.\
**Branch:** `main` (PRs #4–#16 merged; runs list + reject endpoints PR #16, merge `c1376b8`). Red tests for the rejection trace event on `fix/reject-event` (PR #17).

## What works

- `GET /healthz` returns `{"status":"ok"}`.
- Signed GitHub webhook: 202 new, 200 duplicate, 204 ignored, 401 bad signature,
  422 invalid headers, 503 unusable secret, 413 oversized
- Repo allowlist with default deny on both the signed and mock routes: exact,
  case-sensitive `owner/name` match after normalising the GitHub clone URL;
  unlisted repos return 403 `{"detail": "repository not allowed"}`
- Dev-only mock route, enabled only when ENV=dev
- Run states, enforced by transition(): 15 legal transitions
- Pause at AWAITING_APPROVAL; a run survives a restart (SQLite run row)
- Approval endpoint: wrong patch hash returns 409, run stays paused; terminal
  run returns 409 and is unchanged; a valid approval returns 501
- `GET /api/runs` lists runs newest first (`limit` 1–200, default 50; `count`
  is the number of entries returned; equal timestamps keep `run_id`
  ascending order)
- `GET /api/runs/{run_id}` returns the run status and attempts (404 otherwise)
- `POST /api/runs/{run_id}/reject` rejects a run awaiting approval; the body
  must be empty; 409 when the run is not awaiting approval; writes no
  attempt, approval record, or branch
- Three failed attempts end ESCALATED with exact attempt numbers
- Events table with database-assigned IDs; SSE replay with Last-Event-ID;
  payloads redacted before write
- Redaction function for token and assignment shapes
- CLI welcome screen: first run, replay, non-TTY, --plain, unreachable API
- `cicd-agent trigger --repo OWNER/NAME --sha COMMIT [--label NAME]` sends a
  run to the dev-only mock route. The SHA is checked locally (40 lowercase hex
  characters) before any call; `--label` is printed only, never sent. Exit
  codes: 0 success, 2 usage or 422, 3 dev server missing, 4 repo not
  allowlisted, 5 unreachable or unexpected response. Evidence: PR #12 (merge
  `bee5f98`), 196 passed, live 202 with a run ID on port 8001.
- `cicd-agent show RUN_ID` fetches run detail from the live API: prints the
  run ID, status, and one line per attempt. Exit codes: 0 success, 2
  unexpected status, 5 unreachable or unexpected response, 6 run not found.
  Evidence: PR #14 (merge `f0a091f`).
- Tests: 209 passed, 1 xfailed. The xfail is the red rejection-trace test on
  `fix/reject-event` (PR #17); it must be dropped when the fix lands.
- All four quality gates pass: ruff, format, mypy strict, and pytest.
- AGENTS.md and CLAUDE.md are kept locally and not published (see ADR 0007).

## In progress

M1c terminal commands: `trigger` (PR #12) and `show` (PR #14) are done. Not
started: `watch`, `runs`, `reject`, and `approve` (full approval needs
publishing). M1c-3 rejection trace event: red test on `fix/reject-event`
(PR #17); the fix is pending.

## Known issues

- Persistence covers the run row and events only. No LangGraph checkpoint
  tables; no index on status.
- Valid approval returns 501. Publish and completion are not implemented.
- The in-memory store is a test double; it is not used for the restart claim.
- SSE closes after the backlog. No live streaming.
- Store cap of 10,000 runs in memory (from M1a); still true for the
  in-memory path.
- Single process only.
- The allowlist is resolved when the per-env app is first built and cached for
  the process lifetime, so changing `CICD_AGENT_ALLOWED_REPOS` requires a
  restart. This matches production startup semantics; there is no hot reload.
- No sandbox yet.
- Reject writes no `run.status_changed` event; the trace is silent on a
  rejection. Red test on `fix/reject-event` (PR #17); fix pending.
- `list_runs` loads every run and sorts in Python. Before the store grows,
  SQLite needs `LIMIT` and an index on `created_at`.

## Next concrete action (M1c)

1. Rejection trace event: implement behind the red test (PR #17), dropping
   the xfail marker in the same change.
2. `watch`, red tests first.
3. CLI `runs` and `reject` commands against the merged endpoints.
4. M2 sandbox: real containers with hardening; hostile-input suite.

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
| 2026-11-05 | Mock route on `app.main:app`, `CICD_AGENT_ALLOWED_REPOS` unset | 403 `repository not allowed` |
| 2026-11-05 | `uv run pytest -q` | 196 passed, 0 xfailed |
| 2026-11-05 | ruff check, ruff format --check, mypy | pass |
| 2026-11-05 | Live `trigger` via `python -m app.cli` against uvicorn (port 8001) | run ID + label, exit 0; `POST /api/webhooks/mock 202` |
| 2026-11-05 | PR #12 merged | merge `bee5f98` |
| 2026-11-11 | PRs #14 (`show`), #15 (test fix), #16 (runs list + reject endpoints) merged | merges `f0a091f`, `1348af9`, `c1376b8` |
| 2026-11-11 | `uv run pytest -q` | 209 passed, 1 xfailed |
| 2026-11-11 | ruff check, ruff format --check, mypy | pass |

## Not verified / residual risk

- The Docker image and `docker compose up` were not built in this session.
- No GitHub webhook has been delivered from a real repository; verification
  uses signed synthetic payloads.
- Independent reviews used fresh-context subagents, because the Claude Code review
  runtime was unavailable. Reports are in `docs/designs/reviews/`.
- Live uvicorn: health 200 and mock 202 confirmed on a temporary server
  (port 8001); the long-running port 8000 server was not inspected. Full
  webhook matrix last run 2026-10-26.
- Docker not re-run after M1b
- Redaction covers token and assignment shapes only, not every secret format
- Non-TTY first run does not write the welcome-seen flag (design decision,
  not yet an ADR)
