# Master Brief: Agentic CI/CD Orchestration Platform

*Master prompt and specification for the AI engineer, plus the evidence plan for the thesis. Version 1.2. Supersedes the earlier spec and quick-start documents wherever they conflict.*

## 0. How to Use This Document

This is the single source of truth. It does two jobs: it is the standing instruction set for the AI engineer who builds the system, and it defines what must be documented and measured for the thesis. Read all of it before writing any code. Work with the human owner (the student) one milestone at a time.

### 0.1 Operating rules for the AI engineer

| # | Rule |
| --- | --- |
| 1 | **Tests first.** Write each milestone’s exit tests (Section 14) before the implementation, watch them fail, then make them pass. |
| 2 | **Never guess.** If a requirement is ambiguous, stop and give 2 to 3 options with trade-offs, then wait for the owner. |
| 3 | **Small steps.** One milestone at a time, one coherent change per pull request, each linking the exit tests it satisfies. |
| 4 | **Respect the ports.** Graph code depends only on `SandboxPort`, `LLMPort`, and `PublisherPort`. It never imports Docker or an LLM SDK. |
| 5 | **Never weaken a security control** (Section 9) to make a test pass. If a control blocks progress, raise it with the owner. |
| 6 | **No secrets** in git, logs, events, prompts, or the sandbox. |
| 7 | **Record decisions** as short ADRs in `docs/adr/` (template in Section 15). |
| 8 | **Preserve evidence.** Logs, results, and measurements feed the thesis and must be reproducible (Section 16). |
| 9 | **No scope creep.** Anything in Section 2.2 (non-goals) needs the owner’s explicit approval. |
| 10 | **Be candid.** Report failures, flaky tests, and weak results honestly. Never tune on the held-out set. |

### 0.2 Definition of done (every task)

- Tests written first, passing locally and in CI.
- Lint, formatting, and type checks clean.
- No new secrets, no weakened controls, no unpinned dependencies.
- Relevant docs and ADRs updated.
- Any output useful as thesis evidence is saved in a reproducible form.

## 1. Project Overview

### 1.1 Problem

When a CI build fails, developers spend time reading logs and locating the cause. LLM agents can propose fixes, but unverified patches waste reviewer attention, and running model-generated code against real repositories is a security risk.

### 1.2 Product

A self-hosted platform that reacts to a failed pytest build by triaging the failure, proposing a patch, and verifying it in a hardened Docker sandbox (up to 3 attempts). Only a verified patch reaches a human, who approves or rejects it. Approval pushes a branch and opens a pull request. Nothing is pushed without approval.

### 1.3 Thesis statement (draft)

A structured triage-then-repair pipeline with sandbox feedback and a human approval gate fixes more Python test failures, with fewer unsafe or test-tampering patches, than a single-shot LLM given the same failure log.

### 1.4 Research questions and hypotheses

| RQ | Question | Hypothesis |
| --- | --- | --- |
| RQ1 | Does structured triage improve the fix rate over a naive single-shot baseline? | H1: triage plus repair beats the baseline |
| RQ2 | Does sandbox feedback in the retry loop improve the fix rate? | H2: the full pipeline beats triage plus repair without feedback |
| RQ3 | Does the sandbox contain hostile inputs and injected instructions? | H3: zero escapes and zero secret leaks across the hostile test suite |
| RQ4 | What do the improvements cost in tokens, dollars, and seconds? | Reported, not hypothesised |

**Primary contribution:** agent quality (RQ1, RQ2). **Supporting:** isolation rigor (RQ3), cost and latency (RQ4). A negative result is acceptable if it is measured honestly and analysed.

## 2. Locked Decisions and Scope

### 2.1 Decisions

| Area | Decision |
| --- | --- |
| Language scope | Python and pytest only; fixtures use pure-Python dependencies |
| LLM | Hosted API; provider chosen in M3 behind `LLMPort`; only the owner’s own repos and fixtures are ever sent to it |
| Sandbox | Local Docker, hardened per Section 9.2; no E2B |
| Hosting | M1 Mac (8 GB) for development; a hardened Linux VPS for eval and sandbox runs; GitHub Actions for CI |
| Frontend | Next.js, three screens, built only after the eval harness exists (M5) |
| Gate order | **Test first, then approve.** A human only ever sees verified patches |
| Corpus | 18 cases: about 12 synthetic and 6 real, with a dev and held-out split |
| State | SQLite (WAL) for app data and for LangGraph checkpoints, in separate files |
| Streaming | Server-sent events backed by an `events` table |
| Repository | Public on GitHub |
| Windows | CI-tested with a fake sandbox, plus the dashboard in a Windows browser; the full Windows sandbox is untested and documented as such |
| Demo | Live demo required, with a recorded fallback and a cached-LLM mode |

### 2.2 Non-goals (MVP)

Multi-language support; GitLab; E2B; accounts, billing, subscriptions, multi-tenancy, RBAC; hosting customers’ private repos; selective test execution; a separate injection-validator LLM; auto-merge; inline diff editing.

**Roadmap only (thesis future work):** private-repo subscription tier, GitHub App install flow, stronger isolation (gVisor, Firecracker).

### 2.3 Cheap hooks included now

`repo_visibility` and `tenant_id` columns (single local tenant), a per-run budget object, and a configured repository allowlist.

## 3. Users and Jobs to Be Done

