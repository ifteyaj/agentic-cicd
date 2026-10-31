# ADR 0004: M1b test 12 merged to main early

Status: Accepted
Date: 2026-10-31

## Context
The branch harness/m1-webhook-intake carried M1a and then M1b commits.
Pull request #3 merged the branch into main as a whole (merge commit
5171d83). That brought feature commit c5db247, M1b test 12 (the dev-only
mock route), onto main before M1b was complete. The plan was that M1b
stays a draft pull request until test 5 (kill and restart while paused,
then approve) passes.

## Options considered
A. Revert the M1b commits on main through a new pull request.
B. Keep test 12 on main and record the deviation (chosen).
C. Rewrite history to remove the commits from main. Rejected: it changes
   shared history.

## Decision
Option B. Test 12 is guarded: POST /webhooks/mock exists only when
Settings.env == "dev", and the default is "production" (fail closed).
Tests on main at this commit: 163 passed, 4 xfailed; ruff, format, and
mypy pass. Tests 4 to 11 remain open. No behaviour is claimed complete
that is not tested.

For the rest of M1b, work continues on feature/m1b-pause-resume, branched
from main, as a draft pull request into main. It merges only when test 5
passes.

## Consequences
- main contains a route that is unreachable outside dev.
- The harness branch is retired for M1b work.
- docs/CURRENT-STATUS.md still reports M1b as open.
- Lesson: a branch with unfinished milestone work must not be merged with
   a normal merge. Use a draft pull request scoped to one milestone.
