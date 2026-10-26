# Feature specification: M1 webhook intake

**Status:** Approved (revision 4)\
**Owner:** Ifteyaj Ahmed\
**Date:** 2026-10-26\
**Review status:** Third-pass readiness review complete; all blocking findings resolved\
**Approved by / date:** Ifteyaj Ahmed / 2026-10-26

## 1. Summary

Add the first authenticated entry point to `cicd-agent`: a GitHub webhook
endpoint that verifies the request signature, accepts only failed
`workflow_run` completions, and creates exactly one run per signed workflow
attempt while that run is retained in the bounded in-process store. This is the
foundation for triage, patch generation, sandbox validation, and the approval
gate.

Idempotency uses both the delivery ID and the signed workflow identity
(`workflow_run.id` + `run_attempt`). A replayed body with a fresh delivery ID
therefore maps to the original run.

## 2. Problem statement

The service currently exposes only `/healthz`. It cannot receive a CI failure,
and it has no idempotency boundary. GitHub retries deliveries, so a naive
endpoint would create duplicate runs and potentially duplicate sandbox work.
Unsigned requests, successful runs, and non-failure events must never create
repair work.

## 3. Goals and non-goals

### Goals

- Reject requests that are not signed with the configured secret.
- Accept only a completed GitHub Actions `workflow_run` whose conclusion is
  `failure` or `timed_out`.
- Create a run from a valid delivery, recording repository URL, commit SHA,
  workflow run ID, and attempt.
- Return the same run for a repeated delivery ID **or** a repeated signed
  workflow identity (`workflow_run.id` + `run_attempt`) while that run is
  retained by the store.
- Provide clear HTTP status codes for invalid input and missing configuration.
- Bound request size and in-process memory.

### Non-goals

- Triage, patch generation, sandbox execution, or publishing.
- Persistence across process restarts.
- Multi-worker or multi-replica operation. M1 is single-process only.
- Global rate limiting or per-client concurrency limits.
- GitHub App authentication or installation tokens.
- A web UI or dashboard.

## 4. Users and journeys

- **Repository owner:** configures the webhook secret, triggers a failing CI
  run, and expects one run for one failed workflow attempt.
- **Attacker / misconfigured sender:** sends an unsigned, tampered, malformed,
  or replayed request and cannot create unintended work.
- **Evaluator:** sees that signature verification, event filtering, and
  idempotency are tested, and that failure modes are explicit.

## 5. Requirements

Spec-local IDs are prefixed `W` to avoid colliding with `docs/REQUIREMENTS.md`.
M1 maps to project FR-1 through FR-4.

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-W1 | Verify `X-Hub-Signature-256` over the raw body using HMAC-SHA256 and the configured secret | Must |
| FR-W2 | Reject a missing, malformed, non-ASCII, wrong-algorithm, or mismatched signature with 401 | Must |
| FR-W3 | Fail closed with 503 when no usable secret is configured (absent, empty, whitespace, or `change-me`) | Must |
| FR-W4 | Require `X-GitHub-Event: workflow_run`; return 204 for `ping` and other supported-but-ignored events | Must |
| FR-W5 | Require `action=completed` and `conclusion` in `failure` or `timed_out`; return 204 for other completed conclusions | Must |
| FR-W6 | Extract `repository.clone_url`, `workflow_run.head_sha`, `workflow_run.id`, and `workflow_run.run_attempt`; validate all strictly | Must |
| FR-W7 | Create a queued run keyed by `X-GitHub-Delivery` and by the signed workflow identity (`workflow_run.id:run_attempt`); the guarantee holds while the run is retained | Must |
| FR-W8 | Return the original run for a repeated delivery ID after signature verification and **before** JSON parsing; return the original run for a repeated signed workflow identity after payload validation and event filtering | Must |
| FR-W9 | Return 400 for malformed JSON, 422 for a missing/invalid delivery-ID or event header or invalid fields, 413 for oversized bodies, 401 for a missing/malformed signature | Must |
| FR-W10 | Expose the run ID and duplicate flag in the response | Should |

## 6. Acceptance criteria

- [x] Given a valid signature, `workflow_run`, `action=completed`,
      `conclusion=failure`, and a valid payload, a run is created and the
      response is 202 with its run ID and `duplicate: false`.
- [x] Given the same delivery ID again, the response is 200 with the same run ID
      and `duplicate: true`; the store contains one run.