| Persona | Need |
| --- | --- |
| **Developer** (solo or small team, Python project) | After a red CI build, get a safe, reviewable fix proposal instead of debugging from scratch |
| **Thesis examiner** | Reproduce the results and verify the security claims |
| **Owner** | Run evals, record metrics, and give a reliable live demo |

**Core JTBD:** When my pytest suite fails, diagnose the cause and propose a verified patch, so I only have to review and approve.

**Value proposition:** verified patches only, fully traceable, and nothing pushed without approval.

## 4. Architecture

### 4.1 Components

| Component | Responsibility |
| --- | --- |
| Event gateway (FastAPI) | Verifies webhook signatures, normalises payloads (`clone_url`, `git_ref`, `commit_sha`, `repository_context`), creates a run, returns `202` with `run_id` |
| Orchestrator (LangGraph) | Deterministic node sequence with LLM decisions inside nodes; checkpoints at every transition; pauses at the approval gate |
| Agents | Triage agent (typed diagnosis) and repair agent (patch and commit message) |
| Tool registry | Typed, restricted tools; no generic shell |
| Sandbox runtime | A disposable, hardened Docker container per attempt |
| Dashboard (Next.js) | Run list, run detail with live trace and diff, approval gate |
| Eval harness | Runs the corpus across configurations and trials; emits results and charts |

### 4.2 Graph

`ingest → provision_sandbox → triage → repair → validate`

- Validate passes with no violations: `await_approval` (interrupt). Approve leads to `publish` and done. Reject leads to done (rejected).
- Validate fails and attempts are below 3: back to `repair` with a truncated failure summary.
- Validate fails at 3 attempts, or the budget is exceeded: `escalate`, then done.

### 4.3 Run status machine

Statuses: `queued`, `triaging`, `repairing`, `validating`, `awaiting_approval`, `publishing`, `completed`. Terminal: `escalated`, `rejected`, `failed`. All transitions live in one function in `domain/`. Illegal transitions raise an error. Every legal transition has a test.

### 4.4 Ports and adapters

| Port | Skeleton adapter (M1) | Real adapter |
| --- | --- | --- |
| `SandboxPort` | Fake, scripted pass or fail | Docker (M2) |
| `LLMPort` | Fake, canned outputs | Cached wrapper, then provider adapter (M3) |
| `PublisherPort` | Local git branch plus summary | GitHub branch and PR (M6) |

### 4.5 Graph state

State holds references and small values only; large content lives in the database.

| Field | Notes |
| --- | --- |
| `run_id` | Also the LangGraph `thread_id` |
| `repo` | `clone_url`, `git_ref`, `commit_sha` |
| `failure_ref` | ID of the stored failing-test log |
| `triage` | Typed result, or none |
| `attempt_n` | 0-based, hard maximum of 3 |
| `current_attempt_id` | Points at the `attempts` row |
| `last_failure_summary` | Truncated feedback for the next repair attempt |
| `validation` | `passed`, `violations[]`, `duration_ms` |
| `approval` | `decision`, `attempt_id`, `patch_sha256` |
| `budget` | Token cap, tokens used, wall-clock deadline |
| `terminal_reason` | `completed`, `escalated`, `rejected`, or `failed` |

**Rules:** all state types are Pydantic models with explicit serialisation. No open handles, containers, or clients in state. Sandbox handles are re-derived from `run_id` on resume.

### 4.6 Pause and resume

`await_approval` calls LangGraph `interrupt()`. `POST /approve` validates the run state and the patch hash first, then resumes with the decision. Resuming a run that is not paused returns `409`. A server restart while paused must lose nothing.

## 5. Technology Stack

| Concern | Choice |
| --- | --- |
| Python | 3.12, managed by `uv` with a lockfile |
| API | FastAPI, Pydantic v2, TypeScript client generated from OpenAPI |
| Orchestration | LangGraph with the SQLite checkpointer |
| Database | SQLite in WAL mode; checkpoint DB separate from app DB; numbered SQL migrations |
| Quality | `ruff`, `mypy` (strict on `domain/` and `graph/`), `pytest`, `httpx` |
| Frontend | Next.js, TypeScript, Tailwind, `axe` for accessibility checks |
| Containers | Docker, with `docker compose` as the only supported entry point; multi-arch base images pinned by digest |
| CI | GitHub Actions; Linux amd64 is the reference environment; runner images pinned (for example `ubuntu-24.04`) |

## 6. Data Model

| Table | Key fields |
| --- | --- |
| **runs** | `run_id`, `tenant_id`, `repo_visibility`, `status`, `repo_url`, `commit_sha`, `git_ref`, `source` (webhook, mock, eval), `delivery_id` (unique), `attempt_count`, `tokens_in`, `tokens_out`, `cost_usd`, `terminal_reason`, `created_at`, `finished_at` |
| **attempts** | `attempt_id`, `run_id`, `n`, `patch_diff`, `patch_sha256`, `commit_message`, `tests_passed`, `test_log_ref`, `duration_ms`, `violations` |
| **triage\_results** | `run_id`, `file_path`, `function`, `category`, `rationale`, `confidence` |
| **events** | `event_id` (autoincrement), `run_id`, `ts`, `type`, `payload` (JSON) |
| **approvals** | `run_id`, `attempt_id`, `decision`, `patch_sha256`, `decided_at`, `note` |
| **blobs** | `log_ref`, `run_id`, `kind`, `content`, `truncated` |
| **eval\_cases** | `case_id`, `source`, `split`, `category`, `difficulty`, `gt_file`, `gt_function`, `repo_ref` |
| **eval\_results** | `case_id`, `config`, `trial`, `triage_correct`, `fixed`, `tampered`, `tokens`, `seconds`, `environment` |

