# P27 — P26 coding-agent execution bottlenecks

## Decision and evidence boundary

The strongest supported account is **different unfinished paths under an
input-dominated cumulative observation budget**, not an inability of the ALVA
engine to express these tasks. N obtains operation information correctly but
does not connect a new result; B loses calls to interface exploration and also
does not connect its constructions; T changes source but does not close syntax
repair and behavioral verification. None is a demonstrated causal root cause.

Select exactly one low-cost hypothesis for a future **two-slot**, fixed-HE41
developmental contrast: make the Skill's mandatory `describe_operation` step
optional when an advertised native schema is sufficient. Keep all documents,
native tools, safety rules and budgets otherwise unchanged. This tests a
preparatory-call policy, **not** whether descriptor content is useless or whether
Skill text alone caused P26 failure. No experiment is executed or authorized by
this analysis. The exact design is [NEXT-EXPERIMENT.json](../benchmarks/p27_bottleneck/NEXT-EXPERIMENT.json).

Baseline: PR26 `fac39867f32ab4b3b428ed08a4eaf28be08dafa9`.
The actual controlled original ZIP was available and its SHA256 verified before
reading records:

```text
b37b499ec63388824efde38c395c221a71ae04d1367b1ad8555309c3888c6dd2
```

All 50 entries were retained, with 12 actual slot records. P26 outcomes, freeze,
runner and source files remain unchanged. No candidate program, compiler,
provider or historical gate was run. Codex authored the analysis; “zero calls”
here means no new benchmark/model-generation or input-count API calls, not
model-free authorship.

Authority order: the checksum-bound archived AppServer tool/RPC and usage
events, matched native MCP dispatch records and independent terminal evaluations;
then the exact P26 Git-blob freeze and summaries. The public summaries reconcile
with the archive. Raw logs, machine/account metadata, complete arguments,
reasoning text and candidate source are not copied into this PR. Public derived
records contain stage/operation names, counts, hashes, bounded diagnostic
categories and exact archive/event locators, not replacement transcripts.

## How to inspect the reconstruction

[STAGE-TRAJECTORIES.json](../benchmarks/p27_bottleneck/STAGE-TRAJECTORIES.json)
contains all 225 observed tool calls. Each call has a one-based ordinal,
zero-based archive event start/end indices, argument/result fingerprints,
observed response classification, diagnostic categories and usage brackets.
Native calls are joined by actual call identity to `linux.json` dispatch rows;
dynamic CLI/text calls use the archived host tool-result events. No action is
invented for a gap. Chronology distinguishes model STOP from the subsequent
independent host evaluation and overall closeout.

`CHECK`/`COMMIT` in a stage column means a call was reached. Envelope success
does not establish compiler PASS or a modified target; explicit separate fields
record those facts. A late-stage call does not close missing earlier stages.
An effective *text* edit below means changed source bytes, not correct behavior.

| Slot | Tools | Deepest observed path and omissions | Last tool | First stop trigger |
|---|---:|---|---|---|
| 01 HE3-N | 13 | begin, target inspection, schema; no construction | describe_operation | TOKEN |
| 02 HE41-T | 27 | first changed source at #4; 12 checks, none PASS; final compile FAIL | check | TOKEN |
| 03 HE42-T | 11 | first changed source at #5; baseline check PASS, no post-edit PASS; final compile FAIL | edit | TOKEN |
| 04 HE23-T | 11 | first changed source at #4; 4 checks, none PASS; final compile FAIL | check | TOKEN |
| 05 HE42-N | 13 | begin, target inspection, schema; no construction | describe_operation | TOKEN |
| 06 HE23-N | 10 | two ordinary condition rejections, then discovery/schema; no construction | describe_operation | TOKEN |
| 07 HE3-T | 80 | first changed source at #5; 39 checks; 3 post-edit PASS, then invalid final source | check | TOOL |
| 08 HE3-B | 18 | interface/entity exploration; failed construction, no connected change | create_ (rejected) | TOKEN |
| 09 HE41-N | 10 | two reference calls, one unique revision; no attachment/check/commit | create_reference | TOKEN |
| 10 HE42-B | 11 | exploration, failed node request, denied text edit; no attachment | edit (rejected) | TOKEN |
| 11 HE41-B | 10 | failed binary construction; baseline check PASS, late function inspection; no attachment | inspect_function | TOKEN |
| 12 HE23-B | 11 | under-specified detached call, unchanged commit, later new transaction | begin_transaction | TOKEN |

