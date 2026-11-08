# Bounded target dependencies — opt-in prototype

This implementation tests one engineering hypothesis: a target view can include
the nested record/alias/enum facts needed to understand its directly referenced
types and direct callee signatures without dumping whole source modules. It is
not a static behavioral dependency closure, inferred specification, edit plan,
or proven reduction of model cost. No new Core/AEP operation or language rule.

## Run the actual deterministic consumer

From this exact development branch, not an assumed canonical main:

```sh
cargo build --locked --manifest-path alva/Cargo.toml
python -m unittest tests.integrations.test_bounded_target_context -v
python tests/mcp/bounded_target_context_test.py alva/target/debug/alva
```

On Windows use `alva/target/debug/alva.exe`: real compiler/AEP/Guard/authority
inspection, but receipt-stub lifecycle only; no behavior-sandbox claim.
On Linux add the existing OS-isolated evaluator:

```sh
python tests/mcp/bounded_target_context_test.py alva/target/debug/alva \
  --toolchain "$(rustc --print sysroot)" --registry "$HOME/.cargo/registry"
```

Install bubblewrap and util-linux, and use the same trusted Rust registry/SDK
requirements as [Maintenance Host](maintenance-host-v2.md). Unsupported isolation
fails closed. The fixture starts from temporary source-only input; reads target,
checks nested dependencies, prepares a generic arithmetic body, verifies draft
tests, publishes via the actual Guard and rereads fresh authority. It asserts
source bytes remain unchanged. This deterministic witness is not an agent run.
Initial test-development faults (a synthetic fixture parameter name collision
and invalid alias spelling) were corrected locally; neither changed Core or
historical results. No model/provider was called.

For an operator-configured real project, the optional MCP stdio entry is:

```sh
python -m integrations.codex.bounded_target_context --config /absolute/trusted-host.json
```

Use the same trusted config as MaintenanceHost. Do not give the agent editable
policy/assertion/SDK config or an alternate commit path. This entry is separate;
existing three-tool Host, five-tool ContextHost, Native MCP profiles, Skills and
plugin defaults are untouched. No installed plugin is updated automatically.

## Delivered contract

`read_target` retains the original body/declaration/direct-context and returns
an additional `bounded_dependencies` object. The mutation tools are byte-for-byte
the existing five-tool ContextHost catalogue (three actions + two public readers).
No new model-facing tool is added. Under the same Host/session locks the wrapper
uses existing inspect_scope_snapshot, read_function and inspect_project calls.
It checks stable staged project/body identity; every fresh read recollects, with
no authorization or context cache. Extra three Native calls, elapsed projection
time and projected JSON bytes are reported separately. They are not free or
evidence of lower provider input cost.

Fields include current staged `project_revision`, `target_revision`,
`body_revision`, exact canonical `snapshot_sha256`, normalized `types`, direct
`callees`, `unresolved` facts and explicit bounds. It does not expose the full
snapshot, callee bodies, hidden tests, evaluator source, requirement text or
witnesses. All data derives from current actual inspected graph plus the
existing compiler builtin catalogue. No ranking or recommended edit sites.

### Supported completeness, not general completeness

1. Scan the target's actual reachable expression/signature/contract nodes for
   named type references, record/update/variant/match types and direct call names.
2. Include direct in-project callee parameters, returns, purity/effect names,
   without scanning callee bodies or contracts.
3. Follow named types recursively through record fields, aliases and container
   type expressions, including enums. Local names resolve in their declaration
   module; qualified names use exact module-qualified identity, never fuzzy
   fallback. Terminate named cycles using visited declarations.

`COMPLETE_WITHIN_BOUNDARY` means exactly that syntactic boundary is resolved in
this snapshot. It does not mean all types needed for a *future* edit, callee
implementation facts, implicit inference, transitive call behavior, runtime
effects, external libraries or full user intention are known. Missing external
or otherwise unresolvable names yield `PARTIAL` with explicit names/counts.
Unknown snapshot shapes, unavailable nodes or changing identity yield `UNKNOWN`;
the original mutation/verification requirements stay unchanged.

The existing read-only snapshot input bound is 2,048 reachable nodes / 8 MiB.
Projection output is at most **16,384 UTF-8 bytes of canonical JSON** and **64
type/callee declarations**, including metadata in the byte check. If the complete
projection exceeds a bound, return `TOO_BROAD`, empty type/callee arrays, required
declaration count and full-projection digest. Do not truncate a record, enum or
declaration list and label it complete. Metadata-only envelope overflow is
`UNKNOWN`. JSON transport may add whitespace/escaping/envelope bytes; this is
not a hard bound on the whole `read_target` response or provider tokens.

Old projections remain historical observations of their exact revision. After
an edit, obtain a new read_target view to see new dependency facts. The projection
itself is not an execution/preparation/publication receipt. Source readers still
label import projection versus staged AIR and retain EOF/continuation semantics.

## Tests and limits

Units cover nested records/aliases/enums; callee-only cross-module type closure;
builtin versus unresolved call; named cycles; unavailable nodes; unsupported
type forms; deterministic bytes; explicit size/declaration overflow; and changing
snapshot identity. Real Core tests check exact graph-export equality before/
after read-only context, stable repeated reads, new staged revisions after an
accepted edit, UNKNOWN on missing snapshot data without weakening Host gates,
and actual scoped commit/fresh read. An unchanged ContextHost receives no new
dependency object. Existing Host rejection/stale/receipt regressions also run.

Actual local checks: Windows Python 3.14.0 / Rust 1.97.1 passes 35 unchanged
Rust units, fmt/clippy/build, 21 new/related Python units and the actual Core,
Host lifecycle and Native profile tests. Independent WSL Ubuntu 26.04 / Python
3.14.4 / Rust 1.98.0 / bubblewrap 0.11.1 passes seven projection units and the
real Linux-isolated compilation/behavior/Guard-publication fixture. A separate
generic two-module read confirms nested dependency names resolve in the owning
callee module. No old paid study or historical qualification wave was run.

This branch does not rerun any consumed experimental freeze, tune MM/W02 tasks,
implement body-span patches, change default context delivery or start new paid
studies. The next decision needs an independent review of this bounded prototype,
not an automatic model comparison. See the
[engineering baseline/review split](maintenance-engineering-baseline.md).
