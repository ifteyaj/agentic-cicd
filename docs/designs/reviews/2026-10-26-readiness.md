# Independent review — implementation readiness

Reviewer: fresh-context implementation-readiness reviewer (OpenCode subagent),
2026-10-26. Target: revision 1 of `docs/designs/m1-webhook-intake.md`. No design
conversation.

## Findings

| ID | Severity | Section | Issue | Resolution |
| --- | --- | --- | --- | --- |
| R1 | High | §10, §14.1 | `RunStatus` placement conflicts with architecture and tests. | Accepted. Domain module. |
| R2 | High | §8, §14.4 | Pydantic body validation runs before the handler, breaking signature-first ordering. | Accepted. Raw body, manual parse. |
| R3 | Medium | §6, §15 | Negative tests do not assert “no run created”. | Accepted. Store-count assertions. |
| R4 | Medium | §14.3–4 | App factory wired before the route exists. | Accepted. Steps reordered. |
| R5 | Medium | §8, §9 | Payload model, precedence, and 422 mapping undefined. | Accepted. Explicit model and validation ownership. |
| R6 | Medium | §7 | Duplicate with malformed payload would be validated first. | Accepted. Lookup before parse. |
| R7 | Medium | §15 | Test plan omits digest variants, fallbacks, concurrency. | Accepted. Expanded. |
| R8 | Low | §10, §14.3 | Settings could raise at import, breaking `/healthz`. | Accepted. Optional secret; no import-time failure. |
| R9 | Low | §13 | Closeout misses README, architecture status, and xfail count. | Accepted. Closeout list expanded. |
| R10 | Low | §15 | Commands omit `uv sync --frozen`; dependency claim unstated. | Accepted. Commands and dependency note added. |

## Verdict

NOT READY at revision 1. Revision 2 resolves the domain ownership, raw-body
ordering, service contract, negative-test assertions, and closeout gaps.
