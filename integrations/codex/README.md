# ALVA for Codex

This directory is a thin Codex marketplace package around ALVA's shared public
interfaces. It does not define another editing workflow:

- `../skills/alva/` remains the canonical agent workflow;
- the packaged Skill is an exact distribution mirror, enforced by CI;
- `.mcp.json` starts the installed `alva mcp` STDIO server;
- the compiler, AEP, and AIR remain owned by the `alva` binary.

## Prerequisite

Install ALVA `v0.14.1-preview.2` or later and confirm that `alva doctor` can
find the binary. The directory containing `alva` must be on the environment
`PATH` inherited by Codex.

## Install from a clone

From the repository root, register this local marketplace and install the
plugin:

```powershell
codex plugin marketplace add integrations/codex
codex plugin add alva@alva
```

Start a new Codex task after installation so it discovers both the ALVA Skill
and MCP tools. Ask it to modify an ALVA project; it should follow the canonical
resolve → inspect → discover → stage → diff → check → commit workflow.

## Disable or remove

```powershell
codex plugin remove alva@alva
```

Removing the plugin removes only Codex packaging. It does not uninstall or
modify the independently installed `alva` binary.

## Maintainer check

Whenever the canonical Skill changes, refresh the packaged mirror and run:

```powershell
python tests/integrations/codex_plugin_test.py
```

The test fails if any canonical Skill file differs, or if manifest,
marketplace, and MCP wiring drift apart.

For installation and actual host/tool execution, build the compiler and run:

```powershell
cargo build --locked --manifest-path alva/Cargo.toml
python tests/integrations/codex_native_test.py alva/target/debug/alva.exe
```

On Linux use `alva/target/debug/alva`. `--codex /path/to/codex` selects a
particular CLI. This optional test uses a fresh temporary `CODEX_HOME`, installs
this marketplace/plugin, verifies the installed Skill bytes, and uses Codex's
app-server to discover and call the real ALVA MCP tools. It stages, checks and
commits an edit in a copied project, reopens the committed state, aborts another
edit, then independently checks/builds/tests the project. The existing server
and workflow are used without a replacement harness or editing implementation.
User-installed plugins/configuration and repository examples are not changed.

The fixture requires Codex's `mcpServer/tool/call` app-server API. CI pins
Codex `0.164.0`; the integration is also exercised locally with desktop CLI
`0.163.0-alpha.11.2`. It does not issue `turn/start` or call a model/provider,
so it establishes host/tool execution, not autonomous model task performance.
If a host lacks that app-server API, report the fixture as unsupported instead
of replacing it with a static configuration PASS.

The ALVA release binary and this source-distributed plugin have separate
versions. `v0.14.1-preview.2` contains the MCP server; it does not bundle this
marketplace. Keep the clone and the installed binary available to Codex. The
current official [MCP configuration guide](https://learn.chatgpt.com/docs/extend/mcp)
also documents standalone server configuration when a host has no plugin UI.

See [P0 acceptance](../../docs/codex-integration-p0.md) and the
[Python Guard MVP design](../../docs/python-guard-mvp.md) for the separate P1
proposal; the native plugin does not guard ordinary Python projects today.
