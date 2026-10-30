# P35 — Original MM02 occurrence-scoped mutation feasibility

Base: `3a13b3f843f0bbc0be287a950e0c34fc997a7d1c` (P34).
This is Codex-assisted deterministic engineering, not a model capability
experiment. Model generation calls = 0; input-token API calls = 0.
**EXISTING_NATIVE_OCCURRENCE_SCOPE_FEASIBLE.** Actual Linux isolated execution
passes all success conditions with existing public Native MCP operations.
No Core extension is required for this fixed original MM02 case.

## Existing-operation capability analysis

The authoritative implementations inspected are `alva/src/mcp.rs` (`MCP_TOOLS`,
`operation_exposed`), `aep.rs` (registry), `main.rs` (`position_valid_for`,
`resolve_operand_strict`, operation executors), `construction.rs` (construction
registry), and `air.rs` (`create_node`, `set_field`, `replace_slot`, `stage`,
`rebuild_revisions`, `replace_node`). No implementation is changed.

All twenty current Native MCP tools are accounted for:

| Public tools | Capability and limit relevant here |
|---|---|
| `begin_transaction`, `abort_transaction` | Own private staged graph; transaction isolation does not unshare graph occurrences. |
| `resolve_entity`, `inspect_project`, `inspect_entity`, `inspect_body` | Locate named functions, enumerate reachable slots/revisions, inspect staged declarations. Rooted inspection supplies evidence, not an implicit mutation authorization. |
| `applicable_operations`, `describe_operation`, `describe_construction` | Discover admitted operations and kind-dependent slots. Internal AEP discovery does not grant MCP admission. |
| `create_reference`, `create_literal`, `create_binary`, `create_call`, `create_if` | Build nodes from existing revisions. Content-identical construction deduplicates; construction alone does not connect a node. `create_if` can build a changed alternative without mutating the original shared if. |
| `construct_expression` | Existing kinds: field, record, record_update, veclit, fold, match, ok, err, not, range. Range returns a fold sub-form rather than an independent AIR node. No arbitrary node clone, binding constructor or block constructor on this surface. |
| `replace_expression` | Strict revision/semantic-handle resolution and kind-dependent position mapped to `replace_slot`. Binding supports `body`; function does not. No owner/path/index precondition. It mutates the addressed parent entry, so safety depends on which parent is chosen. |
| `change_field` | Scalar field update using `set_field`; not slot rewiring or path-copy. Changing a shared node can propagate. Renaming the fixture or its accumulator is excluded here. |
| `preview_semantic_diff`, `check_transaction`, `commit_transaction` | Describe changes, check ordinary graph/type semantics, publish AIR with ordinary stale-base checking. They do not themselves enforce the MM02 requirement or authorized declaration set. The unchanged P34 Host mediator guards commit. |

Additional existing **AEP gateway** operations include `create_binding`,
`create_block`, `append_step`, `create_query`, declaration/signature editing
and A1-gated operations. These are absent from the twenty MCP tools. In particular,
`create_binding` creates name/type/value slots, not a complete automatic
occurrence copy; `append_step` locates a function's body block then appends a
child, without guaranteeing that block is unshared. They are not used as Agent
capabilities in this result. MCP refusal probes cover create_binding/create_block/
append_step. No environment gate is enabled.

Existing **Core-only mechanisms** include `AirGraph::add`/`compute_revision`,
`EditSession::create_node`, `replace_slot`, `append_child`, and `replace_node`.
The first ones underlie the public executors; there is no public arbitrary
`create_node` tool. `replace_node` replaces every incoming reference and is
explicitly global. Transaction graph cloning is isolation from authority, not
occurrence-local cloning. There is no existing atomic occurrence-rooted
path-copy operation with root/path/base expectations.

## Concrete original-graph route

The immutable P29 bundle hash is
`352a8b6fa459942b8b1d5469a966a706498afa7a2abbc13c39c457dafb069faf`.
The driver takes `case("MM02_SHARED")` directly, verifies that hash, and checks
materialized source/manifest bytes against the original decoded bundle. It never
uses the P33 nonshared control, source rewriting, or alpha-renaming.
The trusted policy is exactly P34's original MM02 policy, authorizing only
`{store.xml.parse_prefix}` with the complete nine-function inventory.

