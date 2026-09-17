#!/usr/bin/env python3
"""Prepare a clean, hash-bound source consumer for the reusable ALVA modules."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LIBRARY = ROOT / "examples" / "json_patch_component" / "src"
APP = Path(__file__).resolve().parent / "src" / "main.alva"
PINNED = {
    "pointer.alva": "af7bd0a723be59b01159f07718a964a31d9bf2acd06c21bd8ea09052d4abd852",
    "patch.alva": "7e265b87aa90ae3a6d6453b440deb7f80b7dcbb8fc8b61d4a453a1f174047038",
}


def normalized_source(path: Path) -> bytes:
    """Bind textual module content independent of Git CRLF materialization."""
    return path.read_bytes().replace(b"\r\n", b"\n")


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    vendor = args.output / "vendor" / "json_patch"
    source = args.output / "src"
    vendor.mkdir(parents=True)
    source.mkdir()
    for name, expected in PINNED.items():
        content = normalized_source(LIBRARY / name)
        actual = sha256(content)
        if actual != expected:
            raise SystemExit(f"{name} hash changed: {actual} != {expected}")
        (vendor / name).write_bytes(content)
    shutil.copy2(APP, source / "main.alva")
    (args.output / "alva.toml").write_text(
        """[project]\nname = \"json_patch_consumer\"\n\n[modules]\n\"json_patch.pointer\" = \"vendor/json_patch/pointer.alva\"\n\"json_patch.patch\" = \"vendor/json_patch/patch.alva\"\n\"consumer.main\" = \"src/main.alva\"\n""",
        encoding="utf-8",
    )
    (args.output / "SOURCE-BINDING.json").write_text(
        json.dumps({"component_commit": "166c41337556be7d3167aeef1a41047ede55bf0c", "sha256": PINNED}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "PASS", "output": str(args.output), "modules": PINNED}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
