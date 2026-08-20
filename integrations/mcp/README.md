# ALVA MCP server

`alva mcp` starts the shared ALVA semantic server over STDIO. The client launches
the process, sends one UTF-8 JSON-RPC message per line on stdin, and receives
only MCP JSON-RPC messages on stdout. Diagnostics and process logs use stderr.

The server supports both protocol eras:

- 2025 clients use `initialize`, `notifications/initialized`, `tools/list`, and
  `tools/call`;
- 2026-07-28 clients may probe with `server/discover` and attach the required
  `io.modelcontextprotocol/*` metadata to every request without an initialize
  handshake.

The transport connection is not program authority. Call `begin_transaction`
with an `alva.toml` path, then pass the returned `transaction_id` to every later
tool. Finish with `commit_transaction` or `abort_transaction`. EOF discards an
uncommitted transaction.

## Claude Code

```bash
claude mcp add --transport stdio alva -- alva mcp
```

Claude Code supplies `CLAUDE_PROJECT_DIR` to local servers. A relative manifest
path is resolved against that directory when it is available.

## Other MCP hosts

Configure a local STDIO server with command `alva` and arguments `["mcp"]`.
Use the canonical [ALVA Skill](../skills/alva/SKILL.md) so the agent follows the
resolve, inspect, discover, stage, diff, check, and commit workflow rather than
falling back to broad source-text patches.

## v1 surface

The initial surface intentionally exposes a compact workflow:

`begin_transaction`, `resolve_entity`, `applicable_operations`,
`describe_operation`, `inspect_project`, `inspect_entity`, `inspect_body`,
`describe_construction`, `construct_expression`, `change_field`,
`preview_semantic_diff`, `check_transaction`, `commit_transaction`, and
`abort_transaction`.

Tool schemas are generated from the typed AEP operation registry. Experimental
A1 operations remain hidden unless their existing feature gate is explicitly
enabled. Results include both `structuredContent` and the same serialized JSON
in a text content block for older clients.