No slot invoked the model-facing independent `test` callback. The host still
ran its frozen final evaluation after the turn stopped. Final outcomes stay:
T four COMPILE_FAIL; B three NO_COMMITTED_CANDIDATE plus one TEST_FAIL; N four
NO_COMMITTED_CANDIDATE. P25's engineering witnesses are not model successes and
were not rerun or used to score extra candidates.

## Native path: successful discovery, no connected modification

Across N's 46 calls there were 19 `describe_operation`, 3 `describe_construction`,
four each of begin/inspect_project/resolve/inspect_body/applicable_operations,
two `create_reference`, and two dynamic calls. Thus 22 calls retrieved schema
or construction descriptions, but many were parallel in the same usage interval.
**22/46 is a call-count share, not a token-cost share.** Most descriptor calls
were for different operations; calling them exact repeated requests is wrong.

For HE3-N and HE42-N, description retrieval began with prior observed totals
92,201 and 91,958 respectively. HE23-N began it at 102,767. HE41-N began it at
67,054 after grouping target inspection calls; task/order differences prevent
attributing these differences causally to grouping. The first three stopped
while retrieving descriptions. Their successful schema/resolve responses are
observable; no future construction/attachment request is recorded. Do not say
the host dropped an already-generated attachment or that another turn would
have completed the task.

HE41-N calls #6–8 describe reference/binary/replacement. They share one enclosing
usage increment: 67,054 → 85,335. Call #9 creates reference `n` in the interval
85,335 → 104,164; call #10 repeats the same arguments in 104,164 → 123,133.
Both return the **same** revision, not two distinct graph nodes. Neither a binary
nor replacement was requested. The fresh final authoritative body hash equals
the initial hash and no authority current file was published. Evidence:
slot 09 calls #6–10 and its construction/authority fields.

There are zero **native AEP** errors, but not zero workflow rejections. HE23-N
call #1 attempts `doctor` through the unavailable `aep` action; #4 tries an
absolute-path read rejected by that condition. The Skill requests CLI doctor,
while the frozen surface exposes no separate doctor tool. This is an observed
surface limitation, not a new common transport exception or an excuse to reopen
P26. Its causal contribution is unknown; the same slot subsequently resolves
the target and retrieves schemas. The errors remain separate from native API
parameter correctness.

## Bridge path: exploration errors and an unchanged commit

