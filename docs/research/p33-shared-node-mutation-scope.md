# P33 — shared anonymous-node mutation scope

**CONFIRMED_SHARED_PARENT_PROPAGATION; P29 MM02 result reproduced.**
Base: `da393659ce5336d6927bfc0a29fb49a94be5d539` (P32).
Model generation calls **0**; input-token API calls **0**. Codex assisted the
engineering/analysis; this is not model-free development or an Agent experiment.
No Core/AEP/MCP/Skill, historical fixture, witness, assertion or result changed.

## Fixed case and actual layered result

The original P29 MM02 bundle SHA256 is
`352a8b6fa459942b8b1d5469a966a706498afa7a2abbc13c39c457dafb069faf`.
It contains unchanged public store.model/xml modules plus P29's two-module
component manifest, not the full server/storage product. The requirement is
first **nonempty decoded prefix** in query order, preserving delimiter's
last-match policy and response/XML behavior. All original P29 goal/regression
assertions are reused without omission. `witnesses.mutate_native("MM02", c)`
is called directly; its operation sequence is not rewritten to get a PASS.

| Layer | Original MM02 Native | Original Text witness | Alpha-renamed parent control Native |
|---|---|---|---|
| Baseline check/build | PASS | Same original source | PASS |
| Baseline target / regressions | expected FAIL / PASS | Same original source | expected FAIL / PASS |
| Staged named bodies changed | prefix **and delimiter** | source patch restricted to prefix | prefix only |
| Authoritative state before commit | Unchanged | Source-authoritative path | Unchanged |
| Preview | Lists both changed functions | Ordinary source path, no AIR commit | Lists prefix only |
| Transaction check | `problems: []` | n/a | `problems: []` |
| Commit / fresh AIR read | PASS; both changes retained | n/a | PASS; prefix change retained |
| Independent project check/build | PASS | PASS | PASS |
| Independent target | PASS | PASS | PASS |
| Independent regressions | **FAIL** | PASS | PASS |
| Delimiter repeated-key observation | **`/`** | `!` | `!` |

The counterexample remains exactly:
`store.xml.parse_delimiter("delimiter=%2F&delimiter=%21")`: expected `!`,
observed `/` after the original Native witness. P29 is neither overwritten nor
rescored. No substantive reproduction discrepancy was observed. Diagnostic
stdout hashes are not expected to equal old hashes: test scheduling/log details
can differ; raw evidence and the actual values are retained separately.

## It is a shared graph entry, not just equal printed text

The selected anonymous `if` parent is:
`33ecf18b03c1348dd59bf91c15f66a73d06cba29dd757254c4e7917ed96beb5f`.
It has `entity=""`, no scalar fields, and the same three child revisions in
`cond`, `then`, `else`. The two functions differ above it (notably the string
passed to strip-prefix), but converge on this common descendant.

`RESULTS.json` records each actual seven-edge path from a different function
root, using `(parent revision, slot, child index, child revision)` tuples.
`SHARING.json` verifies those paths against recorded `inspect_entity` graphs
and records the changed parent reached along both paths after staging. Both
paths reach **the same initial node descriptor** and **the same new staged
node descriptor**. A small audit recomputes the fieldless-if ALVANODE1 hash
from its real slots and matches the revision before and after modification.
This encoder is only an evidence check, not a new language analyzer.

Runtime observations are combined with these concrete implementation facts:

