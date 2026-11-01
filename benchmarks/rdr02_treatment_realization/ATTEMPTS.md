# RDR-02 implementation attempt history

Registration precedes archive-content classification at `67a91cb` (full commit
is reachable in this PR). No historical task or model was executed.

## Attempt 01

All three supplied archives pass original SHA256/length checks. Initial batch
produced parity on available propositions and an inconclusive full-chain result.
It incorrectly left U1 UNKNOWN: the extractor tested MCP `advertised_names`
instead of the actual Registry `describe_operation` response. This is a new
analyzer implementation defect, not a P24 evidence defect or a mechanism effect.
The initial implementation and its three output files are committed before
repair, preserving exact code and results. No registered input/rule changes.

Two earlier preparatory inspection commands also failed: an oversized JSON
transport preview exceeded the tool output limit (no transport file produced),
and a schema inspection treated observer_calls (an integer count) as a list.
Neither ran an evaluator/classifier or changed evidence; the final reader uses
the actual schema and records missing fields rather than fabricating records.

The absence of a standalone evaluated-revision echo in final records is not
repaired by inventing one. Any later result must keep co-recorded files/tests
distinct from an explicit identity receipt and preserve original P32 grading.

## Attempt 02 — bounded extraction repair

Actual successful Registry descriptors and actual Native unknown-tool refusals
now ground U1's coverage gap. Both evaluators still agree on all four units.
The independently implemented validator checks source pointers, complete tool
record ordering, state identities, evaluation exits and missingness. No original
archive, registered input, historical score or comparison rule was changed.

## Portable-check setup failures

The first WSL clone command used the Windows linked worktree as a clone source;
its absolute Windows Git pointer is not resolvable by Linux Git. A second
command lost its temporary-directory variable at the shell boundary and failed
before cloning. Neither ran analysis or changed any input. Cloning from the
actual shared repository into an explicit Linux temporary path succeeded;
eight tests and public-certificate validation then passed on Python 3.14.4.

## PR #40 P2 — independent U1 descriptor reconstruction

Reproduced on `d17d98dc8818c86fda350df91755ac0caac904d7`: erasing U1's
descriptor pointers and Registry flags, then regenerating E0/E1 classifications
and digests, incorrectly passed validation as UNKNOWN. The new regression failed
against that validator before repair. The validator now enumerates the original
hash-pinned public coverage calls, reconstructs successful Registry descriptors,
and checks exact descriptor references, Registry/native exposure, probe coverage
and refusal payloads independently of the projection. The erased-descriptor
regression and field/reference tampering controls now pass (tampering rejected).
Normal data retains CAPABILITY_COVERAGE_GAP, zero E0/E1 disagreements and
INCONCLUSIVE_EVIDENCE_LIMITATION. No analyzer, frozen input/result or archive is
changed; model generation and input-token API calls remain zero.
