#!/usr/bin/env python3
"""Static acceptance checks for the thin ALVA Codex plugin package."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CANONICAL_SKILL = ROOT / "integrations" / "skills" / "alva"
MARKETPLACE_ROOT = ROOT / "integrations" / "codex"
PLUGIN = MARKETPLACE_ROOT / "plugins" / "alva"
PACKAGED_SKILL = PLUGIN / "skills" / "alva"


def relative_files(root: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(root): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def main() -> None:
    canonical = relative_files(CANONICAL_SKILL)
    packaged = relative_files(PACKAGED_SKILL)
    assert canonical == packaged, "packaged Skill differs from integrations/skills/alva"

    manifest = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text("utf-8"))
    assert manifest["name"] == "alva"
    assert manifest["skills"] == "./skills/"
    assert manifest["mcpServers"] == "./.mcp.json"
    assert manifest["interface"]["displayName"] == "ALVA"

    mcp = json.loads((PLUGIN / ".mcp.json").read_text("utf-8"))
    assert mcp == {
        "mcpServers": {
            "alva": {
                "command": "alva",
                "args": ["mcp"],
            }
        }
    }

    marketplace = json.loads(
        (MARKETPLACE_ROOT / ".agents" / "plugins" / "marketplace.json").read_text("utf-8")
    )
    assert marketplace["name"] == "alva"
    entries = marketplace["plugins"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["name"] == manifest["name"]
    assert entry["source"] == {"source": "local", "path": "./plugins/alva"}
    assert entry["policy"] == {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL",
    }
    assert entry["category"] == "Developer Tools"

    print("PASS: Codex plugin manifest, MCP wiring, marketplace, and canonical Skill mirror")


if __name__ == "__main__":
    main()
