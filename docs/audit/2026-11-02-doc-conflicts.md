# Documentation conflict audit — 2026-11-02

Audit only. No code, tests, configuration, or Master Brief content was changed.
Source of truth: `docs/master-brief.md` (Version 1.3). Compared files:
`README.md`, `docs/REQUIREMENTS.md`, `docs/ARCHITECTURE.md`, and
`docs/ROADMAP.md`.

Where this audit says "correct now", it means the behaviour evidenced by the
current repository (routes, stores, and tests), not a proposed fix. Conflicts
are recorded, not resolved, in this task.

## Conflicts

| ID | File and section | What the file says | What the Master Brief says | Correct now |
| --- | --- | --- | --- | --- |
| C-01 | `README.md` §Webhook intake (lines 44–46); `docs/ARCHITECTURE.md` §System context (line 12) | GitHub posts to `http://127.0.0.1:8000/webhooks/github` and the flow starts at `POST /webhooks/github`. | §7.1 (line 188) specifies `POST /api/webhooks/github`. | The implemented route is `/webhooks/github` (`api/app/routes/webhooks.py:71`). The docs match the code, but not the Master Brief's API contract. Either the route or the brief must change later; do not fix here. |
| C-02 | `docs/REQUIREMENTS.md` §Constraints (lines 34–36); §Out of scope for M1 (lines 44–47) | "M1 state is in memory and resets on restart"; persistence across restarts is out of scope for M1. | §2.1 (line 70) chooses SQLite (WAL) for app data; §14.1 test 5 (line 543) requires a paused run to survive a restart by loading from SQLite. | `SQLiteRunStore` persists runs, attempts, and events, and `api/tests/test_restart_survives.py` proves restart survival. However, `create_app()` still defaults to `InMemoryRunStore` when no `db_path` is supplied (`api/app/main.py:24–26`), so restart survival is explicit wiring/test only. The REQUIREMENTS statement about M1 scope is stale. |
| C-03 | `docs/ARCHITECTURE.md` §Failure modes (line 91) | Process restart: "In-memory runs are lost"; recovery is "Planned SQLite persistence". | §14.1 test 5 (line 543) requires restart survival via SQLite; §2.1 (line 70) chooses SQLite for state. | The SQLite store exists and restart survival is tested (`api/tests/test_restart_survives.py:27–61`). The row still describes only the in-memory test double/default fallback. |
| C-04 | `README.md` §Webhook intake (lines 59–60) | "M1 is single-process: deduplication is in memory and resets on restart." | §2.1 (line 70) uses SQLite for app data; §6 (line 173) makes `delivery_id` unique; §7.1 (line 188) dedupes on delivery ID. | The default `create_app()` uses `InMemoryRunStore`, so in-memory dedupe is accurate for default wiring. `SQLiteRunStore` also exists and enforces unique `delivery_id` when a `db_path` is supplied. README omits the SQLite path and conflicts with the brief's target state. |
| C-05 | `docs/ROADMAP.md` §Now — M1 (line 10); `README.md` §Status (line 30); `docs/REQUIREMENTS.md` (lines 20, 47); `docs/ARCHITECTURE.md` §System context (line 18), §Components (line 37), §Known limitations (line 106) | The sandbox validation loop is "not yet implemented"; sandbox execution is "still planned"; there is "no sandbox … implementation yet". | §14 M1 (line 527) requires fake adapters for all three ports; §14.1 test 8 (line 546) requires a stub forced to fail three times to end in `escalated`. | The fake validation loop exists: `RunService` accepts `stub_mode="fail"` and `api/tests/test_escalation.py` proves the three-attempt escalation. The real Docker sandbox is M2. The docs conflate the fake adapter with the real sandbox. |
| C-06 | `docs/ARCHITECTURE.md` §System context (line 21) | Human approval is marked `[planned]`. | §14.1 tests 4, 6, and 7 (lines 542, 544–545) require the pause, patch-hash rejection, and terminal-run rejection. | The approval state and endpoint are implemented (`api/app/routes/runs.py`), and a valid approval returns `501` because publishing is not implemented. The diagram is stale; §Known limitations (line 107) already says the gate exists. |
| C-07 | `docs/ROADMAP.md` §Next — M2 (lines 13–18), §Later — M3 (lines 20–25), §Milestones (lines 38–40) | M2 is evaluation (triage, patch generation, eval harness, baseline metrics); M3 is operations (SQLite persistence, GitHub App auth, deployment). | §14 (lines 528–533): M2 Sandbox, M3 Agent core (triage and repair), M4 Eval harness, M5 Dashboard, M6 Real GitHub, M7 Final evaluation. §2.2 (line 80) puts the GitHub App install flow in roadmap-only future work. | The Master Brief is the authoritative milestone plan. ROADMAP's numbering and content are stale and conflict with it. |
| C-08 | `docs/ROADMAP.md` §Later — M3 operations (line 22) | SQLite persistence behind the repository layer is M3 work. | §2.1 (line 70) chooses SQLite for app data; §14.1 test 5 (line 543) puts SQLite-backed restart survival in M1. | SQLite run, attempt, and event persistence is already implemented (`SQLiteRunStore`). M3 is agent core; only LangGraph checkpoint tables remain future work. The roadmap item is stale. |
| C-09 | `docs/ROADMAP.md` §Milestones (line 38) | M1 is "In progress (walking skeleton complete; sandbox pending)". | §14 (line 527) defines M1 as end-to-end with fakes, including a fake sandbox adapter; the real sandbox is M2. | M1's code-side exit tests pass (182 passed, 0 xfailed per `docs/CURRENT-STATUS.md`); "sandbox pending" belongs to the real M2 sandbox, not M1. The status wording is stale. |
| C-10 | `README.md` §Status (lines 13, 21–28) | "Milestone 1 — walking skeleton implemented"; the CLI item is only the welcome screen. | §14 M1 (line 527) requires "CLI client can create a run, watch it, and approve it". | The README's itemized list is accurate, but the headline overstates M1 against the brief's exit criteria: `api/app/cli.py` implements only the welcome/status commands, not create, watch, or approve. This is a scope conflict between the brief and the documented milestone state. |
| C-11 | `docs/ARCHITECTURE.md` §Data model (lines 59–64) | The M1 `Run` entity lists `run_id`, `delivery_id`, `run_key`, `workflow_run_id`, `run_attempt`, `repo_url`, `commit_sha`, `status`; no tenant or visibility fields. | §2.3 (line 84) says `repo_visibility` and `tenant_id` columns, a per-run budget object, and a repository allowlist are included now. | The SQLite `runs` table (`api/app/services/runs.py:292–307`) has no `tenant_id` or `repo_visibility`; no budget object or allowlist exists. The brief requires these cheap hooks now; the architecture and implementation omit them. |

