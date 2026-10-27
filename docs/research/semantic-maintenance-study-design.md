# Existing-Code Maintenance / Semantic Evolution: minimal T/S design

**DESIGN ONLY; MODEL EXECUTION NOT STARTED.** Baseline is P28
`e78162036c5a373a1a3f1f4644f6149478aac842`. This document proposes a future
two-slot, one-task developmental comparison, not another twelve-slot function
generation benchmark. No Core, MCP, AEP operation, Skill or historical executor
is changed. It is not an execution freeze or new automatic authorization.

## Question, conditions and falsifier

For a supported, bounded maintenance change in an existing ALVA program, can
the current Native workflow reach a genuinely changed target and independently
correct task/regressions while retaining non-target behavior, compared with
ordinary same-language Text editing under a common resource policy?

Narrow hypothesis: **existing structure makes target-connected semantic edits
operationally usable to this model; transactional publication adds observable
state control without preventing behavioral closure.** This is a package-level
usability hypothesis, not proof that typed structure causes correctness.

- **T — ALVA Text:** ordinary revision-bound exact source editing, read/search,
  normal Git diff and base-hash checks, project check/build, compiler diagnostics,
  independent test and finish. Allow normal repair iterations, multi-file edits
  within scope and local non-published working-tree invalidity. Do not deliberately
  remove normal diagnostics, tests, language documentation or diff inspection.
- **S — ALVA Native Semantic:** existing twenty MCP tools and unmodified official
  Skill/references; resolve/inspect/discovery, existing construction/replacement,
  preview, check, commit; common read/check/build/test/finish as appropriate.
  No text mutation, raw AIR editing, CLI fallback for missing MCP operations,
  prewritten candidate, new operator or extra semantic navigation.

Both use identical task facts, initial source bytes, independent assertions,
model/reasoning, SDK, OS isolation, scope authorization and resource policy.
Both may inspect the complete approved initial program and common language
documentation (`alva/README.md`, exact frozen bytes); S additionally gets its
actual native schemas and full official Skill/reference bytes. These interfaces
and extra operational information differ. Never call them information-equivalent
or attribute a difference solely to AIR semantics. P28's optional-descriptor
override is not carried forward as an established optimization.

The proposed staged-usability hypothesis is not supported in this pair if S
does not connect a target change before a resource stop. It is also not a utility
gain if S connects/commits but fails task or regression tests, or if a no-op
commit is the only publication. T failing while S succeeds is one developmental
observation, not a general effect. If both succeed there is no demonstrated
correctness increment; compare costs and control evidence descriptively. If both
fail under censoring, retain that outcome without diagnosing intrinsic language
or eventual capability. No extra slot, task replacement or budget extension.

## Three fixed candidates and actual qualification

The [catalogue](../../benchmarks/maintenance_design/TASK-CANDIDATES.json) carries
the complete public requirements, exact source-blob provenance and transported
input bytes. They are existing example implementations, not answer-rich stubs.
The [result](../../benchmarks/maintenance_design/FEASIBILITY.json) distinguishes:

1. **MM01, record update policy:** existing `demo.model.touch_size` must leave
   negative-size metadata unchanged and keep +1 for nonnegative sizes. Preserve
   key/etag, accessor/constructor and application result 6. Text and Native
   engineering paths build and pass the same independent tests. Native changes
   only the target body; source projection stays unchanged, private staging
   publishes nothing, commit/fresh authority re-read succeeds. Bounded integers,
   not a new overflow policy. **Only currently eligible model task.**
2. **MM02, parser policy maintenance:** first nonempty decoded prefix wins;
   delimiter last-match and XML/response behavior must remain unchanged.
   Text passes. Native's tested anonymous-parent replacement passes target
   tests/check/commit but changes `parse_delimiter`, failing its independent
   regression. The same original parent revision is reachable from both
   functions. **FAILED_NON_TARGET_SCOPE for this witness, not a theorem of
   inexpressibility.** Preserve it; no silent fix, replacement or model slot.
3. **MM03, cross-module API evolution:** add fallback to `size_of`, use it only
   for negative size, update app caller with 0, retain `run()==6` and touch_size.
   Text builds/tests. Actual MCP lacks add_param/add_call_arg and explicitly
   refuses their descriptions. CLI/P20 expressibility is not Native MCP support.
   **UNSUPPORTED_NATIVE_MCP**, candidate-local, not eligible for the next pilot.

Risks, expected regions and explicit non-model files are recorded per candidate.
MM01/MM03 derive from `tests/project`; MM02 derives from unchanged
`examples/store_split` model/XML modules with a two-module manifest. No full
server, storage, FFI or industrial-regression coverage is claimed. Finite vectors
do not specify every behavior of these libraries.

