# Native MCP / Skill pilot preparation: blocked before generation

Engineering base: PR #23, `ca930db61823c8318f1126f5649d1863f10fcc37`.

**Phase A: PASS. Phase B: BLOCKED_NATIVE_MCP_OPERATION_COVERAGE.**
Model tasks started: **0/12**. Generation calls: **0**. Input-token API calls:
**0**. No model candidate, scientific outcome, N-vs-B effect or token-economy
estimate exists. No execution freeze or scientific RESULTS file was fabricated.

## Actual Phase A acceptance

`phase_a.py` used the installed `codex-cli 0.163.0-alpha.11.2` Windows AppServer,
an isolated temporary CODEX_HOME, and the existing marketplace/plugin mechanism.
The installed Skill **and all three references** were checked byte-for-byte
against exact Git blobs from the base, not merely checked for filenames.
It called `skills/list`, `thread/start`, `mcpServerStatus/list` and
`mcpServer/tool/call`. There was **no turn/start**.

The native server actually advertised 14 separate operation schemas. The actual
chain was AppServer -> installed plugin stdio -> WSL Linux relay -> P23
namespace -> unmodified `alva mcp` -> `alva agent` -> AIR. Nine semantic calls
performed begin/resolve/discovery/body inspection/field mutation/preview/check/
commit on the existing public `tests/project` fixture. After the client closed,
the trusted owner confirmed MCP termination, opened a new native process in the
same workspace, reread the committed change, and ran project check/build plus
independent generated Rust behavior tests **inside** P23 isolation. The emitted
Rust contained the AIR change; source projection bytes remained unchanged.

See `evidence/PHASE-A.json`: this is an actual Codex Host test, not a mock or a
model's ability to select/use the Skill. The full Skill was available and
discovered, not claimed to have been consumed by a model. Linux
`test_integration.py` separately uses synthetic transport peers with real
namespaces/native MCP; its results are explicitly not Codex Host acceptance.

## Two concrete integration fixes

1. Codex probes optional resource discovery despite ALVA advertising only tools.
   P23 previously poisoned the whole workspace on the native `-32601`. The opt-in
   `optional_discovery=True` now preserves the **original** error for exactly
   `resources/list`, `resources/templates/list`, `prompts/list`. It permits no
   semantic action. Defaults and all other RPC errors still fail closed.
2. AppServer owns and can terminate its plugin subprocesses; verification cannot
   rely on a plugin process's exit handler. A trusted owner now outlives the
   stdio relay and performs termination confirmation/verification. Codex may
   create separate metadata and thread MCP connections, so each gets a separate
   disposable namespace. Verification requires exactly one committed semantic
   context; multiple competing authorities are not silently combined.

The fixed helper is a **zero-model public fixture service**, not an implemented
12-slot controller or a general public-test service. It has no provider access,
credentials, arbitrary host mounts, shell fallback, or candidate host execution.
Its Unix socket is outside candidate mounts in a private Linux temp directory;
only the trusted host/relay can address it. Metadata contexts see only the same
approved public initial bytes, not another slot. The host serializes final
shutdown with pending native requests and refuses unconfirmed closure.

Earlier zero-model development attempts are retained locally under separate
attempt directories, never overwritten as successful scientific slots:
`phase-a` exposed optional-discovery termination; `phase-a-compatibility`
exposed child-owned teardown; `phase-a-owned-lifecycle` exposed simultaneous
metadata/thread handshakes. `phase-a-host-contexts` and the final fixture passed.
These are engineering iterations with **zero model tasks**, not pilot retries.

## Observed common blocker, not a model failure

Before any generation, `SELECTION.json` fixed all four public adapted HumanEval
types (41 arithmetic, 23 ASCII length, 42 vector mapping, 3 prefix state), with
fresh initial files committed at `12c13c1f6d6e272050949826f711431bb89e8064`.
The bounded descriptions/attribution are reused, not prior answers, candidates,
patches or repair traces. No task was replaced after observing capability data.
These adaptations are not official HumanEval or MultiPL-E scores.

`native_coverage.py` materialized exactly those new Git blobs and checked all
four initial projects inside the sandbox. For **each** project, actual native
calls showed:

| Observation | Result |
|---|---|
| Registry `describe_operation` for create_reference/literal/binary/call and replace_expression | Success |
| `tools/list` advertises those five operation entry points | No |
| Calling each of those entry points through actual MCP | `E_MCP_UNKNOWN_TOOL` |
| Supported `construct_expression kind=veclit` with schema-correct elem_type/items | Success, detached node |
| `change_field` on the function's actual current revision, field=body | `E_AEP_002`: function does not allow field body |
| Reread target function body | Unchanged |

The last error is **not** an invalid entity-name/revision mix-up: the test uses
the revision returned by `inspect_entity`. AIR fields and child slots are
different; field mutation is not slot replacement. The native MCP whitelist in
`alva/src/mcp.rs` excludes the existing AEP CLI creation/replacement operations.
Typed construction does not by itself attach a new expression to a function.
See `evidence/NATIVE-COVERAGE.json` for actual schemas/arguments/responses.

This is a callable-entry-point/target-attachment gap in the **current MCP
surface**, not a claim that ALVA cannot express the behaviors, not a model
discovery failure, and not a mathematical proof about arbitrary programs.
The four initial stubs have no existing computation that can simply be fixed by
changing an operator or literal field. We did not replace them with answer-rich
scaffolds, route N through the thin CLI bridge, or add operations to make N pass.

The intended bridge-vs-native coding comparison is therefore blocked at task
preparation: the bridge can call existing CLI attachment operations that N
cannot invoke. Paying for twelve sessions would not fix that interface contract
or isolate Schema/Skill discovery as intended. This is the concrete common
blocker triggering the user's stop rule, **not a newly invented scientific
threshold or reviewer gate**. Fixing native operation exposure would alter the
public MCP operation set, explicitly outside this node's authorization.

## Tests and boundaries

- Actual Windows Codex -> explicitly selected WSL Linux acceptance: PASS.
- Linux optional discovery/lifecycle integration regressions: PASS.
- Four exact new initial projects check-valid; native entry-point gap reproduced
  on all four. No commits of model candidates and no behavioral scores assigned.
- Dedicated CI runs real Linux isolation/native tests and the bounded coverage
  reproduction; it does not claim to run Windows Codex+WSL or any models.
- Native Windows/macOS candidate execution remains unsupported. WSL execution
  is Linux, not a new Windows sandbox backend.

No ALVA Core, native MCP API, AEP registry, language, Skill or installed user
plugin was modified. No P3/P21 or P22/P23 original evidence was changed or
rescored. The P23 Python transport's opt-in discovery compatibility is the only
existing implementation edited. No E5/SS gate was reopened.

Remaining work is **not executed**: a general safe batch controller, model/
budget/order/SDK execution freeze, twelve sessions, candidate/AIR archives,
independent model outcomes and comparison. This PR makes no correctness-gain or
superiority claim and does not authorize an operation-set change or rerun.

Official documentation consulted for AppServer/plugin wiring:
[AppServer](https://developers.openai.com/codex/app-server),
[plugin packaging](https://developers.openai.com/plugins/build/plugins).
Runtime behavior was established by actual local calls, not documentation alone.
