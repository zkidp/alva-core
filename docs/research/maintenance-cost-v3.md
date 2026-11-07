# Maintenance cost V3: measured engineering optimization

8 November 2026. Implementation base:
`e0bbfe44f4cf8f88c791758687bf401580efef72`.
The deterministic acceptance protocol was committed separately, before the
first candidate measurement, in
`dcf1a1db5fd5500849e9481bec299c4e38f763ac`
([protocol](maintenance-cost-v3-protocol.json)).
No model generation or input-token API call is made. Provider usage and dollar
cost remain null, not zero. Historical model results are unchanged.

## What changed

1. **Batch complete scope reads.** A private read-only AEP operation returns
   all nodes reachable from the current module heads, using the existing node
   encoding. Core bounds it to 2,048 nodes and 8 MiB. The actual P34 collector
   validates complete coverage and runs the same declaration, metadata and
   body comparison as before. It rejects missing, malformed and extra nodes.
   Baseline, preparation and publication still collect separate snapshots;
   the snapshot-to-commit interval remains inside the Guard lock. There is no
   cached authorization or error-triggered fallback. The old serial transport
   remains the default for existing Guard clients; this Host explicitly opts
   into the private batch path. Default 20-tool/maintenance 9-tool MCP profiles
   do not expose it or change schemas.
2. **One AIR transfer, two digest rechecks.** Draft evaluation receives the
   actual full AIR once. Subsequent consistency checks serialize and SHA-256
   hash the full current AIR inside Core, but return its descriptor without
   the hex payload. Exact byte changes still invalidate the proposal; this
   includes changes outside reachable heads. No test outcome is cached.
3. **Compact model-facing results.** The entire available builtin catalogue
   becomes a `name: arity` map, retaining names and arities without repeated
   field labels. Publication returns its actual revision, scope status and
   fresh-verification status. Preparation keeps its diff/checks and opaque
   proposal ID. Full internal receipts/counters remain available to trusted
   programmatic callers; MCP does not repeat that audit/accounting data into
   model context. A post-commit verification failure still reports that a
   publication happened and preserves its revision.

This changes transport and context encoding, not task requirements, scope
authorization, test assertions or original shared graph structure.

## Measurement

`tests/mcp/host_cost_test.py` runs each original registered task three times in
both modes: 24 complete successful workflows. Order alternates per repetition.
Both use the same current compiler binary, SDK, source bundle, deterministic
body witness, policy, isolated evaluator and independent final tests. Every
workflow performs three agent actions and runs new draft tests. The witness
is engineering input, never evidence of model discovery or agent success.

The baseline selects serial Guard reads/full exports and V2 response encoding.
The optimized path selects batching/digest rechecks/compact encoding. New
measurement-only telemetry is removed from the V2 model-facing baseline, so
the instrumentation does not inflate its response cost. The tests require
exact equality of baseline snapshot digests and entire staged scope decisions,
including coverage and unchanged/changed-function evidence. Real task and
regression tests, protected commit and fresh authority must pass in both arms.

| Task | Native calls, baseline → optimized | Call reduction | Guard reads, baseline → optimized |
| --- | --- | --- | --- |
| MM01 | 167 → 17 | 89.8% | 153 → 3 |
| MM02 | 604 → 17 | 97.2% | 590 → 3 |
| MM04 | 1,224 → 17 | 98.6% | 1,210 → 3 |
| MM07 | 200 → 17 | 91.5% | 186 → 3 |

The [curated final result summary](maintenance-cost-v3-results.json) records
all 12 pairs. Every pair passed all predeclared gates and independent tests.
Median reductions within each task:

| Task | AEP request + reply bytes | Model-facing MCP result bytes | Publication result bytes | End-to-end wall reduction |
| --- | --- | --- | --- | --- |
| MM01 | 47.00% | 44.99% | 81.04% | 1.54% |
| MM02 | 48.48% | 41.01% | 81.08% | 3.45% |
| MM04 | 48.44% | 36.12% | 81.14% | 4.11% |
| MM07 | 47.46% | 38.99% | 81.04% | 0.33% |

For example, MM02's AEP traffic falls from 534,892 to 275,594 bytes and
MM04's from 1,106,712 to 570,600. Native-call elapsed time falls by roughly
23%–50% in task medians, but overall workflow improvement is small on this
shared host. These timings are observations without a latency acceptance
threshold or statistical performance claim. Build/test work is unchanged.

The machine-readable CI artifact records actual AEP request/reply line bytes,
adapter reply bytes, MCP tool-result bytes (including both standard text and
structured fields), Native elapsed time, total workflow wall time, per-task
receipts and final checks. It does not count these byte measurements as
provider tokens or model requests. The schema and candidate-body input are
unchanged between arms. Four tasks × three repetitions must individually
clear the predeclared 85% Native-call, 25% Native-wire-byte, 10% model-facing
response-byte and 60% publication-response-byte reduction thresholds.

Tests additionally cover the original actual-Core Host lifecycle controls,
including unauthorized changes, stale base, wrong return types, altered draft,
source or test identity, receipt mismatch, failed-test invalidation, expiry,
consumed proposals and verification failure after a real commit. New batch
controls compare old/new decisions on allowed body changes, non-target/shared
changes, metadata/signature/interface changes, declaration coverage changes
and unsupported slots/externs. Corrupt/incomplete/oversized batches must never
forward a Native commit. Existing compiler, conformance, profile and packaging
checks remain required. CI runs Windows/Linux lifecycle and compiler checks
and the real behavior/cost qualification on Linux.

The local server uses the existing explicit shared-UID RLIMIT_NPROC 512 profile;
CI retains the original 128 profile. No frozen benchmark or old isolation
implementation is modified. The previous preliminary runs are development
checks, not additional research samples; only the final implementation's
three predeclared paired repetitions support the reported figures.

## Product claim and remaining work

Supported: **for these fixed maintenance workflows, ALVA transfers less data,
uses fewer Native round trips and feeds smaller tool results to the model,
while preserving the tested authorization and behavioral outcomes.**

Unsupported: a claim of lower complete model-token usage, provider bill,
better autonomous success or superiority to another product. Input byte
reduction does not establish total-token reduction; models may spend more
reasoning/output or make more retries. Isolated builds/tests still dominate
wall time, so lower RPC counts should not be advertised as a proportional
end-to-end speedup.

The next research gate is a fresh, bounded paired model comparison with this
implementation frozen. Preserve original bundles and independent evaluators;
give Text equivalent public context, trusted draft tests and scope-protected
publication. Predeclare total-token/success criteria and count every attempt,
all reported input/cached/output/reasoning usage, retries, latency and backend
work. A model result must determine whether token cost can become a validated
selling point. This implementation does not overwrite the preceding
comparison's unfavorable token signal.
