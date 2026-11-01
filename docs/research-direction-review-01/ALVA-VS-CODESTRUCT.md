# Architecture difference is not measured utility

ALVA pinned base: `60902939732f03f5653d6b2ce320ed7ca25b4c17`.
CodeStruct inspected source: `d89efa473754f455d38ab47b4dc938cfc8334a0d`.
[Source manifest and retrieval limits](SOURCES.md) records the exact files.
This is a source review, not a new tool/model comparison.

## Representation and authority

[CodeStruct's writer](https://github.com/amazon-science/CodeStruct/blob/d89efa473754f455d38ab47b4dc938cfc8334a0d/SWE-agent/tools/ast_edit/bin/editCode#L420)
reads file text and parses it for selection; its
[file writer](https://github.com/amazon-science/CodeStruct/blob/d89efa473754f455d38ab47b4dc938cfc8334a0d/SWE-agent/tools/ast_edit/lib/file_operations.py#L136)
writes the resulting text back. These inspected paths do not establish a
persistent, authoritative AST revision store. Caches of derived signatures
are not semantic authority. This is a bounded observation about this release,
not a claim that CodeStruct cannot be combined with a database or Git gate.

ALVA's [AirGraph](../../alva/src/air.rs#L60) has content-addressed nodes and named
entity heads. After authority exists, [project loading](../../alva/src/project.rs#L189)
uses committed AIR; old `.alva` projection need not change after a Native
commit. Therefore source diff alone can miss an AIR edit unless the evaluator
reads the actual authority or deliberately projects it. This is an experimental
confound to control, not evidence that source-authoritative systems are weaker.

| Question | CodeStruct implementation | ALVA implementation and consequence |
| --- | --- | --- |
| Address identity | File plus named function/class selector, optionally class-qualified; reparsed against current text | Stable named entity plus changing revision. Anonymous revision identifies shared content, not a unique lexical occurrence. |
| Sharing | The inspected source writer targets source spans, not an authoritative shared-expression DAG | Identical anonymous content deduplicates; in-session map mutation and ancestor rebuilding can change two declarations (P33). |
| Source/semantic synchronization | File text remains the edit/publication object in this writer | AIR commit and source projection are distinct; neither “all source updated atomically” nor complete Git/source visibility follows. |

## Editing, locality and compositional cost

The [selector implementation](https://github.com/amazon-science/CodeStruct/blob/d89efa473754f455d38ab47b4dc938cfc8334a0d/SWE-agent/tools/ast_edit/bin/editCode#L291)
distinguishes definition names and class-qualified methods. Non-delete operations
require a unique selected node; deletion separately collects all matches. It is
incorrect to promise unique-occurrence semantics for every operation. For a
unique source definition, replacing that span naturally leaves another span
untouched even if its text is equal. This does not prove behavioral locality.

ALVA Native's twenty-tool surface exposes constructors and `replace_expression`,
not every Registry operation. A child constructor can be detached. Replacing
a shared parent slot has no owner/path argument. P35 safely rebuilt/wrapped
the needed region and reattached at an existing unshared binding; P36's model
independently found a different safe wrapper. Where there is no available
unshared attachment or allowed construction, current feasibility is UNKNOWN,
not a reason to invent an operation. Rebuilding call ancestors was required
in P37 MM07; direct indexed-call-argument editing was not available there.

CodeStruct's [advertised configuration](https://github.com/amazon-science/CodeStruct/blob/d89efa473754f455d38ab47b4dc938cfc8334a0d/SWE-agent/tools/ast_edit/config.yaml)
uses insert/delete/replace-definition operations and explicitly recommends
string replacement for small edits. The CLI additionally implements
`replace_in_node`; its [MCP request schema](https://github.com/amazon-science/CodeStruct/blob/d89efa473754f455d38ab47b4dc938cfc8334a0d/SWE-agent/tools/ast_edit/lib/codewrite_server.py#L30)
advertises a narrower operation enum and ordinary string fallback. Thus neither
system should be assessed from “all operations mentioned anywhere in the repo.”
No calls-per-task comparative advantage can be inferred from these APIs.

ALVA's official Skill prohibits silent broad-source fallback when Native cannot
express the request. CodeStruct intentionally retains text editing. A study
that removes this fallback only from CodeStruct would not test its normal
workflow. Conversely, allowing ALVA text rescue changes the Native condition
and must be separately named and measured.

## Checks, transactions and publication

The [syntax gate](https://github.com/amazon-science/CodeStruct/blob/d89efa473754f455d38ab47b4dc938cfc8334a0d/SWE-agent/tools/ast_edit/bin/editCode#L598)
parses candidate Python before writing; string replacement also uses Python
syntax validation. It is not a Python type checker or behavioral verifier.
The inspected gate is explicitly conditional on Python; Tree-sitter language
recognition alone is not evidence of equivalent validation for every language.
Rejection before write differs from rollback after an externally visible edit.

ALVA stage validates graph structure/cycles; transaction check converts to AST
and runs project semantic checks; commit checks again and writes a generation
under a base-revision check. Independent Rust build and behavior tests remain
necessary. P33 passes check/commit yet breaks delimiter; P38 C1 has an allowed
target-body edit yet breaks a protected caller. P34 adds actual body-level
authorization, not complete behavioral protection.

| Property | What is established | What remains unestablished |
| --- | --- | --- |
| CodeStruct private transaction / base CAS | Not in the inspected writer or MCP wrapper | Complete ecosystem absence, crash-atomic multi-file publication and concurrency guarantees were not audited. |
| ALVA transaction | Private graph, check, abort, serialized store update and expected-base rejection in actual code; historical deterministic execution evidence | Source+AIR atomicity, full semantic safety, arbitrary long-stall/crash schedules. Store lock expiry is an explicit implementation assumption. |
| Strong alternative | Git immutable candidate commit, expected-old ref update, required CI on exact candidate; private worktree | Git does not provide ALVA type/effect checking by itself. Tests and environment identity must be bound separately. |
| Behavior | External executed assertions needed in both architectures | Finite test pass is not equivalence or trusted-intent completeness. |

See [Git CAS documentation](https://git-scm.com/docs/git-update-ref),
[branch checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
and [P38's parity result](../../benchmarks/p38_authorized_effect_contract/NOVELTY-DECISION.md).
Do not compare ALVA transactions only to an unguarded `write()` and call the
difference a research contribution over strong conventional tooling.

## Agent usability, prior claim collision and external validity

The [published CodeStruct paper](https://aclanthology.org/2026.acl-long.607/)
and [17-page PDF](https://aclanthology.org/2026.acl-long.607.pdf), pp.13290–13306,
already study named-AST reading/editing with real repository tasks and multiple
models, including performance/cost analysis. Therefore “structured actions can
help coding agents” and “semantic units reduce text brittleness” are not ready
new ALVA scientific claims. This review does not reproduce their experiments.

ALVA P26/P28 expose discovery/composition/censoring failures; P32/P36 establish
two end-to-end existing-code successes. They differ in tasks, model/runtime,
documents and budget from CodeStruct. No numeric cross-paper ranking is valid.
Schema discovery can work while target attachment fails; a completed target
attachment can still fail publication or behavior. This finer state attribution
is a candidate empirical measurement question, not an established missing
capability in CodeStruct's evaluator.

Mainstream repositories improve language familiarity and task naturalness.
ALVA's small controlled programs improve exact identity/operation observation,
but introduce custom-language familiarity, tool granularity, source/AIR
authority and author-designed-oracle confounds. No reviewed question requires
inventing more grammar. A source parser, Git snapshots and adequate trace
capture may support the same measurement without AIR.

## License and reuse boundary

The pinned [CodeStruct LICENSE](https://github.com/amazon-science/CodeStruct/blob/d89efa473754f455d38ab47b4dc938cfc8334a0d/LICENSE)
states **CC-BY-NC-4.0** and its files carry that notice; ALVA has
[Apache-2.0](../../LICENSE). These are not interchangeable distribution terms.
This review copies no CodeStruct code, dependency tree, results dataset or
paper into ALVA. Retain attribution and check the particular files' notices
before any separately authorized reuse; no blanket relicensing or legal
clearance is asserted. An independently implemented comparison or separate
upstream checkout is preferable to vendoring. Separate authorization and
license review would be needed for reuse beyond this read-only analysis.

**Bottom line:** source-AST editing is strong prior art; authoritative AIR is
a real alternative representation, with both useful observability and its own
locality risks. No measured advantage over CodeStruct follows. Retain the
instrument, narrow the scientific question, and require a source/Git baseline
capable of falsifying any proposed need for AIR.
