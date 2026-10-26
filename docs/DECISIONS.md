# Decisions

Durable project decisions, newest first. Long-form decisions live in `docs/adr/`.

## 2026-10-26 — Adopt the AI coding harness for this repository

**Status:** Accepted\
**Context:** The project needs a repeatable path from idea to reviewed
specification, tested implementation, and maintained documentation.\
**Decision:** Use the global harness: EGM for substantial specs and independent
review, Matt Pocock skills for implementation discipline, Graphify for codebase
navigation, and the Markdown docs in `docs/` as project truth.\
**Alternatives:** Ad-hoc prompting; a second planning framework (deferred to
avoid competing workflows).\
**Consequences:** Substantial features require a spec under `docs/designs/` and
a review before implementation. Small fixes still go direct.\
**Links:** Global harness `~/ai-dev-stack/ai-dev-stack`.

## 2026-10-26 — M1 webhook intake uses in-memory dual-key idempotency

**Status:** Accepted for M1\
**Context:** M1 needs to receive and deduplicate GitHub deliveries before
persistence is implemented. The delivery header is unsigned and can be changed
by a replayer, so a delivery ID alone is not a sufficient replay boundary.\
**Decision:** Key runs by both `X-GitHub-Delivery` and the signed workflow
identity (`workflow_run.id` + `run_attempt`) in an in-memory store. A repeated
delivery returns the original run before parsing; a repeated signed identity
returns the original run after payload validation. Replace with SQLite behind
the same service interface in a later milestone.\
**Alternatives:** SQLite immediately (more work, not needed to prove the
contract); delivery-ID-only dedupe (a captured body replayed with a new delivery
ID would create a second run); no deduplication (duplicate runs on GitHub
retries).\
**Consequences:** Runs are lost on restart. The store is capped at 10,000 runs,
so the guarantee holds while a run is retained. The dual-key contract and tests
remain valid when the store is replaced.\
**Links:** `docs/designs/m1-webhook-intake.md`, ADR 0001.

## Existing architecture decisions

- [ADR 0001: SQLite instead of PostgreSQL and Redis](adr/0001-sqlite-over-postgres.md)
- [ADR 0002: Approval gate after sandbox validation](adr/0002-gate-after-validation.md)