- [x] Given the same signed workflow identity with a **different** delivery ID,
      the response is 200 with the original run; the store contains one run.
- [x] Given a duplicate delivery with different or malformed content, the
      response is still 200 with the original run.
- [x] Given a duplicate delivery whose body would otherwise be ignored (for
      example `conclusion=success`), the response is 200 with the original run;
      the delivery lookup precedes event/action filtering.
- [x] Given a missing signature header, tampered body, `sha1=` prefix with a
      valid SHA-1 HMAC, `sha512=` prefix, uppercase digest, non-hex digest,
      non-ASCII digest, or malformed signature, the response is 401 and no run
      is created. Given a missing `X-GitHub-Delivery` or `X-GitHub-Event`, the
      response is 422.
- [x] Given no usable secret, the response is 503 and no run is created.
- [x] Given `ping`, a non-`workflow_run` event, a non-completed action, or
      `conclusion` in `success`/`cancelled`/`skipped`/`neutral`/`stale`/
      `action_required`, the response is 204 and no run is created.
- [x] Given malformed JSON on a **new** delivery, the response is 400 and no run
      is created.
- [x] Given a JSON value that is not an object, the response is 422.
- [x] Given a non-GitHub URL, a URL with credentials, a zero SHA, a short SHA,
      a missing workflow run ID, or a non-positive attempt, the response is 422
      and no run is created.
- [x] Given a request body over the 1 MiB limit, the response is 413 and no run
      is created.
- [x] Given concurrent requests with the same delivery ID or workflow identity,
      exactly one run is created; exactly one response is 202 and the others are
      200 with the same run ID.
- [x] Automated tests cover every case above and assert the store count.
- [x] The five existing webhook `xfail` tests pass without the marker. The four
      status-machine tests remain strict `xfail`.

### Implementation verification

Implemented on branch `harness/m1-webhook-intake` on 2026-10-26. Evidence:

- `uv run pytest -q` → 161 passed, 4 xfailed (the four status-machine tests).
- `uv run ruff check .` → pass; `uv run ruff format --check .` → 20 files.
- `uv run mypy` → pass, 12 source files.
- Live `uvicorn` smoke test: health 200, new delivery 202, duplicate 200,
  signed replay with a new delivery ID 200, `ping` 204, malformed JSON 400,
  valid-signature/ignore mismatch 401, missing event 422.
- The five original webhook `xfail` markers were removed in the same change;
  `test_webhook_dedupe.py` now passes `workflow_run_id` and `run_attempt` as the
  §10 contract requires.

## 7. Edge cases and failure states

| Case | Expected behaviour |
| --- | --- |
| Empty body with a valid signature | Parse fails → 400 |
| Empty or whitespace secret | 503, no body read |
| Secret exactly `change-me` | 503 (documented placeholder) |
| Secret with surrounding whitespace | Rejected as unusable (503); never silently trimmed for HMAC |
| `sha256=` with no digest | 401 |
| Uppercase hex digest | 401 (strict lowercase contract) |
| Non-hex or odd-length digest | 401, never 500 |
| Non-ASCII digest | 401, never 500 |
| `sha1=` with a valid SHA-1 HMAC | 401; SHA-256 is hard-coded |
| `sha512=` with a valid SHA-512 HMAC | 401 |
| Missing `X-GitHub-Delivery` or invalid characters/length | 422 |
| Missing `X-GitHub-Event` | 422 |
| `X-GitHub-Event: ping` | 204 after a successful JSON parse, before workflow-run shape validation |
| `X-GitHub-Event: push` or other event | 204 after a successful JSON parse, before workflow-run shape validation |
| `workflow_run` not completed | 204 after JSON parse and payload validation |
| Completed with `conclusion=action_required` | 204; approval-blocked, not a code failure |
| Missing `action` or `conclusion` | 422 |
| Duplicate delivery with a different payload | Return original run; log delivery ID and a content hash, not the body |
| Duplicate delivery with malformed JSON | Return original run (delivery lookup happens before parsing) |
| Duplicate delivery whose body would be ignored | Return original run (delivery lookup happens before event filtering) |
| Same workflow identity, new delivery ID | Return original run; signed replay protection |
| Repository clone URL ending in `.git` | Accepted and normalized by removing one `.git` suffix |
| Repository URL with credentials, non-HTTPS, or non-GitHub host | 422 |
| Commit SHA all zeros (branch deletion) | 422 |
| Body over 1 MiB | 413 before verification |
| Concurrent duplicate requests | One run; one 202, the rest 200 with the same run ID |
| Process restart | Dedupe is lost; documented limitation |
| Store cap reached (10,000 runs) | Oldest run evicted from both indexes; a later replay of an evicted run may create a new run |

