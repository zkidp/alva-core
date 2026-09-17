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
    "pointer.alva": "5e0232eab5e4b6fbb83a43b4ad5784bce6833d3f8f7e0789f2fe4140c3dfd9f2",
    "patch.alva": "cffb242f6a32f572094d60f1238c04355d728c55f968f9826d44aef5e60020b4",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
        actual = sha256(LIBRARY / name)
        if actual != expected:
            raise SystemExit(f"{name} hash changed: {actual} != {expected}")
        shutil.copy2(LIBRARY / name, vendor / name)
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
