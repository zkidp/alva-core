# P23: native MCP persistent sandbox adapter v1

Engineering parent: P22 `6a0d238159b1f5987b5c8fd1fa1b94aef984eb7f`.
This adds `persistent.py`; it does not replace P22's batch-only `sandbox.py`,
its README/evidence, or any frozen benchmark controller. No models are used.

## Trusted host interface

```python
from integrations.benchmark_runtime_v2.freeze import pack_git
from integrations.benchmark_runtime_v2.persistent import PersistentSandbox
from integrations.benchmark_runtime_v2.sandbox import SDK

# These choices/IDs belong to the trusted host, not an agent tool.
bundle = pack_git(repo, approved_commit, explicit_public_input_paths)
assert bundle["payload_sha256"] == approved_bundle_id
with PersistentSandbox(bundle, approved_bundle_id, SDK(alva, toolchain, registry)) as box:
    with box.mcp() as mcp:
        mcp.request("initialize", {
            "protocolVersion": "2025-11-25", "capabilities": {},
            "clientInfo": {"name": "trusted-host", "version": "1"}})
        mcp.notify("notifications/initialized")
        schemas = mcp.request("tools/list")
        result = mcp.tool("begin_transaction", {"project": "/work/project/alva.toml"})
        # Check native isError/structuredContent; pass returned transaction_id
        # unchanged into subsequent native tools, as required by their schemas.
    # A new mcp() process can reread committed AIR in this SAME workspace.
    # Host-approved commands also execute inside exactly this boundary:
    checked = box.run(["/sdk/alva", "project", "check", "/work/project/alva.toml", "--json"])
```

The fixture uses the existing public `tests/project` (three exact Git blobs at
the parent), not a model candidate/reference solution. Its actual sandbox path
is `/work/project/tests/project/alva.toml`. The example above assumes input
paths place a manifest at the project root; no implicit path relocation occurs.

`request`, `notify`, and session `close` serialize through a per-session lock.
The host must serialize workspace lifecycle operations: one active process,
one slot, no concurrent `run`/`mcp`/workspace `close`. Native tool schemas and
transaction IDs are not rewritten. IDs are **session-scoped**, not globally
unique: PID namespaces can make IDs repeat across new processes. Never carry
an old handle into a new session; call begin again. The RPC layer assigns
monotonic request IDs within each session, validates the response ID/version,
and does not replay, restart, or retry an uncertain action.

This supports ALVA's current newline JSON-RPC transport, not arbitrary MCP
servers/framing/transports. Native ordinary tool `isError` is returned intact
(including wrong transaction IDs); it is not a transport crash. Malformed JSON,
wrong response ID, JSON-RPC error, unexpected EOF/exit, RPC/wall/output limit or
unconfirmed cleanup raises `Closed` and makes the entire workspace unusable.
Callers must retain that failure, not reconstruct/retry the action elsewhere.
No returned `exit=0`, native commit, or compiler PASS is itself a task oracle.

## Isolation and persistence

The implementation reuses `LinuxSandbox`'s real namespace availability probe,
`_base()` mount/network/capability/environment boundary, and existing `SDK`
approval contract. It reuses `decode`/`materialize` with an externally approved
bundle ID, copying exact bytes to read-only `/input` and writable
`/work/project`. Candidate files are never imported or executed by host Python.
There is no arbitrary host-mount option. The only writable persistent mapping is
the disposable per-workspace `/work`; `/tmp` is a new private tmpfs per process.
Public SDKs are read-only; the public registry is copied once, without following
registry symlinks. User homes, host root, host Cargo configuration/credentials,
reference trees and other slots are not mounted. SDK and input approval must
occur before use; **do not approve private material as public runtime inputs**.

