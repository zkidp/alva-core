# VNext-02A: typed execution and recovery telemetry

Status: implemented as an additive runtime facility.

Development evidence is bound to `zkidp/alva-research` VNext-01 commit
`62c12ebf5d7923134c790efe8afdd5b487180e7f`. This change does not revise V2
evidence or add a model experiment.

## Event boundary

`agent_runtime.rs` defines the system-side JSONL event schema. It distinguishes:

- `operation_requested` and `operation_rejected`;
- `transaction_started` and `transaction_aborted`;
- `mutation_staged` and `semantic_check_passed`;
- `commit_attempted`, `commit_succeeded`, and `stale_write_rejected`;
- `recovery_started`, `recovery_action_succeeded`, and `recovery_completed`;
- `final_task_verified`.

Every full event carries a session ID and may carry a transaction ID, base and
current revisions, target entity, operation, rejection reason, resulting
revision, verification status, and parent event ID. Causal links connect a
stale rejection to its rejected operation, commit attempt, and request.

The full stream is enabled with:

```text
alva agent --event-log <path> --session-id <id> --transaction-id <id>
alva mcp --event-log <path>
```

MCP generates the transaction identifier before starting the shared AEP child
and passes it into the recorder. MCP and direct AEP therefore use the same
runtime event implementation.

## Agent-visible projection

Tool responses expose only a compact `execution` projection: latest state,
event and parent IDs, revision transition, and rejection reason. Operation and
target details remain in the system-side event stream rather than being copied
into every model response.

`recovery_action_succeeded` contains no intent-verification claim. Recovery
completion records a separate `verification_status` of `passed`, `failed`, or
`unknown`; final task verification is a separate event again. The compiler or
runtime cannot promote affected-site evidence into a business-intent answer.

## Non-goals

This increment does not implement automatic semantic merge, recovery-context
construction, atomic multi-file patching, or a model-facing experiment. Event
logging is evidence telemetry, not an atomic extension of the authoritative
AIR commit protocol; a logging I/O failure is surfaced but is not claimed to
roll back an already completed mutation.

The acceptance fixture `tests/runtime/typed_recovery_events_test.py` verifies
the typed stream, compact projection, transaction identity, and the causal
chain for a real stale commit rejection. Rust unit tests enforce the semantic
separation between recovery action success and intent verification.
