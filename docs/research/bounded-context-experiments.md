# Bounded context: correctness, behavioral limits, and acquisition cost

This Codex-assisted engineering investigation adds no model-generation or token
counting API calls. It is not a controlled agent experiment. The development base
is `e0f160f4307ae6fa66733b350b63f081af712168` (PR44), not released main.
It reuses the P42 projection without changing Core, Host mutation semantics,
Skill, frozen inputs, scores, or previous scientific dispositions.

## Questions and actual experiments

### E1 — Are bounded facts correct and revision-bound?

`benchmarks/bounded_context_audit/experiments.py` builds a new three-module public
fixture. An independent whole-graph reference computes all declaration tables,
all function containment closures and direct-call edges before selecting the
target dependency fixed point. Handwritten expectations independently require
four recursive record/alias/enum types and one direct callee. The callee's own
callee is deliberately outside the projection boundary.

Real Native inspections matched both references. Repeated projection was
deterministic and left the transaction unchanged. An actual target body change
changed both the draft project revision and body revision; the returned context
matched that new snapshot. Abort left source and published authority unchanged.
This checks identity binding, not a new concurrent-source stale protection claim.

Explicit descriptor fault injections produced PARTIAL for missing type/callee,
TOO_BROAD with no silently truncated declaration list for byte/declaration
overflow, and rejection for an incomplete graph. These are synthetic malformed
descriptors, **not valid alternative AIR revisions**. Through the actual Host,
an incomplete snapshot produced UNKNOWN without blocking ordinary fallback.

Result: **bounded structural correctness observed in this fixture**, not arbitrary
program completeness. Existing P42 regression tests provide additional coverage;
rerunning them does not create new research samples.

### E2 — Can complete signatures still leave necessary behavior unknown?

Two two-module programs have identical target syntax, type facts and direct
callee signatures. The callee increments in one and decrements in the other.
The public requirement is target(x)=x+2 while preserving the callee.
Their full contexts are **not byte-identical**: real project/callee revisions and
snapshot hashes differ. Opaque identities distinguish content but do not explain
its behavior.

Using the existing LinuxProjectEvaluator, four real isolated check/build/test
evaluations gave:

| Callee | Candidate target | Compiler/build | Independent behavior |
| --- | --- | --- | --- |
| x+1 | callee(x)+1 | PASS | PASS |
| x+1 | callee(x)+3 | PASS | FAIL |
| x-1 | callee(x)+1 | PASS | FAIL |
| x-1 | callee(x)+3 | PASS | PASS |

No candidate was published. These operator-authored controls demonstrate the
boundary, not agent correctness. COMPLETE_WITHIN_BOUNDARY must never mean
behavior fully known, compiler success must not mean task success, and a source
fallback may be necessary. Generated code executes inside the existing Linux OS
boundary; the trusted read/draft driver itself is not claimed to be sandboxed.

### E3 — Do existing records establish acquisition economy?

`accounting.py` re-computes public frozen-summary costs only, with input byte hashes.
Hashes identify the actual checkout bytes (CRLF/LF checkouts can differ), not
new historical freeze identities. It does not reconstruct raw tool responses.
V4 is a different treatment from P42 and cannot establish the latter's effect.

| Task | Text tokens | V3 tokens | V4 tokens | V4/Text | V4/V3 |
| --- | ---: | ---: | ---: | ---: | ---: |
| H01 | 41,523 | 24,916 | 46,358 | 1.116 | 1.861 |
| H02 | 14,113 | 24,602 | 12,355 | 0.875 | 0.502 |
| H03 | 23,723 | 25,232 | 16,797 | 0.708 | 0.666 |
| H04 | 11,750 | 25,527 | 16,386 | 1.395 | 0.642 |

All twelve published outcomes passed. Median paired V4/V3 is 0.654, but aggregate
ratio is 0.916 and H01 has substantial adverse cost. Against Text, median ratio
is 0.996 while aggregate ratio is **1.009**, not a saving. Submitted chat requests
were Text20, V3 14, V4 20. These are published submitted requests, not a newly
verified provider-internal request count. Historical failed promotion remains.

