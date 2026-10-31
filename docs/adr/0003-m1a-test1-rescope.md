# ADR 0003: Re-scope M1a exit test 1 to the signed GitHub route

Status: Accepted
Date: 2026-10-31

## Context
M1a exit test 1 read "mock webhook returns 202 with a run_id and a run
row exists". No mock route exists in api/app/. A search for "mock" in
api/app/ finds no route, and `pytest -k mock` selects 0 tests. The signed
route POST /webhooks/github already returns 202 with a run_id, and
api/tests/test_webhook_route.py lines 78-84 assert the run row exists.

## Options considered
A. Add a dev-only POST /webhooks/mock in M1a. Adds an unsigned entry
   point, needs a dev-only guard, and needs its own tests.
B. Test the signed GitHub route for test 1, and defer the mock route to
   M1b, where the CLI trigger command needs it.

## Decision
Option B. Test 1 is satisfied by the signed route. The dev-only mock
route moves to M1b with its own tests, including a test that it is
unavailable when the environment is not dev.

## Consequences
- No unsigned entry point exists in M1a, so the attack surface is unchanged.
- The CLI cannot create runs until M1b.
- The original wording of test 1 in the Master Brief is superseded for
  M1a. The Master Brief is not edited by this ADR; the owner will decide
  whether to update it.
- Evidence: api/tests/test_webhook_route.py lines 78-84;
  `uv run pytest -v tests/test_webhook_route.py` gives 79 passed.
