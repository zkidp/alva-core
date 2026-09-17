#!/usr/bin/env python3
"""Exercise a supplied ALVA release binary from a clean consumer directory."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CALLER_SOURCE = ROOT / "examples" / "json_patch_component" / "call_component.py"


def load_caller(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("portable_json_patch_caller", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parsed(data: bytes) -> Any:
    return json.loads(data, parse_int=Decimal, parse_float=Decimal)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    args = parser.parse_args()
    source_binary = args.binary.resolve()
    assert source_binary.is_file()

    with tempfile.TemporaryDirectory(prefix="alva-json-consumer-") as temp_text:
        consumer = Path(temp_text)
        binary = consumer / "bin" / "json_patch_component"
        binary.parent.mkdir()
        shutil.copy2(source_binary, binary)
        binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
        caller_path = consumer / "call_component.py"
        shutil.copy2(CALLER_SOURCE, caller_path)
        (consumer / "INTERFACE.txt").write_text(
            "one UTF-8 JSON request on stdin; one JSON result on zero exit; reject all nonzero exits\n",
            encoding="utf-8",
        )
        requests = consumer / "requests"
        requests.mkdir()
        caller = load_caller(caller_path)

        patch_file = requests / "patch.json"
        patch_file.write_bytes(
            b'{"mode":"patch","doc":{"items":[1,2]},"patch":[{"op":"add","path":"/items/1","value":9}]}'
        )
        pointer_file = requests / "pointer.json"
        pointer_file.write_bytes(
            b'{"mode":"pointer","doc":{"a/b":{"m~n":7}},"pointer":"/a~1b/m~0n"}'
        )
        exact_file = requests / "exact.json"
        exact_file.write_bytes(
            b'{"mode":"patch","doc":{"n":9007199254740993.0},"patch":[{"op":"test","path":"/n","value":9007199254740993}]}'
        )
        reject_file = requests / "reject.json"
        reject_file.write_bytes(
            b'{"mode":"patch","doc":{"a":1},"patch":[{"op":"remove","path":"/missing"}]}'
        )

        different_cwd = consumer / "work" / "nested"
        different_cwd.mkdir(parents=True)
        previous = Path.cwd()
        os.chdir(different_cwd)
        try:
            assert parsed(caller.call_component_file(binary, patch_file)) == {"items": [1, 9, 2]}
            assert parsed(caller.call_component_file(binary, pointer_file)) == Decimal(7)
            exact = caller.call_component_file(binary, exact_file)
            assert b"9007199254740993.0" in exact
            try:
                caller.call_component_file(binary, reject_file)
            except RuntimeError as exc:
                assert "json.patch:" in str(exc)
            else:
                raise AssertionError("expected patch rejection was accepted")
        finally:
            os.chdir(previous)

        nonzero = consumer / "nonzero.py"
        nonzero.write_text("#!/usr/bin/env python3\nraise SystemExit(3)\n", encoding="utf-8")
        invalid = consumer / "invalid.py"
        invalid.write_text("#!/usr/bin/env python3\nprint('{')\n", encoding="utf-8")
        sleeper = consumer / "sleeper.py"
        sleeper.write_text("#!/usr/bin/env python3\nimport time\ntime.sleep(2)\n", encoding="utf-8")
        for helper in (nonzero, invalid, sleeper):
            helper.chmod(helper.stat().st_mode | stat.S_IXUSR)
        for helper, timeout in ((nonzero, 1.0), (invalid, 1.0), (sleeper, 0.05)):
            try:
                caller.call_component_file(helper, patch_file, timeout=timeout)
            except (RuntimeError, subprocess.TimeoutExpired):
                pass
            else:
                raise AssertionError(f"caller accepted failure from {helper.name}")

        print(
            json.dumps(
                {
                    "status": "PASS",
                    "actual_alva_cases": 4,
                    "caller_failure_cases": 3,
                    "consumer_root": str(consumer),
                    "source_binary": str(source_binary),
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