Both original functions reach shared if
`33ecf18b03c1348dd59bf91c15f66a73d06cba29dd757254c4e7917ed96beb5f`.
However, its immediate `rest` binding parents differ: prefix binds the result
of stripping `"prefix="`, delimiter strips `"delimiter="`. The prefix binding
is absent from delimiter's reachable graph. This creates an existing safe
attachment point above the shared node. No complete function reconstruction is
needed for this fixed case.

The candidate sequence uses only existing public tools:

1. Inspect from named prefix and delimiter roots. Verify the shared node and
   ordered slot/index path, and verify the immediate prefix binding is absent
   from delimiter's reachable graph. Use its current revision as parent.
2. Create reference `found`, empty string, equality `found == ""`, and `true`.
3. Create a new condition `if(unset, original_rest_equals_part, true)`.
4. Create a new if with that condition and the original shared if's then/else
   children. The original shared if remains unchanged; identical leaf nodes may
   still be shared safely.
5. `replace_expression(parent=<prefix rest binding revision>,
   child=<new if revision>, position="body")` reconnects the changed subtree.
6. Inspect all nine body-root revisions, preview and check; call actual
   `GuardedNative` commit with unchanged trusted P34 policy. Independently count
   underlying Native commit dispatches, then open a new MCP process to inspect
   committed AIR and execute the original P29 goals/regressions in isolation.

This reconstructs the changed shared if and reconnects through a prefix-only
parent. It does not modify the shared parent then attempt to repair delimiter.
Merkle rebuilding still visits module heads, but unchanged delimiter content
must retain its complete graph and body revision.

The condition preserves first **nonempty decoded** prefix: while `found` is empty,
unmatched parts preserve it and matching parts decode into it; an empty decoded
value leaves it empty for the next match. Once nonempty, all later parts preserve
it. Decoding and delimiter's last-match code are reused unchanged.

## Deterministic experiments and evidence

`benchmarks/p35_occurrence_scope/reproduce.py` contains three bounded routes:

| Route | Actual staging and publication result |
|---|---|
| Detached construction | All body revisions unchanged; abort, no commit, target remains expected FAIL. No maintenance success credit. Also probe direct function-body replacement and unexposed AEP operations, retaining actual refusals. |
| Original P29 shared mutation | Prefix and delimiter change; check problems=[]; real P34 Guard SCOPE_VIOLATION; zero underlying commits; authority unchanged; target remains expected FAIL, regression PASS. Historical unguarded P29/P33 failure is not overwritten. |
| Prefix binding reconnection | Only prefix changes; old shared if and complete delimiter graph unchanged; check problems=[]; real Guard SCOPE_ALLOWED; one underlying commit; AIR published; new-process project revision equals commit and body roots equal staging; original goal/regressions and scope PASS. |

Every route starts from a fresh original bundle and executes original baseline
goal (expected FAIL) and regressions (PASS). All candidate Native MCP, compiler
and generated Rust execution uses unchanged P22/P23 `PersistentSandbox` and
`SDK` under Linux OS isolation. No host-permission fallback. Raw calls, Guard
reads/decisions and dispatch ledger, and compiler/test diagnostics are retained
only as ignored local output or Actions artifacts; public `RESULTS.json` is a
derived summary with body revisions, graph paths, preview, check, Guard, commit,
fresh authority and independent results. No raw agent transcript enters Git.

Reproduce on supported Linux with an unchanged SDK:

```sh
python benchmarks/p35_occurrence_scope/reproduce.py \
  --alva alva/target/debug/alva \
  --toolchain "$(rustc --print sysroot)" \
  --registry "$HOME/.cargo/registry" --output out/p35-new
```

