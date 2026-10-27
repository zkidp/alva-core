# P20–P28: engineering control is established locally; agent utility is not

Baseline: `e78162036c5a373a1a3f1f4644f6149478aac842` (P28). This is a
source-backed consolidation and maintenance design, not a new function-generation
benchmark. Historical dispositions, scores, freezes and executors are unchanged.
Model-generation experiment calls and input-count API calls in this node: **0**.
Codex authored analysis and engineering checks; this is not model-free authorship.

## Four different evidence layers

1. **Engine expressibility/control:** a deterministic script can construct,
   attach, validate and publish a change; invalid/stale publication can be refused.
2. **Agent interface use:** the model discovers a real operation, obtains the
   right schema and makes a schema-correct call. This can still be inspection only.
3. **Agent composition:** model operations produce a connected change to the
   intended program. Detached nodes, identical revisions and unchanged commits
   do not qualify. Staged change and published change are separate observations.
4. **Independent behavior:** actual final authority is compiled and executed
   against task and regression assertions, with scope checked separately.

Evidence at one layer does not establish the next. `ok:true`, a clean diff,
`problems:[]`, and a successful commit are not ground truth for layer 4.

## Evidence ledger (do not pool these units)

| Node | Controlling public evidence | Established | Not established / retained disposition |
|---|---|---|---|
| P20 | [case](../../feasibility/native_api/CASE.md), [report](../../feasibility/native_api/README.md), [actual results](../../feasibility/native_api/RESULTS.json), [driver](../../feasibility/native_api/run.py) | One existing two-module metadata API evolution is SUPPORTED through CLI AEP and ordinary Text. Both execute independent behavior successfully. Private invalid staging is repairable; invalid and stale commits do not change authority. Source projection remains old after AIR commit. | Mechanically authored case, not a model success or Native MCP capability test. No recovery completion, whole-source atomicity, universal stale protection or industrial-effect claim. |
| P21 | [report](../../benchmarks/cross_language/REPORT.md), [results](../../benchmarks/cross_language/RESULTS.json), [freeze](../../benchmarks/cross_language/FREEZE.json) | Twelve adapted public-task sessions: Python 4/4 PASS, ALVA Text 1/4 PASS, thin CLI AEP 0/4 committed candidates. Three Text compile failures and discovery/argument failures are observable. | Not an official benchmark score or language effect. C was a thin JSON bridge, not native schemas/full Skill. Old execution lacked an OS sandbox; recursive type-comparison limits are disclosed. Do not retroactively certify security or replace scores. |
| P22 | [analysis](../cross-language-failure-analysis.md), [runtime](../../integrations/benchmark_runtime_v2/README.md), [bounded evidence](../../evidence/benchmark-hardening/P21-FAILURE-ANALYSIS.json) | Prospective Linux OS isolation includes candidate compilation/build scripts/tests; strict Git-blob transport addresses two exact old dependency EOL mismatches. Reconstructed P21 paths separate malformed syntax and missing/guessed arguments from unavailable language capabilities. | Infrastructure repair, no new model results or historical rescoring. Native Windows/macOS execution unsupported. Kernel/toolchain trust and availability limits remain. |
| P23 | [persistent contract](../../integrations/benchmark_runtime_v2/PERSISTENT.md), [Linux record](../../evidence/native-mcp-sandbox/LINUX.json), [adapter](../../integrations/benchmark_runtime_v2/persistent.py) | Real persistent native stdio sessions, transaction IDs, committed AIR re-read and isolated generated-code behavior are supported in the tested Linux boundary. | Not agent discovery/composition. One active process per trusted workspace; lifecycle ownership matters. No source-projection atomicity or arbitrary sandbox guarantee. |
| P24 | [report](../../benchmarks/native_mcp_skill/REPORT.md), [status](../../benchmarks/native_mcp_skill/STATUS.json), [coverage](../../benchmarks/native_mcp_skill/evidence/NATIVE-COVERAGE.json) | Actual Codex AppServer → native MCP/Skill → isolated AEP/AIR integration: Phase A PASS. | Phase B remains BLOCKED_NATIVE_MCP_OPERATION_COVERAGE, 0/12 model tasks. Registry descriptions did not mean MCP-callable construction/attachment. P25 does not retroactively execute P24. |
| P25 | [exposure repair](../native-mcp-operation-exposure.md), [driver](../../tests/mcp/coding_closure.py), [engineering witnesses](../../tests/mcp/coding_closure_inside.py) | Six existing operations exposed; total 20 tools. Four fixed stub witnesses build and pass 27 engineering assertions; private invalid repair and stale refusal observed. | Not 27 model successes or a task-population success rate. Historical anonymous IDs can succeed without an effective edit; transaction check can miss return-type inconsistency. Independent compilation remains essential. Raw local output was removed from tracked tree additively; CI Artifacts carry logs. |
| P26 | [report](../../benchmarks/native_prospective/REPORT.md), [results](../../benchmarks/native_prospective/RESULTS.json), [freeze](../../benchmarks/native_prospective/FREEZE.json) | Twelve new sessions: N resolves targets in 4/4 and makes no native operation errors. T performs source edits. | No connected semantic target change in B or N. T: four final COMPILE_FAIL; B: three NO_COMMITTED_CANDIDATE and one unchanged-commit TEST_FAIL; N: four NO_COMMITTED_CANDIDATE. No end-to-end utility established. N's extra schemas/docs make this a workflow-package contrast, not a pure semantic-mechanism effect. |
| P27 | [audit](../p26-execution-bottleneck-analysis.md), [stages](../../benchmarks/p27_bottleneck/STAGE-TRAJECTORIES.json), [costs](../../benchmarks/p27_bottleneck/TOKEN-COSTS.json), [validation](../../benchmarks/p27_bottleneck/VALIDATION.json) | Audit of 12 archived P26 slots / 225 tools: N reaches descriptions or detached references; B explores APIs and publishes one no-op; T syntax repair remains open. Eleven TOKEN-first, one TOOL-first, no WALL-first stops. | Accounting is not causal attribution. Descriptor-call share is not token share; repeated checks used changed source states. Skill duplication at provider wire is unverified. Optional descriptor policy was a prospective hypothesis, not an audit result. |
| P28 | [report](../../benchmarks/p28_optional_descriptor/REPORT.md), [results](../../benchmarks/p28_optional_descriptor/RESULTS.json), [freeze](../../benchmarks/p28_optional_descriptor/FREEZE.json) | Two fresh HE41 observations: C1 describes once vs C0 three times. Shared live observer distinguishes detached construction from connected body change. | Neither connects or commits; both token-interrupted with acknowledged terminals. C1 total 136,603 vs C0 124,780. DESCRIPTOR_CALLS_REDUCED_NO_OBSERVED_STAGE_PROGRESS_BENEFIT. Not evidence that descriptions are useless or that optional discovery generally helps. |

