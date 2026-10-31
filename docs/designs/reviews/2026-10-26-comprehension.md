# Independent review — comprehension

Reviewer: fresh-context naive-reader reviewer (OpenCode subagent), 2026-10-26.
Target: revision 1 of `docs/designs/m1-webhook-intake.md`. No design
conversation.

## Findings

| ID | Severity | Section | Problem | Resolution |
| --- | --- | --- | --- | --- |
| H-1 | High | §10, §14, FR-6/8 | Service must return `.run_id` for the existing test but the route needs a created/duplicate signal; neither is defined. | Accepted. `CreateResult(run, created)` and explicit service contract. |
| H-2 | High | §8, §10, §13 | `RunStatus` in services conflicts with `app.domain` and the status-machine test. | Accepted. `app/domain/status.py`. |
| H-3 | High | §14 vs FR-6 | Ordered “fields → create” makes a malformed duplicate return 400/422 instead of the original run. | Accepted. Duplicate lookup happens before parsing. |
| M-1 | Medium | §9, §8 | No status for missing/empty delivery ID. | Accepted. 422. |
| M-2 | Medium | §10, FR-3 | If the secret is a required settings field, startup fails instead of returning 503; empty/whitespace undefined. | Accepted. Optional `SecretStr`; unusable values → 503. |
| M-3 | Medium | FR-4 | Precedence for `clone_url`/`html_url` and `after`/`head_sha` undefined. | Accepted. `clone_url` and `workflow_run.head_sha` only in M1. |
| M-4 | Medium | §5 | No event/conclusion filter, so any signed payload creates work. | Accepted. `workflow_run` failure filtering. |
| M-5 | Medium | §6 | Acceptance omits distinct deliveries, duplicate-different-payload, concurrency, malformed digests, missing delivery header, and no-run assertions. | Accepted. §6 and §15 expanded. |
| M-6 | Medium | §8, §9, §14 | “Validation at the HTTP boundary (Pydantic)” conflicts with manual raw-body parsing; error mapping undefined. | Accepted. Split ownership and explicit error mapping. |
| L-1 | Low | §18 | Open questions already answered by the requirements. | Accepted. Decisions recorded. |
| L-2 | Low | FR-7, §9 | 422 wording inconsistent for missing vs invalid fields. | Accepted. 422 for missing or invalid. |
| L-3 | Low | Architecture/status docs | Architecture claims M1 is current while status says in progress. | Accepted. Marked M1 in review. |

## Verdict

CHANGES REQUIRED at revision 1. Revision 2 defines the service contract,
domain ownership, duplicate ordering, secret semantics, event filtering, and
the missing tests.
