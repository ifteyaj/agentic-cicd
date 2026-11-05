![Preview](preview.png)

# agentic-cicd

Verified CI-fix agent: when a GitHub Actions run fails, it triages the failure, proposes a
patch, validates that patch in a sandbox, and waits for a human approval gate before
publishing anything. Nothing is auto-merged.

The installable Python package and CLI inside this repository are called **`cicd-agent`**.

## Status

M1 walking skeleton complete; CLI commands arrive in M1c. The service exposes:

- `GET /healthz` — liveness.
- `POST /api/webhooks/github` — verifies the `X-Hub-Signature-256` HMAC over the
  raw body, accepts only failed (`failure`/`timed_out`) completed
  `workflow_run` events, and creates exactly one queued run per delivery ID and
  per signed `workflow_run.id:run_attempt`.

Implemented in M1:

- Run states enforced by `transition()` (15 legal transitions).
- Pause at `AWAITING_APPROVAL`; a run survives a restart via the SQLite run row.
- Approval endpoint with patch-hash check (wrong hash and terminal runs return 409).
- Three failed validation attempts escalate the run.
- Events table with database-assigned IDs, SSE replay with `Last-Event-ID`.
- Payload redaction before storage and a CLI welcome screen.

The M1 validation loop is a fake adapter; the real Docker sandbox is M2.
Triage, patch generation, and publishing remain planned.
A valid approval currently returns `501` because publishing is not implemented.

## Webhook intake

Configure a secret and start the API:

```bash
cd api
export GITHUB_WEBHOOK_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
uv run uvicorn app.main:app --reload
```

The secret must not be blank or `change-me`; otherwise every delivery returns
`503`. Point a GitHub webhook at
`http://127.0.0.1:8000/api/webhooks/github` with content type `application/json`
and the `workflow_run` event.

Repositories must be on the allowlist. Set `CICD_AGENT_ALLOWED_REPOS` to a
comma-separated list of `owner/name` entries; an unset or empty list rejects
every repository. Matching is case-sensitive (`Example/Repo` is refused). A
duplicate delivery for a repository later removed from the allowlist still
returns `200`, because the delivery lookup runs first.

| Response | Meaning |
| --- | --- |
| `202` | New run created (`{"run_id", "duplicate": false}`) |
| `200` | Duplicate delivery or workflow attempt (`duplicate: true`) |
| `204` | Event or conclusion ignored |
| `400` | Malformed JSON |
| `401` | Missing or invalid signature |
| `403` | Repository not on the allowlist |
| `413` | Body over 1 MiB |
| `422` | Missing/invalid header or field |
| `503` | Webhook secret not configured or unusable |

M1 is single-process: the default wiring is in-memory, so deduplication resets
on restart. The SQLite store is implemented and tested; it persists runs,
attempts, and events. Do not run multiple workers.

## Layout

```
api/                FastAPI service, tests, and Python project (cicd-agent)
  app/
    domain/         Status machine and core domain types
    services/       Run orchestration, stores
    routes/         HTTP endpoints
    security/       Webhook signature verification
fixtures/           Seeded-bug repositories used to evaluate the agent
eval/               Evaluation harness and corpus
prompts/            Agent prompts
docs/               ADRs, setup, security notes
docker/             Docker support files
```

## Quickstart

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
cd api
uv sync
uv run pytest
uv run uvicorn app.main:app --reload
```

Then `curl http://127.0.0.1:8000/healthz` should return `{"status":"ok"}`.

## Docker

```bash
docker compose up --build
```

The API is published on `127.0.0.1:8000` only.

## Quality gates

```bash
cd api
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest -q
```

These are the same checks CI runs on every push and pull request.

## Licence

MIT. See [LICENSE](LICENSE).
