#!/usr/bin/env python3
"""Build the release CLI and run pinned external plus local conformance cases."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ALVA_DIR = ROOT / "alva"
PROJECT = ROOT / "examples" / "json_patch_component" / "alva.toml"
UPSTREAM = Path(__file__).resolve().parent / "upstream"
EXE_SUFFIX = ".exe" if os.name == "nt" else ""


def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    if kwargs.get("check") and completed.returncode != 0:
        sys.stderr.write(completed.stdout.decode("utf-8", errors="replace"))
        sys.stderr.write(completed.stderr.decode("utf-8", errors="replace"))
        completed.check_returncode()
    return completed


def semantic_json(data: bytes | str) -> Any:
    return json.loads(data, parse_float=Decimal, parse_int=int)


def invoke(executable: Path, payload: bytes) -> subprocess.CompletedProcess[bytes]:
    try:
        return run([str(executable)], input=payload, timeout=10, check=False)
    except subprocess.TimeoutExpired as exc:
        raise AssertionError("infrastructure failure: component timed out") from exc


def assert_success(executable: Path, payload: bytes, expected: Any, label: str) -> None:
    completed = invoke(executable, payload)
    assert completed.returncode == 0, (
        f"{label}: expected success, exit={completed.returncode}, "
        f"stderr={completed.stderr.decode(errors='replace')!r}"
    )
    assert completed.stderr == b"", f"{label}: success wrote stderr"
    assert completed.stdout, f"{label}: success returned empty stdout"
    actual = semantic_json(completed.stdout)
    expected_semantic = semantic_json(json.dumps(expected, separators=(",", ":")))
    assert actual == expected_semantic, f"{label}: {actual!r} != {expected_semantic!r}"


def assert_rejection(
    executable: Path,
    payload: bytes,
    label: str,
    markers: tuple[str, ...] = ("json.patch:", "json.pointer:"),
) -> None:
    completed = invoke(executable, payload)
    assert completed.returncode != 0, f"{label}: expected rejection"
    assert completed.stdout == b"", f"{label}: rejection leaked stdout"
    stderr = completed.stderr.decode("utf-8", errors="replace")
    assert "panicked at" not in stderr, f"{label}: implementation panic is not a valid rejection"
    assert any(marker in stderr for marker in markers), (
        f"{label}: unclassified process failure: {stderr!r}"
    )


def request(mode: str, doc: Any, **fields: Any) -> bytes:
    value = {"mode": mode, "doc": doc, **fields}
    return json.dumps(value, separators=(",", ":")).encode("utf-8")


def main() -> int:
    run(["cargo", "build"], cwd=ALVA_DIR, check=True)
    compiler = ALVA_DIR / "target" / "debug" / f"alva{EXE_SUFFIX}"
    assert compiler.exists()

    with tempfile.TemporaryDirectory(prefix="alva-json-patch-") as temp_text:
        temp = Path(temp_text)
        generated = temp / "generated"
        run(
            [str(compiler), "project", "build", str(PROJECT), "--out-dir", str(generated)],
            cwd=ROOT,
            check=True,
        )
        crate = generated / "json_patch_component"
        run(
            ["cargo", "build", "--manifest-path", str(crate / "Cargo.toml"), "--release"],
            check=True,
        )
        executable = crate / "target" / "release" / f"json_patch_component{EXE_SUFFIX}"
        assert executable.exists()

        totals = {
            "upstream_enabled": 0,
            "upstream_expected_success": 0,
            "upstream_expected_rejection": 0,
            "upstream_disabled": 0,
            "local_success": 0,
            "local_rejection": 0,
        }
        per_file: dict[str, dict[str, int]] = {}
        for source in ("tests.json", "spec_tests.json"):
            records = json.loads((UPSTREAM / source).read_text(encoding="utf-8"))
            file_counts = {"records": len(records), "enabled": 0, "disabled": 0}
            for ordinal, case in enumerate(records, start=1):
                label = f"{source}#{ordinal}: {case.get('comment', '')}"
                if case.get("disabled") is True:
                    totals["upstream_disabled"] += 1
                    file_counts["disabled"] += 1
                    continue
                assert "doc" in case and "patch" in case, f"{label}: non-runnable active record"
                payload = request("patch", case["doc"], patch=case["patch"])
                totals["upstream_enabled"] += 1
                file_counts["enabled"] += 1
                if "expected" in case:
                    assert_success(executable, payload, case["expected"], label)
                    totals["upstream_expected_success"] += 1
                elif "error" in case:
                    assert_rejection(executable, payload, label)
                    totals["upstream_expected_rejection"] += 1
                else:
                    raise AssertionError(f"{label}: enabled record has no expected outcome")
            per_file[source] = file_counts

        pointer_success = [
            ({"foo": ["bar", "baz"]}, "", {"foo": ["bar", "baz"]}),
            ({"": 0}, "/", 0),
            ({"a/b": 1}, "/a~1b", 1),
            ({"m~n": 2}, "/m~0n", 2),
            ({"~1": 3}, "/~01", 3),
            (["zero", "one"], "/1", "one"),
        ]
        for ordinal, (doc, pointer, expected) in enumerate(pointer_success, start=1):
            assert_success(
                executable,
                request("pointer", doc, pointer=pointer),
                expected,
                f"local pointer success #{ordinal}",
            )
            totals["local_success"] += 1

        pointer_rejections = [
            ({}, "not/a/pointer"),
            ({"a": 1}, "/a~"),
            ({"a": 1}, "/a~2"),
            ([0, 1], "/01"),
            ([0, 1], "/-"),
            ({"a": 1}, "/missing"),
        ]
        for ordinal, (doc, pointer) in enumerate(pointer_rejections, start=1):
            assert_rejection(
                executable,
                request("pointer", doc, pointer=pointer),
                f"local pointer rejection #{ordinal}",
            )
            totals["local_rejection"] += 1

        numeric_payloads = [
            (b'{"mode":"patch","doc":{"n":1},"patch":[{"op":"test","path":"/n","value":1.0}]}', {"n": 1}),
            (b'{"mode":"patch","doc":{"n":9007199254740993},"patch":[{"op":"test","path":"/n","value":9007199254740993.0}]}', {"n": 9007199254740993}),
            (b'{"mode":"patch","doc":{"n":1e2},"patch":[{"op":"test","path":"/n","value":100}]}', {"n": 100}),
        ]
        for ordinal, (payload, expected) in enumerate(numeric_payloads, start=1):
            assert_success(executable, payload, expected, f"numeric equality #{ordinal}")
            totals["local_success"] += 1

        assert_rejection(
            executable,
            b'{"mode":"patch","doc":{"n":9007199254740993},"patch":[{"op":"test","path":"/n","value":9007199254740992.0}]}',
            "large unequal numbers",
        )
        totals["local_rejection"] += 1

        assert_rejection(
            executable,
            request(
                "patch",
                {"a": 1},
                patch=[
                    {"op": "add", "path": "/b", "value": 2},
                    {"op": "remove", "path": "/missing"},
                ],
            ),
            "multi-operation failure emits no partial document",
        )
        totals["local_rejection"] += 1

        malformed_requests = [
            (b"not-json", "invalid JSON", ("json.patch:",)),
            (b'{"mode":"patch","patch":[]}', "missing document", ("json.patch:",)),
            (b'{"mode":1,"doc":{},"patch":[]}', "wrong mode type", ("json.patch:",)),
            (b'{"mode":"patch","doc":{},"patch":{}}', "patch is not an array", ("json.patch:",)),
            (b"\xff", "invalid UTF-8", ("io.read-stdin:",)),
            (b" " * (1024 * 1024 + 1), "input exceeds 1 MiB", ("io.read-stdin:",)),
        ]
        for payload, label, markers in malformed_requests:
            assert_rejection(executable, payload, label, markers)
            totals["local_rejection"] += 1

        print(
            json.dumps(
                {
                    "status": "PASS",
                    "platform": sys.platform,
                    "executable": str(executable),
                    "per_file": per_file,
                    "totals": totals,
                },
                indent=2,
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
