# M1a exit tests 1–3 — verification report

Verify only. No code, tests, specs, or configuration changed. No commit created.
Working directory: `api/`. No `.env` read or secret printed.

## 1. Test 1 — "Mock webhook returns 202 with a run_id, and a run row exists."

### 1a. App search for a mock route

Command: `grep -RniE "mock|webhooks/mock|ENV|dev" api/app/` (run from `api/`)

Result (all non-cache matches):
- `api/app/config.py:1` docstring "Environment-backed settings."
- `api/app/config.py:13` `model_config = SettingsConfigDict(env_file=".env", extra="ignore")`

No route, path, or token contains `mock`, `webhooks/mock`, or dev-only gating. There is
no mock webhook route in `api/app/`. Only `POST /webhooks/github` exists
(`api/app/routes/webhooks.py:68`) plus `GET /healthz` (`api/app/main.py:20`).

### 1b. Document requirements for a mock route

- `docs/designs/m1-webhook-intake.md`: search for `mock`, `ENV`, `dev` found only
  "triggers" in a user-journey line (`§4`). The routing contract requires a single
  route, `POST /webhooks/github` (`§9`, line 229). No mock endpoint is specified.
  Quoted requirement: `POST /webhooks/github` responses include `202 | New run |
  {"run_id": "...", "duplicate": false}`. The implementation-verification section
  lists "new delivery 202", not a mock route.
- Master Brief: `docs/master-brief.md` does not exist. Closest equivalents checked
  (`docs/PRODUCT.md`, `docs/REQUIRES.md` typo searched, `docs/REQUIREMENTS.md`,
  `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`) contain no mock-route requirement
  and no `ENV=dev` gating. `grep` for `mock|ENV=|dev mode|dev-only|trigger` found
  only "triggers a failing CI" in `PRODUCT.md`.

### 1c. Dev-only gating

Not applicable: no mock route exists, and no `ENV`-based enablement code exists in
`api/app/`. Settings are environment-backed (`pydantic-settings`), with only
`github_webhook_secret` defined (`api/app/config.py:12-16`); there is no `ENV`
field.

### 1d. Tests named with "mock"

Command: `uv run pytest -v -k "mock"` (from `api/`)

Output (tail):
```
collected 165 items / 165 deselected / 0 selected
====================== 165 deselected, 1 warning in 0.54s ======================
```
No tests match "mock".

### 1e. Route tests for 202 and run row

Command: `uv run pytest -v tests/test_webhook_route.py`
Result: `79 passed, 1 warning in 0.93s`.

Evidence in `api/tests/test_webhook_route.py`:
- Line 78: `assert response.status_code == 202`
- Line 81: `assert body["duplicate"] is False`
- Line 82: `assert store.count() == 1`
- Line 83: `run = store.get(body["run_id"])`
- Line 84: `assert run is not None`

These prove a signed `POST /webhooks/github` with default fixture payload returns 202
with `run_id`, that `run_id` resolves to a stored `Run`, and that the store holds
one run. This is the signed GitHub route, not a mock route.

Verdict: NOT PROVEN for the specifically named mock route; the equivalent 202 + run
row behaviour is PROVEN on `POST /webhooks/github`.

## 2. Test 2 — "Same delivery ID twice creates one run."

### 2a. Command and output

Command: `uv run pytest -v tests/test_webhook_dedupe.py`

Output:
```
tests/test_webhook_dedupe.py::test_same_delivery_id_creates_one_run PASSED [100%]
============================== 1 passed in 0.02s ==============================
```

### 2b. Assertions in the test body

`api/tests/test_webhook_dedupe.py`:
- Line 20: `assert first.run_id == second.run_id`
- Line 23: `assert store.count() == 1`

It also asserts `first.created is True` (line 21) and `second.created is False`
(line 22). Both required conditions (same run_id returned; exactly one run in
store) are asserted.

### 2c. HTTP route or service layer?

Service layer only. The test constructs `InMemoryRunStore()` and `RunService`
directly and calls `service.create_from_delivery(...)`; no `TestClient` or HTTP
call is used. HTTP-route coverage for the same behaviour exists separately in
`api/tests/test_webhook_route.py::test_repeated_delivery_returns_original_run`
(lines 97-100), which asserts first 202, second 200, same `run_id`, and
`store.count() == 1`.

