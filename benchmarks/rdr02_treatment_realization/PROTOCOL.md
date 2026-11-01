# RDR-02 prospective archival comparison

Registered before archive-content analysis or E0/E1 execution. Approved base:
`5cc33a531e465d97ded33a0749db6451468a54b8`. RDR-01's question, four units,
strong baseline and parity stop rule are unchanged. This is read-only analysis,
not a replay, model study, new candidate, rescore or production mechanism.

## Fixed inputs and units

- U1: P24 Native coverage; public real MCP coverage records and Phase-A
  evidence. **Not a model unit**; never in an Agent outcome denominator.
- U2: P26-12-HE23-B, P26 original RAW.zip and public records/P27 stages.
- U3: MM01-S, P30 original RAW.zip, observer, backend and AppServer records.
- U4: P32-MM01-S, P32 original RAW.zip, observer, backend and AppServer records.

INPUT-MANIFEST.json freezes exact public Git-blob paths, hashes and schema
roles, and original archive identities, lengths and selected member names.
Public inputs are exact blobs in the **current committed tree**, loaded using
`git show HEAD:<path>` and verified against the manifest, never by resolving
the historical base commit at runtime. A shallow or new single-root checkout
therefore needs no old Git objects. Private archives remain local;
only derived factual values, hashes and precise pointers may be published.
Archive lookup is by explicit CLI arguments, not machine-specific paths.

The discovery step hashes archives and lists member names, without interpreting
their contents. Integrity mismatch makes that source unavailable/fail-closed;
no replacement transcript or archive is manufactured. Analyze all four units
in a batch; a missing archive does not prevent other units' analysis.

## Evidence schema / extraction boundary

One shared evidence projection supplies **the same accessible observations**
to both evaluators: exposure/probed operation names and actual errors; request
and dispatched call IDs/arguments/results; constructor and attachment events;
baseline/staged/final body identities; before/commit/fresh project identities;
host denial; independent check/build/task/regression/scope records and exact
tested-state identity when available. Every derived fact needs a source ID,
ZIP member or public path, JSON pointer (or JSONL line) and record hash.

Full source transcripts are neither copied to Git nor used as classifier
features. Do not inspect model private reasoning. Extract tool/RPC, observer,
authority and evaluator records only. Historical final score/disposition labels
are **post-hoc crosschecks**, never classification inputs. Do not use reference
patches, witness programs or additional assertions. Unit IDs route schemas,
not outcomes. The source bank/projection is shared; no E1-only evidence.

Use tri-state factual claims: true/false/null (unknown), with explicit N/A
for non-model coverage. Missing revision, dispatch or evaluation identity is
not silently supplied by a report's PASS string. Public derived observations
may corroborate raw records, but do not replace absent raw state evidence.

## Frozen E0/E1 semantic rules

Both receive exposure, all relevant actual calls/results and available state/
evaluation data, including AIR snapshots. E0 implements ordinary process +
target-state diff + tested/published identity checks. E1 constructs an explicit
exposure/dispatch/construction/attachment/staging/authorization/publication/
evaluation chain. Implementations are separate; equality is tested, not forced
by sharing a final classifier or feeding one evaluator the other's output.

For each stage output TRUE/FALSE/UNKNOWN/NOT_APPLICABLE with evidence pointers.
Required operations explicitly refused/absent while Registry advertises them
constitute CAPABILITY_COVERAGE_GAP. A native commit response and final authority
establish publication, not target change. Equal before/after target identity
with a real published commit is PUBLISHED_WITHOUT_TARGET_CHANGE; correctness
still comes from independent task tests and task requirement, not empty diff.
Changed staged body + host denial/no Native commit establishes
CONNECTED_NOT_PUBLISHED. Changed target + actual commit + matching fresh
authority + matching tested authority + successful independent task/regression/
scope establishes VERIFIED_PUBLISHED_MAINTENANCE. If a required link is absent,
retain its UNKNOWN and never promote the full chain to verified success.

Constructor success is node creation, not attachment. check_transaction is
not behavior. AppServer approval error is not a Native semantic rejection.
P30 staged behavior stays **NOT_INDEPENDENTLY_EVALUATED** unless an actual
independent staged evaluation exists (none may be invented).

## Comparison, missingness and independent validation

Compare substantive stage propositions and supported classifications, not
spelling, diagrams or number of labels. Same propositions => BASELINE_PARITY.
Any disagreement must identify exact raw evidence, E0's alleged inability,
extra information, implementation defects and standard equivalent checks.
Fix implementation errors with retained attempt history, not new thresholds.

Independent validator must not call E0/E1. It reopens bound inputs, checks
hashes, source pointers, extraction and critical state/call/evaluation links,
and recomputes stage predicates independently. Compare against historical
labels only after this, never as a substitute for source-grounded validation.
Portable CI may verify the public inputs/derived certificate; **without private
archives it cannot claim raw validation**. Provide separate raw-validation mode.

Primary dispositions:

- OBSERVED_INCREMENTAL_MEASUREMENT_VALUE only for a substantiated distinction
  surviving a complete standard E0 with identical evidence; not global novelty.
- NO_OBSERVED_INCREMENTAL_VALUE if all sufficiently evidenced units agree.
  **Stop Direction D's new mechanism claim if all four units are sufficiently
  evidenced and equal.** No added task, weaker baseline or model experiment.
- INCONCLUSIVE_EVIDENCE_LIMITATION if missing key records prevents reliable
  comparison. Parity on available propositions alone is not full-chain proof.

No pooled model success rate, significance test, causal mechanism inference,
global benchmark-defect claim or Agent utility claim. Heterogeneous evidence
units include one no-model engineering record and three selected historical
slots, not a representative effect sample.

## Execution and publication handoff

Freeze this protocol, manifest and public transport in one commit before the
single batch analysis. Preserve all true execution failures as attempt records;
ordinary implementation repairs must not alter the above criteria. No runtime
candidate execution, provider/generation/token API, Core/Skill/history changes.
Separate the E0/E1 result from the requested systems/case-study paper handoff.
No manuscript submission, new mechanism, adapter or next experiment authorized.