1. [`air.rs:97`](../../alva/src/air.rs#L97), `compute_revision`, hashes
   canonical `(kind, fields, child revisions)`. `canonical_node` at line 486
   does **not** include enclosing function, occurrence path or lexical owner.
2. [`air.rs:110`](../../alva/src/air.rs#L110), `AirGraph::add`, inserts into
   `nodes: BTreeMap<revision, AirNode>` only if the hash is absent. Identical
   anonymous subtrees are deduplicated. Therefore those two traversals address
   one stored entry, not two independently mutable nodes with equal labels.
3. [`main.rs:1950`](../../alva/src/main.rs#L1950), `replace_expression`, resolves
   `parent`/`child`, maps the friendly position to a slot, and invokes
   `EditSession::replace_slot`. Its public arguments have **no owner function
   or occurrence path** (AEP registry at `aep.rs:577`). Earlier resolve/inspect
   of prefix is not a mutation scope capability.
4. [`air.rs:3984`](../../alva/src/air.rs#L3984), `replace_slot`, clones the graph
   through `stage`, then uses `g.nodes.get_mut(&parent_revision)` and replaces
   that stored node's selected slot. It does not clone a particular incoming
   occurrence. All paths referencing that map key now see the changed slot.
5. [`air.rs:230`](../../alva/src/air.rs#L230), `rebuild_revisions` /
   `recompute_revision`, traverses **all module heads**, recomputing changed
   ancestors and moving named heads. Both function ancestry chains therefore
   receive new revisions. The transaction graph remains private until commit.

This path does **not** call `replace_node`'s explicit global-reference scan
(line 3955). The propagation is the shared parent's in-staging map mutation
followed by whole-program Merkle rebuilding, not a global `replace_node`
operation, name-based multi-function search, hidden task rule or stale conflict.
`resolve_current` is node resolution, not a guarantee of local occurrence scope.
The graph clone provides transactional isolation from authoritative state;
it does not provide per-function isolation **within** that clone.

Do not generalize this finding to every expression with equal source text:
content equivalence, same stored revision, reachable sharing, and chosen parent
are separate questions. The recorded graph paths establish each for this case.

## What preview, check, commit and independent verification actually do

**Staging inspection:** both body hashes change immediately after the original
replacement; the other seven recorded function bodies do not change. Before
commit, the complete authoritative/source file snapshot stays byte-identical.

**Preview:** `diff_graphs` / `diff_node` (`air.rs:2444` / `2484`) walks module
roots and reports changed function revisions. Here it correctly returns:

```text
CHANGED module store.xml
CHANGED function store.xml.parse_prefix
CHANGED function store.xml.parse_delimiter
```

Its named-function set equals the changed bodies among **all nine functions in
this fixed component**. Thus this case is not evidence of a missing preview
entry. Preview is descriptive, not an authorization check; it accepts no allowed
function set and does not automatically refuse delimiter modification. Its
current text summary is not a universal proof of semantic impact completeness,
especially for arbitrary added/removed declarations, types or dynamic behavior.

**Check:** `EditSession::check` (`air.rs:4202`) runs graph/schema integrity,
cycle detection, then `project::check_graph_semantic` (`project.rs:170`) over
reconstructed modules and ordinary semantic checking. Reachable content hashes,
slot kinds/cardinality and supported compiler semantics are checked. This is
not evaluation of P29's user requirement or its independent Rust assertions.
A well-typed first-match delimiter policy is valid ALVA but wrong for the
authorized maintenance task. `problems: []` is therefore compatible with this
behavioral regression, not evidence that the oracle is wrong.

**Commit:** `main.rs:2671` rechecks the staged graph, then
`write_authoritative` (`air.rs:880`) locks/rechecks base revision and writes the
next AIR generation. Actual commit revision
`08bd952ecf68d1f09c27cda496337bede0bf00c0eb6d72135e1b43fb0f1cc293`
matches a fresh MCP process and both staged function hashes. Source projection
is unchanged; evaluation uses AIR authority, not stale `.alva` projection.
The concurrency/base comparison does not enforce a local edit authorization or
task behavior. No stale scenario is run or credited in P33.

**Independent tests:** generated code actually executes inside existing Linux
OS isolation. Original target test passes; original delimiter regression fails;
the response-record and XML-render regression assertions remain included. A
separate same-crate observation prints the actual delimiter value. The driver
initially attempted an external Rust binary observer, but generated module
visibility forbade that import; it was corrected to a same-crate test without
changing visibility, candidate source or assertions. This was an engineering
observer setup error, not a new MM02 result or a Core repair.

Independent behavior tests identify the concrete policy violation. Structural
scope comparison alone can flag an unauthorized delimiter change before commit,
but cannot determine whether every changed body preserves behavior.

## Minimal nonshared-parent control (not a replacement task)

Only inside `parse_delimiter`, rename bound accumulator `found` to
`delimiter_found` at its binder and sole reference. No prefix source, task,
other function, requirement or assertion is changed. The control passes original
baseline regressions, still fails the unimplemented prefix requirement, and
returns `!` for the original delimiter observation before mutation.

Changing the `then` reference makes delimiter's selected `if` parent differ;
prefix's original parent revision remains unchanged. The original P29 Native
operation sequence is then applied unchanged. The selected prefix parent is
no longer reachable from delimiter, only prefix's staged body changes, preview
lists only prefix, and task plus regressions PASS after commit/fresh read.

This establishes a **nonshared selected-parent** control, not a graph with no
shared descendants: the original `rest == part` child can still be shared.
It supports the identified alias-propagation mechanism; it is not a production
recommendation to rename variables, nor proof of general fix correctness or
Agent usability. It is not counted as a model success.

## Minimal controls and recommendation — design only

| Option | Directly addresses | Cost / limitation |
|---|---|---|
| Occurrence/path-scoped replacement | Changes one caller-specified incoming occurrence | Future Core work: root declaration + ordered slot/index path + expected base/root/parent revisions; path-copy changed parent and ancestors and reconnect **only that root**; reject stale/ambiguous path. More validation and API surface; no behavioral guarantee. |
| Copy-on-write / unsharing | Shared-parent aliasing | A bare clone re-deduplicates to the same content hash. Construct the changed subtree and path-copy its occurrence to a unique owner; do not merely clone then mutate the same revision. Storage/ancestor rebuilding cost; preserve global operations as explicit behavior if needed. |
| Precommit affected-declaration comparison | Unexpected named-region changes | Existing staged inspections/preview can flag this case; compare against trusted allowed declarations, not model-self-declared scope. Body hash differences can include benign rewrites; type/field/signature changes require broader declaration coverage. |
| Host-owned authorized-scope guard | Prevent publication of known out-of-scope changes | Smallest immediate integration option without Core change: freeze trusted scope and base named revisions; enumerate/inspect complete relevant declarations before/after; refuse commit on extra changes or incomplete/UNKNOWN comparison. Adds reads and strictness; not an automatic repair or comprehensive semantic impact analysis. |
| Independent behavioral regressions | Concrete user-visible wrong outcomes | Required despite check/commit/scope PASS; finite tests are incomplete. Current check/build consumes authority, so this driver tests committed AIR **in a disposable isolated workspace**, not a fictional precommit staged evaluator. External promotion could be withheld until tests pass. |

**Recommendation:** first use the existing precommit scope evidence to refuse
the known cross-function spill under a trusted, explicit scope policy; here
preview already supplies the warning and both staged bodies are inspectable.
Do not turn that into a claim of behavioral preservation. For an actual local
mutation guarantee, the minimal future Core proposal is occurrence-scoped
path-copy rooted at an explicitly named declaration, not more prompts, a new
ledger, blanket node de-duplication removal, or a change to static checking.
This node implements **neither** that guard nor the Core proposal. The cost is
path-validation/ancestor-copy work plus truthful affected-set/evaluation checks;
concurrency revision preconditions and independent behavior remain necessary.
No P34 execution or model study is authorized automatically.

## Reproduction, evidence and limits

`benchmarks/p33_shared_scope/reproduce.py` is a thin deterministic driver over
P29 `Client`/`evaluate`/witnesses and P22/P23 `PersistentSandbox`. It does not
replace the harness, alter MCP schemas, use AppServer/provider credentials or
perform host-permission candidate execution. Local tested platform: Linux via
Ubuntu-26.04 WSL; original ALVA ELF SHA256
`29e5abd692206876a3929112e471cb99ce457d478dcd81c50cb006aa3b958257`,
same as P29. Runtime/compiler/source hashes are in RESULTS.json. Windows/macOS
candidate execution is unsupported, no fallback.

```text
python benchmarks/p33_shared_scope/reproduce.py --alva <Linux-alva> --toolchain <Rust-sysroot> --registry <public-Cargo-registry> --output <new-controlled-folder>
python benchmarks/p33_shared_scope/publish.py <controlled-folder>
python -m unittest benchmarks.p33_shared_scope.test_scope -v
```

The first command refuses an existing output directory, never writes P29 files,
and reproduces the fixed case plus its single mechanism control. `publish.py`
recomputes hash/path evidence without executing candidates. Public RESULTS,
SHARING and VALIDATION contain derived evidence only. Local `raw.json` holds
actual calls, initial/staged graph inspection, final source/AIR and evaluations;
its hash is bound in RESULTS.json. Raw records and failed development attempts
stay local; CI saves its own logs/engineering records as Actions artifacts.
CI uses an unchanged freshly built trusted SDK, records its own binary/runtime
identity and checks the same semantic assertions rather than pretending its
binary hash/test-log order must match the local ELF. No historical gate rerun.

Supported conclusion: the original parent-sharing witness propagates the slot
change to both functions; staging/preview expose that scope, while ordinary
check and commit accept it; independent regressions demonstrate the unwanted
behavior. This is not a universal ALVA correctness failure, a theorem that MM02
cannot be expressed safely with other operation compositions, a static-check
soundness result, a model-effect estimate, or a Text-vs-Native utility score.
Historical P20–P32 dispositions remain unchanged. STOP for reviewer.