The P25 fixtures and P20 scripts are engineering evidence, not scientific model
attempts. P24's planned slots are not failures or completed samples. P27 is an
audit of P26, not another independent outcome sample. P28 is selected after P26,
not held-out generalization. No cross-node pooled rate is computed.

This node reads these public records, immutable source and freezes. It does not
claim to have re-audited private P21/P26 archives or rerun earlier acceptance.
Prior archive verification claims remain attributable to their original audits.

## What the positive observations actually support

- An existing program offers real named functions, typed fields and reusable
  expressions: P20 shows a real API change can be staged privately, repaired,
  committed and independently tested. This is stronger than a transaction demo.
- P25 establishes a **particular** Native MCP coding closure, not every Registry
  operation. Engineering expressibility survives later model failures.
- P26's bounded interface observation is useful: target resolution/schema use
  works in N, whereas B has 25 CLI operation errors. Two ordinary N workflow
  rejections still occurred. This does not identify a causal correctness gain.
- P28's fewer descriptor calls show a local behavior difference, but its frozen
  primary endpoint is negative. Do not extend this into more HE41 tuning.

## Unidentified causes and non-claims

Model familiarity, operation composition, document/onboarding support, task
selection and resource censoring remain entangled. All P26 final totals exceed
the 120k observation threshold and turns last only 20.728–65.947 seconds of a
480-second allowance. P28 also crosses the threshold quickly. These are finite,
censored prefixes, not demonstrations of what unconstrained solvers would do.
Cached input is part of input; reasoning output part of output. Cumulative
usage is neither unique context length nor an invoice. Do not allocate a shared
usage interval once to every parallel tool or treat bytes as measured tokens.

Do not claim ALVA superiority/inferiority, inherent correctness gains, semantic
soundness from check/commit, universal non-target isolation, fewer repairs or
industrial demand. Ordinary Git/worktrees plus checked CAS publication can
offer analogous concurrency controls. Safety and behavior are different claims.

## Decision: move to existing-code maintenance, with explicit coverage limits

Stop from-zero HumanEval construction as the primary task. The next falsifiable
question is whether a model can apply **bounded edits to an existing identified
program**, retain unrelated behavior, and close independent verification through
the current Native workflow compared with a strong same-language Text workflow.

The [new candidate catalogue](../../benchmarks/maintenance_design/TASK-CANDIDATES.json)
was declared before its engineering execution. [Actual qualification](../../benchmarks/maintenance_design/FEASIBILITY.json)
adds three maintenance candidates without changing old fixtures or Core:

| Candidate | Text engineering | Native engineering | Consequence |
|---|---|---|---|
| MM01 metadata update policy | PASS | SUPPORTED: connected change, private staging, commit, fresh authority, independent goal/regressions PASS | A one-pair maintenance pilot can be designed. No agent outcome exists. |
| MM02 first-nonempty query prefix | PASS | FAILED_NON_TARGET_SCOPE: goal PASS, unrelated delimiter regression FAIL after check/commit | Preserve the failing sequence and its counterexample; exclude it from a claim of ready local-edit coverage. Do not fix Core or search alternate witnesses until PASS in this node. |
| MM03 fallback accessor API + caller | PASS | UNSUPPORTED_NATIVE_MCP: add_param/add_call_arg absent and descriptors explicitly refused | Candidate-local surface gap, not proof AIR/CLI lacks signature evolution. No new primitive or MCP exposure. |

MM02's shared anonymous parent belongs to both parse_prefix and parse_delimiter.
The tested replace_expression sequence changes both. For
`delimiter=%2F&delimiter=%21`, expected `!`, actual `/`; target prefix tests pass.
The bounded finding is an ownership/scope hazard of this sequence, not a proof
that every possible sequence is impossible or that all semantic edits spread.
It is directly relevant to the proposed value claim and must remain visible.

All three are public-example-derived development cases, not three independent
industrial projects; MM01/MM03 share an initial fixture. MM02 uses two unchanged
store modules under a declared component manifest, not the entire storage
server. Their engineering selection is not a model-performance selection.

Only MM01 is presently ready for the proposed [minimal T/S study](semantic-maintenance-study-design.md).
MM02/MM03 do not block that independent candidate. No maintenance model study,
Core repair, broader task search, language redesign or historical rerun is
authorized or started here. **STOP after design and review.**