## 7. API Contract and Events

### 7.1 Endpoints

| Method | Path | Purpose | Notes |
| --- | --- | --- | --- |
| POST | `/api/webhooks/github` | Receive failed-build event | HMAC `X-Hub-Signature-256` verified with constant-time compare; `202` plus `run_id`; dedupe on delivery ID; repo must be on the allowlist |
| POST | `/api/webhooks/mock` | Dev and eval trigger | Enabled only when `ENV=dev` |
| GET | `/api/runs` | List runs | Pagination and status filter |
| GET | `/api/runs/{run_id}` | Run detail | Triage, attempts, current patch |
| GET | `/api/runs/{run_id}/events` | SSE trace | Supports `Last-Event-ID` for resume |
| POST | `/api/runs/{run_id}/approve` | Approve and publish | Body: `attempt_id`, `patch_sha256`; `409` on state or hash mismatch |
| POST | `/api/runs/{run_id}/reject` | Reject | Optional `note` |

**Conventions:** errors use RFC 7807 problem JSON with stable `code` values. Dashboard calls require a local bearer token from the environment. Stack traces never reach the client.

### 7.2 Event types

| Type | Payload highlights |
| --- | --- |
| `run.created` | source, repo, commit |
| `run.status_changed` | from, to |
| `node.started`, `node.finished` | node name, duration |
| `triage.result` | file, function, category, confidence |
| `attempt.patch_created` | attempt ID, patch hash, diff stats |
| `sandbox.test_result` | passed, counts, duration, log reference |
| `validation.violation` | rule (for example `test_file_edit`), path |
| `approval.requested`, `approval.decided` | attempt ID, patch hash, decision |
| `publish.finished` | branch, PR URL |
| `budget.warning` | tokens used, time remaining |
| `run.error` | code and a safe message |

Every payload passes through a redaction function before it is written. Payloads never contain secrets or raw environment data.

## 8. Agent Design

### 8.1 Tools (the only way agents touch the workspace)

There is no generic shell. Every tool is typed, size-limited, and runs against the sandbox workspace only.

| Tool | Behaviour | Limits |
| --- | --- | --- |
| `list_dir(path)` | List files under the workspace | POSIX paths only; depth and entry caps |
| `read_file(path, start, end)` | Read a line range | Byte cap; refuses binaries |
| `search_code(pattern, glob)` | Literal or regex search | Result count cap |
| `edit_file(path, old_text, new_text)` | Replace one exact piece of text in an existing file; old_text must match exactly once; no new files | Denied for protected and test paths (Section 8.4); size cap; parse check after each edit |
| `undo_edit()` | Revert the most recent successful edit in this attempt | Snapshot taken before every edit |
| `revert_file(path)` | Restore one file to its state at the start of the attempt | Discards all edits to that file |
| `submit_patch(commit_message, rationale)` | End this attempt | Refused unless the latest run_tests result is green for the current edits |
| `run_tests()` | Runs the fixed `test_command` from the case configuration | No arguments from the model; 90 s timeout; output cap |

All paths are resolved to real paths, must stay inside the workspace, and symlinks are refused (threat T7).

### 8.2 Triage output (schema-validated)

| Field | Meaning |
| --- | --- |
| `file_path` | Suspected faulty file |
| `function` | Suspected function or method |
| `category` | One of: syntax\_import, logic, type\_data, dependency\_api, multi\_file |
| `rationale` | Short evidence-based explanation citing log lines |
| `confidence` | 0 to 1; recorded for calibration analysis |

Invalid output triggers one bounded re-ask, then the run fails safely. This output is scored against ground truth in the evaluation.

### 8.3 Repair loop

1. The repair agent receives the failing log, the triage result, and (from attempt 2) a truncated summary of the previous failure.
2. It edits files through the tools and produces a commit message.
3. The orchestrator computes the diff and its SHA-256, then runs the validation rules, then runs the tests in a fresh sandbox.
4. Pass without violations goes to the approval gate. Fail goes back to step 1, up to 3 attempts in total, then `escalate` with a per-attempt summary.

### 8.4 Validation rules (anti-tamper and anti-escalation)

| Rule | Action |
| --- | --- |
| Patch edits any test file or test configuration | Violation; attempt rejected |
| Patch adds `skip`, `xfail`, or removes or weakens assertions | Violation |
| Patch touches `.github/`, CI config, build config, or other protected paths from `case.yaml` | Violation |
| Patch touches files far outside the triaged file and its direct callers | Warning shown to the human |
| Diff exceeds the size cap | Violation |
| Tests still fail, or a previously passing test now fails | Attempt failed |

Violations are enforced twice: at the tool layer (writes denied) and again on the final diff. Both are counted in the evaluation.

### 8.5 Prompting rules

