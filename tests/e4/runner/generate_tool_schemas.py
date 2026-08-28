#!/usr/bin/env python3
"""Generate the four deterministic E4 tool surfaces from E3 definitions."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
E3_SCHEMAS = HERE.parents[1] / "e3" / "runner" / "tool-schemas"
OUT = HERE / "tool-schemas"

TEXT_NAMES = (
    "read_file", "list_files", "write_file", "apply_patch", "check_project",
)
CONTROL_NAMES = (
    "resolve_entity", "inspect_project", "inspect_module", "inspect_function",
    "inspect_entity", "inspect_body", "inspect_test", "inspect_change_impact",
    "inspect_schema_gaps", "preview_semantic_diff",
)
LIFECYCLE_NAMES = (
    "begin_patch_session", "commit_patch", "discard_patch",
)
AFFORDANCE_NAMES = (
    "applicable_operations", "describe_operation", "migrate_signature",
    "rename_entity", "set_effect",
)


def _function(name: str, description: str, properties: dict, required=()):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": list(required),
                "additionalProperties": False,
            },
        },
    }


def _text_definitions():
    path = {"path": {"type": "string", "description": "pre-registered src/**/*.alva path"}}
    return {
        "read_file": _function("read_file", "Read one pre-registered ALVA source file.", path, ("path",)),
        "list_files": _function("list_files", "List only pre-registered ALVA source files.", path),
        "write_file": _function(
            "write_file", "Atomically replace one pre-registered ALVA source file.",
            {**path, "content": {"type": "string", "description": "complete UTF-8 file content"}},
            ("path", "content"),
        ),
        "apply_patch": _function(
            "apply_patch", "Atomically apply a strict unified diff to pre-registered source files.",
            {"diff": {"type": "string", "description": "unified diff with a/ and b/ paths"}},
            ("diff",),
        ),
        "check_project": _function(
            "check_project", "Import the current text and run ALVA compiler/type/effect checks.", {},
        ),
        "begin_patch_session": _function(
            "begin_patch_session", "Begin a rollback-capable text and semantic patch session.", {},
        ),
        "commit_patch": _function(
            "commit_patch", "Check and commit the current patch session.", {},
        ),
        "discard_patch": _function(
            "discard_patch", "Discard the session and restore its original text state.", {},
        ),
    }


def _load_e3():
    high = json.loads((E3_SCHEMAS / "TOOLS-HIGH.json").read_text(encoding="utf-8"))["tools"]
    by_name = {item["function"]["name"]: item for item in high}
    if len(by_name) != 42:
        raise RuntimeError("E3 HIGH surface is not the frozen 42-tool surface")
    return high, by_name


def build_surfaces():
    high, e3 = _load_e3()
    text = _text_definitions()

    def choose(names):
        return [text[name] if name in text else e3[name] for name in names]

    surfaces = {
        "TEXT": choose(TEXT_NAMES),
        "TEXT_VERIFY": choose(TEXT_NAMES + CONTROL_NAMES + LIFECYCLE_NAMES),
        "HYBRID": choose(TEXT_NAMES + CONTROL_NAMES + LIFECYCLE_NAMES + AFFORDANCE_NAMES),
        "FULL_ALVA": high,
    }
    expected = {"TEXT": 5, "TEXT_VERIFY": 18, "HYBRID": 23, "FULL_ALVA": 42}
    for arm, tools in surfaces.items():
        names = [tool["function"]["name"] for tool in tools]
        if len(names) != expected[arm] or len(names) != len(set(names)):
            raise RuntimeError(f"{arm} surface count/uniqueness failure")
    return surfaces


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {"schema_version": "e4-interface-architecture-v1", "arms": {}}
    for arm, tools in build_surfaces().items():
        payload = (json.dumps({"arm": arm, "tools": tools}, indent=2, ensure_ascii=False) + "\n").encode()
        path = OUT / f"TOOLS-{arm}.json"
        path.write_bytes(payload)
        manifest["arms"][arm] = {
            "file": path.name,
            "tool_count": len(tools),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "tool_names": [tool["function"]["name"] for tool in tools],
        }
    (OUT / "SCHEMA-MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    main()
