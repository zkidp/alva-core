# VNext-02B Intent-Preserving Recovery

Status: implementation complete for the S06/S07 developmental scope.

Base: `d95b0b97b8817517d5dcc2cb3273654a456e0bd8f5`

Model calls: `0`. Batch patch and general semantic merge remain deferred.

## Scope

This increment preserves a writer's public task obligations across stale
commit recovery and rebinds a named target against the current authoritative
AIR graph. It supports the two VNext-01 families:

- rename to edit: stable AIR entity identity maps the old qualified name to
  the current qualified name;
- signature to call site: the real base/current AIR delta reports the changed
  function signature and affected named targets without choosing argument
  values for the writer.

The writer registers `original_target` and `original_obligations` before the
first staged mutation. Registration is immutable for that transaction. A stale
commit creates a bounded `RecoveryContext`; `begin_recovery` rebases the
transaction onto the latest authoritative graph without applying a repair.

## Recovery context

The context binds:

- deterministic recovery ID and rejected stale event ID;
- original base and current authoritative revisions;
- original public obligations;
- original and current target snapshots plus rebinding classification;
- bounded named-target changes derived from the actual AIR revision delta;
- preserved and unresolved obligations;
- validation state.

The context has no fields for hidden I1/I2 predicates or evaluator-owned
verifiers. It does not ingest evaluator evidence. Function signature facts are
compiler-derived; task-specific values remain the writer's responsibility.

## Verification boundary

`begin_recovery` and later mutation success do not prove task correctness.
Every new context starts with `validation_state = unknown`, and a successful
recovery mutation emits `recovery_action_succeeded` without verification
status. Only the internal verifier-owned completion hook can transition the
context and emit `final_task_verified` followed by `recovery_completed`. That
hook is not registered as an AEP or MCP operation, so an agent cannot
self-assert intent preservation.

## Non-goals

- automatic conflict resolution;
- semantic merge;
- inferred or reconstructed obligations after a conflict;
- hidden-oracle projection;
- batch or multi-file atomic patch;
- model prompts or model execution.

The deterministic acceptance test exercises concurrent S06 rename/edit and
S07 signature/call-site conflicts, stale-state preservation, real-delta
summaries, obligation retention, the UNKNOWN boundary, and telemetry ON/OFF
equivalence.
