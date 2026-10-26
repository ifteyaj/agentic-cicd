# ADR 0002: Approval gate after sandbox validation

Status: Accepted
Date: 2026-10-26

## Context

The original spec placed the human approval step before sandbox testing. This meant humans
reviewed unverified guesses.

## Options considered

A. Approve first, then test (original spec): human reviews a guess; evaluation needs a
   simulated approval step.
B. Test first, then approve: human reviews a verified patch; evaluation runs fully
   headless.

## Decision

Option B. The sandbox validates the patch (up to 3 attempts) before the run reaches the
approval gate.

## Consequences

Better review experience: the developer only ever sees a patch already shown to pass. The
eval harness runs without human intervention. The sandboxed validation must exist before
the gate demo, so it is a prerequisite for M1's approval ceremony.
