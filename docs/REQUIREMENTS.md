# Requirements

**Status:** Implemented for FR-1 through FR-4\
**Last updated:** 2026-10-26

## Functional requirements

| ID | Requirement | Priority | Acceptance summary |
| --- | --- | --- | --- |
| FR-1 | Receive a GitHub Actions failure webhook | Must | Valid signed request creates exactly one run |
| FR-2 | Reject unsigned or tampered requests | Must | 401, no run created |
| FR-3 | Deduplicate GitHub redeliveries | Must | Same delivery ID or signed workflow attempt returns the original run |
| FR-4 | Record the run's repository and commit | Must | Run exposes repo URL and commit SHA |
| FR-5 | Triage a failure from logs | Should | Classification with evidence |
| FR-6 | Propose a patch | Should | Unified diff against the failing repo |
| FR-7 | Validate the patch in a sandbox | Must | Sandbox result stored on the run |
| FR-8 | Require human approval after validation | Must | No publish transition without approval |
| FR-9 | Publish an approved patch | Could | PR or branch push after approval |

M1 implements FR-1 through FR-4. FR-5 through FR-9 remain planned.

## Non-functional requirements

| ID | Requirement | Target | Verification |
| --- | --- | --- | --- |
| NFR-1 | Signature comparison is constant-time | No early exit on mismatch | Code review + `hmac.compare_digest` |
| NFR-2 | Fail closed without a configured secret | 503, no run | Route test |
| NFR-3 | Deterministic tests | No network, no wall-clock dependence | Test suite |
| NFR-4 | Type and lint clean | mypy strict, ruff clean | CI |
| NFR-5 | Webhook body is not logged with secrets | No raw body at info level | Code review |

## Constraints

- M1 state is in memory and resets on restart (ADR 0001 covers the later SQLite
  migration).
- The service must not execute model-generated code; no sandbox yet.

## Dependencies

- GitHub webhook delivery semantics (`X-GitHub-Delivery`,
  `X-Hub-Signature-256`).
- A configured `GITHUB_WEBHOOK_SECRET`.

## Out of scope for M1

- Persistence across restarts.
- Triage, patch generation, sandbox execution, and publishing.
- GitHub App installation tokens.
