#!/usr/bin/env python3
"""Static acceptance checks for the thin ALVA Claude Code plugin package."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CANONICAL_SKILL = ROOT / "integrations" / "skills" / "alva"
MARKETPLACE_ROOT = ROOT / "integrations" / "claude-code"
PLUGIN = MARKETPLACE_ROOT / "plugins" / "alva"
PACKAGED_SKILL = PLUGIN / "skills" / "alva"


def relative_files(root: Path) -> dict[Path, bytes]:
    # Git may materialize text files with CRLF on Windows. Compare the exact
    # repository content after reversing only that checkout conversion.
    return {
        path.relative_to(root): path.read_bytes().replace(b"\r\n", b"\n")
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def main() -> None:
    canonical = relative_files(CANONICAL_SKILL)
    packaged = relative_files(PACKAGED_SKILL)
    assert canonical == packaged, "packaged Skill differs from integrations/skills/alva"

    manifest = json.loads(
        (PLUGIN / ".claude-plugin" / "plugin.json").read_text("utf-8")
    )
    assert manifest["name"] == "alva"
    assert manifest["version"] == "0.1.0"
    assert "skills" not in manifest
    assert "mcpServers" not in manifest
    assert not (PLUGIN / "CLAUDE.md").exists()

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
        (MARKETPLACE_ROOT / ".claude-plugin" / "marketplace.json").read_text("utf-8")
    )
    assert marketplace["name"] == "alva"
    entries = marketplace["plugins"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["name"] == manifest["name"]
    assert entry["source"] == "./plugins/alva"
    assert "version" not in entry

    print(
        "PASS: Claude Code plugin manifest, MCP wiring, marketplace, "
        "and canonical Skill mirror"
    )


if __name__ == "__main__":
    main()