Output must not already exist. Windows driver execution refuses explicitly;
this workstation has no usable WSL, so actual execution is delegated to the
repository's Linux CI runner. Local Python compilation and all seven existing
P34 guard unit regressions pass. The P35 workflow also runs the public Rust
format, Clippy, unit-test and build baseline, plus the actual isolated routes.
This directly invokes Native through the P34 mediator; it does not claim an
AppServer/model approval-route experiment or model tool-use success.

## Supported conclusions and limits

Every success condition above passed in actual Linux execution; construction
or SCOPE_ALLOWED alone was not credited. The route establishes fixed-case
engineering expressibility with existing
Native tools, without changing Core/AEP/MCP/official Skill or the original graph
before the transaction. It does not establish automatic occurrence semantics
for arbitrary parents, Agent discoverability, universal behavioral preservation,
or a language/correctness advantage. P29's original sequence still spills.

This result does not supply general path-copy semantics for graphs without an
available unshared attachment parent. No new stale-path, ambiguity, concurrent
mutation, shared-ancestor copy or arbitrary-kind reconstruction experiment was
run. Current revision/commit preconditions and P34 Guard remain unchanged.
Because this fixed case is feasible, no Core extension is proposed or implemented.

## Verified revisions, CI and Git scope

Evidence execution HEAD: `5ad595d8820753bd731d6c97de4667b5de683597`;
parent: `03571c3509fd7cba92973f264419369273a6866d`.
The unchanged final driver passed [Linux CI run 41098355252](https://github.com/zkidp/alva-core/actions/runs/41098355252).
That run passed cargo fmt, Clippy with warnings denied, 26 Rust unit tests,
SDK build, seven P34 guard regressions, and all three isolated P35 routes.
The earlier initial witness also passed run 41097982393; final evidence uses the
stronger second driver with explicit commit revision equality and refusal probes.
Public RESULTS.json is derived from that successful job's JSON output.
Its raw_sha256 fields hash canonical parsed records, not indented file bytes.
The retained Actions artifact is `p35-native-engineering-evidence`, ID
`12997540867`, archive digest SHA256
`a4437a487172ff8d4922a31dc85bb6a21e0984da7322a5cdfd6e4adae19e3fa6`.

Published AIR generation: **1**. Committed and fresh-process project revision:
`b414a22eeaac90b281f7ae267965713a8fa5e82d67aa28f5cdd0a3275931f139`.
Prefix body: `14a972cff2d1b88cd843e80c5fab0a8c19d80db7f2936fd3a724016c3b6168d9`
→ `37d4de36ae0441ce924088130f155bab20ed693c2b6ca6f7fd7022fa07e3ea9b`.
Delimiter body remains
`62e883ecbd8302c9f6683f0380c69a1054d6f8f26cc7ea40bd190a76db2ff672`.
All other seven body revisions remain unchanged. The original shared if remains
byte-equivalent as an inspected node. The original repeated-delimiter assertion
`delimiter=%2F&delimiter=%21` → `!` passes, along with all other original
regressions and every original goal vector. Preview lists prefix only.

Exact additive changed files relative to P34:

- `.github/workflows/p35-occurrence-scope.yml`
- `benchmarks/p35_occurrence_scope/reproduce.py`
- `benchmarks/p35_occurrence_scope/RESULTS.json`
- `docs/research/p35-occurrence-scope-feasibility.md`

Branch: `codex/p35-occurrence-scope-feasibility`, targeting the P34 branch
`codex/p34-host-owned-scope-guard`.
[Full branch comparison](https://github.com/zkidp/alva-core/compare/3a13b3f843f0bbc0be287a950e0c34fc997a7d1c...codex/p35-occurrence-scope-feasibility).
The final PR description records the final publication HEAD/parent, exact-head
CI, origin equality and clean worktree after the derived-evidence commit;
this report records the reproducible execution commit without a self-hash cycle.

Only additive P35 driver/workflow/report/results files are permitted. P20–P34
frozen artifacts and all original programs/assertions remain byte-identical.
No rescoring, model slots, provider calls, default plugin change, automatic
merge, Core implementation or later experiment is included. STOP after PR creation.
