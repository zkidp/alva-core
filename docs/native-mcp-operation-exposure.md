# P25: bounded native MCP operation exposure repair

Base: P24 `837226e69262d37c6e5fd5af5465790066bd7211`.
This is existing Gateway capability exposure, not a language/AIR/AEP extension,
not an agent experiment, and not a retroactive change to P24's disposition.

## Minimal closure and implementation

Six existing canonical Registry operations are added to the MCP allowlist:

| Operation | Necessary role in the fixed engineering witnesses |
|---|---|
| `create_reference` | Input variables and fold bindings |
| `create_literal` | Integer/boolean constants |
| `create_binary` | Arithmetic, comparisons and accumulators |
| `create_call` | Existing pure builtins and recursive function calls |
| `create_if` | Empty-vector branch and boolean fold branch |
| `replace_expression` | Attach the new expression to the existing function block |

Existing `construct_expression` supplies vector/fold construction. The current
function block is reused; `create_block`, `append_step`, `create_binding` and
the rest of the Registry remain closed. Total advertised tools: **20**, not the
whole Registry. No aliases or unregistered operations are added.

`alva/src/mcp.rs` still derives argument schemas from
`aep::operation_input_schema`, forwards to the real `alva agent`, and uses the
unchanged AIR transaction implementation. One exposure/gate predicate is shared
by tools/list, calls and applicable-operation filtering. `describe_operation`
now returns `E_MCP_OPERATION_NOT_EXPOSED` for a closed operation instead of
presenting its Registry description as a callable MCP capability. Missing/wrong
transaction IDs and ordinary Gateway errors retain their existing handling.
Legacy and modern MCP envelopes remain supported.

The deterministic schema golden is updated from
`7a972f59a9232b08f4e13740dc98853ce9262a5d21ab67fe98ccafacb8b93ed9` to
`28aff2aba83255c2a9551a8a644fa6f7502427910562f05536cf980aaa86ba0b`.
The new value is the actual serialized Rust tools/list output, observed from
the golden assertion, not a disabled or weakened assertion. Additional unit
tests compare every emitted parameter schema with its Registry source after
removing only the MCP transaction_id wrapper, and verify bounded discovery.

## Actual zero-model closure

`tests/mcp/coding_closure.py` obtains the **unchanged** eight initial files for
HE41/HE23/HE42/HE3 from exact P24 Git blobs using P22 `pack_git` and P23
`PersistentSandbox`. It also materializes the existing public protocol test's
stdio client, using only that client class, not reopening its old fixtures.
The trusted new witness driver is passed as explicit UTF-8 process input; its
actual bytes and SHA256 are recorded separately from the initial Git bundle.
This is an engineering test, not a formal execution freeze.

All real MCP/agent processes, AIR writes, compiler invocations, generated Rust,
Cargo tests and direct CLI regression run **inside** the P23 Linux namespace.
Only building the trusted updated compiler SDK itself precedes isolation.
There is no host-permission candidate build/test fallback. Source projection
bytes are checked unchanged. Witness expressions and public test vectors are
test-only: **never add these test files, transcripts or solution paths to a
future model's inputs or to its initial source tree**.

Each case performs initialize/tools-list, actual schema/operation discovery,
begin/resolve/inspect, node construction, target attachment, preview/check/
commit, closes the MCP process, rereads committed AIR from a new process, then
builds and executes independent behavior assertions. Each original baseline is
check-valid but fails its whole behavior suite; all final suites pass:

| Exact P24 initial case | API closure | Independent final behavior |
|---|---|---|
| HE41 | SUPPORTED | 7/7 |
| HE23 | SUPPORTED | 6/6 |
| HE42 | SUPPORTED | 6/6 |
| HE3 | SUPPORTED (modern protocol) | 8/8 |

These are 27 engineering assertions, not model task outcomes. An additional
direct CLI HE41 witness passes its corresponding seven assertions; do not pool
that repeated parity check as another independent task.

The fixture records:

- Closed describe/call refusal; required and wrong transaction-ID refusal.
- An attached missing-symbol expression causing check **and commit** rejection,
  no initial authority publication, followed by repair and valid commit.
- A stale named-function revision rejected with `E_AEP_OPERAND_STALE`.
- Two real concurrent MCP sessions on one separate guard project: winner
  commits; stale-base commit receives `E_AEP_CONFLICT`; published AIR hashes
  remain unchanged after rejection (accepted stale writes in this scenario: 0).
- The same 20 parameter schemas across legacy/modern and fresh sessions.
- Actual RPC arguments/responses, compiler/test output, AIR hashes, exact input
  bundle identity, SDK binary hash, driver hash and Rust/Cargo versions.

Public local evidence: `evidence/native-mcp-operation-exposure/LINUX.json` and
`WINDOWS.json`. Linux was explicitly run under WSL2 Ubuntu with the public
approved SDK; that is **Linux execution**, not a Windows sandbox backend.
The dedicated CI publishes fresh Ubuntu results and asserts native
Windows/macOS `UNSUPPORTED_FAIL_CLOSED`. Existing Core CI supplies broader
compiler/CLI/MCP regression results. No P0-P24 historical study gate or model
slot is rerun.

## Known limitations retained, not silently repaired

1. **Anonymous historical nodes:** an old anonymous block revision may still be
   accepted under the existing detached-node allowance. The fixture separately
   records that response and verifies the current staged program revision does
   not change. It does not claim universal rejection of old anonymous IDs. Use
   fresh inspect results; named revision rejection and stale-base publication
   protection are separate tested properties. No AIR semantics were changed.
2. **Existing checker limit:** during development, an i64-returning function
   with a staged string result received `problems:[]` from check_transaction.
   The fixture retains the exact body/response as
   `existing_checker_observation`, then **aborts without commit**. This is not
   counted as a successful rejection test or as a task result. That checker
   repair path is stopped here because changing Core semantic checking is
   outside this exposure-only scope. Independent compile and behavior checking
   remain necessary; no soundness guarantee is inferred from check/commit.
3. The vectors establish the specified bounded public cases only, not arbitrary
   ALVA programs, adversarial compiler correctness, or an agent benefit.
4. The P22/P23 trusted kernel/SDK assumptions and per-process resource limits
   remain unchanged. Native Windows/macOS candidate isolation remains unsupported.

## Reproduction and research boundary

```text
cargo test --locked --manifest-path alva/Cargo.toml mcp::tests
cargo build --locked --manifest-path alva/Cargo.toml
python tests/mcp/coding_closure.py --alva /approved/linux/alva --toolchain /approved/rust-sysroot --registry /approved/public-registry --output out/p25.json
```

On Linux, supply bubblewrap/util-linux and an approved offline Cargo registry.
`--repo` may point to a normal Linux Git clone containing the exact P24 commit
when Windows worktree Git-dir paths are not meaningful to Linux Git. No input
normalization, task replacement or enriched initial source is allowed.

P24 Phase A remains **PASS**, and its Phase B remains **BLOCKED / NOT_STARTED**.
Its report, blocked evidence, input files and executor are untouched, as are
P21/P3 historical execution/results. The P24 old-API gap reproduction is not
repurposed as a new-SDK acceptance gate. P25 updates no Skill, Gateway operation,
AIR model, capability flag or main branch. **Generation calls = 0; input-token
API calls = 0.** Codex authored engineering code/witnesses, not controlled agent
outcomes. Any later model study requires a new execution freeze and separate
execution; it is not P24 Phase B having secretly run. STOP after this PR.
