# Native MCP/Skill development preflight

Read [REPORT.md](REPORT.md) first: **Phase A PASS; pilot NOT STARTED**, blocked
by the current native MCP operation exposure. This directory is not an
execution-ready benchmark and contains no model outcomes or placeholder freeze.

Actual Windows Codex Host acceptance (explicit WSL Linux candidate backend):

```text
python benchmarks/native_mcp_skill/phase_a.py --attempt unique-development-label --alva /approved/linux/alva --toolchain /approved/rust-sysroot --registry /approved/public-registry --output out/phase-a.json
```

Requires the installed Codex CLI with plugin/AppServer support, WSL distribution
`Ubuntu-26.04` (override `--distro`), and the already tested P22/P23 Linux SDK.
It installs the existing plugin only in a new temporary CODEX_HOME, copies exact
public plugin/Skill blobs, and changes only local `.mcp.json` transport wiring.
No user plugin or credential file is opened/copied by these scripts. The trusted
Codex Host inherits the ordinary host process environment; no credential values
are recorded or supplied to the isolated candidate (P23 clears its environment).
It starts no model turn, needs no provider key, and never executes a candidate
on the Windows host. Every attempt has a new directory; no historical directory
is removed/reused. `proxy.py` is a trusted fixed-fixture service/stdio relay, not
a substitute ALVA MCP server or semantic operation implementation.

Linux reproducible regressions and coverage (no Codex installation/model needed):

```text
python benchmarks/native_mcp_skill/test_integration.py --alva /approved/alva --toolchain /approved/rust-sysroot --registry /approved/public-registry --output out/integration.json
python benchmarks/native_mcp_skill/native_coverage.py --commit 12c13c1f6d6e272050949826f711431bb89e8064 --alva /approved/alva --toolchain /approved/rust-sysroot --registry /approved/public-registry --output out/coverage.json
```

Use `--repo` for a normal Linux Git clone containing the input commit when a
Windows worktree's Git-dir paths cannot be interpreted by native Linux Git.
There is no CRLF/LF relaxation: `pack_git` and P23 materialize exact blobs.
The coverage test intentionally expects and records the current entry-point gap,
not a passing task solution. Do not report that label as pilot effectiveness.

The P23 namespace/SDK trust and per-process resource limitations remain unchanged.
Optional metadata `-32601` handling is whitelisted and opt-in; semantic RPC
failures still terminate without retries. This does not authorize running a
general model workflow through the fixed integration-fixture service.
