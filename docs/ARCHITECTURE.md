# Architecture

**Status:** Current (M1 walking skeleton implemented: webhook intake + run lifecycle)\
**Last updated:** 2026-10-31

## System context

```text
GitHub Actions failure
        |
        v
  POST /webhooks/github  ---> signature check ---> run creation (idempotent)
                                                        |
                                                        v
                                              [planned] triage -> patch
                                                        |
                                                        v
                                              [planned] sandbox validation
                                                        |
                                                        v
                                              [planned] human approval
                                                        |
                                                        v
                                              [planned] publish
```

## Components

| Component | Responsibility | Depends on |
| --- | --- | --- |
| `app.main` | App factory, health route, wiring | routes, services, settings |
| `app.routes.webhooks` | HTTP intake and response codes | security, services |
| `app.security.signature` | GitHub HMAC verification | stdlib only |
| `app.services.runs` | Create and deduplicate runs | domain types, store |
| `app.domain` | Run/status types and transitions | stdlib only |
| `app.config` | Environment-backed settings | pydantic-settings |
| [planned] sandbox | Execute a patch against fixtures | container runtime |
| store | SQLite persistence (run rows, attempts, events) | ADR 0001 |

## Data flow (M1)

1. GitHub sends a webhook with a delivery ID, event header, and signature.
2. The route fails closed (503) if no usable secret is configured, rejects a
   missing signature (401), and enforces the 1 MiB cap (413).
3. The route reads the raw body and verifies the HMAC over those exact bytes
   (401 on failure), before any JSON parsing.
4. The delivery ID is validated (422) and looked up; a known delivery returns
   its original run (200) even if the retry body is malformed.
5. Missing event headers are rejected (422). JSON is parsed (400 on syntax
   errors) and non-`workflow_run` events are ignored (204).
6. `workflow_run` payloads are validated (422), then filtered to completed
   `failure`/`timed_out` runs (204 otherwise).
7. `RunService.create_from_delivery` returns the existing run for a repeated
   signed workflow identity or creates a new queued run atomically.
8. The route returns 202 for a new run and 200 for a duplicate.

## Data model (M1)

| Entity | Key fields | Ownership |
| --- | --- | --- |
| Run | `run_id`, `delivery_id`, `run_key`, `workflow_run_id`, `run_attempt`, `repo_url`, `commit_sha`, `status` | `app.domain.run` |
| RunStatus | Full lifecycle enum; runs advance through it via `transition()` | `app.domain.status` |
| InMemoryRunStore | Test double; two indexes over the same runs; 10,000-run cap | `app.services.runs` |
| SQLiteRunStore | SQLite-backed run, attempt, and event rows; survives restart | `app.services.runs` |

The in-memory store is a test double: it is process-local, capped at 10,000
runs, and evicts the oldest run from both indexes, so the idempotency guarantee
holds while a run is retained. The SQLite store persists run, attempt, and
event rows.

## Boundaries and invariants

- Signature verification happens before JSON parsing, over the raw bytes.
- A delivery ID maps to at most one run; a signed workflow identity
  (`workflow_run.id:run_attempt`) maps to at most one run while retained.
- A repeated delivery ID returns its run before parsing or event filtering.
- Ignored events and non-failure conclusions never create a run.
- The route never executes a patch or touches the sandbox.
- `domain/` does not import FastAPI or HTTP types.

## Failure modes

| Failure | Behaviour | Recovery |
| --- | --- | --- |
| Missing/invalid signature | 401, no run | Sender fixes secret/signature |
| Secret not configured/unusable | 503, no run | Operator sets `GITHUB_WEBHOOK_SECRET` |
| Body over 1 MiB | 413, no run | Sender reduces payload |
| Malformed JSON | 400, no run | Sender fixes payload |
| Missing/invalid header or field | 422, no run | Sender fixes payload |
| Ignored event or conclusion | 204, no run | None needed |
| Process restart | In-memory runs are lost | Planned SQLite persistence |
| Store cap reached | Oldest run evicted | Replay may create a new run; documented |

## Deployment

- Local: `uv run uvicorn app.main:app --reload`, bound to `127.0.0.1:8000`.
- Docker: `docker compose up --build`, API published on `127.0.0.1:8000`.
- No production deployment is claimed for M1.

## Known limitations

- SQLite store persists run rows and events; the in-memory store is a test double and is process-local.
- Single-process only. Multiple workers would each hold a separate store.
- The in-memory store is capped at 10,000 runs and evicts the oldest.
- No authentication beyond webhook signature verification.
- No sandbox, triage, patch generation, or publishing implementation yet.
- The approval gate exists as state and endpoint; valid approval currently returns 501.
