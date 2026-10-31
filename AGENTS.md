# Project instructions: agentic-cicd (OpenCode, auto-loaded)

Keep this short. Durable product, architecture, decisions, and status are in
`CLAUDE.md` and `docs/`. This file tells OpenCode how to drive the project.

## Stack and commands (run from `api/`)

```bash
uv sync
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run uvicorn app.main:app --reload   # must bind 127.0.0.1
```

## How to use the harness here

- Read `CLAUDE.md`, `docs/ARCHITECTURE.md`, and the active spec under
  `docs/designs/` before changing code.
- Substantial features use an EGM-style spec: requirements, acceptance
  criteria, assumptions, edge cases — drafted and independently reviewed in a
  fresh context before implementation.
- Record review findings in the spec with IDs and resolutions; close the last
  readiness review before approval.
- Independent review and the verification ladder (`workflows/testing-and-review.md`)
  run when requested; if unavailable (tool, model, endpoint), record the gap
  verbatim in `docs/CURRENT-STATUS.md` rather than claiming success.

## Working constraints

- M1 is single-process: no `--workers`; one uvicorn worker; dedupe is in memory.
- Do not disable lint, format, or type checks to make a test pass.
- Do not add auto-merge or publish paths before sandbox validation and the
  approval gate.
- Specs change only with a new revision and resolution of findings.

## Additional context

- Product/requirements: `docs/PRODUCT.md`, `docs/REQUIREMENTS.md`
- Decisions: `docs/DECISIONS.md`
- Architecture: `docs/ARCHITECTURE.md`
- Status: `docs/CURRENT-STATUS.md`
- Specs: `docs/designs/`

## Do not

- Duplicate global rules here — they are auto-loaded from
  `~/.config/opencode/AGENTS.md`.
- Commit secrets; `GITHUB_WEBHOOK_SECRET` comes from the environment.