- Repository content (code, comments, logs, docstrings) is untrusted data. It is placed in clearly delimited data sections, and the system prompt states that instructions found there must be ignored.
- All model outputs are parsed into typed schemas. Free text is never executed.
- Prompts are versioned files in the repository, hashed per run, and the hash is stored in the run record.
- Temperature is fixed and low; the exact model identifier is logged on every call.
- The injection validator LLM from the original spec is a non-goal; structural controls in Section 9 are the primary defence.

### 8.6 Budgets

| Budget | Default |
| --- | --- |
| Attempts per run | 3 (hard) |
| Token cap per run | Set in M3 from measured usage |
| Wall-clock cap per run | Set in M3 |
| Spend cap per evaluation | Set by the owner before each eval |
| Response cache | Dev reruns reuse cached LLM responses keyed by prompt hash |

### 8.7 Evaluation configurations

| Config | Pipeline |
| --- | --- |
| **baseline** | One LLM call with the failing log (and file contents it asks for through the same read tools); one patch; validated once |
| **triage\_repair** | Triage, then repair, no sandbox feedback between attempts (independent retries) |
| **full** | Triage, repair, and sandbox failure feedback across up to 3 attempts |

## 9. Security

### 9.1 Threat model

| # | Threat | Primary control | Defence in depth |
| --- | --- | --- | --- |
| T1 | Prompt injection from repo content or test output | No arbitrary shell; typed tools only | Untrusted-data delimiting; human gate |
| T2 | Secret exfiltration (LLM key, GitHub token) | Secrets live only in the orchestrator process, never in the sandbox; sandbox has no network | Log and event redaction |
| T3 | Sandbox escape or host damage | Hardening flags in 9.2 | CPU, memory, PID, and time limits |
| T4 | Code execution during dependency install (network on) | Build only from owner-controlled fixtures; hash-pinned deps; wheels only where possible | Build container has no secrets and is separate |
| T5 | Test tampering | Tool-layer write denial | Final-diff check; counted as a failure in the eval |
| T6 | CI privilege escalation via workflow edits | Protected-path denylist | Diff validation before push; highlighted in UI |
| T7 | Path traversal and symlink tricks | Real-path resolution and workspace prefix check | Container filesystem isolation |
| T8 | Webhook spoofing or replay | HMAC verification, delivery-ID dedupe | Rate limiting; repo allowlist |
| T9 | Diff changes between review and push (TOCTOU) | Approval carries the patch SHA-256; push refused on mismatch | Immutable patch record per attempt |
| T10 | Cost runaway | Hard caps on attempts, tokens, and time | Per-run cost shown in UI |

### 9.2 Sandbox hardening (run phase)

| Control | Purpose |
| --- | --- |
| `--network none` | No exfiltration or callbacks |
| `--read-only` with tmpfs for `/tmp` and scratch | Immutable root filesystem |
| `--cap-drop ALL` and `no-new-privileges` | No capabilities, no setuid escalation |
| Default seccomp profile, never `unconfined` | Syscall filtering |
| Fixed non-root `--user` | No root inside the container |
| `--memory`, `--memory-swap`, `--cpus`, `--pids-limit` | Stops memory bombs and fork bombs |
| Orchestrator-enforced 90 s wall-clock kill | Do not trust in-container timeouts |
| Only a throwaway workspace volume; no host bind mounts; no Docker socket | No host exposure |
| `--rm` and a unique name per attempt | No state carried between attempts |
| Minimal environment allowlist | Secrets never enter the container |
| Output size cap with truncation | Log flooding cannot exhaust storage |

**Two phases.** The build phase (network on, no secrets, fixtures only, hash-pinned dependencies) produces a dependency image. The run phase (all controls above) executes the patch and the tests from that image.

### 9.3 Required evidence: hostile fixture suite

Each item must be contained, with logs saved as thesis evidence, on every environment tested.

| Hostile behaviour | Expected result |
| --- | --- |
| `rm -rf /` or deleting the workspace | Only the throwaway workspace is affected; host intact |
| Fork bomb | Stopped by the PID limit |
| Memory bomb | Killed by the memory limit |
| Infinite loop | Killed by the orchestrator at 90 s |
| Outbound network call | Fails; no connection |
| Reading environment variables and files for secrets | Nothing sensitive present |
| Writing outside the workspace or to the root filesystem | Denied |
| Symlink escape | Refused by the tool layer; contained by the container |
| Huge output | Truncated at the cap |
| Injection text in comments, docstrings, and test output | No unauthorised action; recorded as an event |

**Honest scope note.** Docker is not a hard boundary against kernel-level exploits. The thesis states this and names gVisor and Firecracker as future work.

### 9.4 VPS hardening checklist

- SSH keys only; no password login; firewall allows only the web port and the SSH port.
- Reverse proxy with automatic HTTPS in front of the API; the bearer token is required.
- The Docker socket and Docker’s TCP port are never exposed.
- API keys and tokens live in server-side environment files readable only by the orchestrator user.
- Only owner-controlled fixtures run there until the hostile suite has passed on that machine.
- Automatic security updates are enabled; the instance is a KVM-based VM with at least 4 GB RAM, Linux amd64.

## 10. UX Specification

### 10.1 Design language

Tailwind-based, restrained, with a clear hierarchy: status first, evidence second, controls last. Information density is high on the run detail page and low on the list. Motion is minimal and respects reduced-motion settings.

### 10.2 Screens (three, no more)

