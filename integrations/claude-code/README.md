# ALVA for Claude Code

This directory packages the canonical ALVA Skill and shared `alva mcp` server
for Claude Code. It is a thin host integration: it does not define another ALVA
workflow, compiler, or MCP operation surface.

## Prerequisite

Install ALVA Developer Preview `v0.14.1-preview.2` or later and make sure
`alva` is available on `PATH`:

```bash
alva --version
alva doctor
```

## Install from a clone

From the repository root:

```bash
claude plugin marketplace add ./integrations/claude-code
claude plugin install alva@alva
```

Claude Code copies the plugin into its cache. The packaged Skill is an exact
mirror of `integrations/skills/alva`, and the plugin's `.mcp.json` starts the
independently installed `alva mcp` server. A host MCP permission prompt is an
expected trust decision; it is not workflow coaching.

Restart Claude Code or run `/reload-plugins` after installation if requested.
The Skill is available as `/alva:alva` and may also be selected automatically
for ALVA project work.

## Remove

```bash
claude plugin uninstall alva@alva
claude plugin marketplace remove alva
```

Removing the plugin does not remove or modify the independently installed ALVA
binary.

## Maintainer validation

From the repository root:

```bash
claude plugin validate --strict integrations/claude-code
claude plugin validate --strict integrations/claude-code/plugins/alva
python tests/integrations/claude_code_plugin_test.py
```

The repository fixture fails if the packaged Skill drifts from the canonical
copy or if the manifest, marketplace, or MCP wiring changes unexpectedly.
