# Prospective protocol

Freeze this document, AEC-V0-CONTRACT.md, COUNTEREXAMPLES.json, oracle.json
and fixtures in a Git commit before running the mechanism comparisons.
Implementation repairs may change harness code, never these registered inputs.
The harness verifies registered bytes against that commit.

Selection: four tiny new deterministic programs isolate respectively a
protected caller regression, a permitted caller change, shared structural
propagation, and insufficient proof. Cases 1 and 2 intentionally pair the
same arithmetic edit with different trusted behavior policies. These are
synthetic counterexamples, not representative tasks or model experiments.

Execute all cases in a batch. Candidate-local errors become blocked rows and
do not prevent other cases. Retain every executed wave, its failures, code
revision and archive hashes. Do not silently replace a failed wave.

All mechanisms receive identical candidate states, intent and available sample
tests. A and D require the registered evidence strength; B's ordinary testing
does not manufacture a proof. C is measured according to its real implemented
policy and also scored against the stronger registered authorization policy.
Do not call C's correctly scoped behavior a Guard implementation defect.

Metrics: per-case expected-vs-observed decision; exact matches; invalid allows;
false rejections of the legitimate case; UNKNOWN count; actual C commit count
and contract-invalid publication count; evidence requirements; single-run
decision time and complete acquisition/evaluation time. Timings are descriptive
and share acquisition costs, not statistical speed claims. Record missing
measurements as null. Proof-required UNKNOWN is not a semantically invalid
candidate and is counted separately from proven-invalid candidates.

Success of the study does not require favorable AEC results. If A and D agree
on every executed case, report NO_OBSERVED_INCREMENTAL_VALUE over the strong
baseline. If cases cannot be observed, report INCONCLUSIVE_WITH_LIMITATION.
Do not infer universal reliability or novelty from four cases.
