# Default: Minimal Iterative Recovery

A confirmed `E_AEP_CONFLICT` is not a terminal conversation failure. Keep the
original user assignment and the complete conversation/tool feedback. Preserve
the rejected proposal or semantic diff in host evidence before discarding its
private staging; do not blindly replay it over the winner.

1. Abort the rejected transaction. This drops private staging, not the user
   task or conversation. With MCP, retire the old `transaction_id` only after
   abort succeeds.
2. Begin a new transaction on the same manifest; retain its new MCP handle.
   `begin_transaction` reads current AIR authority, not stale source projection.
3. Inspect current authority, re-resolve targets and re-run operation discovery.
   Return these tool results to the same writer conversation. **A read-only
   response is not recovery completion**: allow the next model turn to act on it.
4. Continue ordinary inspect/edit/check feedback under the host's existing
   budget. A staged compiler PASS or applied patch is not final task success.
5. Review and check, then commit. Commit still performs authoritative checks
   and stale protection. On another confirmed conflict, refresh again with the
   same original task; never replay remaining actions based on the old state.
6. After commit, run the actual task-relevant verifier/tests. Without adequate
   evidence, report verification UNKNOWN, not intention preserved. Keep hidden
   evaluation predicates host-side; never add them to recovery hints.

Do not retry an ambiguous transport outcome as if it were a confirmed conflict.
Stop for corrupt authority, unresolved ambiguity, unavailable operations,
cancelled scope or exhausted host budget. Close/abort remaining private staging
when ending the session. Recovery does not authorize expanded edits.

## Optional assistance, not a prerequisite

RecoveryContext/rebinding is IMPLEMENTED / OPTIONAL / EXPERIMENTAL ASSISTANCE /
NOT DEFAULT. Do not require `register_recovery_intent`, `inspect_recovery_context`
or `begin_recovery` for ordinary recovery. If a task needs that assistance and
the exposed API supports it, registration must precede mutation; do not invent
obligations retrospectively after rejection. Abort/new-begin clears that optional
context, so use its separately documented lifecycle when deliberately selected.

## Host orchestration and evidence

Custom hosts can reuse [scripts/recovery_loop.py](../scripts/recovery_loop.py).
It consumes normalized AEP envelopes and host-owned turn/budget/verifier
callbacks. It contains no model client, provider policy, semantic merge or
transaction implementation. Its conversation records are transport-neutral;
translate them into the host's message format without losing tool results.
MCP adapters must retain the new handle and inject it into subsequent calls;
the helper itself does not own MCP transaction identity. Keep the existing
native agent/MCP transport alive as appropriate.

Use native `--event-log` evidence for stale rejection, operation requests,
staged mutation, semantic check and commit. Correlate inspection via its
operation name. Ordinary abort/begin produces `transaction_started`, not the
optional 02B `recovery_started` core event. The host should therefore emit a
separate `alva.integration-recovery.v1` recovery-start event linked to the
rejection and fresh transaction; never relabel native evidence. The helper
emits these host events, distinct inspection/mutation/check/commit phases and
explicit host-verifier status. Sink failures must not change program behavior.

`operation_succeeded`, `state_committed`, public checks and final task
verification remain separate. One-sided intention satisfaction does not measure
storage partial writes. Source projection remains an explicit materialization
step, not an atomic write with AIR commit. No batch patch is introduced.