MIC-01 retains ten eligible pairs, Text9/10 vs Native8/10 correct. The eight
both-success pairs have median totals Text157,012.5 and Native459,289. These
survivor medians are not unconditional efficiency or a causal effect. The quota
incident, two submissions after first quota fault and missing per-slot CLI
identity remain limitations; disposition remains INCONCLUSIVE_PROVIDER_LIMIT.

The corresponding V4/MIC raw archives were not found in the scoped local
workspace/private/WSL archive search. Unique/duplicate source delivery, useful
source coverage and exact per-request exposure are therefore **UNKNOWN**, not
zero. Public diagnostic arguments and token totals are insufficient substitutes.
The tested UTF-8 interval meter can support a future raw analysis, but no raw
historical deliveries have been processed in this node.

## Actual environment and payload cost

Local E1/E2 ran on Ubuntu26.04/WSL, Python3.14.4, Rust1.98.0 with bubblewrap0.11.1.
Binary SHA256: `cc652843102be3ffef4bb84f69b1a851bff229c8eb603b14ced827008626dd49`.
Windows Python3.14 ran the affected Python tests; isolated executable behavior is
Linux-only. CI independently rebuilds the unchanged compiler on Linux/Windows,
executes E1 on both and E2 only on Linux; logs/results are Actions artifacts,
not tracked local output. Fresh binary builds can have different binary hashes.

On the new small E1 fixture, whole ALVA source was787 bytes, target body37 bytes,
dependency projection1,527 bytes, full read_target response3,932 bytes. Projection
adds three Native inspections. Its JSON metadata can exceed small source text;
these figures are payload sizes, **not measured provider tokens or agent exposure**.
Backend wire work and evaluation time are recorded separately from model costs.

## Decision and next bounded experiment (design only)

H1 has limited engineering support; H2 acquisition savings and H3 correct
maintenance with lower acquisition remain **unestablished**. No default promotion,
language superiority, model correctness gain or new paid run is warranted here.

If authorized next, use at most three fresh **known-target** maintenance cases
outside closed W02/MM/H tuning families. Write public requirements and independent
behavior/scope regressions before engineering solutions. Include a direct-only
case, recursive type use and a callee-behavior-dependent case. Predeclare support
selection; retain unsupported candidates. Unknown-target discovery is a different
question because P42 requires a supplied target and is not a locator.

Use three conditions with identical body replacement, Guard, prepare/publish,
independent tests and source fallback: A strong Text acquisition (normal source
read/search and generic symbol/dependency tools available to that baseline),
B ordinary ContextHost, C bounded P42 ContextHost. Precisely inventory any
baseline tools actually implemented before freeze; do not call a deprived
read-only baseline conventional tooling. Differences are acquisition information,
not stronger mutation powers. Keep model/task facts/docs/resource admission equal.
No engineering witnesses, hidden assertions or analysis slices enter model input.

Before any future model call, freeze actual cases, exact input/tool/doc bytes,
order, model identity, budget and stop/interrupt semantics. This document is
**not an execution freeze**; no placeholders are represented as frozen inputs.
Record actual response source intervals/version, unique and repeated bytes,
first accepted change, provider totals (cache included), backend work, elapsed
time, final task/regression/scope and unresolved dependencies. Preserve failures
and censored costs separately; no survivor-only economy claim. Report each pair
and worst adverse tail, not just medians. A cheaper but wrong candidate is not a
benefit. Predeclare the economy screen and tolerated adverse tail before execution;
do not select thresholds based on these old records. Require no observed task or
scope deterioration for a favorable *developmental signal*, never statistical proof.

Stop here. No participant study, new model execution, Core extension or closed
study reopening was performed.

## Reproduce

Run from repository root (output paths must not already exist):

```sh
python -m unittest tests.integrations.test_bounded_context_audit tests.integrations.test_bounded_target_context tests.integrations.test_maintenance_context -v
python benchmarks/bounded_context_audit/accounting.py --output /tmp/context-accounting.json
python benchmarks/bounded_context_audit/experiments.py --alva /absolute/path/to/alva --output /tmp/context-experiments --toolchain "$(rustc --print sysroot)" --registry "${CARGO_HOME:-$HOME/.cargo}/registry"
```

See `.github/workflows/bounded-context-audit.yml` for clean CI reproduction.