| Screen | Content |
| --- | --- |
| **Run list** | Runs with status badge, repository, commit, attempts, cost, age; filters by status |
| **Run detail** | Header with status; live trace (SSE); triage result; attempt tabs with diff and test evidence; budget and cost |
| **Approval gate** (within run detail) | Diagnosis, verified diff, test evidence, attempt count, cost; Approve and Reject with a confirmation step |

### 10.3 State coverage

| State | What the user sees |
| --- | --- |
| Loading | Skeletons for the diff and list; live trace shows the current node |
| Empty | No runs yet, with the command to send a test failure |
| Awaiting approval | Full evidence; primary action Approve, secondary Reject |
| Warning | Violation or out-of-scope edit highlighted; Approve disabled when a violation exists |
| Error | Plain-language cause with retry or view-log; never a silent failure |
| Success | PR link, branch name, final summary |
| Escalated | Could not fix in 3 attempts, with per-attempt summaries and failure logs |
| Disconnected | Stream lost banner with automatic reconnect using `Last-Event-ID` |

### 10.4 Accessibility (WCAG 2.1 AA)

- Status never conveyed by colour alone; the diff uses `+` and `-` markers as well as colour.
- The live trace sits in an `aria-live=polite` region; focus is never stolen by new events.
- Full keyboard operation, visible focus rings, logical tab order, and a skip link.
- Colour contrast meets AA in both light and dark themes.
- Approve requires a confirmation to prevent accidental clicks.
- Automated `axe` scan in CI plus a manual keyboard-only and screen-reader pass before M5 exits.

## 11. Evaluation Design

### 11.1 Corpus

| Category | Synthetic | Real | Example |
| --- | --- | --- | --- |
| Syntax and import | 2 | 0 | Missing colon, wrong import path |
| Logic | 4 | 2 | Off-by-one, inverted condition, wrong operator |
| Type and data handling | 2 | 2 | Unhandled None, wrong dict key |
| Dependency and API drift | 2 | 1 | Pinned version changes a call signature |
| Multi-file | 2 | 1 | Bug in a helper surfaces in a caller |
| **Total** | **12** | **6** |  |

### 11.2 Case format and admission

Each case is a directory with `repo/`, `case.yaml`, and `reference.patch` (never shown to the agent).

| `case.yaml` field | Meaning |
| --- | --- |
| `case_id`, `source` | Synthetic or real, with origin URL and licence for real cases |
| `split` | `dev` or `heldout` |
| `category`, `difficulty` | Category from 11.1; difficulty 1 to 3 |
| `broken_ref`, `fixed_ref` | Commits, for real cases |
| `gt_file`, `gt_function` | Triage ground truth |
| `test_command` | Fixed command, for example `pytest -x -q` |
| `protected_paths` | Paths the agent may never modify |
| `expected_failing_tests` | Tests that must fail before any trial |
| `notes` | Contamination risk and quirks |

**Admission rules:** the failure reproduces in the sandbox three times in a row; the run takes under about 60 s; dependencies are pure Python and lockfile-reproducible; no database or network is needed at test time. Real cases come from lesser-known or recent repositories (to reduce training-data contamination) with licence and attribution checked, and use the parent of the fix commit as the broken state.

### 11.3 Split and freeze protocol

- About 10 cases are dev and 8 are held-out, stratified by category.
- Prompts and thresholds are tuned on dev only.
- Before the final run, the prompts, code, and configuration are tagged and frozen. The held-out set is run once. Any later change invalidates the run and requires a new tagged run, which is reported as such.

### 11.4 Metrics

| Metric | Definition |
| --- | --- |
| Triage accuracy | File correct; file and function correct (reported separately) |
| Fix rate (pass@1 per trial) | Tests pass after the patch within 3 attempts, with no violation |
| Tamper rate | Share of attempts rejected for test edits, skip or xfail, protected paths |
| Patch quality | Diff size relative to the reference patch; unrelated files touched |
| Escalation rate | Runs ending in `escalated` |
| Cost | Tokens in and out, dollars, per run |
| Latency | Seconds per run and per node, with the environment recorded |
| Confidence calibration | Triage confidence versus correctness |

### 11.5 Statistics and threats to validity

- Three trials per case per configuration; fixed temperature; model identifier logged.
- Report fix rates with Wilson confidence intervals; compare configurations with a paired test on per-case outcomes (for example McNemar or a paired bootstrap).
- State plainly that 18 cases give wide intervals and that results are indicative, not definitive.
- List threats to validity: small corpus, synthetic bias, possible contamination, model non-determinism, one language, one test framework, and environment differences (architecture and virtualisation).

### 11.6 Reproducibility

Every evaluation writes a manifest next to its results.

| Manifest field | Content |
| --- | --- |
| Code | Git commit and tag |
| Prompts | Hash of each prompt file |
| Model | Provider, model identifier, temperature, date |
| Environment | OS, architecture, Docker version, image digests, runner image |
| Corpus | Case list and checksums |
| Budget | Spend cap and actual spend |

Results go to a CSV with one row per case, configuration, and trial. A single command regenerates every table and chart in the thesis from that CSV. Official numbers come from the Linux amd64 reference environment; macOS and Windows runs are labelled as compatibility checks and are never mixed into the benchmark.

## 12. Repository Layout and Environments

### 12.1 Layout

