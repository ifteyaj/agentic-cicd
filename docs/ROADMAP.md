# Roadmap

**Last updated:** 2026-10-31

## Now — M1 intake and validation foundation

- [x] M0 scaffold, health endpoint, fixtures, CI
- [x] M1 webhook intake: signature verification, idempotent run creation
- [x] M1 status machine and illegal-transition protection
- [ ] M1 sandbox validation loop (up to 3 attempts) — not yet implemented
- [x] M1 human approval gate after validation (publish pending)

## Next — M2 evaluation

- [ ] Triage classification over the three seeded fixtures
- [ ] Patch generation with a recorded diff
- [ ] Eval harness that runs fully headless
- [ ] Baseline metrics for fixed / not-fixed / unsafe

## Later — M3 operations

- [ ] SQLite persistence behind the repository layer
- [ ] GitHub App authentication
- [ ] Deployment runbook and observability
- [ ] Drift checks on design documents

## Explicitly deferred

- Auto-merge — contradicts the human approval gate.
- Multi-tenant deployment — single-user capstone scope.
- Providers other than GitHub Actions — no requirement yet.

## Milestones

| Milestone | Outcome | Target | Status |
| --- | --- | --- | --- |
| M0 | Skeleton, health, fixtures, CI | 2026-10-26 | Done |
| M1 | Verified patch reaches approval gate | TBD | In progress (walking skeleton complete; sandbox pending) |
| M2 | Headless evaluation over fixtures | TBD | Planned |
| M3 | Persistence and deployment | TBD | Planned |
