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