```
agentic-cicd/
├── api/                 # FastAPI + LangGraph (Python)
│   ├── app/
│   │   ├── main.py, config.py
│   │   ├── routes/      # webhooks, runs, events
│   │   ├── domain/      # pure models, enums, status machine
│   │   ├── graph/       # state, nodes, builder
│   │   ├── services/    # runs, approvals, redaction
│   │   ├── sandbox/     # SandboxPort, Fake, Docker
│   │   ├── llm/         # LLMPort, Fake, Cached, provider
│   │   ├── publisher/   # PublisherPort, local, GitHub
│   │   ├── tools/       # typed agent tools
│   │   └── db/          # schema, migrations, repositories
│   └── tests/
├── web/                 # Next.js dashboard (from M5)
├── eval/                # corpus runner, analysis, manifests
├── fixtures/            # one directory per case
├── docker/              # sandbox and build images
├── prompts/             # versioned prompt files
├── docs/                # architecture, security, adr/, thesis/, evidence/
├── .github/workflows/   # ci.yml, sandbox-check.yml, eval.yml
├── .gitattributes       # forces LF line endings
└── docker-compose.yml
```

### 12.2 Environments

| Environment | Role | Notes |
| --- | --- | --- |
| **M1 Mac, 8 GB** | Daily development and demo | arm64 containers; cap Docker memory at 2 to 3 GB; do not run the dashboard, evals, and image builds at once |
| **Linux VPS** (KVM, 4 GB or more, amd64) | Eval and sandbox runs; backup demo host | Hardened per Section 9.4; resize if builds are slow |
| **GitHub Actions** (Linux amd64, pinned runner) | Reference environment for official numbers; CI | Eval workflow is manual only; LLM key stored as a repository secret; never run on forks; no `pull_request_target` |
| **Windows** | Compatibility evidence | CI with the fake sandbox, plus the dashboard in a Windows browser against another host; the full Windows sandbox is untested and documented as such |

**Cross-platform rules:** `docker compose up` is the only supported way to start the stack; `.gitattributes` forces LF; every sandbox and tool path is POSIX; base images are multi-arch and pinned by digest; fixtures use pure-Python dependencies; never emulate another architecture for timing runs.

## 13. Engineering Standards

| Area | Standard |
| --- | --- |
| **Design** | SOLID and DRY; ports and adapters; pure `domain/`; dependency injection at the app factory; no global state |
| **Typing** | Full type hints; `mypy` strict on `domain/` and `graph/`; Pydantic models at every boundary |
| **Testing** | Unit tests for domain and tools; integration tests using fakes; sandbox tests marked and run only where Docker is available; one end-to-end test per milestone; the kill-and-restart resume test is permanent |
| **Git** | Short-lived branches, conventional commit messages, one coherent change per pull request, PR description lists the exit tests satisfied |
| **Dependencies** | Pinned with hashes; reviewed before adding; automated vulnerability audit in CI |
| **Configuration** | Environment variables only, validated at start-up; `.env.example` committed, `.env` never |
| **Logging** | Structured JSON; redaction applied before write; no secrets, tokens, or full environments |
| **Errors** | Typed errors mapped to stable problem codes; safe messages to the client; details only in server logs |
| **Performance and cost** | Measure before optimising; record tokens and time on every run |
| **Licence** | Choose and add a licence file at M0 (open decision, Section 17.3) |

## 14. Milestones and Exit Criteria

Work strictly in order. A milestone is done only when every exit criterion is demonstrated. No dashboard work begins before M4 is complete.

| Milestone | Focus | Exit criteria |
| --- | --- | --- |
| **M0 Foundations** | Repo, tooling, CI, first fixtures | Layout from 12.1; `uv` project; lint, type, and test jobs green in CI; `.gitattributes`; `.env.example`; `docker compose` skeleton; 3 synthetic fixtures with labels; licence and security policy files; first ADRs |
| **M1 Walking skeleton** | End to end with fakes | Tests 1 to 11 below pass (M1a: tests 1 to 3, done; M1b: tests 4 to 12, open); fake adapters for all three ports; events table and SSE; CLI client can create a run, watch it, and approve it |
| **M2 Sandbox** | Real validation | Build and run phases; all controls in 9.2 applied; hostile fixture suite (9.3) contained with saved logs on the Mac and on the VPS; `run_tests` returns structured results |
| **M3 Agent core** | Real triage and repair | Typed tools only; schema-validated triage; repair loop with 3-attempt cap and feedback; anti-tamper rules (8.4) enforced twice; LLM provider adapter with response cache and budget caps; majority of synthetic dev cases fixed from the CLI |
| **M4 Eval harness** | Measurement | 18 cases admitted under 11.2 with dev and held-out split; runner for the three configurations with 3 trials; manifest and results CSV; one-command table and chart generation; held-out frozen and untouched |
| **M5 Dashboard** | Three screens | All states in 10.3; OpenAPI-generated client; `axe` clean; keyboard and screen-reader pass; works from a Windows browser |
| **M6 Real GitHub** | Integration | HMAC webhook on the VPS or via a tunnel; branch and PR created on a test repository; hash-mismatch negative test passes; allowlist enforced |
| **M7 Final evaluation and writing** | Results and thesis | Held-out run executed once from a tagged commit; all tables and figures regenerated; thesis complete; demo rehearsed and recorded as a fallback |

