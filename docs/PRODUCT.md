# Product

**Status:** Draft — capstone project\
**Owner:** Ifteyaj Ahmed\
**Last updated:** 2026-10-26

## Problem

A failing GitHub Actions run produces logs, not a fix. A developer must read the
logs, infer the cause, write a patch, and verify it — often for failures that
follow a small set of patterns. Automating the first pass is useful, but an
unverified model-generated patch is unsafe to publish.

## Target users

- **Primary:** a solo developer or small team maintaining a repository with CI.
- **Secondary:** a capstone evaluator inspecting the design, safety boundaries,
  and evaluation evidence.

## Value proposition

“When CI fails, get a patch that has already been tested in a sandbox, with a
human deciding whether to publish it.”

## Product boundaries

### In scope

- Receive a GitHub Actions failure event.
- Triage the failure and classify the likely cause.
- Propose a patch.
- Validate the patch in a sandbox (bounded attempts).
- Present a verified patch at a human approval gate.
- Record an evaluation trail for the capstone.

### Out of scope

- Auto-merging or auto-deploying changes.
- Multi-tenant operation.
- Replacing human code review.
- Supporting every CI provider in the first milestone.

## Success measures

| Measure | Target | How measured |
| --- | --- | --- |
| Seeded fixtures fixed | ≥ 3 of 3 | `eval/` run against `fixtures/` |
| Patches validated before approval | 100% | Run records and evaluation logs |
| Unsafe publish without approval | 0 | Audit of run state transitions |
| Webhook signature bypass | 0 in tests | Security test suite |

## Constraints

- Single laptop / small VPS deployment.
- SQLite rather than PostgreSQL/Redis (ADR 0001).
- Approval gate after sandbox validation (ADR 0002).
- Model-generated code must not run outside the sandbox boundary.

## Open questions

- [ ] Which LLM provider and budget for triage/patch generation?
- [ ] How are sandbox resource limits enforced and evidenced?
- [ ] Which GitHub event(s) are authoritative: `workflow_run` or `push`?
