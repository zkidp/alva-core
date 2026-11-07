# Declaration body editor: deterministic prototype

7 November 2026. This implements the interface change proposed after MIC-01:
let a caller read and replace a named function body rather than construct and
attach each anonymous expression. **No model was run and no token advantage
is established.** MIC-01's inconclusive disposition remains unchanged.

The opt-in `maintenance` MCP profile exposes nine tools, including one body
mutation operation. `read_function` supplies declaration metadata without
duplicating the body, one editable fragment, and its complete revision.
`replace_function_body` takes a qualified function, expected body revision and
that fragment. The implementation reuses the parser, AST-to-AIR construction,
graph checks, semantic checker and authoritative commit store. It copies the
function/module references and changes only the selected declaration head;
it does not modify shared old expressions or function nodes in place.

The original 20-tool profile and schema digest remain available unchanged.
One read correction affects both profiles: an existing complete revision passed
to `inspect_entity` now reads that exact snapshot. The old canonical resolver
could redirect shared named nodes through another declaration's entity label
or reject them as ambiguous, preventing complete Guard inspection. Named
handles and legacy mutation resolution retain their previous behavior.

Testing also uncovered an existing omission: ordinary function checking did
not compare the final body expression with the declared return type. The new
body editor adds that comparison for its target, using existing inference and
unification, before accepting the staged graph. It rejects wrong return types,
expression type errors, unbound references and effect violations atomically.
This does not change legacy `project check` semantics or establish complete
static soundness. Building and independent behavior tests remain necessary.

## Evidence

The committed [result summary](declaration-body-edit-v1-results.json) records
the original MM02 bundle ID, all before/staged/fresh body roots, semantic diff,
actual Guard decision and Native publication receipt. The original bundle is
`352a8b6fa459942b8b1d5469a966a706498afa7a2abbc13c39c457dafb069faf`.
Its source and manifest were imported unchanged, with no alpha-renaming or
preliminary sharing changes. A host-only deterministic witness extracted a
replacement body from the existing engineering source witness. No P35
attachment sequence is required by this interface.

| Check | Result |
| --- | --- |
| Baseline independent MM02 task / regression | TEST_FAIL / PASS |
| Staged changed functions | `store.xml.parse_prefix` only |
| Transaction check | No problems |
| Actual unchanged P34 Guard | SCOPE_ALLOWED |
| Underlying successful Native commits | 1 |
| AIR publication and fresh-process body roots | Consistent |
| Original source / manifest | Byte-identical |
| Independent task / regression after commit | PASS / PASS |

The delimiter last-match counterexample and the original response/XML
regressions remain in the unchanged evaluator. Other function body roots stay
identical throughout staging and fresh authority reads. The raw Guard ledger
is retained under ignored `out/body-edit-v1/`; its digest is in the summary.
It includes trusted inspection calls, not just agent-visible calls.

Additional verification covers:

- Shared bodies within a module and an entire function shared across modules.
  Real Guard allow/deny cases exercise editing either shared declaration,
  including the declaration that does not own the stored entity label.
- Byte-identical failed transaction state; exact/stale revisions; ambiguous
  declarations; syntax, size, type and effect errors; sequential edits; no-op
  round trips; result/vector/string projections; immutable historical nodes.
- Denied Guard commits never dispatched to Native, and competing transactions
  rejected by the existing authoritative base check without changing AIR.
- 32 Rust unit tests, the legacy MCP acceptance fixture, both maintenance
  transport cases and builds, seven existing Guard tests, format/Clippy checks,
  and the existing parser/type/effect/contract/codegen conformance suite.

Local executable verification used a fresh build in a separate Linux export,
with offline dependencies. The original MM02 ran through existing P22/P23
namespace isolation and the actual P34 mediator. On the shared Linux host the
existing prospective RLIMIT_NPROC=512 wrapper was used; old isolation sources
were not edited. Exported shell scripts had Windows CRLF converted to their
committed LF for Linux execution. Windows execution is covered by the new CI
workflow; the local Windows host has no MSVC linker.

## Limits and next decision

This is a body-only prototype. Signature evolution, general occurrence paths,
automatic rebasing, and declaration creation are outside its scope. An existing
content revision with conflicting stored entity metadata is explicitly refused.
It clones staged graphs and rewrites a complete body fragment; neither memory
efficiency nor lower input/output token use has been measured. A whole-body
write can cost more than a small text patch. Host Guard inspection still has
its own backend cost, even when invisible to a model.

Model generation calls = 0. Input-token API calls = 0. Provider requests and
dollar cost are not measured. No old study is rescored; no frozen benchmark,
official Skill or paper artifact is modified. This engineering witness must
not be counted as autonomous agent success.

The next useful study requires a new pre-generation freeze: matched Text and
compact Native tasks, fresh model sessions, equal task/test/authorization and
resource limits, an explicit pinned CLI, and the repaired provider fault gate.
Measure correct authorized completions, total reported tokens (including cached
input), latency, model-visible calls and trusted backend calls separately.
Use success-conditioned token comparisons only alongside completion rates and
all failure outcomes. This implementation alone is not a reason to repeat the
old experiment or to claim an advantage over CodeStruct or text editing.

Reproduction commands and interface usage are in the
[prototype guide](../declaration-body-edit-v1.md) and
[CI workflow](../../.github/workflows/declaration-body-edit.yml).
