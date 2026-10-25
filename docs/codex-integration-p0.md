# ALVA × Codex P0 acceptance

Canonical starting point: `main` at
`cd73ae8c653953289ee758ce24e4821f1b4c5108` (checked 2026-10-26).
The existing Codex plugin is `alva@alva`, version `0.1.0`. The ALVA developer
preview is `v0.14.1-preview.2`; GitHub labels the older `v0.7-public-snapshot`
as its stable/latest release. Select the documented preview explicitly.

## Existing components reused

- `integrations/codex/`: local marketplace, plugin manifest, `.mcp.json`, and
  packaged Skill mirror.
- `integrations/skills/alva/`: canonical workflow and references.
- `alva/src/mcp.rs`: real stdio MCP transport delegating to `alva agent`.
- Existing AEP/AIR resolve, staged mutation, check, commit and abort behavior.
- `tests/mcp/mcp_protocol_test.py`: legacy/modern wire and authority tests.

No server, Skill, agent loop, or semantic operation was reimplemented. No
existing transport defect was reproduced in the tested canonical version;
the missing acceptance coverage was installation followed by real Codex-hosted
tool calls. The new fixture adds that coverage and keeps packaging checks.

## Reproduction and scope

Build ALVA and run `tests/integrations/codex_native_test.py` as documented in
the [Codex integration README](../integrations/codex/README.md). The test copies
the public `tests/project` fixture, creates an isolated temporary Codex home,
installs the existing local marketplace/plugin, and verifies Skill discovery
and all 14 advertised MCP tools through Codex app-server.

The test then calls begin, resolve, applicable operations, describe operation,
inspect body/entity, change field, diff, check and commit. It confirms no
authority was published before commit; a fresh transaction reads the changed
literal. A second staged edit is aborted without advancing authority. Original
source projection bytes remain unchanged. Independent project check/build and
generated-project tests complete the native operation.

This is an actual plugin → Codex app-server → MCP → AEP → AIR → project build
test. There is no `turn/start`, provider generation, credential discovery, or
test of autonomous model planning. The fixture does not install into the user's
normal profile. The temporary configuration is removed on completion.

## Local execution

On Windows x86-64 with Codex `0.163.0-alpha.11.2`, the installed-plugin workflow
passed, as did 24 compiler unit tests, build, format, strict Clippy, both plugin
packaging tests, and the existing MCP protocol/authority fixture.

The first MCP fixture build hit a DNS failure for `index.crates.io`. Re-running
with `CARGO_NET_OFFLINE=true` and the existing dependency cache passed; the
installed-plugin test also passed using that cache. This is recorded as an
environment dependency, not a semantic/server fix. No dependency or budget
contract was changed.

An attempt to retrieve published binary assets locally was blocked by DNS for
`release-assets.githubusercontent.com`. Thus the local end-to-end result uses
the compiler built from canonical source, not a downloaded release executable.
Release metadata and the tagged MCP source were inspected separately.

The new `Codex native integration` CI workflow pins public Codex `0.164.0` and
runs the same no-provider fixture on Linux and Windows. Its results must be
read from the PR checks; this document's local execution is not a substitute
for either CI platform. Existing full CI remains required. No macOS installed
Codex-host result is claimed.

## P1 boundary

[Python Guard MVP](python-guard-mvp.md) defines snapshot/verify/report as a
separate design. There is no Python implementation, automatic plugin update,
cross-language semantic transaction claim, or model comparison in this change.
Public API behavior is preserved and no frozen research artifacts are touched.