## 3. Test 3 — "Valid HMAC passes; tampered body or bad signature returns 401."

### 3a. Command and output

Command: `uv run pytest -v tests/test_webhook_signature.py tests/test_webhook_route.py`

Output (tail):
```
======================== 99 passed, 1 warning in 1.01s ========================
```

### 3b. Route-level tampered body -> 401; valid signature -> 202/200

`api/tests/test_webhook_route.py`:
- `test_tampered_body_is_rejected` lines 188-194, including
  line 193: `assert response.status_code == 401` and line 194:
  `assert store.count() == 0`.
- `test_valid_delivery_creates_run` lines 78-82: line 78
  `assert response.status_code == 202`.
- `test_repeated_delivery_returns_original_run` lines 97-98: line 97
  `assert first.status_code == 202`, line 98 `assert second.status_code == 200`.

An invalid signature losing to malformed JSON is also covered by
`test_invalid_signature_wins_over_malformed_json` (route-level 401).

### 3c. Missing signature header at route level

`test_invalid_signatures_are_rejected` is parametrized with `None` and asserts
route-level 401 (`api/tests/test_webhook_route.py:178` param values;
assert at line 185: `assert response.status_code == 401`). Missing signature
returns 401 without creating a run (`store.count() == 0`).

## Full suite

Command: `uv run pytest -q`

Output (tail):
```
161 passed, 4 xfailed, 1 warning in 1.03s
```

xfail markers remaining: 4, all in `tests/test_status_machine.py` (lines 4, 21, 28, 36).

## Verdict table

| Test | Verdict | Evidence (file, line, command output) | Gap, if any |
| --- | --- | --- | --- |
| Test 1: mock webhook 202 + run row | NOT PROVEN (mock route absent) | No `mock` match in `api/app/` (search, file:line above); no mock tests (165 deselected by `-k "mock"`); `POST /webhooks/github` 202 + `store.get(run_id)` is not None + `store.count() == 1` at `api/tests/test_webhook_route.py:78-84`. Equivalent behaviour exists only on the signed GitHub route. | The mock route and any `ENV=dev` gating do not exist. Test1 as literally named is not implementable today. |
| Test 2: same delivery ID -> one run | PARTIAL (service layer) | `api/tests/test_webhook_dedupe.py:20` (`assert first.run_id == second.run_id`); line 23 (`assert store.count() == 1`); command `uv run pytest -v tests/test_webhook_dedupe.py` -> 1 passed. Route-level equivalent at `api/tests/test_webhook_route.py:97-100`. | The cited test exercises the service layer, not HTTP. Store is in-process only. |
| Test 3: valid HMAC passes; tampered/bad signature -> 401 | PROVEN | `api/tests/test_webhook_route.py:193-194` (tampered body -> 401, count 0); lines 78, 97, 98 (valid -> 202/200); invalid signature with `None` parametrized -> 401. Combined command `uv run pytest -v tests/test_webhook_signature.py tests/test_webhook_route.py` -> 99 passed. | None at route level. |

## Test 1 — options found in the spec and which the spec supports

No mock route is defined in any spec found in this repository. The only route
documented by `docs/designs/m1-webhook-intake.md` is `POST /webhooks/github`
(`§9`, processing order in `§9` and `§13`), with `202` for a new run and `200`
for a duplicate delivery/workflow identity. The Master Brief
(`docs/master-brief.md`) is absent; the closest equivalent documents
(`docs/PRODUCT.md`, `docs/REQUIREMENTS.md`, `docs/ARCHITECTURE.md`,
`docs/ROADMAP.md`) do not require a mock webhook or `ENV=dev` gating.

Therefore, among the options referenced:

- Option (a) "add a dev-only mock route in M1a": not supported by any spec or file
  currently in the repository; would be a new, unspecified route, env var, and test.
- Option (b) "re-scope Test 1 to the signed GitHub route": supported by the
  existing approved spec, because the 202 + run row behaviour that Test 1 checks is
  exactly what `docs/designs/m1-webhook-intake.md §9` requires and
  `api/tests/test_webhook_route.py::test_valid_delivery_creates_run` verifies.

No choice is made here; the report records only the spec-supported facts.
