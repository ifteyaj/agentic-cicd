# Roadmap

**Last updated:** 2026-10-31

## Now — M1 intake and validation foundation

- [x] M0 scaffold, health endpoint, fixtures, CI
- [x] M1 webhook intake: signature verification, idempotent run creation
- [x] M1 status machine and illegal-transition protection
- [x] M1 sandbox validation loop as a fake adapter (up to 3 attempts); the real Docker sandbox is M2
- [x] M1 human approval gate after validation (publish pending)
- [x] SQLite persistence for run, attempt, and event rows

## Next — M2 sandbox

- [ ] Real Docker sandbox with the hardening controls from the brief
- [ ] Hostile fixture suite contained with saved logs

## Then — M3 agent core

- [ ] Typed tools only; schema-validated triage
- [ ] Repair loop with the 3-attempt cap and sandbox feedback
- [ ] LLM provider adapter with response cache and budget caps

## Then — M4 evaluation

- [ ] Triage classification over the seeded fixtures
- [ ] Patch generation with a recorded diff
- [ ] Eval harness that runs fully headless
- [ ] Baseline metrics for fixed / not-fixed / unsafe

## Later — M5 dashboard

- [ ] Three-screen Next.js dashboard

## Later — M6 GitHub

- [ ] Real GitHub integration: branch and PR creation

## Explicitly deferred

- Auto-merge — contradicts the human approval gate.
- Multi-tenant deployment — single-user capstone scope.
- Providers other than GitHub Actions — no requirement yet.

## Milestones

| Milestone | Outcome | Target | Status |
| --- | --- | --- | --- |
| M0 | Skeleton, health, fixtures, CI | 2026-10-26 | Done |
| M1 | Verified patch reaches approval gate | TBD | In progress (walking skeleton complete; fake sandbox adapter; real sandbox is M2) |
| M2 | Real Docker sandbox and hostile-suite containment | TBD | Planned |
| M3 | Agent core: triage and repair | TBD | Planned |
| M4 | Headless evaluation over fixtures | TBD | Planned |
| M5 | Three-screen dashboard | TBD | Planned |
| M6 | Real GitHub integration | TBD | Planned |