The initial engineering script attempted a second transaction within one MCP
process and received E_MCP_TRANSACTION_ACTIVE. This is invalid driver use, not
a Core bug or a failed stale protection guarantee. The corrected new candidate
qualification uses one active transaction and does **not** rerun historical stale
gates. All engineering attempts are generation-free and remain private logs.
The independently confirmed MM02 scope failure is retained, not repaired.

## Authority, initial equivalence and independent scoring

Every future slot gets a fresh namespace and the exact approved source-only
baseline; no alva-air/current, compiled answer or engineering witness is present.
Baseline build/behavior is checked once per approved input definition before
generation, not inferred from a Git ID. Original baseline passes regressions
and fails the proposed requirement. MM03's target test compilation fails because
its new arity is absent; the baseline program itself is check/build-valid.

T remains source-authoritative, with no AIR store. S starts from those same
source bytes; its first successful commit creates authoritative AIR. Commit
does not rewrite source. Evaluate S from its **committed authority**, after a
fresh MCP process re-read and project build; evaluate T from final source in a
source-only tree. Never build S's stale projection as its alleged final program,
or silently give T a hidden AIR store. Common host-only readonly body/declaration
inspection may measure both representations but adds no agent feedback.

Independent evaluator appends host-owned Rust assertions only in a separate
isolated evaluation process after candidate MCP closes, then executes generated
code. Neither agent self-report, compiler/check, transaction result nor diff is
the task oracle. Same target tests and non-target regressions apply to both.
S's check may miss type/scope mistakes (P25/MM02); independent build/test is
mandatory, not replaced by check/commit.

Primary slot result: separately report effective target change, final task
PASS/FAIL/UNKNOWN, regression PASS/FAIL/UNKNOWN and scope PASS/FAIL/UNKNOWN.
Scope follows the frozen user-approved editable/protected paths, declarations
and public non-target invariants, not a gold reference edit set. A different
correct implementation is not rejected merely for differing from the engineering
patch. Changed-body hashes are observations; benign alternative edits and
unresolved scope questions must remain distinguishable from behavioral regressions.
`COMPLETED_CORRECT_MAINTENANCE` requires all four to pass and usable terminal
evidence; S additionally needs changed committed authority, not detached staging
or a no-op commit. The primary paired table shows all components, not just this
conjunction. No committed S candidate is NO_COMMITTED_CANDIDATE, not four invented
behavioral counterexamples. A last known correct intermediate is not selected
afterward to replace the frozen final-state rule.

Secondary state-control/safety metrics: precommit authority changes, invalid
integration (independent compiler failure of published state), accepted stale
publication, actual non-target declaration changes, unrelated regression impact,
and recovery completion **only if exercised**. Transient invalid private Text or
AIR working state is not invalid published integration. Stale rejection is not
recovery success or correct task intent. Unexercised properties remain N/A, not 0.
For the conflict-free pilot, S publication means an actual AIR commit. T handoff
means an explicit finish of the candidate source tree, not each intermediate
edit. A resource-stopped Text tree is still scored for final task correctness,
but is not retroactively labeled an intentional publication. Publication-safety
counts with unmatched publication opportunities are descriptive, not an arm
success-rate comparison. Neither path writes the real source repository.

Secondary effort: actual input/cached/output/reasoning/total tokens, model tools,
observer/host-only calls separately, first effective change, construction and
attachment stages, repairs, checks, commit attempts, wall time and termination.
Count changed source files plus semantic declarations; S source bytes alone
cannot measure its edit size. An unrelated body hash change triggers scrutiny
and behavior tests, not automatic proof that every semantic consequence changed.

## Concurrency: distinct matched control probe, not a built-in advantage

The proposed **first model pair is conflict-free**. Existing P20/P25 stale
engineering findings stay separate; MM01's new stale probe was not executed.
Do not manufacture model conflict/recovery outcomes or add paid slots here.

If a later explicitly authorized deterministic stale probe is included, open
two real native MCP processes in the existing isolated driver, not two active
transactions in one MCP process or competing P23 process owners. Both begin
from the same approved AIR base. Winner publishes; loser attempts publication;
assert actual refusal and byte-identical authority after rejection. No recovery
credit for aborting. Do not redesign P23 to run this node.