## 8. Data model and validation

### Run

| Field | Type | Constraint |
| --- | --- | --- |
| `run_id` | `str` | UUID4, unique |
| `delivery_id` | `str` | Non-empty, `^[A-Za-z0-9-]{1,128}$` |
| `run_key` | `str` | `f"{workflow_run_id}:{run_attempt}"`, signed identity |
| `workflow_run_id` | `int` | JSON integer (not bool/float/string), `> 0` |
| `run_attempt` | `int` | JSON integer (not bool/float/string), `>= 1` |
| `repo_url` | `str` | HTTPS, host `github.com`, no userinfo/port/query/fragment, exactly `owner/repo` (one optional `.git` removed) |
| `commit_sha` | `str` | 40 or 64 lowercase hex, not all zeros |
| `status` | `RunStatus` | `QUEUED` in M1 |

`Run`, `RunStatus`, and `run_key` construction live in `app/domain/`.
`RunStatus` defines the full lifecycle enum so the later status machine can add
transitions without moving types. M1 uses only `QUEUED`; `transition` and
`IllegalTransition` are deliberately out of scope, so the four status-machine
tests remain strict `xfail`.

`workflow_run_id` and `run_attempt` are stored explicitly because later
milestones need them to fetch logs; `run_key` is derived, not parsed back.

Field strictness: `workflow_run.id` and `run_attempt` must be JSON integers;
`true`, `1.0`, and `"1"` are rejected with 422. The repository URL path must be
exactly two segments matching `^[A-Za-z0-9_.-]+$` each and must not contain
`.` or `..` segments; a trailing slash is rejected. The host comparison is
case-insensitive but the stored URL is normalized to lowercase `github.com`
without a trailing `.git`. A JSON body whose top-level value is not an object
(including `[]`, `"x"`, `1`, `null`) is a shape error → 422, not a syntax
error.

### Store contract

```python
class InMemoryRunStore:
    def __init__(self, max_runs: int = 10_000) -> None: ...
    def count(self) -> int: ...
    def get_by_delivery(self, delivery_id: str) -> Run | None: ...
    def get_by_run_key(self, run_key: str) -> Run | None: ...
    def insert(self, run: Run) -> None: ...   # evicts oldest when full
    def create_if_absent(self, run: Run) -> tuple[Run, bool]:
        """Atomically return the existing run for either key, or insert."""
```

The store keeps two indexes (`delivery_id`, `run_key`) pointing at the same
`Run`. Eviction removes the oldest run from both indexes. The cap bounds memory;
it is not a replay quota. `create_if_absent` holds the store lock across the
two lookups and the insert, which is the atomic boundary used by the service.

### Validation ownership

- HTTP boundary: required headers, body size, JSON syntax, payload shape.
- `app/security/signature.py`: header syntax and HMAC comparison. Total
  function: returns `False` for any malformed input, never raises.
- `app/services/runs.py`: `validate_delivery_id` (format), repo URL, commit SHA,
  workflow identity, and duplicate lookup. Raises `InvalidRunInput` for invalid
  fields. `create_from_delivery` calls the same validators.
- The route maps `InvalidRunInput` to 422.

## 9. API and integration contracts

### `POST /webhooks/github`

Headers:

- `X-Hub-Signature-256: sha256=<64 lowercase hex>` (required)
- `X-GitHub-Delivery: <1–128 chars, letters/digits/hyphen>` (required)
- `X-GitHub-Event: workflow_run` (required; `ping` and others return 204)
- `Content-Type: application/json` (advisory; not enforced in M1)

Accepted body (only fields used in M1):

```json
{
  "action": "completed",
  "workflow_run": {
    "id": 123456789,
    "run_attempt": 1,
    "head_sha": "0123456789abcdef0123456789abcdef01234567",
    "conclusion": "failure"
  },
  "repository": {"clone_url": "https://github.com/example/repo.git"}
}
```

Unknown extra fields are ignored. `push` payloads are not accepted in M1.

Responses:

