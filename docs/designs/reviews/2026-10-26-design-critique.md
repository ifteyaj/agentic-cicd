# Independent review — design critique

Reviewer: fresh-context design critic (OpenCode subagent), 2026-10-26.
Target: revision 1 of `docs/designs/m1-webhook-intake.md`.
Context provided: spec, source, tests, product/architecture/decision docs. No
design conversation.

## Findings

| ID | Severity | Location | Finding | Resolution |
| --- | --- | --- | --- | --- |
| R1 | High | FR-7, §8, §14, architecture | A Pydantic body is parsed before the handler, so malformed unsigned requests return 422 and the “verify before parsing” invariant is broken. | Accepted. Raw `Request` body, verify, then `json.loads`, then model validation. |
| R2 | High | §8, §10 vs architecture/tests | `RunStatus` in services conflicts with `app.domain` and the existing status-machine test imports. | Accepted. Moved to `app/domain/status.py`. |
| R3 | High | FR-4, PRODUCT, REQUIREMENTS | No event/action/conclusion filtering; successful workflow runs and pushes create repair runs; `ping` returns 422. | Accepted. `workflow_run` completed failures only; `ping`/ignored → 204. |
| R4 | High | §7, §14 | “Thread-safe dictionary” does not make check-and-insert atomic; no concurrency test. | Accepted. One lock around lookup+insert; concurrency test. |
| R5 | High | FR-2, §10 | `compare_digest` raises `TypeError` on non-ASCII strings; malformed headers can return 500. | Accepted. Strict regex, bytes, catch-all → 401. |
| R6 | Medium | FR-5/6, §7, §9 | Missing/blank delivery ID undefined; duplicate lookup after field validation conflicts with idempotent return. | Accepted. 422 for invalid ID; lookup before parse. |
| R7 | Medium | FR-3, `.env.example`, compose | “Configured secret” undefined; `change-me` would be accepted; Docker path never gets the secret. | Accepted. Absent/empty/whitespace/`change-me` → 503; `SecretStr`; compose wiring. |
| R8 | Medium | §7, §11, §16 | No body-size or store bound; unauthenticated allocation/CPU DoS. | Accepted. 1 MiB streaming cap; 10,000-run store cap. |
| R9 | Medium | FR-8, §10 | Service return type and created/duplicate signal not specified; route cannot avoid a race. | Accepted. `CreateResult(run, created)`, explicit methods. |
| R10 | Medium | §6, §15 | No test proves HMAC covers raw bytes; route tests could re-serialize. | Accepted. Post exact `content=` bytes and sign them. |
| R11 | Medium | §7, §8, §9 | Payload precedence and URL/SHA validation weak; zero SHA accepted; credentials in URL. | Accepted. `clone_url` only, HTTPS GitHub host, non-zero 40/64 SHA. |
| R12 | Low | Requirements/docs | FR IDs collide; architecture pre-claims M1; FR-8 priority conflict. | Accepted. `FR-W*`; architecture marked in review. |
| R13 | Low | §1, §3, §7 | “Exactly one run” reads as durable; it is process-local only. | Accepted. Qualified everywhere. |

## Verdict

Not implementation-ready at revision 1. Resolve R1, R2, R3, R4, R5, R7, R6,
and R10 before approval. Revision 2 records the resolutions in §19.
