# MIC-02: compact maintenance interface diagnostic protocol

Design registered before any new model generation, 8 November 2026. Base:
`0edae8ec2ebcba8e2b340fb329e82eed6730027c`. The design follows MIC-01 diagnosis;
it is not an independent confirmation selected without observing prior results.

Question: does the compact Native **interface bundle**, with the repaired
shared workbench, reduce reported token use without reducing correct authorized
completion, relative to strong controlled Text editing of the same ALVA tasks?
It does not test language superiority, a direct CodeStruct comparison, or the
isolated causal effect of one API method. The common workbench changes too.

## Fixed tasks and schedule

Four known tasks, two fresh repetitions per arm, 16 slots maximum:

| Task | Component | Coverage |
| --- | --- | --- |
| MM01 | demo.model / demo.app | Record update and metadata preservation |
| MM02 | store.model / store.xml | Original shared prefix parser, delimiter/XML preservation |
| MM04 | build.model | Graph completeness and explicit error behavior |
| MM07 | store.model | XML escaping; prior both-arm failure retained |

Source bundles, public requirements, authorized bodies, hidden goal/regression
assertions and manifests are copied byte-for-byte in value from the old
registration. The three source groups are correlated; there are zero independent
new tasks. MM05/06 are omitted to bound this diagnostic and avoid allocating
three tasks to build.model. Selection is author-informed, including old outcomes;
do not generalize success rates to unseen tasks or represent this as the next
paper's decisive benchmark.

Seed 20261108 shuffles eight task/repetition pairs. Within repetition one use
T then N; repetition two N then T. Exact schedule is in REGISTRATION.json.
No post-result task replacement, extra repetitions, dropped rows or expansion.

## Arms, context and boundaries

Both arms receive the same public task, original source-only component,
language docs, complete official Skill and references, compact profile guide,
study checks/tests and scope policy. The new guide overrides incompatible
legacy workflow instructions; T edits source and N uses the compact profile.
Docs are equally available, not force-loaded into one arm. Task-specific
engineering witnesses, old traces/results, evaluator implementations and
precomputed body/attachment revisions are never model-visible. Each session
starts fresh, with no chat inheritance, repository access, shell or delegation.

T receives ten typed study tools: revision/read/search/diff/doc/check/test/
finish, unique exact-span edit and full-file write. N receives the same eight
read/check/handoff tools and the nine real `alva mcp --profile maintenance`
tools. N does not expose study_edit/write or the old low-level constructors.
Source reads in N return import source, while read_function reads current AIR;
the common instructions explicitly explain the distinction. No task-aware
shortcut or prepared replacement is supplied.

`contract.py` defines exact typed schemas and validation. Calls use object
arguments, not an action string plus a serialized JSON string. Ordinary tool
errors may be repaired within the one fixed turn; they are retained, not an
automatic candidate failure or a reason to replace the slot.

Both arms receive the same bounded compiler feedback and task/regression
status. No expected values or hidden assertion source is returned. A separate
fresh evaluator consumes exact final source in T or published AIR in N.
N must actually commit and a new process must agree with its authority. A
detached node, staged graph, successful check, or no-op does not earn completion.

As in MIC-01, the actual P34 collector supplies complete baseline/final scope
evidence for BOTH arms. Use the same final function-body and metadata policy;
do not credit N with a preventive Guard unavailable to T. No live asymmetric
P34 commit interception is part of this comparison. Product Guard integration
already has separate deterministic tests and is not a new efficacy endpoint.
All workspaces are disposable; no production deployment occurs.

## Model, budget and stop behavior

Model gpt-5.6-sol, low. Confirm the exact requested model is available through
the real session metadata before generation; no fallback or substitution.
Concurrency one, one fresh slot and one model turn per scheduled entry; no
replacement, extra turn, operator repair or automatic replay.

Each arm: 80 total model-visible tool calls (study plus Native), 480 active-turn
seconds, 600,000 cumulative reported-token observation threshold, 20-second
interrupt grace. These are observation/interruption limits, not provider hard
caps. Overshoot and delayed usage reports are retained. The maximum schedule
is sixteen logical model turn requests; provider generation request counts are
not assumed equal to turns. Dollar cost and provider request counts stay null
unless reliably observed. No token-count API is needed.