## Coverage gaps (not direct contradictions)

These are omissions found while comparing the four files. They are recorded for
completeness and were not treated as conflicts because the docs do not state the
opposite.

- `README.md` §Status (lines 13–19) says "The service exposes" only `GET
  /healthz` and `POST /webhooks/github`. The code also exposes `GET
  /api/runs/{run_id}`, `POST /api/runs/{run_id}/approve`, `GET
  /api/runs/{run_id}/events`, and the dev-only `POST /webhooks/mock`
  (`api/app/routes/`). The Master Brief §7.1 lists the runs endpoints and
  `/api/webhooks/mock`.
- The Master Brief §7.1 (line 196) requires RFC 7807 problem JSON with stable
  `code` values. The implementation returns `{"detail": ...}`
  (`_error()` in `api/app/routes/webhooks.py` and `runs.py`); the docs do not
  mention an error format.
- The Master Brief §2.3 (line 84) and §7.1 (line 188) require a configured
  repository allowlist. No doc in this set describes it, and no allowlist is
  enforced in the current routes.
- The Master Brief §6 (lines 171–180) lists `triage_results`, `approvals`,
  `blobs`, `eval_cases`, and `eval_results` tables. `docs/ARCHITECTURE.md`
  describes only the M1 run, attempt, and event rows. This is expected for M1
  but should be stated as a milestone gap rather than a complete data model.

## Items checked and found consistent

- Gate order: test first, then approve. `README.md` (lines 5–7, 30–31),
  `docs/REQUIREMENTS.md` (FR-7/FR-8), `docs/ROADMAP.md` (line 11), and
  `docs/ARCHITECTURE.md` (lines 106–107) agree with §2.1 (line 68) and the M1
  tests.
- Status names and transitions: `README.md` line 23's "15 legal transitions"
  matches `api/app/domain/status.py`; the enum matches §4.3 (line 122).
- Publish remains unimplemented and a valid approval returns `501`; this is
  stated consistently in `README.md`, `docs/REQUIREMENTS.md`, and
  `docs/ARCHITECTURE.md`, and is consistent with publishing being later work.
