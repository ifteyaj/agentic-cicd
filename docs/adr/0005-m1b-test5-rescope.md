# ADR 0005: Re-scope M1b test 5 to restart survival

Status: Accepted
Date: 2026-10-31

## Context
Master Brief section 14.1 test 5 read: "Kill the server while paused,
restart, approve, and the run completes." M1b has no approve step, so the
full test cannot pass in this milestone. The persistence claim, that a
paused run survives a restart, is now proven by
api/tests/test_restart_survives.py. Approval is a separate behaviour and
belongs to the approval test.

## Options considered
A. Keep test 5 open until the approval step exists.
B. Re-scope test 5 to restart survival and close it now (chosen).
C. Implement a placeholder approve step to satisfy the original wording.
   Rejected: it would be invented behaviour with no spec.

## Decision
Option B. Test 5 now reads: a paused run survives a process restart, is
loaded from SQLite by a new store instance, and remains AWAITING_APPROVAL.
The approve-and-complete behaviour moves to the approval tests (6 and the
approval flow).

## Consequences
- Proven: the run row survives restart. Evidence: tests/test_restart_survives.py.
- Not proven in M1b: LangGraph checkpoint persistence (no checkpoint
  tables), any index on status, and approval or completion after restart.
- Persistence claim in the thesis must be limited to the run row.