| Status | Meaning | Body |
| --- | --- | --- |
| 202 | New run | `{"run_id": "...", "duplicate": false}` |
| 200 | Duplicate delivery or workflow identity | `{"run_id": "...", "duplicate": true}` |
| 204 | Ignored event / not a failure | empty |
| 400 | Malformed JSON on a new delivery | `{"detail": "..."}` |
| 401 | Missing/invalid signature | `{"detail": "invalid signature"}` |
| 413 | Body over 1 MiB | `{"detail": "payload too large"}` |
| 422 | Missing/invalid delivery-ID or event header, or invalid fields | `{"detail": "..."}` |
| 503 | Usable secret not configured | `{"detail": "webhook secret is not configured"}` |

### Processing order (invariant)

1. Check usable secret → 503. Do not read the body.
2. Check presence of the signature header → 401. Do not read the body.
3. Enforce `Content-Length` limit if present and parseable → 413. Ignore a
   malformed or duplicate `Content-Length`; the streaming cap still applies.
4. Read the body with a streaming 1 MiB cap → 413.
5. Verify the signature over the raw bytes → 401.
6. Validate `X-GitHub-Delivery` format → 422.
7. Look up the delivery ID; if present → 200 with the original run. (Nothing
   below runs; this is why a malformed retry body still returns 200.)
8. Require `X-GitHub-Event` → 422 if absent.
9. Parse JSON → 400. A non-object value is left for step 11 → 422.
10. If the event is not `workflow_run` → 204 (before payload shape validation).
11. Validate the `workflow_run` payload shape and extract repository URL,
    commit SHA, action, conclusion, and workflow identity → 422.
12. Filter `action == "completed"` and `conclusion in {failure, timed_out}`;
    otherwise → 204.
13. Look up the signed run key; if present → 200 with the original run.
14. Create the run atomically. If `created` is false due to a race, return 200
    with the existing run; otherwise 202.

Precedence rules made explicit:

- **Delivery ID outranks everything after signature verification.** A repeated
  delivery ID returns 200 before parsing, event filtering, or shape validation.
  It never returns 400, 422, or 204 for a body that is different from the
  original.
- **The run key is checked after filtering.** A repeated signed identity whose
  body is ignored (`success`, `action_required`, non-`workflow_run`) returns
  204, not 200; ignored events never create or claim a run.
- **Authentication outranks the duplicate fast path.** An unsigned or badly
  signed duplicate is 401, so the endpoint is not an unauthenticated run-ID
  oracle.
- **Size outranks authentication.** `Content-Length` and streaming limits are
  enforced before verification, so an unauthenticated client can distinguish
  413 from 401. This is accepted: it reveals nothing about stored runs.

This order ensures an unsigned request can never be parsed, a duplicate
delivery returns its original run even if the retry body is malformed or would
be ignored, and a signed replay with a new delivery ID is caught by the run key.

## 10. Architecture and component boundaries

- `app/domain/status.py`: `RunStatus` enum. No framework imports.
- `app/domain/run.py`: frozen `Run` dataclass and `run_key` helper. No framework
  imports.
- `app/security/signature.py`: pure `verify_github_signature(body: bytes,
  header: str | None, secret: str) -> bool`. No FastAPI import. Never raises.
- `app/services/runs.py`: `InMemoryRunStore`, `RunService`, `CreateResult`,
  `InvalidRunInput`. The service owns idempotency and domain validation. No
  HTTP import.
- `app/routes/webhooks.py`: raw-body route, ordered checks, error mapping. No
  direct store mutation.
- `app/config.py`: `Settings` with `github_webhook_secret: SecretStr | None`.
  Never raises at import.
- `app/main.py`: `create_app(run_service: RunService | None = None,
  webhook_secret: str | None = None) -> FastAPI`; module-level `app` remains.

### Service contract

```python
@dataclass(frozen=True)
class CreateResult:
    run: Run
    created: bool

    @property
    def run_id(self) -> str:
        return self.run.run_id

def validate_delivery_id(delivery_id: str) -> None: ...

class RunService:
    def __init__(self, store: InMemoryRunStore) -> None: ...
    def get_by_delivery(self, delivery_id: str) -> Run | None: ...
    def get_by_run_key(self, run_key: str) -> Run | None: ...
    def create_from_delivery(
        self,
        delivery_id: str,
        *,
        repo_url: str,
        commit_sha: str,
        workflow_run_id: int,
        run_attempt: int,
    ) -> CreateResult: ...
```

