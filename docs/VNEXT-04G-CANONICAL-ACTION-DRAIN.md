# Canonical Post-Response Action Drain

VNext-04G integrates the host-orchestration rule developed in alva-research
04E (`a8cc3f7329c7c34c23a9f2f0e73c39d4e022f969`) and prospectively evaluated
in 04F (`16ffcc125f1d03dd7650a345febff725edfb83c0`). The frozen 04F
developmental comparison reported a task-paired difference of +5.208
percentage points. It supports this product integration but is not
confirmatory or external-host evidence.

## Canonical rule

Provider request/token admission determines whether the host may request the
next model turn. It does not discard legal actions already returned in a
confirmed completed response. Those actions are offered to dispatch in their
original order under a separate action-admission boundary.

The transport-neutral Skill helper exposes `ReturnedTurn` and an optional
`action_admission` callback. Provider adapters must verify response completion
before constructing `ReturnedTurn.completed`; incomplete or unknown responses
fail closed. Each stable action ID enters an execution ledger before dispatch,
so a duplicate is suppressed and an unknown outcome is never blindly retried.

The actual provider usage ledger is neither cleared nor rewritten. There is no
change to the inherited next-input reservation formula. The normal dispatcher
continues to own operation allowlists, argument validation, tool limits,
authority, transaction, stale and commit checks. Host action admission remains
available for wall-clock, cancellation, tool-count and additional safety gates.

A new conflict ends the old response tail and enters the existing minimal
abort/begin/re-inspect recovery path. Request admission decides whether another
turn may then be requested. A successful commit ends the tail; independent host
verification remains separate, and absence or failure of that verifier produces
UNKNOWN rather than a success claim. The helper never synthesizes a commit.

## Repository and installation boundary

The canonical Skill source and repository-packaged Codex and Claude Code plugin
copies are byte-matched by tests. This commit does not install or update either
plugin in a user's environment. To obtain the integrated behavior, build or
install from this core revision and explicitly reinstall/update the desired
repository plugin package using that host's normal installation workflow. Then
run the corresponding packaging test to verify the source package.

No Rust/AIR operation, MCP schema, source materialization, storage semantic,
RecoveryContext default, snapshot, context compaction or batch patch changes in
04G. No model was invoked by implementation or acceptance tests.

## Deterministic acceptance

`tests/runtime/post_response_action_drain_test.py` uses synthetic provider-turn
and dispatch callbacks. It checks completed-response drain after request-budget
exhaustion, no next request, independent action gates, incomplete-response
fail-closed behavior, conflict and commit tail stops, duplicate suppression,
unknown-outcome non-retry, UNKNOWN verification, and no synthesized commit.

The existing CLI/MCP recovery, telemetry, plugin packaging, Rust and repository
regressions remain part of acceptance. The known Windows path-prefix assertion
from the unchanged baseline remains disclosed rather than repaired here.

Acceptance on Windows completed as follows:

- action-drain plus existing recovery policy tests: 15/15 PASS;
- real CLI/MCP minimal recovery, typed telemetry, optional 02B regression,
  MCP protocol, source projection, transaction work, stale/crash atomicity:
  PASS;
- canonical, Codex and Claude Code Skill validation and both packaging mirrors:
  PASS;
- `cargo fmt --check`, `cargo clippy -- -D warnings`, and `cargo build`: PASS;
- `cargo test`: 41/42 PASS. The sole failure is the pre-existing
  `project::path_confinement_tests::accepts_existing_module_inside_project_root`
  Windows path-prefix assertion. No Rust source changed in 04G.

All acceptance used synthetic callbacks or local binaries; model calls were 0.