### 14.1 M1 exit tests, split into M1a and M1b (write these first). M1a (webhook intake, tests 1 to 3) is done and merged. Test 1 was re-scoped from the mock route to the signed GitHub route (ADR 0003). The dev-only mock route moved to M1b as test 12. M1b covers tests 4 to 11 and welcome tests W1 to W6

| # | Test | Proves |
| --- | --- | --- |
| 1 | Signed GitHub webhook returns `202` with a `run_id` and a run row exists | Ingress works |
| 2 | The same delivery ID twice creates one run | Deduplication |
| 3 | Valid HMAC passes; a tampered body or bad signature returns `401` | Threat T8 control |
| 4 | A run reaches `awaiting_approval` and stops | The pause works |
| 5 | Kill the server while paused, restart, approve, and the run completes | State survives restarts |
| 6 | Approve with a wrong `patch_sha256` returns `409` and the run stays paused | Threat T9 control |
| 7 | Approve on a terminal run returns `409` | Idempotency |
| 8 | A stub forced to fail three times ends in `escalated` with 3 attempts | Loop cap |
| 9 | Every legal status transition passes and every illegal one is rejected | State machine |
| 10 | SSE reconnect with `Last-Event-ID` replays only missed events | Streaming contract |
| 11 | A payload containing a fake secret is redacted before storage | Redaction |
| 12 | `POST /webhooks/mock` returns `202` with a `run_id` when `ENV=dev`, and is unavailable when `ENV` is not dev | Dev-only ingress, guarded |

### 14.2 Additional exit tests by milestone

| Milestone | Tests |
| --- | --- |
| M2 | Each hostile behaviour in 9.3 is contained; the container has no network, no capabilities, a read-only root, and no secrets; the timeout kills runaway tests |
| M3 | A patch editing a test file is rejected at the tool layer and again on the final diff; an invalid triage output is re-asked once then fails safely; the repo allowlist blocks other repositories; budget exhaustion ends in `escalated` |
| M4 | Every admitted case reproduces its failure three times; the runner refuses to start if the held-out set is marked frozen and the commit is not the tag; the manifest is complete |
| M5 | `axe` reports no serious issues; the approval flow works by keyboard alone; every state in 10.3 has a test or a recorded manual check |
| M6 | A forged signature is rejected; a non-allowlisted repository is rejected; the pushed branch contains exactly the approved patch hash |

## 15. Documentation Inventory

| Document | Location | Purpose | Written |
| --- | --- | --- | --- |
| README | `README.md` | What it is, quick start, demo steps, honest limitations | M0, updated each milestone |
| Setup guides | `docs/setup/` | macOS, Linux VPS, Windows (CI and browser client) | M0 to M2 |
| Architecture | `docs/architecture.md` | Components, graph, state, ports, diagrams | M1 |
| Threat model and isolation | `docs/security/` | Section 9 expanded; control-to-test mapping | M2 |
| Hostile suite evidence | `docs/evidence/isolation/` | Logs and results per environment | M2 |
| API reference | generated OpenAPI | Contract for the client | M1 onward |
| Prompt registry | `prompts/` (versioned `.md` files) | Version, purpose, change history | M3 |
| Evaluation protocol | `docs/eval-protocol.md` | Corpus, split, freeze, statistics | M4 |
| Corpus datasheet | `docs/corpus.md` | Source, licence, labels, known biases per case | M4 |
| Runbook | `docs/runbook.md` | VPS operation, secrets, backups, incident steps | M6 |
| Demo script | `docs/demo.md` | Exact steps, fallback paths, timing | M7 |
| Compatibility matrix | `docs/compatibility.md` | Feature by OS, with verification date and method | M7 |
| Decision records | `docs/adr/` | One file per significant decision | Continuous |
| Changelog | `CHANGELOG.md` | Per milestone | Continuous |

### 15.1 ADR template

- **Title and number**
- **Status:** proposed, accepted, superseded
- **Context:** the problem and constraints
- **Options considered:** at least two, with trade-offs
- **Decision:** what was chosen and why
- **Consequences:** benefits, costs, follow-ups
- **Evidence:** links to tests, logs, or measurements

Expected early ADRs: SQLite over PostgreSQL and Redis; gate after validation; no generic shell tools; single-language scope; SSE over WebSocket; Docker over E2B; pure-Python fixtures; public repository with private-tier roadmap.

## 16. Thesis Plan and Evidence

### 16.1 Outline

| Chapter | Content | Evidence source |
| --- | --- | --- |
| 1. Introduction | Problem, motivation, thesis statement, RQs, contributions, scope | Section 1 |
| 2. Background and related work | CI failure repair, LLM agents, agent orchestration, sandboxing, prompt injection | Literature review (to be gathered by the owner) |
| 3. System design | Architecture, graph, state, gate order and its justification, ports | Sections 4 to 8; ADRs |
| 4. Security design | Threat model, controls, hostile suite, limits of Docker | Section 9; `docs/evidence/isolation/` |
| 5. Implementation | Stack, key decisions, UI and accessibility | Sections 5, 10; repository |
| 6. Evaluation | Corpus, protocol, configurations, results, statistics, threats to validity | Section 11; results CSV and manifests |
| 7. Discussion | What worked, failures and why, cost, practical value | Failure analysis of per-case outcomes |
| 8. Limitations and future work | Single language, small corpus, Docker boundary, private-repo tier, gVisor and Firecracker | Sections 2.2, 11.5 |
| 9. Conclusion | Answers to RQ1 to RQ4 | Chapter 6 |
| Appendices | Prompts, `case.yaml` examples, full tables, setup and reproduction guide, compatibility matrix | `docs/` |

