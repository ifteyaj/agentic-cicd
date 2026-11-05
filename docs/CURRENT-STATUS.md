# Current status

**Last updated:** 2026-11-05\
**Current milestone:** M1 walking skeleton. M1b complete on the code side; gate review not yet passed. M1c: repository allowlist and `trigger` merged; `show`, `watch`, `runs`, `reject`, and `approve` not started.\
**Branch:** `main` (PRs #4–#12 merged; allowlist PR #11, `884b7e0`; trigger PR #12, `bee5f98`).

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
- Tests: 196 passed, 0 xfailed
- All four quality gates pass: ruff, format, mypy strict, and pytest.
- AGENTS.md and CLAUDE.md are kept locally and not published (see ADR 0007).

## In progress

M1c terminal commands: `trigger` is done (PR #12). Not started: `show`,
`watch`, `runs`, `reject`, and `approve` (full approval needs publishing).

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

## Next concrete action (M1c)

1. `show`, then `watch`, each with a red test first.
2. `runs` and `reject` after the list and reject endpoints exist.
3. M2 sandbox: real containers with hardening; hostile-input suite.

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
