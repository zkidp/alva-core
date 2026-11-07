# Maintenance Host V2: deterministic engineering qualification

8 November 2026. Base `582955cefb2466016f29b541a0cb0f50e2438790`.
This is a new implementation and qualification, not a rerun of the frozen
DeepSeek comparison. Model generation calls and input-token API calls: **0**.
Historical bundles, registrations, assertions, runtime freezes and results
are unchanged. No new evidence is counted as autonomous agent success.

## Change and rationale

The preceding comparison did not establish a token advantage: among six
both-success pairs, median Native/Text reported-total ratio was 1.50955.
Hiding the same work without measuring it would not repair that conclusion.
This change instead removes model-managed transaction/revision choreography
and makes behavior validation apply to the exact staged candidate before
publication. It prepares a different interface for a prospective comparison.

The model-facing entry has three actions: read a target, prepare a complete
body, and publish one passing proposal. A bounded context is generated from
the actual graph and compiler builtin catalogue, without task-specific edit
recipes. The Host uses actual AEP, actual occurrence-copy body replacement,
actual P34 scope collection/commit authorization, Core durable publication,
and fresh-process AIR inspection. Nothing treats unconnected constructed
nodes or a passing source projection as a successfully published change.

The two new AEP inspections export a staged graph and read direct context.
They are not added to either existing Native MCP profile. The default 20-tool
schema digest remains unchanged; the maintenance profile remains nine tools.
Skill routes now select the actually exposed profile before following general
Native discovery instructions. The default plugin wiring is unchanged.

Return checking moves from a body-editor-only extra check into the common
source/AIR checker. It uses existing inference/unification, expands aliases
for the return comparison and preserves codegen's implicit `Ok` wrapping for
explicit Result returns. Existing expression errors suppress cascading return
errors. This does not establish complete type soundness; real builds and
behavior tests remain required. Existing conformance assertions were retained.

## Evidence

`tests/mcp/host_workflow_linux.py` reads the unchanged compact-maintenance
registration, original bundles, deterministic engineering witnesses and
independent task/regression assertions. Witnesses are test-only and must not
be supplied to a future model session. Each original baseline fails its task
and passes regression. Each candidate is tested in a separate P22 namespace
with staged AIR authoritative, before the live project has `alva-air/current`.
Source files remain byte-identical through staging and publication.

| Original task | Isolated draft check/build/test | Actual P34 | Fresh AIR | Final independent task/regression | Agent tool invocations |
| --- | --- | --- | --- | --- | --- |
| MM01 | PASS | SCOPE_ALLOWED | matches | PASS/PASS | 3 |
| MM02 | PASS | SCOPE_ALLOWED | matches | PASS/PASS | 3 |
| MM04 | PASS | SCOPE_ALLOWED | matches | PASS/PASS | 3 |
| MM07 | PASS | SCOPE_ALLOWED | matches | PASS/PASS | 3 |

Original MM02 bundle:
`352a8b6fa459942b8b1d5469a966a706498afa7a2abbc13c39c457dafb069faf`.
No alpha-renaming or preliminary sharing change is applied. Its unchanged
independent delimiter regression still expects `!` from
`delimiter=%2F&delimiter=%21`.

A separate well-typed wrong candidate passes check/build, fails actual
isolated behavior tests, produces no proposal and publishes nothing. A
standalone MCP STDIO subprocess also completes all three actions using the
actual isolated evaluator. The lifecycle suite exercises actual Core/P34 with
explicit controlled evaluator receipts, covering stale bases, forbidden scope,
bad return types, receipt/draft/source/test-identity changes, failed-test
invalidation, expiry, consumed proposals and fresh-reader failure after commit.
These fault controls do not substitute for the independent behavior tests.

The provider-style schema serializes to 1,245 UTF-8 bytes using the lifecycle
test's JSON encoding, versus 4,281 for the previous ten-tool Text workbench.
This is a byte measurement, not a token or provider-cost estimate. The happy
path requires three agent tool invocations, with no model involved in this
qualification. Backend work remains substantial: initial qualification counted
167/604/1,224/200 Native calls for MM01/MM02/MM04/MM07 respectively, including
153/590/1,210/186 Guard reads. The evaluator additionally performs one fresh
draft read plus project check, build and Cargo test. This accounting prevents
calling hidden Host work an efficiency win. Batching Guard inspection without
weakening its scope proof is a possible later optimization.

Checks: 35 Rust unit tests; fmt and clippy with warnings denied; existing
conformance and codegen regressions; seven public single-file examples and
the ten-module durable store project; both existing MCP profile fixtures;
seven P34 unit controls; both Skill/plugin packaging checks; Host lifecycle
controls; four isolated task qualifications and wrong-behavior control.
The branch workflow repeats compiler, profiles, packaging and lifecycle checks
on Linux and Windows, with real namespace behavior qualification on Linux.
Its downloadable JSON artifact contains per-task receipts/revisions and work
counts, without model transcripts or credentials.

The local Linux qualification used the existing explicit shared-UID resource
profile (RLIMIT_NPROC 512; per-real-UID), since that host already exceeds 128
unrelated threads. CI uses the original 128 profile. No old isolation source
or historical runtime freeze was changed. Compiler/Host bytes have changed;
this is not byte-identical reproduction of a historical experiment.

## Supported conclusion and next decision

**The Host V2 workflow is deterministically feasible on these four tasks.**
It validates exact drafts before protected publication and removes exposed
transaction choreography. It does not show that a model can discover the
right body, improve success, reduce total tokens, beat a competitor, or support
arbitrary projects. Direct context is bounded; evaluator identity does not hash
the entire installed registry/standard library; policy and filesystem writers
remain trusted/coordinated. See the [operator guide](../maintenance-host-v2.md)
for the actual deployment boundary.

Next, freeze a new finite paired comparison only after these checks pass.
Give Text the same requirement/regression testing and publication safety,
equivalent public context/document access, model/config, limits and task input.
Keep independent evaluators hidden from both. Record all attempts, both-success
paired totals, cached/input/output/reasoning separately, latency, backend
commands/Guard work and actual provider usage; unknown requests/cost remain
null. Predeclare the success and efficiency criteria before seeing outcomes.
No new model run is authorized or performed by this implementation artifact.
