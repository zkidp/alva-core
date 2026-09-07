# VNext-02A Integration Port

Status: implementation complete; VNext-02B not started.

This change clean-ports the VNext-02A typed execution-event capability onto
the authoritative core substrate without merging the divergent experimental
architecture.

## Provenance and boundary

- Core base: `c4bcfb8c092a2e54736b7d7955a63e5dc2d72566`
- Typed-event design reference: `3673d43b04479ec7faa67cc1ad3e0d86d1aea9d9`
- Failure-localization evidence: `62c12ebf5d7923134c790efe8afdd5b487180e7f`
- Model calls: `0`
- Research gate: none
- Batch patch: deferred
- Intent-preserving recovery (VNext-02B): not started

`agent_runtime.rs` remains the sole transport-neutral transaction lifecycle
owner. `execution_events.rs` contains only the event schema, observational
recorder, system JSONL sink, and compact response projection. MCP launches the
same agent runtime used by the CLI and forwards the runtime-produced compact
projection; it does not infer events.

## Event semantics

The schema distinguishes operation success, recovery action success, recovery
completion, and final task verification. A recovery action cannot carry a
verification status. Only `recovery_completed` and `final_task_verified` may
carry `passed`, `failed`, or `unknown` verification status.

A stale authoritative commit produces this causal chain:

```text
operation_requested
-> commit_attempted
-> semantic_check_passed
-> operation_rejected
-> stale_write_rejected
```

## Observational guarantee

The JSONL sink is best-effort system evidence. Failure to open, encode, append,
or flush the sink disables that sink without changing the transaction result.
Logging enabled and disabled therefore preserve the same:

- AIR revision;
- source projection and source bytes;
- operation success/failure result;
- semantic diagnostics.

The acceptance test runs the same transaction with logging on and off and
compares the responses after removing only the additional compact `execution`
projection. Existing stale rejection, exact crash old-or-new atomicity, source
projection, transaction work, incremental checking, and MCP protocol tests
remain the regression authority.
