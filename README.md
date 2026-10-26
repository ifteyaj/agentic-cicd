# agentic-cicd

Verified CI-fix agent: when a GitHub Actions run fails, it triages the failure, proposes a
patch, validates that patch in a sandbox, and waits for a human approval gate before
publishing anything. Nothing is auto-merged.

The installable Python package and CLI inside this repository are called **`cicd-agent`**.

## Status

Milestone 0 — skeleton only. The only endpoint implemented is `/healthz`. The behaviour for
M1 is recorded as strict `xfail` tests, which turn red the moment a feature lands so the
marker has to be removed.

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