Native `alva mcp`, its `alva agent` child, AIR writes, source files, generated
crates, Cargo build scripts and generated-code tests remain inside this boundary.
Closing one MCP process does not delete the workspace's committed AIR. Opening
a new process reuses that AIR; it does not export/reimport candidate bytes on the
host. Explicit workspace close destroys the disposable tree; this is not a
durable recovery service, source publication, or OS-wide atomic transaction.
AIR authority commit and source projection remain distinct native operations.

Defaults: workspace wall 120s (after trusted input/SDK preparation), RPC 15s,
8 MiB total stdout+stderr per process, 1 MiB per outgoing RPC, 16 MiB inputs.
An independent watchdog kills an idle or busy process at workspace wall expiry.
Nonblocking bounded stream reads handle backpressure; EOF and cleanup must be
confirmed. Clean session close allows 5s then kills; no unbounded wait is used.
The same P22 prlimit values apply before bwrap (CPU 90s, address space 4GiB,
file size 256MiB, nofile 256, nproc 128). These remain **per-process**, not total
workspace disk/RAM/CPU quotas. The trusted host must separately bound concurrency
and storage. Pipe limits are checked while receiving; an idle writer can block
on bounded kernel pipes until the wall watchdog terminates it.

`run(argv)` launches only an explicit in-sandbox executable, adds no shell and
keeps the workspace. Nonzero exit is fail-closed with bounded stderr evidence;
there is no usable success result or automatic retry. The host can deliberately
use a trusted in-sandbox driver to capture expected check/test failures as data,
but must not reinterpret them as correctness. Do not put hidden reference
source in `argv` or inputs. P23 uses public integration assertions, not a hidden
benchmark evaluator.

Linux is the only execution backend. Missing bwrap/prlimit/SDK, denied namespace
creation, native Windows and macOS raise `Unsupported`; no host fallback exists.
An explicitly selected WSL2 Linux environment is a Linux test, **not native
Windows sandbox support**. This relies on a trusted kernel, compiler and public
runtime; it is not kernel-exploit protection or a general multi-tenant service.

## Reproduction and evidence

```text
cargo build --locked --manifest-path alva/Cargo.toml
python tests/benchmark_runtime_v2/persistent_probes.py --alva alva/target/debug/alva --toolchain /approved/rust-sysroot --registry /approved/public-registry --output out/p23-linux.json
```

Install bubblewrap/util-linux on Linux and provision offline Cargo dependencies
in the trusted SDK preparation step. `--repo` may identify a normal Linux Git
clone containing the exact parent; this is useful for Windows worktree metadata
whose absolute Git-dir paths are not meaningful to Linux Git. Both byte inputs
and parent commit remain identical; the tests do not relax checks for line endings.

The zero-model test performs real initialize/initialized/tools-list/schema
queries; begin/resolve/inspect/change/preview/check/commit; a new MCP process
reloading AIR; and real project check/build/Cargo tests in isolation. It confirms
source projection bytes are unchanged and generated Rust contains the committed
AIR change. Host-only synthetic reference/other-slot/private sentinels, root/input
and SDK writes, live-host/external-network connections, and a mount syscall are
tested at the OS boundary. No real user files or credentials are probed.

Separate rows cover abnormal exit, wall/output limits, a real native RPC error,
an idle-session watchdog, and synthetic malformed/wrong-ID/EOF/timeout peers
inside the sandbox. Cleanup uncertainty is tested by **injecting wait failure**,
not by claiming a real unkillable process was created. No old P0/P1/P2/P20 gates
or P21 slots are rerun. `evidence/native-mcp-sandbox/` records local actual logs;
the dedicated `native-mcp-sandbox.yml` CI publishes fresh Linux logs and
Windows/macOS fail-closed assertions as artifacts.

This is a transport/isolation integration result. It includes no Codex model
task, no full Skill effectiveness test, no candidate benchmark score, and no
evidence that AEP improves agent correctness. A future model protocol, approved
SDK/runtime identities, evaluation separation and budgets still need their own
pre-execution freeze. P23 does not authorize that study.