B records 14 E_AEP_UNKNOWN_TOOL, 7 E_AEP_ENTITY_NOT_FOUND, 3 E_AEP_OP and one
E_AEP_NO_TRANSACTION: the existing total of 25 CLI errors. Separately there are
four rejected paths and two condition-denied text edits. The thin bridge has
no individually advertised semantic schemas/Skill; no B slot calls
`describe_operation`. Requests for `help`, `list_tools`, `get_module`, `query`
and other unavailable names are observed error sequences, not evidence about
hidden thought or about the absence of implemented ALVA capabilities. Some
inspection eventually succeeds (e.g. HE41-B's final `inspect_function`); do not
equate lack of `resolve_entity` with no useful inspection whatsoever.

HE23-B is especially diagnostic. Call #6 sends `create_call` without a `name`
and receives a node revision. The frozen native schema requires that field;
the CLI nevertheless returns a success envelope. This is recorded as an
under-specified successful **detached** construction, not proof of a correct
expression. Call #7 commits with no intervening attachment, preview or explicit
transaction check. Its committed project revision equals the begin revision.
Independent fresh-process body hashes are unchanged, and behavior FAILS.
Subsequent tool-list/capability exploration and a new begin do not repair that
state. Evidence: slot 12 calls #3/#6/#7/#8–11, missing-field and authority fields.
No Gateway permissiveness or operation semantics is repaired in this node.

## Text path: changed bytes, recurring syntax errors, no behavior loop

T made 58 accepted byte-changing edits and 59 compiler checks. Final recorded
E_DIAG categories include unsupported expression tags (`var`, `name`, `for`,
`mul`, `binary`, `binop`, etc.), malformed blocks and missing valid function
bodies. Returned diagnostics are visible tool evidence, not fabricated test
counterexamples. The attempted forms were not accepted by this compiler;
that is not proof the task requires a missing language feature.

HE41-T/HE23-T had no check PASS. HE42-T's sole PASS at call #4 precedes its first
edit (#5), so it is only a baseline result. HE3-T's PASS calls are #4 (baseline)
and #56/#76/#78 (after edits); further editing leaves invalid final source.
The three check-valid intermediate states have **no archived independent behavior
evaluation**. They cannot be called correct tasks or rescored without new work,
which this node does not perform. This also limits a blanket “always invalid”
description of the repair path.

The T trace has 55 repeated argument signatures, mostly `check {}`. Each was
applied to a different source generation; same-source-state repeated calls are
zero, and no exact source-byte state was revisited. These are not 55 proven
wasted calls. Recurring diagnostic categories across changed source states
support incomplete repair, not a claim about model familiarity as an internal
mental state. Each normalized diagnostic has its code, tag/category and message
digest linked to its actual tool event; final diagnostics are recorded separately.

## Input, schemas, duplication and usage

[TOKEN-COSTS.json](../benchmarks/p27_bottleneck/TOKEN-COSTS.json) records exact
UTF-8 sizes and hashes of each frozen component and the per-slot prompt sizes.

| Component | Bytes | Measurement boundary |
|---|---:|---|
| Official Skill | 3,723 | Exact inline text and identical workspace file contents |
| workflow reference | 4,415 | Exact frozen text |
| diagnostics reference | 2,738 | Exact frozen text |
| examples reference | 2,524 | Exact frozen text |
| All four documents | 13,400 | Not a provider token count |
| Twenty native schemas | 13,021 | Defined canonical JSON serialization, not provider wire |
| Shared study schema | 543 | Defined canonical JSON serialization, not provider wire |

T/B initial prompts are 807–918 bytes; N prompts are 14,387–14,498 bytes. Each
document occurs once in the explicit N initial text; T/B contain none. The same
documents are also written to the discoverable workspace Skill directory. The
`$alva` marker is present, but turn/start contains only an explicit text item,
not a separate `skill` input item. Archived events confirm the exact initial
user text, not the serialized provider request or any internal automatic Skill
expansion. Therefore **an additional provider-side full-text copy is unknown**.
The started/completed userMessage copies in the event log are two lifecycle
events for one message, not evidence of two model-input deliveries.

Native RPC results also repeat the same parsed payload in text and
structuredContent representations. The derived trace quantifies this at the RPC
boundary only. Whether Codex forwards both representations, deduplicates them,
or defers parts of tool schema delivery is not established by this archive.
Descriptor responses contain extra preconditions/examples, not merely identical
copies of every advertised input schema. No complete information-equivalence
claim is made.

First reported input counts are 10,213–10,242 tokens for T/B and 14,163–14,190
for N. This is a joint package/configuration observation; it cannot allocate
the difference to Skill, schemas or system instructions individually. Exact
provider token counts for component spans are unavailable. No counting endpoint,
byte-to-token conversion, reconstructed provider request or tokenizer estimate
is substituted for them.

| Arm | Input | Cached input | Output | Reasoning output (subset) | Total |
|---|---:|---:|---:|---:|---:|
| T | 492,676 | 431,872 | 6,304 | 2,588 | 498,980 |
| B | 500,532 | 422,144 | 5,280 | 2,849 | 505,812 |
| N | 513,636 | 441,856 | 4,373 | 1,915 | 518,009 |

Cached input is a subset of input, reasoning output a subset of output. Neither
is added twice or deducted from total. Counts accumulate across requests and
sessions; they do not measure unique context size and cannot establish dollars.
All arms are input-dominated, including T/B without ALVA documents. This is not
an attribution of the entire budget cost to the Skill.

Each tool is bracketed by the last preceding and first subsequent usage event.
Shared intervals explicitly list their call ordinals; **do not add the same
increment once per call**. An interval includes model input/output and potentially
several parallel tools; individual call charge is null. A missing bracket remains
null, not zero. Initial turn-origin deltas are labeled accounting intervals,
not measured pre-call usage. HE41-N's first construction is bracketed by
85,335/104,164 with eight prior calls; HE23-B's first returned node by
53,379/64,908 with five prior calls. T first changed-byte edits are calls
#4/#5/#4/#5 for HE41/HE42/HE23/HE3, with preceding observed totals
31,178/41,840/31,109/42,167. No slot reaches an attached new target.

The trace confirms **11 TOKEN-first**, **1 TOOL-first**, **0 WALL-first** stops.
In HE3-T the 80th callback event precedes the later token-crossing notification,
even though both limits are exceeded in the final record. Actual model elapsed
times are 20.728–65.947 seconds against 480 seconds. No wall-clock bottleneck is
observed; tool durationMs is not CPU time. All 12 interrupts and terminals are
confirmed. Seven usage updates occur in each N slot; T/B have 10 or 11. These
are observations, not proven API-request counts. All final totals exceed the
120,000 observation threshold; overshoots remain in the trace. They are not hard
provider cap violations. Finite censored prefixes cannot establish how a longer
run would end.

## Mechanism classification and the single next hypothesis

| Mechanism | Supported observation | Not established |
|---|---|---|
| Language syntax use | T repeatedly emits unsupported forms | Internal unfamiliarity or missing required language capability |
| Diagnostic repair | T ends invalid despite checks; HE3 temporarily check-valid | Correctness of unchecked intermediate behavior |
| API/Schema use | B unknown names/fields/operands; N native calls have no parameter errors | Schema support causes final task correctness |
| Repeated/unproductive exploration | B rejected names; HE41-N duplicate reference revision | All repeated checks or all distinct descriptor queries are wasted |
| Detached construction | N/HE41 and B/HE23 return nodes with no attachment | A successful node return is a program edit |
| Operation composition | Multiple ID-dependent construction/attachment stages remain | That composition complexity caused the observed failures |
| Context/budget | Input-dominated cumulative limits stop every prefix | Which text component caused it, or that extra budget would solve it |
| Unknown | No private reasoning/provider wire or future actions | A single proven causal root cause |

Why choose optional descriptor discovery rather than a larger intervention:
it changes one narrow rule corresponding to 19 actual descriptor calls while
leaving real schemas and safety checks intact. HE41 supplies a concrete
construction-but-no-attachment boundary. No new operation, reference example,
task hint, language redesign or budget increase is needed. Eager-document
compaction is an alternative, but actual duplicate provider injection is
unverified and combining it here would change two variables. Repair guidance
or budget redesign would address different unresolved hypotheses.

The proposed two fresh HE41-N slots use the same full document corpus and
advertised schemas. C0 retains the P26 rule; C1 adds only the exact policy
override in NEXT-EXPERIMENT.json. A shared trusted read-only observer would
record the live target-body hash after mutation in both conditions, without
feeding evidence to the model or repairing/committing. Detached success and
anonymous-revision no-ops get no attachment credit. Commit must still be followed
by fresh authority reread and independent compile/behavior evaluation.

Primary: an actual connected target-body change before interruption. Secondary:
descriptor behavior, observable usage intervals, committed target change and
independent correctness. If descriptor calls decrease but no connected change
is reached, the hypothesized stage-progress mechanism is unsupported in that
wave. If both conditions connect, there is no differentiating result. No change
in descriptor behavior means no behavioral uptake, not content ineffectiveness.
One observation per condition is developmental, not statistical confirmation.

This is an analysis-informed development task, not fresh-task validation. Two
slots are sufficient for the bounded falsifier; no third slot, retry or
replacement is proposed. A new real freeze and explicit future execution
authorization are still required. **P27 ends here.**

## Reproducibility and validation

See [audit.py](../benchmarks/p27_bottleneck/audit.py),
[README](../benchmarks/p27_bottleneck/README.md),
[tests](../benchmarks/p27_bottleneck/test_audit.py) and
[VALIDATION.json](../benchmarks/p27_bottleneck/VALIDATION.json).
All 12 archived prompts, tool counts, usage totals and outcomes reconcile with
P26's exact public blobs. Public output is sanitized derived accounting, not raw
logs. CI tests synthetic corner cases and public-source consistency on Linux
and Windows; it does not claim possession of the private ZIP. No P26/P21/P3
file, Core/AEP/MCP implementation or historical score is changed. No model,
input-count API or candidate-code execution was started by P27. STOP for review.
