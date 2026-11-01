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