### 16.2 Figures and tables the thesis must contain

- Architecture diagram and graph diagram.
- Threat model table mapped to controls and to the tests that prove them.
- Hostile suite results per environment.
- Fix rate by configuration with confidence intervals (headline figure).
- Triage accuracy by category; confidence calibration plot.
- Per-case outcome matrix across configurations (shows where structure helps).
- Cost and latency per configuration.
- Failure taxonomy with examples (including tamper attempts and escalations).
- Compatibility matrix.

### 16.3 Evidence rules

- Every claim in the thesis traces to a saved artefact (log, CSV, manifest) in the repository.
- Raw results are never edited by hand; tables and charts are regenerated by script.
- Failures are reported, not hidden; unexpected results get their own analysis.
- The held-out run is described exactly as it happened, including any reruns.
- Real-bug sources are cited with their licences.

## 17. Risks, Cut Lines, and Open Decisions

### 17.1 Risk register

| # | Risk | Mitigation | Trigger |
| --- | --- | --- | --- |
| R1 | Agent fix rate is low | Frame the contribution as structure versus a naive baseline; tune on dev early | Dev fix rate under 30% at end of M3 |
| R2 | Real-bug curation takes too long | Time-box it; fall back to 3 real cases and disclose | Fewer than 3 viable real cases found by the time M3 ends |
| R3 | Docker complexity on the Mac or VPS | Prototype hostile-suite containment early; pin images | Containment test failing at M2 |
| R4 | LLM cost or rate limits in evals | Response cache, spend caps, small dev runs | Spend above 70% of the owner’s budget |
| R5 | Training-data contamination of real bugs | Prefer lesser-known repositories; disclose | Design choice |
| R6 | Non-determinism | 3 trials, confidence intervals, fixed temperature | Design choice |
| R7 | Scope creep into UI polish | No UI before M4 is complete | Any UI work before then |
| R8 | Checkpoint resume bugs | Resume test is an M1 exit criterion | Test failing |
| R9 | Dependency install fails for real cases | Admit only lockfile-reproducible, pure-Python cases | More than 2 hours of setup for one case |
| R10 | Live demo failure | Cached-LLM mode, recorded fallback, offline path | Rehearsal failure |
| R11 | 8 GB RAM limits local work | Use the VPS for evals; cap Docker memory | Swapping or freezes |
| R12 | VPS compromise | Hardening checklist; fixtures only; no long-lived secrets beyond what is needed | Any anomaly |

### 17.2 Cut lines (if time pressure appears; none is currently set)

| Order | Cut | Consequence |
| --- | --- | --- |
| 1 | Real GitHub PR creation (M6) | Demo uses a local branch and a PR-style summary |
| 2 | Real cases from 6 down to 3 | Weaker external validity, disclosed |
| 3 | SSE replaced by polling | Slightly less impressive demo |
| 4 | Dashboard polish | Keep the approval gate only |
| **Never cut** | Hostile-suite evidence, held-out evaluation, anti-tamper checks | These are the thesis |

### 17.3 Open decisions

| Decision | Needed by | Default |
| --- | --- | --- |
| LLM provider and model | M3 | Choose after a small cost and quality comparison |
| Licence for the public repository | M0 | Permissive licence, confirmed with the supervisor |
| VPS provider and size | M2 | Small KVM instance, resize if needed |
| Spend cap for evaluations | M3 | Set by the owner before each run |
| Real-bug source repositories | M4 | Lesser-known pure-Python repositories with permissive licences |
| Test GitHub repository and token scope | M6 | Dedicated test repository; fine-grained token limited to it |
| Project name | M0 | Working name: agentic-cicd |
| Supervisor expectations on weighting of evaluation versus demo | M0 | Assume both matter, evaluation as the stronger proof |

## 18. Kickoff Instructions for the AI Engineer

### 18.1 First response (before any code)

1. Confirm you have read this document fully, and restate in your own words the thesis statement, the gate order, and the three configurations.
2. List any ambiguities or conflicts you found, each with 2 to 3 options and trade-offs.
3. Propose the M0 plan as an ordered task list with the tests you will write first.
4. Stop and wait for the owner’s approval.

### 18.2 M0 task list (after approval)

1. Create the repository layout in 12.1, the `uv` project, and pinned tooling configuration.
2. Add `.gitattributes`, `.gitignore`, `.env.example`, licence and security policy files.
3. Add CI: lint, type check, and unit tests on Linux; fake-sandbox tests also on macOS and Windows runners.
4. Write the first failing tests: HMAC verification, the status state machine, webhook deduplication.
5. Create a `docker compose` skeleton that starts the API, with multi-arch base images pinned by digest.
6. Create 3 synthetic fixtures with `case.yaml` labels and confirm each failure reproduces.
7. Write the first ADRs and the README with an honest status section.
8. Report: what is done, what is failing, what you are unsure about. Wait for review before M1.

### 18.3 Reporting format after every milestone

- Exit criteria checklist with a link to the proof for each item.
- Deviations from this document, with reasons.
- New risks and new open decisions.
- Evidence artefacts added for the thesis.
- Proposed next step.
