# ADR 0007: Untrack agent instruction files

Status: Accepted
Date: 2026-11-02

## Context
AGENTS.md and CLAUDE.md hold instructions for coding agents. Neither is
read at runtime. Keeping them out of the published repository avoids
publishing local working notes.

## Options considered
A. Keep AGENTS.md and CLAUDE.md tracked.
B. Untrack the files and ignore them (chosen).
C. Delete the files from history (rejected: rewrites shared history with
   merged pull requests).

## Decision
Option B. AGENTS.md and CLAUDE.md are untracked and listed in `.gitignore`.
Evidence: PR #5 (merge d01f0e5), `.gitignore` entries.

## Consequences
- A fresh clone and CI do not get the files.
- Other machines need the files copied by hand.
- History still exposes older versions of both files.
