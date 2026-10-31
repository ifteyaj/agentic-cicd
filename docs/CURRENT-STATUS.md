# Current status

**Last updated:** 2026-10-26\
**Current milestone:** M1 — webhook intake (implemented)\
**Branch:** `harness/m1-webhook-intake`

## What works

- `GET /healthz` returns `{"status":"ok"}`.
- `POST /webhooks/github` verifies the SHA-256 HMAC over the raw body, rejects
  unusable secrets (503), enforces a 1 MiB cap (413), filters events and
  conclusions (204), validates headers and fields (422), and creates at most one
  queued run per delivery ID and per signed `workflow_run.id:run_attempt`
  (202/200).
- Concurrent duplicate requests produce exactly one run.
- All four quality gates pass: ruff, format, mypy strict, and pytest.
- `AGENTS.md` at the repository root so OpenCode auto-loads harness global
  rules and project-specific constraints (AGENTS.md adapter; source is
  `config/global-rules.md`).
## In progress

- M1 status machine and illegal-transition protection (four strict `xfail`
  tests remain).

## Known issues

| Issue | Impact | Workaround | Owner |
| --- | --- | --- | --- |
| Four status-machine tests are strict `xfail` | Status transitions are not implemented | Remove the markers when the status machine lands | Ifteyaj |
| Runs are in memory | Lost on restart | None in M1; SQLite planned | Ifteyaj |
| Store cap is 10,000 runs | Replaying an evicted run can create a new run | Accepted for M1; documented in the spec | Ifteyaj |
| Single process only | Multiple workers would not share dedupe state | Run one uvicorn worker | Ifteyaj |
| No sandbox yet | Model-generated code cannot be executed safely | Keep execution out of M1 | Ifteyaj |

## Next concrete action

1. Implement the status machine and transition guards, removing the four
   `xfail` markers.
2. Add the sandbox validation loop and approval gate.
3. Replace the in-memory store behind the same `RunService` interface.

## Recently verified

| Date | Check | Result |
| --- | --- | --- |
| 2026-10-26 | `uv run pytest -q` | 161 passed, 4 xfailed |
| 2026-10-26 | `uv run ruff check .` | Pass |
| 2026-10-26 | `uv run ruff format --check .` | 20 files formatted |
| 2026-10-26 | `uv run mypy` | Pass (12 source files) |
| 2026-10-26 | Live uvicorn smoke test | health 200; new 202; duplicate 200; replay 200; ping 204; malformed 400; bad signature 401; missing event 422 |
| 2026-10-26 | `graphify extract . --code-only` | 53 nodes, 55 edges |

## Not verified / residual risk

- The Docker image and `docker compose up` were not built in this session.
- No GitHub webhook has been delivered from a real repository; verification uses
  signed synthetic payloads.
- The Claude Code EGM runtime could not be executed because the model endpoint
  returned HTTP 402 (billing). Independent reviews used fresh-context subagents
  instead; reports are in `docs/designs/reviews/`.
