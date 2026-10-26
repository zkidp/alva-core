# Prospective benchmark runtime v2

Independent from `benchmarks/cross_language`: do not replace its frozen code or
use its historical evaluate function for untrusted future candidates. No Guard,
MCP server, ALVA operation or agent harness is reimplemented here.

## Execution contract

`LinuxSandbox(SDK(...)).run(files: dict[str, bytes], argv: list[str], stdin=b'')`
accepts only host-approved exact input bytes and an explicit in-sandbox executable.
All input names are relative, bytes are copied (no candidate symlinks/hardlinks),
and candidate state lives in a new `/work/project`. Read-only `/input` retains
the original supplied bytes. Every invocation is a separate disposable batch;
no outputs are automatically published/applied. `EXECUTED`/exit 0 describes a
process, **not task correctness**; the trusted external evaluator decides that.

Linux prerequisites: bubblewrap, util-linux prlimit, a kernel permitting the
requested user/mount/PID/network/IPC namespaces, and normal public `/usr/bin`,
`/usr/lib` runtime. The child sees no host root/home/other slots/references.
The root, proc, runtime, input and SDK are read-only; only `/work` and `/tmp`
are writable disposable storage (plus minimal `/dev` devices). The environment
is rebuilt for both the launcher and child. The network namespace has no route
to host or external services. There is no `--ro-bind / /`, host `/etc`, inherited
Cargo credentials/config, native-host execution fallback, or privileged container.

The trusted host selects the ALVA ELF binary, Rust **toolchain directory** and
public Cargo **registry directory**, not a home/project/Cargo-home bind. ALVA
and toolchain are read-only, registry files are copied into disposable Cargo
home; registry symlinks are refused. The caller must provision and hash-bind
this public SDK before model generation, including allowed runtime identity.
No automatic fetch occurs in the sandbox. Unavailable offline dependencies
are an environment failure, not permission to enable networking or retry outside.

CPU/address-space/file-size/open-file/process limits use prlimit before bwrap.
Wall and bounded-output monitors kill the process group and depend on namespace
death/parent-death cleanup. Unconfirmed cleanup refuses usable evidence. These
are per-process limits, not aggregate memory/disk/process-tree quotas. The
trusted host must bound total concurrency/storage separately. This is OS
isolation under a trusted kernel/runtime, not a proof against kernel exploits
or complete availability protection. Paths/configuration alone are not security.

Unsupported platform, absent bwrap/prlimit, denied namespaces or absent SDK:
raise `Unsupported`; never call an unsandboxed substitute. Native Windows and
macOS are intentionally unsupported. Explicit WSL2 Linux execution is supported
only when its real Linux probes pass; no automatic native-Windows fallback exists.
The module is batch-only: a persistent native MCP stdio wrapper is not yet
implemented and must be designed/validated separately before a model study.

## Freeze contract

`pack_git(repo, commit, paths)` reads an explicit complete list from immutable
Git blobs, not working files or inferred HEAD cleanliness. Each entry binds its
path, resolved commit/blob, byte length, SHA256 and base64. `decode` requires an
externally approved bundle ID (self-consistent hashes are not authentication).
`materialize` writes exact decoded bytes into a new directory; `verify_runtime`
rejects mismatched content, missing/extra files or symlinks. It does not relax
checks for CRLF, silently skip an input, or import fallback modules from a
working checkout. The future controller must actually execute/import the
materialized versions, with every dependency in the declared closure.

The byte source can be CRLF or LF in Git: whichever bytes are in the bound blob
are transported unchanged. The two P21 dependencies happen to be LF blobs.
Canonical ASCII JSON/base64 is the transport, not an alternate accepted source
representation. Git mode is provenance, not a cross-platform ACL attestation.
Python/interpreter/OS and external SDK binaries remain separately declared,
platform-specific trusted artifacts; the v2 example is a source-byte transport,
not automatic closure/toolchain freezing for a complete study. All such artifacts
must be fixed and checked before future generation, never normalized after it.

## No-model reproduction

```text
python -m unittest discover -s tests/benchmark_runtime_v2 -p test_freeze.py -v
python tests/benchmark_runtime_v2/linux_probes.py --alva /approved/alva --toolchain /approved/rust-toolchain --registry /approved/registry --output out/linux-probes.json
```

Use an ALVA binary built from this unchanged repository; compilation of the
trusted toolchain itself can precede sandboxing. The probes create only synthetic
host sentinels, a new arithmetic fixture and a hostile Rust build-script/test
probe. They do not run any P21 candidate or model. On unsupported systems the
probe exits 2 with `UNSUPPORTED_FAIL_CLOSED`. CI asserts native Windows refusal,
strict LF/CRLF consistency on both OSes, and real Linux OS denial/build/test
behavior. Historical evidence is not rewritten by any command here.