Pin an explicit copied CLI executable and required companion bytes, SDK ELF,
Rust toolchain, public Cargo registry, Python runtime and new study runtime.
Record executable hashes before and after EVERY slot, with actual process launch
identity. A matching version string or PATH resolver is insufficient. Each
slot records authority, inputs, prompt/docs/tool schemas, limits and code hashes.

First common provider/service failure (including terminal failed turns),
authentication, isolation, executable mismatch, unexpected tool exposure or
unconfirmed cleanup stops all subsequent launches. Use the repaired provider
gate, not the old controller behavior. Retain partial rows; no alternate account,
budget extension, later resumption, or replacement within this registration.
Ordinary candidate errors, wrong behavior and budget interruption with confirmed
cleanup remain task outcomes. Failure to reach terminal/cleanup confirmation
is infrastructure uncertainty. Preserve interruption request, acknowledgment,
terminal reason, usage availability and owned-process cleanup receipt.

## Outcomes and fixed diagnostic rule

Correct completion requires confirmed terminal state, independent task PASS,
regression PASS, changed target body, unchanged non-target bodies and declaration
metadata, and candidate-bound fresh authority. N also requires a successful
Native publication receipt. Infrastructure-invalid slots are UNKNOWN rather
than ordinary wrong answers. Final scoring never repairs a candidate.

Report every scheduled slot, completion counts out of eight per arm, failed
checks and tools, scope refusals, actual publications, model/backend calls,
latency, complete raw usage fields, and observed resource totals with missingness.
Keep input, cached input, output, reasoning output and reported total separate;
cached input is included in total and reasoning output is a subset of output.
Never subtract cached input from total or add reasoning output twice.

The cost endpoint is the **median of per-pair N/T reported-total-token ratios**
on pairs where BOTH succeed and both usage reports are complete. This is not
the ratio of arm medians. Also report the latter descriptively and all failures
to expose survivor selection. Setup, model-active, backend evaluation and
finalization timing are separate; unavailable fields are null, never zero.

Fixed screening rule, implemented in score.py:

1. Missing/invalid scheduled slots: INCONCLUSIVE_INFRASTRUCTURE.
2. Fewer than four usable both-success cost pairs:
   INCONCLUSIVE_INSUFFICIENT_PAIRED_SUCCESSES.
3. Otherwise, N has at least as many correct completions as T across all eight
   pairs AND median paired token ratio <=0.75: EXPLORATORY_FAVORABLE_SIGNAL.
4. Otherwise: NO_EXPLORATORY_FAVORABLE_SIGNAL.

The 25% threshold is a product screening target, not significance, a confidence
interval, proof of superiority, or permission to ignore failures. Better
completion with no token reduction may motivate a separately registered
quality hypothesis; it does not retroactively satisfy this efficiency screen.
Two repetitions and four familiar tasks cannot certify general reliability.

## Runtime qualification before generation

REGISTRATION.json freezes DESIGN and inputs; it deliberately has runtime_freeze
null and status DESIGN_REGISTERED_RUNTIME_NOT_FROZEN. Do not label it a validated
execution freeze, overwrite an old freeze, or point the old launcher at it.
This phase performs no model launch and supplies no generation entry point.

The next implementation stage must integrate the typed workbench and compact
MCP into a new runtime, then retain these no-model receipts before producing
a separate immutable runtime freeze commit:

- All four original baselines: check/build/regression PASS and task TEST_FAIL.
  Real deterministic T and compact N routes must both reach task/regression/
  scope PASS with exact candidate binding; unavailable routes stay blockers.
- Real AppServer-to-Linux T/N dispatch, exact model availability, exact tool
  exposure, public-only context mounts, current AIR reads, commits and fresh
  independent evaluation. No turn/start or inherited model thread is used.
- Per-slot executable stamping, source versus AIR revision handling, separate
  backend/model accounting, stop-on-first-provider-fault and confirmed cleanup
  verified with controlled faults. Test the actual new runtime, not only mocks.

These checks address observed failures, not extra research endpoints. Freeze
the successful receipts and runtime bytes before the first model turn. On a
specific implementation/environment failure, report its evidence instead of
launching an unqualified experiment. This is a bounded diagnostic, not a
continuation or rescore of the paper's historical slots.