`create_from_delivery` performs the atomic lookup-and-insert via
`store.create_if_absent` and returns `created=False` for an existing delivery ID
or run key. The `CreateResult.run_id` property keeps the existing dedupe test's
`first.run_id` assertion valid. `validate_delivery_id` is the callable the route
uses at step 6; it raises `InvalidRunInput` and is also invoked by
`create_from_delivery`.

The existing `api/tests/test_webhook_dedupe.py` call is amended to pass
`workflow_run_id=123, run_attempt=1`; its `first.run_id == second.run_id` and
`store.count() == 1` assertions stay unchanged.

### Secret precedence

- If `create_app(webhook_secret=...)` is passed with a non-`None` value, use that
  value exactly. Passing `""` is therefore an explicit *unusable* secret and
  makes the app return 503; this is how the 503 test forces the state without
  mutating the environment.
- Otherwise (`None`, the default) read `Settings.github_webhook_secret`.
- The raw value keys the HMAC. A separate usability check rejects absent, empty,
  whitespace-only, and `change-me` values before any body read.

## 11. Security, privacy, accessibility, performance

- **Authentication:** HMAC-SHA256 only, hard-coded; strict header regex;
  `hmac.compare_digest` on ASCII bytes; all parse errors return 401.
- **Fail closed:** absent/empty/whitespace/`change-me` secret → 503. Recommend a
  random secret of at least 16 characters in the README.
- **Ordering:** secret and signature presence checked before body read; raw
  bytes verified before JSON parsing.
- **Replay:** the signed `workflow_run.id:run_attempt` is the primary idempotency
  key, so a captured body replayed with a new delivery ID returns the original
  run while it is retained. A legitimate re-run has a new `run_attempt` and is
  accepted.
- **Resource bounds:** 1 MiB per-request streaming cap; store capped at 10,000
  runs with oldest-first eviction. Eviction removes the idempotency record, so a
  replay of an evicted run may create a new run; the cap bounds memory and is
  not a replay quota. Per-client rate limiting is deferred to the edge.
- **Logging:** info level only: validated delivery ID, repo URL, run ID,
  duplicate flag, SHA-256 content hash. Never log headers, signature, secret, or
  body.
- **Privacy:** repository metadata only; no user data.
- **Accessibility:** no UI in scope.
- **Performance:** one 1 MiB-bounded HMAC, two index lookups, one insert; no I/O.
- **Deployment:** single-process only. Multi-worker operation requires a shared
  store and is out of scope.

## 12. Migration and compatibility

- No persisted data, so no migration.
- `/healthz` contract unchanged.
- `create_app()` keeps its no-argument default; tests may inject a service and
  secret.
- The in-memory store will later be replaced behind the same `RunService`
  interface; idempotency tests must survive that change.
- Existing webhook `xfail` tests become passing tests; status-machine tests stay
  `xfail` until their milestone.

## 13. Files and modules likely to change

- `api/app/domain/status.py` — new `RunStatus` enum.
- `api/app/domain/run.py` — new frozen `Run` dataclass and `run_key` helper.
- `api/app/security/signature.py` — new strict verifier.
- `api/app/services/runs.py` — new store, service, result, and error.
- `api/app/routes/webhooks.py` — new route.
- `api/app/config.py` — new settings.
- `api/app/main.py` — app factory wiring.
- `api/app/routes/__init__.py` — export router if needed.
- `api/tests/test_webhook_signature.py` — remove `xfail`; add malformed cases.
- `api/tests/test_webhook_dedupe.py` — remove `xfail`; add `workflow_run_id` and
  `run_attempt` arguments; keep `first.run_id`.
- `api/tests/test_webhook_route.py` — new endpoint tests.
- `api/tests/test_runs.py` — new service/store tests.
- `api/tests/test_config.py` — new settings tests (unusable secret handling).
- `README.md`, `docs/ARCHITECTURE.md`, `docs/CURRENT-STATUS.md`,
  `docs/DECISIONS.md`, `CLAUDE.md` — closeout; correct any text that claims M1
  is implemented before it is.
- `.env.example`, `docker-compose.yml` — wire `GITHUB_WEBHOOK_SECRET`.

## 14. Implementation steps

