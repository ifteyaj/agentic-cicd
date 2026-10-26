# ADR 0001: SQLite instead of PostgreSQL and Redis

Status: Accepted
Date: 2026-10-26

## Context

The system needs persistent state for LangGraph checkpoints and application data. The
deployment target is a single laptop and a small VPS.

## Options considered

A. PostgreSQL + Redis (original spec): production-grade, requires extra services, adds
   setup complexity.
B. SQLite in WAL mode: zero setup, file-based, survives restarts, supports concurrent
   reads.

## Decision

SQLite, with separate files for app data and LangGraph checkpoints to avoid lock
contention.

## Consequences

Zero-dependency setup. Single writer only, which fits a one-user capstone. A later swap to
PostgreSQL is possible behind the repository layer. Not suitable for multi-tenant
production use (documented as future work).