The corresponding strong Text control is a fresh candidate worktree with a
recorded full source-tree base hash, ordinary exact patch/Git apply --check,
tests and a trusted serialized compare-and-swap publication precondition. A
changed authoritative source hash rejects publication, even if a non-overlapping
patch would apply. If Text lacks this publisher in a study, label it ordinary
unconditional-write control and **do not** infer an intrinsic correctness gain
from S's native stale refusal. With matched checked publication, compare control
delivery and task completion; do not claim an ALVA-only concurrency capability.

No whole-source/AIR joint atomicity, arbitrary semantic merge, external-effect
rollback, kernel security proof or universal stale protection is claimed.

## Executable resource proposal (not inherited 120k)

Proposed minimal future schedule, fixed before any generation: **MM01 T, MM01 S**,
one fresh session/namespace each; no result-dependent reordering or retries.
Model: `gpt-5.6-sol / low`, same resolved provider/configuration in both. No model
availability call is made by this design node. It is one pair, not a general
utility estimate; MM02/MM03 remain visible coverage limitations, not replaced.

| Resource | Proposed common value | Meaning |
|---|---:|---|
| Concurrent slots | 1 | No cross-slot material or history |
| Model tool dispatches | 80 | Existing common service dispatch gate; already-started actions/unknown outcomes are recorded |
| Active-turn wall observation | 480 seconds | Existing active-turn observation allowance; not a provider hard wall cap |
| Cumulative reported total tokens | 600,000 | Observation/interruption threshold, not hard token admission |
| Interrupt grace | 20 seconds | Require actual RPC ack and terminal; otherwise common infrastructure HOLD |
| Provider requests / monetary cost | unknown unless actually exposed | Never infer from one AppServer turn or tool count |

Why not 120k: P27 observes first N construction only in the 85,335–104,164
enclosing interval, after eight prior calls; P28 C0 reaches two detached nodes
then stops at 124,780. These are **input-dominated cumulative charges**, not
unique context lengths. The original 480-second wall allowance was not the first
bottleneck. The proposed 600k gives a bounded several-fold cumulative-work
envelope for existing-code discovery, attachment, checks and repairs. It is a
design choice, **not an empirically validated sufficient budget, power estimate,
predicted request count or promise of success**. Do not tune it after outcomes.
No byte-to-token conversion or cached-input subtraction is used.

Implement the new frozen resource configuration around the existing P21/P26
Controller/interrupt protocol and existing native sandbox service; do not edit
historical runners, reset ledgers or redesign the controller. Model-visible
limits must match the new config rather than reusing P26's old prompt literal.
At the first observed threshold, record trigger order, issue one interrupt,
acknowledge it and confirm terminal. Preserve actual usage/overshoot and unknown
action outcomes. Both conditions keep genuine tool/wall/safety gates. A separate
fixed evaluation allowance follows termination and cannot provide extra model
repair turns. Missing usage remains null, not zero.

Report resource-stopped slots as censored **and** show their frozen final-state
evaluation, with no assertion that extra time would solve them. A larger budget
than P26 makes this a new maintenance workflow study, not a clean replication
or causal explanation of P26/P28. Both arms face exactly this same proposal.

## Freeze, contamination boundary and stopping

Before any separately authorized model execution, bind actual MM01 public task,
initial bytes, tool schemas, full delivered docs/Skill, input strings, trusted
scope policy, hidden evaluator/regressions, SDK/runtime/controller versions,
common budget and two-slot order with exact hashes. Use existing exact-byte
transport; bind runtime bytes actually executed, not platform checkout guesses.
No placeholder request, invented token measurement or post-outcome relaxation.

The allowed candidate namespace contains **only** catalogue public_inputs plus
explicitly approved generic docs. Engineering witness code, goals/regressions,
FEASIBILITY results, P20/P25 solution witnesses, P21/P26/P28 candidates/transcripts,
other slots and repository history are not mounted or exposed by read/doc tools.
Do not copy this design or synthesis into the model prompt: they describe the
engineering sequence and failures. Only the standalone public requirement is
task input. Final evaluator source and expected values remain host-owned; any
public test feedback contract must be identical and frozen for T/S.

Reuse the existing Linux OS boundary for MCP, text-host execution, compiler,
Cargo/build scripts and tests. Native Windows/macOS remain unsupported. No host
execution fallback. A common genuine transport/isolation defect stops remaining
slots; ordinary bad syntax, malformed arguments, wrong behavior, scope mistakes
or resource stops remain candidate outcomes. No slot replacement or post hoc
test changes. No new historical gate or insurance audit is required.

Next action is a reviewer decision on this **one-pair proposal**, not automatic
execution. MM02's narrow scope hazard or MM03's missing exposure may be considered
separately later; neither forces a Core change or blocks MM01. No new primitive,
language feature, benchmark expansion, paper claim or merge follows this node.
