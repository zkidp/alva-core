# Minimal Iterative Recovery: canonical integration default

Implemented on `e16cd38dc57723817df9637994d4bb566be1b310` without changes to
Rust, AIR storage, AEP operations, MCP tool schemas, or source projection.
Default behavior lives in the canonical ALVA Skill and its byte-matched Codex
and Claude Code plugin copies. It applies when those integrations are used;
it does not rewrite already installed third-party host loops automatically.

## Product behavior

After a confirmed stale/conflict rejection, retain the original assignment and
writer conversation. Abort only private staging; begin on current authority,
re-inspect, and feed those results back into subsequent writer turns. Continue
ordinary discovery/edit/check/commit under existing host limits. Inspection,
applied mutation and compiler PASS are not completion criteria. Commit keeps
its full authoritative checks; final task verification remains separate.

The existing lifecycle was sufficient on both real CLI and MCP paths. MCP
retires the aborted handle and starts a new one; the user conversation is not
the transaction handle. No restart primitive or semantic merge was added.
The transport-neutral `scripts/recovery_loop.py` in the canonical Skill offers
custom hosts the same loop with dispatch, turn, budget and verifier callbacks.
It has no model client or provider-specific policy. Hosts own protocol
translation, message persistence, cancellation and closing unused staging.

RecoveryContext/rebinding remains IMPLEMENTED / OPTIONAL / EXPERIMENTAL
ASSISTANCE / NOT DEFAULT. Its separate opt-in lifecycle is unchanged; it is
not deleted and its tools are not made mandatory. Source materialization is
still explicit and not atomic with AIR commit. Batch patch remains deferred.

## Observability boundary

Native 02A logs remain unchanged. They distinguish stale rejection, requested
inspection, staged mutation, check and commit. An ordinary begin is a native
transaction-start event, not the optional 02B recovery-start event. The host
helper therefore records a separately namespaced recovery-start event linked
to its rejection, native event ID when available, and fresh transaction.
Explicit host verification is recorded only when the host invokes its verifier.
Without a verifier the outcome stays UNKNOWN even after commit. Host sink
exceptions do not affect program state or operation results.

No model-produced success assertion is accepted as verification. The host's
verifier callback must implement the actual task outcome; merely passing a
compiler callback would not prove all intentions. Host events do not expose
hidden predicates to the writer. One-sided intention satisfaction and storage
partial writes remain different measurements.

## Deterministic acceptance

All commands below were run locally with zero new model calls:

- `tests/runtime/minimal_iterative_recovery_test.py --binary <alva>`: PASS on
  real CLI/MCP. Checks stale fail-closed, unchanged winner store, new current
  transaction, preserved assignment/history, read-only continuation, multiple
  turns, final independent checks, no mandatory 02B calls, source bytes
  unchanged, and telemetry ON/OFF/broken-sink equivalence. Also proves that
  an invalid mutation after a successful check is rejected by commit itself.
- `tests/runtime/recovery_loop_policy_test.py -v`: 7/7 PASS. Covers budgets,
  ambiguous transport, failed restart, non-tool completion, repeated conflict
  dropping stale action tails, failed verification and untyped results.
- `tests/air/strict_stale_and_crash_test.py`: PASS with a DEBUG binary
  (`ALVA=<debug-alva>`); crash injection is deliberately disabled in release.
- `tests/air/source_projection_test.py`: PASS.
- `tests/air/transaction_work_test.py`: PASS, including incremental/full
  checking equivalence and transitive-dependent checking.
- `tests/runtime/typed_execution_events_test.py`: PASS.
- `tests/runtime/intent_preserving_recovery_test.py`: PASS; optional 02B intact.
- `tests/mcp/mcp_protocol_test.py <alva>`: PASS for legacy/modern transport,
  authority safety, source/semantic behavior and project build.
- Both plugin packaging tests and the skill-creator validator: PASS.
- `cargo fmt --check`, `cargo clippy -- -D warnings`, `cargo build`: PASS.
- `cargo test`: 41/42 PASS. The sole failure is the existing Windows
  `project::path_confinement_tests::accepts_existing_module_inside_project_root`
  path-prefix assertion. It was reproduced unchanged on clean baseline
  `c4bcfb8c092a2e54736b7d7955a63e5dc2d72566`; it was not repaired here.

The initial crash-test invocation used release and timed out at its disabled
failpoint; rerunning with the required debug binary passed. This was a test
configuration issue, not a product change or an additional scientific gate.

## Scope after acceptance

Minimal Iterative Recovery is the canonical Skill default and reusable host
policy. This is engineering acceptance, not new evidence of model benefit.
V2 and the earlier developmental evidence stay frozen in the research repo.
Fresh M versus M+C validation has NOT_STARTED; this change neither creates
fresh tasks nor invokes models. A large confirmatory study remains unauthorized.