1. Add `app/domain/status.py` and `app/domain/run.py` (including `run_key`).
2. Add `InMemoryRunStore`, `RunService`, `CreateResult`, and `InvalidRunInput`
   with atomic check-and-insert under a `threading.Lock`; add unit tests.
3. Add `verify_github_signature` with strict header validation; convert and
   extend signature tests.
4. Add `Settings` with an optional `SecretStr`; never raise at import.
5. Add the raw-body route with the §9 processing order and error mapping.
6. Wire `create_app(run_service=None, webhook_secret=None)` while preserving
   `app = create_app()`.
7. Add route tests for 202, 200 (delivery and run key), 204 (ping, wrong event,
   success, action_required), 400, 401 (all digest variants), 413, 422
   (headers/fields/URL/SHA/workflow identity), and 503, each asserting store
   count.
8. Add a concurrency test: N threads, one 202, N-1 responses 200 with the same
   run ID, store count 1.
9. Run ruff, format, mypy, and pytest; update docs and `.env.example`.

## 15. Testing and verification plan

- Unit (signature): valid; tampered; missing; empty digest; uppercase; non-hex;
  non-ASCII; `sha1=` with a **valid SHA-1 HMAC**; `sha512=` with a valid SHA-512
  HMAC; oversized header; verifier never raises.
- Unit (service/store): same delivery twice → one run; same run key/new
  delivery → one run; different attempts → two runs; invalid delivery ID;
  invalid repo URL (including credentials and non-GitHub host); zero/short SHA;
  missing/non-positive workflow identity; store cap eviction from both indexes;
  concurrent same-delivery creation.
- Integration (route): every response code in §9; raw non-canonical body signed
  as sent; invalid signature + malformed JSON → 401; duplicate delivery +
  malformed JSON → 200; duplicate delivery whose body would be ignored → 200;
  same run key/new delivery → 200; non-object JSON → 422; no-run assertions via
  the injected store; concurrency statuses.
- Commands:

```bash
cd api
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest -q
```

- No new runtime dependencies. `hmac`, `hashlib`, `json`, `re`, and
  `threading` are stdlib; `httpx` and `pydantic-settings` are already present.

## 16. Observability and operations

- Log at info: validated delivery ID, repo URL, run ID, duplicate flag, content
  hash. Never log headers, signature, secret, or raw body.
- A 401/413/503 spike is an operational signal; no metrics are added in M1.
- Single worker only. Document the `uvicorn` command without `--workers`.

## 17. Alternatives and trade-offs

- **Pydantic body parameter:** rejected; FastAPI would parse before the handler,
  breaking verify-before-parse and turning malformed unsigned requests into 422.
- **Accept all events:** rejected; it would create repair runs for successful
  builds and pushes.
- **Delivery-ID-only dedupe:** rejected; the header is unsigned. The signed
  workflow run identity closes replay without conflating legitimate re-runs.
- **SQLite immediately:** rejected for M1; the service interface isolates the
  later migration (ADR 0001).
- **Accepting `sha1=`:** rejected; GitHub's current header is SHA-256, and
  accepting SHA-1 weakens the contract.

## 18. Open questions and decisions

- **Decided:** duplicate delivery or run key with different content returns the
  original run (idempotent), not 409.
- **Decided:** M1 accepts `workflow_run` `failure`/`timed_out` only; `push`,
  `action_required`, and successful runs are ignored.
- **Decided:** delivery IDs and event headers are unsigned inputs and are
  validated defensively; the signed run key is the replay boundary.
- **Open:** should the store cap be configurable per deployment? Default 10,000
  is sufficient for M1. **Resolved in revision 4:** not configurable in M1; the
  guarantee is qualified as “while retained”.

## 19. Review findings and resolution

Reviewers: four independent fresh-context sessions in round 1, two in round 2.
Reports are in `docs/designs/reviews/`.

### Round 1

