# MM01 maintenance pilot

One exploratory pair, fixed order **T then S**, authorized from P29
`8df4d24a55f1176a9fc8b9eaf5292c8b088ff5b4`. This is not a replication,
language comparison, or causal isolation of AIR semantics.

`FREEZE.json` transports the actual original three source/manifest blobs,
public requirement, developer/user inputs, tools, Skill/references, common
language documentation, host-only assertions, SDK identity, CLI identity,
runtime bytes and schedule. No witness implementation, historical candidate,
other task, evaluator or other slot is mounted in the model namespace.
The evaluator strings match P29's MM01 goals/regressions, not a new solution.

The new adapter imports the unchanged P21/P26 controller and P23 service and
process owner. Its only task-specific additions are the revision-bound source
workbench, MM01 evaluator, readonly body observer and two-slot orchestration.
Candidate MCP, source tools, compiler, generated Rust and tests execute in the
existing Linux namespaces. Windows is only the trusted AppServer controller;
there is no Windows/macOS candidate-execution fallback. No Core/AEP/Skill change.

T has exact source editing, pagination, search, baseline Git diff, project
check, and a test callback that performs project build plus independent tests.
S has native MCP mutations, the complete unmodified official Skill/references,
and common readonly source/document/check/test/finish callbacks. S's `diff`
reports authority-file hashes and projection status; staged semantic inspection
is the real native `preview_semantic_diff`. The interfaces and documentation
delivery differ: full Skill is both discoverable and in S's first user input.
Neither interface is called information-equivalent to the other.

All test assertions execute only in a separate evaluation namespace. Model test
feedback is combined PASS/FAIL plus ordinary compiler diagnostics, never test
source, hidden values or assertion output. Final evaluation occurs after the
candidate MCP/sidecar processes close, from the final source or committed AIR,
without selecting a prior intermediate. Fresh MCP reads measure the target and
non-target body hashes, not behavioral truth. Readonly staged observations are
host-only, serial, in the real transaction; counted separately from model calls.

Both arms: `gpt-5.6-sol / low`, 80 model tools, 480 active-turn seconds,
600,000 cumulative reported token **observation** threshold, 20-second interrupt
confirmation grace, concurrency one, one AppServer turn per fresh session.
Actual usage and overshoot remain recorded, cached tokens are not subtracted.
Provider request count and dollar cost are unknown unless actually exposed.
No retries, replacements, third slot, second model turn or result-based tuning.
The fixed post-terminal evaluation allowance cannot buy model repair turns.

Scoring reports independently: target-body change, task test, regression test,
scope, compilation/build, commits, fresh authority read and resources. Scope
uses protected manifest/editable source/public non-target invariants, not gold
patch equality. A changed non-target hash alone is not a regression. S requires
an effective changed committed authority for completed maintenance; detached
staging and no-op commit do not qualify. T's final source is evaluated even if
resource-stopped, but only explicit finish denotes intentional handoff.
Staging/check/commit success never replaces independent behavior evaluation.
Conflict/recovery are not exercised in this pair; do not report them as zero
failures. Temporary private invalidity is not published invalid integration.

Commands (supply approved public SDK paths; do not supply secrets):

```text
python benchmarks/mm01_pilot/pilot.py prepare --attempt preflight-final --alva <Linux binary> --toolchain <Linux Rust sysroot> --registry <public registry>
python -m unittest benchmarks.mm01_pilot.test_pilot -v
# Commit + push the complete PASS freeze, verify clean/origin equality FIRST.
python benchmarks/mm01_pilot/pilot.py run --attempt execution-01 --alva <same binary> --toolchain <same sysroot> --registry <same registry>
```

Raw requests, tool records, final source/AIR and evaluator outputs go only to
ignored `.local/mm01-pilot/<attempt>/RAW.zip`; Git receives its hash manifest
and derived bounded results. Never archive CLI credentials. Preflight creates
AppServer threads and invokes tools but sends **no `turn/start`**. CI consumes
only the exact runtime byte transport, not permissive newline alternatives.
Review the historical MM02 shared-parent scope hazard in the final discussion,
never in MM01 model inputs. Stop after this pair or a real common infrastructure
failure; no automatic next study or merge.
