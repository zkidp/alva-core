# Single native API evolution case (declared before mutation)

Baseline: `7168a2346b9f3656e0f8d68fbee294d525a292a0` (verified P2).
Canonical main at setup: `cd73ae8c653953289ee758ce24e4821f1b4c5108`;
P0/P1/P2 are open stacked PRs, not merged main. No merge is performed.
The closeout decision is the public `docs/NEXT-RESEARCH-DECISION.md` added in
`0a77ac8f57253732e06d9670320aa73ba1f0c1a7`; no P3 artifacts are imported.

## Public maintenance requirement

Use the unmodified public `tests/project` metadata library and its dependent
application. This is an upstream-fixture-derived development case, not an
industrial workload or an agent-effect sample. The existing unary
`demo.model.touch_size(m)` always increments size by one; `demo.app.run()`
constructs size 5 metadata and returns 6 after calling it.

Evolve the API to `touch_size(m, delta: i64)`: add delta to size, preserve key
and etag, support signed/zero deltas and repeated calls. No old unary overload
is required. Update the application call to supply 1, preserving run() == 6.
Affected modules: demo.model (signature/body), demo.app (call arity).
Arithmetic overflow is outside this case; vectors are bounded.

The independent evaluator is `behavior.rs`: actual generated Rust execution,
not AIR/check success, literal inspection, or agent claims. Baseline tests
exercise unary increment; target vectors exercise +7, 0, -3, negative starting
size, repeated changes, preserved metadata and application compatibility.
Both source and structured paths use the same evaluator and task facts.

## Declared sequence and boundaries

Before mutation, query applicable_operations, describe_operation for each used
operation, and describe_construction. If the public surface cannot express
this exact edit, record the missing capability and UNSUPPORTED; do not switch
cases or add operations. Implementation/runtime defects are FAILED, not an
excuse to expand Core.

For an expressible case: add the parameter first, observe check/commit refusal
of the incomplete cross-module state, repair the body and caller in the same
staging transaction, preview/check/commit, reload authority and build/test.
Record authority bytes before/after and unchanged source projection bytes.
Ordinary source editing must face the same intermediate check and final tests;
it does not acquire AIR authority or a transactional publication API.

Predeclared stale-base scenario: establish original AIR authority, open two
sessions at that same revision, stage the API evolution in one, and make a
checked rename `demo.app.run` -> `demo.app.run_legacy` in the other. Commit the
API evolution first; the old rename commit must return E_AEP_CONFLICT and leave
authority unchanged. Abort the losing session. This is a perturbation within
this case, not another task. It does not test recovery or concurrent source
materialization. No automatic recovery is added.

Result: SUPPORTED only if expression, repairability, independent behavior and
stale protection are observed; UNSUPPORTED for a missing public capability;
FAILED for an observed violated expectation. Generation and input-token API
calls = 0. Codex authors/mechanically executes the script; this is not a
controlled coding-agent performance experiment. Only this one case is run.
