# No substantive E0/E1 disagreement on accessible observations

Actual disagreement count: **0** across the four fixed heterogeneous evidence
units. Identical observation digests are passed to the two separately implemented
evaluators. This is classification agreement, not a model success rate.

| Unit | Both evaluators recover | What neither may infer |
| --- | --- | --- |
| U1 P24 | Registry descriptors for needed constructors/attachment exist, while actual Native MCP calls return E_MCP_UNKNOWN_TOOL. | That a model failed: P24 has no model task. “Listed in MCP tools” and “described by Registry” are different observations. |
| U2 P26 HE23-B | A create_call produced a revision; a generation-1 commit published with the same project/target identity; final task tests fail. | Every intermediate target state: no per-operation target observer. Backend bridge callId is absent. Empty diff alone does not prove task failure. |
| U3 P30 MM01-S | Matching observer/replace call identifies changed staging; AppServer approval rejects commit before Native dispatch; authority remains original. | Staged candidate correctness. The final task failure tests the unchanged authoritative state, not the uncommitted candidate. |
| U4 P32 MM01-S | Connected target, matching actual model/Native commit call, stored/fresh authority and final independent task/regression results. | A standalone self-describing tested-revision receipt: finalization co-records files and tests but does not echo that identity in evaluator output. |

The object-bound vocabulary does not reveal any additional grounded distinction
over a strong state-aware baseline. All specific observations, call IDs, output
digests, target identities and missing fields are in OBSERVATIONS.json, with
source/member/JSON pointers. A separate validator reopens the original source
records, not classifier outputs, to check these assertions.

## Binding-strength qualification

The historical finalizer takes a final file snapshot, performs a fresh authority
read and evaluates the active workspace after closing model workers. Its
co-recorded files/tests support the original historical result under trusted
Host semantics. There is **no contrary observation** and this study does not
invalidate P32's COMPLETED_CORRECT_MAINTENANCE disposition.

However, the selected raw final evaluation object has no independently echoed
tested-revision value. We preserve that field as UNKNOWN rather than claim an
additional self-contained identity check was recorded. This is an evidence
strength distinction, not a newly observed wrong-version execution or a demand
to rerun historical models. Original finalizer source is available for inspection
at the approved base; it was not executed here or supplied only to E1.

Thus the **full requested identity-chain comparison** is inconclusive despite
parity on the accessible propositions. Missing links do not favor E1. This is
not OBSERVED_INCREMENTAL_MEASUREMENT_VALUE and not a clean four-unit falsification
of every possible measurement method.

## Implementation disagreement versus scientific disagreement

Attempt 01 misread the Native tool list as Registry exposure and left U1
UNKNOWN in **both** evaluators. The exact initial code/results are retained in
commit `1aae947096c3c07c0c55934c8610d605bce470ad`'s reachable history; ATTEMPTS.md
records the defect. Correcting the shared extraction uses actual describe
responses plus explicit unknown-tool refusal, not an expected outcome label.
No case, rule, original evidence or historical score changed. Ordinary argument
errors do not establish a coverage gap; the regression checks this distinction.
