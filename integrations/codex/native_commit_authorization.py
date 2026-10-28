"""Prospective, host-owned per-server/tool authorization; no Core API changes.

Only a trusted host may choose the server/allowed operation list and transport.
Do not let an agent write this configuration. This is not a sandbox: the server
must already terminate in the approved Linux P22/P23 isolation boundary.
"""
import json
import re


def scoped_server(command, args, *, enabled_tools):
    if not isinstance(command, str) or not command or not isinstance(args, list) or not all(isinstance(a, str) for a in args):
        raise ValueError("Explicit trusted transport required")
    names = list(enabled_tools)
    if not names or len(set(names)) != len(names) or any(not isinstance(n, str) or not re.fullmatch(r"[a-z_]+", n) for n in names):
        raise ValueError("Explicit unique tool allowlist required")
    if "commit_transaction" not in names:
        raise ValueError("This helper authorizes exactly the commit tool")
    return {"command": command, "args": list(args), "required": True, "tool_timeout_sec": 120,
            "enabled_tools": names, "default_tools_approval_mode": "auto",
            "tools": {"commit_transaction": {"approval_mode": "approve"}}}


def toml_value(value):
    """Render only JSON scalars/lists plus explicit TOML inline tables."""
    if isinstance(value, dict):
        return "{" + ",".join(json.dumps(k, ensure_ascii=False) + "=" + toml_value(v) for k, v in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ",".join(toml_value(v) for v in value) + "]"
    if isinstance(value, (str, int, float, bool)):
        return json.dumps(value, ensure_ascii=False)
    raise ValueError("Unsupported config value")


def server_override(server):
    """Single named server only; global approval/sandbox policy is untouched."""
    return "mcp_servers=" + toml_value({"alva": server})


def host_options(server):
    """Opt-in prospective Host options, fail closed on widened policy/config.

The caller must still create a fresh read-only AppServer thread and use an
isolated CODEX_HOME. No user config or installed plugin is modified here.
"""
    if server != scoped_server(server.get("command"), server.get("args"), enabled_tools=server.get("enabled_tools", [])):
        raise ValueError("Only the exact scoped authorization policy is supported")
    values = {"approval_policy": "never", "sandbox_mode": "read-only",
              "features.plugins": False, "features.apps": False, "features.shell_tool": False,
              "features.view_image": False, "features.image_generation": False, "agents.enabled": False,
              "web_search": "disabled", "windows.sandbox": "unelevated"}
    args = ["--strict-config"]
    for name, value in values.items():
        args += ["-c", name + "=" + toml_value(value)]
    return args + ["-c", server_override(server)]
