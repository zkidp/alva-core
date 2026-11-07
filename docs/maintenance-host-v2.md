# Maintenance Host V2

This opt-in Linux maintenance entry offers three model-facing tools:
`read_target`, `prepare_change`, `publish_change`. It moves transaction and
revision bookkeeping, scope checks and staged behavior tests into the trusted
Host. It makes no model or provider calls. The existing default 20-tool and
maintenance 9-tool Native MCP profiles remain available and unchanged.

## Run

Build the current compiler, install Python 3.11+, bubblewrap and util-linux,
and provide a Rust toolchain and offline Cargo registry. From this checkout:

```sh
cargo build --locked --manifest-path alva/Cargo.toml
python -m integrations.codex.maintenance_host --config /absolute/trusted-host.json
```

Register that command as an MCP STDIO server, with this checkout as its working
directory. It negotiates protocol `2025-11-25`. Do not expose a second raw
Native commit route or unrestricted project writes to the same maintenance
agent. This does not silently replace the default plugin server.

The configuration is trusted operator input, never model input. Example for
a project with module `m`, functions `a` and `b`, and no types:

```json
{
  "alva": "/absolute/alva",
  "toolchain": "/absolute/rust-toolchain",
  "registry": "/absolute/cargo/registry",
  "project": "/absolute/project/alva.toml",
  "inputs": ["alva.toml", "m.alva"],
  "crate": "host_demo",
  "assertions": "\n#[test] fn required_behavior() { assert_eq!(crate::m::a(), 2); }\n",
  "policy": {
    "authorized_functions": ["m.a"],
    "modules": {"m": {"functions": ["a", "b"], "types": []}}
  }
}
```

Use the actual generated crate/module names in assertions. List the complete
component declarations in the P34 policy. This release supports its closed
function-body component boundary; unsupported graph/declaration shapes fail
closed. An empty assertion string runs the project's existing generated tests
but is not evidence that a new behavior requirement was tested. Supply both
requirement and regression tests for meaningful qualification. Keep the test
plan and SDK stable during a session. Explicit `inputs` also permits Python
3.10; automatic manifest discovery requires `tomllib` (3.11+).

## Lifecycle

1. `read_target(function)` opens a private transaction and returns an opaque
   view ID, declaration, body and bounded direct context. Compiler-owned
   builtin names and arities are included; this is not complete dependency or
   effect analysis. The default view lifetime is 900 seconds.
2. `prepare_change(view_id, body)` replaces only that named function's body
   through the existing occurrence-copy editor. Parse/type errors leave the
   previous draft intact. Every preparation attempt invalidates any previous
   proposal. The Host invokes the actual P34 scope collector, checks the graph
   and exports its staged AIR through private AEP operations. It then runs a
   separate Linux namespace with that AIR as authority, checks/builds the
   project, and runs the trusted tests. The live project is not published.
3. Only a passing, correctly bound receipt produces a proposal.
   `publish_change(proposal_id)` consumes it before dispatch. The Host rechecks
   the exact draft, source digest and evaluator identity; actual P34 commit
   authorization runs again. Core performs the normal base-revision conflict
   check and durable AIR publication. A new AEP process verifies authority and
   the target body. Source files remain projections and are not rewritten.

A body rejection can be repaired using the same view. Expiry or a competing
publication requires reading again. There is no automatic rebase or publication
retry. If commit succeeded but fresh verification failed, the response preserves
the commit receipt as `PUBLISHED_UNVERIFIED` and blocks further actions. An
uncertain commit transport outcome also blocks the session.

## Boundaries and accounting

The Host and its config are trusted. Core inspection/publication is a trusted
child process; generated candidate code and draft/final behavioral evaluation
run in the existing P22 Linux namespace backend. Windows supports lifecycle and
protocol tests; this entry has no unsandboxed candidate-execution fallback.

Receipts bind the tested file digest, project revision and evaluator identity
(compiler ELF, rustc executable, assertions, driver and resource budget).
They are session-local authorization records, not portable signed proofs.
The complete standard library/registry tree is trusted configuration, not
rehash-pinned by each receipt. Source digests detect changes before dispatch;
AIR's compare-and-swap handles competing semantic publications. This is not
an atomic transaction over arbitrary concurrent filesystem writes. Keep
source/manifest writers coordinated. It is not a security boundary against an
agent separately granted unrestricted shell or filesystem access.

`host_work` counts agent tool invocations, underlying Native calls/reply bytes,
Guard reads and draft evaluation runs/time. Evaluator receipts separately count
their commands and fresh draft reads. Moving work behind the Host does not make
that work free. Lower tool/schema overhead does not by itself establish a
token, latency or cost advantage. See the deterministic qualification report
in [research/maintenance-host-v2.md](research/maintenance-host-v2.md).