| ID | Finding | Severity | Decision | Resolution |
| --- | --- | --- | --- | --- |
| R-01 | Pydantic body parsing before signature verification | High | Accept | Raw-body route; verify, then parse |
| R-02 | `RunStatus` placed in services, conflicting with `app.domain` | High | Accept | Moved to `app/domain/status.py` |
| R-03 | No event/action/conclusion filtering | High | Accept | `workflow_run` failure/timed_out only |
| R-04 | Non-atomic check-and-insert | High | Accept | One lock; concurrency test |
| R-05 | Non-ASCII/malformed signature can raise 500 | High | Accept | Strict regex, bytes, catch-all → 401 |
| R-06 | Missing/blank delivery ID; duplicate vs validation order | High | Accept | 422 for invalid ID; lookup before parse |
| R-07 | “Configured secret” undefined; `change-me` accepted | High | Accept | Unusable values → 503; `SecretStr` |
| R-08 | Unbounded body and store | High | Accept | 1 MiB cap; 10,000-run cap |
| R-09 | Service contract underspecified | Medium | Accept | `CreateResult`, explicit methods |
| R-10 | No proof signature covers raw bytes | Medium | Accept | Exact `content=` route test |
| R-11 | Weak URL/SHA validation | Medium | Accept | HTTPS GitHub URL, non-zero 40/64 SHA |
| R-12 | Requirement ID collision; doc status | Medium | Accept | `FR-W*`; architecture marked in review |
| R-13 | Process-lifetime guarantee unqualified | Low | Accept | Qualified in summary and §11 |
| R-14 | Unsigned delivery ID replay | High | Accept | Signed run-key idempotency |
| R-15 | Algorithm-confusion test used SHA-256 under `sha1=` | Medium | Accept | Valid SHA-1/SHA-512 HMAC tests |
| R-16 | Test plan omitted edge cases/no-run assertions | Medium | Accept | Expanded in §15 |

### Round 2

| ID | Finding | Severity | Decision | Resolution |
| --- | --- | --- | --- | --- |
| R-17 | Event/action filter ordered before JSON parse | High | Accept | Reordered: parse → validate → filter → create |
| R-18 | Real `clone_url` ends in `.git` | High | Accept | Accept and normalize optional `.git`; path rules defined |
| R-19 | `CreateResult` breaks `first.run_id` test | High | Accept | `CreateResult.run_id` property |
| R-20 | Duplicate race could return 202 | High | Accept | Branch on `created`; concurrency asserts one 202 |
| R-21 | `action_required` is not a code failure | Medium | Accept | Ignored with 204 |
| R-22 | Missing event/action/conclusion precedence | Medium | Accept | Missing event/action/conclusion → 422; ignored values → 204 |
| R-23 | Store API and eviction unspecified | Medium | Accept | Explicit store contract; both indexes evicted |
| R-24 | Content-Type required but unenforced | Low | Accept | Marked advisory in M1 |
| R-25 | Docs claimed M1 current before implementation | Low | Accept | Architecture marked “M0 current; M1 in review” |
| R-26 | Per-request cap is not global rate limiting | Low | Accept as residual risk | Documented in §11 and non-goals |

### Round 3 (final readiness)

Reviewer: one independent fresh-context session. Verdict before fixes: BLOCK.

| ID | Finding | Severity | Decision | Resolution |
| --- | --- | --- | --- | --- |
| R-27 | Duplicate lookup ordered after parse/validation, contradicting FR-W8 and the duplicate-malformed AC | High | Accept | Delivery lookup moved to step 7, before parse; run-key lookup at step 13; precedence stated |
| R-28 | `ping`/`push` would fail shape validation (422) before the event filter (204) | High | Accept | Event filter is step 10, before shape validation |
| R-29 | Duplicate delivery of an ignored body returned 200 vs 204 with no stated precedence | High | Accept | Delivery ID outranks filtering; run key is checked after filtering |
| R-30 | Existing dedupe test lacks `workflow_run_id`/`run_attempt` and would raise `TypeError` | High | Accept | Spec mandates amending the call; §10 documents it |
| R-31 | FR-W9 said 422 for “missing headers”, contradicting 401 for a missing signature | High | Accept | Status table split by header; `401` for signature, `422` for delivery/event |
| R-32 | “One run for the process lifetime” contradicted the 10,000-run eviction | Medium | Accept | Guarantee qualified as “while retained”; eviction documented |
| R-33 | No callable delivery-ID validator for step 6 | Medium | Accept | `validate_delivery_id` added to the service contract |
| R-34 | Unsigned duplicate lookup could become a run-ID oracle | High | Accept | Lookup remains after signature verification; stated explicitly |
| R-35 | Numeric/URL/JSON-shape strictness and the 503 test hook were ambiguous | Medium | Accept | Strict integer, URL path, non-object → 422, and `webhook_secret=""` rules added |
