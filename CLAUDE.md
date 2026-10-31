# agentic-cicd — agent instructions

## What this project is

A verified CI-fix agent. When a GitHub Actions run fails, it triages the
failure, proposes a patch, validates the patch in a sandbox, and waits for a
human approval gate before publishing. Nothing is auto-merged.

Current state: **Milestone 1 webhook intake is implemented.** `POST /webhooks/github`
verifies the raw-body HMAC, filters events, and creates deduplicated queued
runs. The status machine, sandbox, triage, patch generation, and approval gate
are still planned; the four status-machine tests remain strict `xfail`.

## Stack and commands

- Python 3.12 (managed by `uv`)
- FastAPI, Pydantic v2, Uvicorn
- pytest, ruff, mypy (strict)

Run from `api/`:

```bash
uv sync
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run uvicorn app.main:app --reload
```

All four checks are required before a commit. CI runs exactly these.

## Repository layout

```text
api/app/domain/      Status machine and core domain types
api/app/services/    Run orchestration, stores
api/app/routes/      HTTP endpoints
api/app/security/    Webhook signature verification
api/tests/           Pytest suite
fixtures/            Seeded-bug repositories for evaluation
docs/                Product truth, ADRs, designs, status
docs/designs/        Feature specifications (EGM)
graphify-out/        Generated code graph (ignored)
```

## Architectural boundaries

- `domain/` must not import FastAPI, HTTP, or persistence code.
- `services/` orchestrates domain objects and stores; it must not parse HTTP.
- `routes/` handles HTTP concerns only and delegates to services/security.
- `security/` contains pure verification functions with no framework imports.
- Persistent state is planned as SQLite (ADR 0001). M1 uses in-memory stores;
  restarting the process resets runs. This limitation must be stated in specs.
- Webhook dedupe is dual-keyed: `X-GitHub-Delivery` (checked before parsing) and
  the signed `workflow_run.id:run_attempt` (checked after validation). Ignored
  events and non-failure conclusions return 204 and never create a run.
- M1 is single-process only; do not add `--workers`.
- The approval gate comes **after** sandbox validation (ADR 0002).

## Documentation

- Product: `docs/PRODUCT.md`
- Requirements: `docs/REQUIREMENTS.md`
- Architecture: `docs/ARCHITECTURE.md`
- Decisions: `docs/DECISIONS.md` and `docs/adr/`
- Roadmap: `docs/ROADMAP.md`
- Current status: `docs/CURRENT-STATUS.md`
- Feature specs: `docs/designs/`

Substantial features use the Elephant-Goldfish workflow: draft under
`docs/designs/`, independent review, human approval, then implement.

## Security and deployment

- Never commit secrets. `GITHUB_WEBHOOK_SECRET` comes from the environment;
  `.env.example` contains only a placeholder.
- Verify the GitHub signature over the **raw request body**, using a
  constant-time comparison. Fail closed if the secret is not configured.
- The service binds to `127.0.0.1` in local development.
- Sandboxed execution is not implemented yet. Do not add code that executes
  model-generated code outside the planned sandbox boundary.

## Agent notes

- Read this file, the relevant spec, and the tests before changing code.
- Prefer the existing module boundaries; do not create a parallel app factory.
- Keep the strict `xfail` convention: when a feature lands, remove the marker
  in the same change, or CI will fail on XPASS.
- Report what was run, what passed, and what was not run.
