#!/usr/bin/env python3
"""Build the release CLI and run pinned external plus local conformance cases."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from decimal import Decimal
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ALVA_DIR = ROOT / "alva"
PROJECT = ROOT / "examples" / "json_patch_component" / "alva.toml"
UPSTREAM = Path(__file__).resolve().parent / "upstream"
EXE_SUFFIX = ".exe" if os.name == "nt" else ""
CALLER = ROOT / "examples" / "json_patch_component" / "call_component.py"


def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    if kwargs.get("check") and completed.returncode != 0:
        sys.stderr.write(completed.stdout.decode("utf-8", errors="replace"))
        sys.stderr.write(completed.stderr.decode("utf-8", errors="replace"))
        completed.check_returncode()
    return completed


def reject_non_json_constant(text: str) -> None:
    raise ValueError(f"non-JSON numeric constant: {text}")


def semantic_json(data: bytes | str) -> Any:
    return json.loads(
        data,
        parse_float=Decimal,
        parse_int=Decimal,
        parse_constant=reject_non_json_constant,
    )


def encode_json(value: Any) -> bytes:
    """Encode JSON without converting Decimal values through binary float."""
    if value is None:
        return b"null"
    if type(value) is bool:
        return b"true" if value else b"false"
    if type(value) is int:
        return str(value).encode("ascii")
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("non-finite Decimal is not JSON")
        return str(value).encode("ascii")
    if type(value) is str:
        return json.dumps(value, ensure_ascii=False).encode("utf-8")
    if type(value) is list:
        return b"[" + b",".join(encode_json(item) for item in value) + b"]"
    if type(value) is dict:
        parts = []
        for key, item in value.items():
            if type(key) is not str:
                raise TypeError("JSON object keys must be strings")
            parts.append(encode_json(key) + b":" + encode_json(item))
        return b"{" + b",".join(parts) + b"}"
    raise TypeError(f"unsupported JSON value type: {type(value).__name__}")


def json_semantically_equal(left: Any, right: Any) -> bool:
    """Compare JSON values with explicit JSON types and exact numeric equality."""
    if left is None or right is None:
        return left is None and right is None
    if type(left) is bool or type(right) is bool:
        return type(left) is bool and type(right) is bool and left is right
    if isinstance(left, (int, Decimal)) and not isinstance(left, bool):
        return (
            isinstance(right, (int, Decimal))
            and not isinstance(right, bool)
            and Decimal(left) == Decimal(right)
        )
    if type(left) is str or type(right) is str:
        return type(left) is str and type(right) is str and left == right
    if type(left) is list or type(right) is list:
        return (
            type(left) is list
            and type(right) is list
            and len(left) == len(right)
            and all(json_semantically_equal(a, b) for a, b in zip(left, right))
        )
    if type(left) is dict or type(right) is dict:
        return (
            type(left) is dict
            and type(right) is dict
            and left.keys() == right.keys()
            and all(json_semantically_equal(left[key], right[key]) for key in left)
        )
    return False


def assert_comparator_regressions() -> None:
    assert not json_semantically_equal(True, Decimal(1))
    assert not json_semantically_equal(False, Decimal(0))
    assert json_semantically_equal(Decimal(1), Decimal("1.0"))
    assert json_semantically_equal(
        {"outer": {"a": Decimal(1), "b": True}},
        {"outer": {"b": True, "a": Decimal("1.0")}},
    )
    assert json_semantically_equal(
        [Decimal(1), [False, {"n": Decimal("2.0")}]],
        [Decimal("1.0"), [False, {"n": Decimal(2)}]],
    )
    assert not json_semantically_equal([Decimal(1), Decimal(2)], [Decimal(2), Decimal(1)])
    try:
        assert_json_equal({"value": True}, {"value": Decimal(1)}, "wrong JSON type")
    except AssertionError:
        pass
    else:
        raise AssertionError("comparator accepted an intentionally wrong JSON type")


def assert_json_equal(actual: Any, expected: Any, label: str) -> None:
    assert json_semantically_equal(actual, expected), f"{label}: {actual!r} != {expected!r}"


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
    assert_json_equal(actual, expected, label)


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
    return encode_json(value)


def load_caller_module() -> Any:
    spec = spec_from_file_location("alva_json_patch_caller", CALLER)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    assert_comparator_regressions()
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
            records = semantic_json((UPSTREAM / source).read_bytes())
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

        caller = load_caller_module()
        unequal_request = (
            b'{"mode":"patch","doc":{"n":9007199254740993.0},'
            b'"patch":[{"op":"test","path":"/n","value":9007199254740992.0}]}'
        )
        unequal_file = temp / "unequal-numbers.json"
        unequal_file.write_bytes(unequal_request)
        try:
            caller.call_component_file(executable, unequal_file)
        except RuntimeError as exc:
            message = str(exc)
            assert "json.patch:" in message
            assert "panicked at" not in message
            assert "timed out" not in message
        else:
            raise AssertionError("file caller accepted two distinct large decimal values")
        assert unequal_file.read_bytes() == unequal_request
        unequal_caller_process = run(
            [sys.executable, str(CALLER), str(executable), str(unequal_file)],
            timeout=10,
            check=False,
        )
        assert unequal_caller_process.returncode != 0
        assert unequal_caller_process.stdout == b""
        unequal_stderr = unequal_caller_process.stderr.decode(errors="replace")
        assert "json.patch:" in unequal_stderr
        assert "panicked at" not in unequal_stderr
        assert "timed out" not in unequal_stderr
        totals["local_rejection"] += 1

        equal_request = (
            b'{"mode":"patch","doc":{"n":9007199254740993.0},'
            b'"patch":[{"op":"test","path":"/n","value":9007199254740993}]}'
        )
        equal_file = temp / "equal-numbers.json"
        equal_file.write_bytes(equal_request)
        equal_response = caller.call_component_file(executable, equal_file)
        assert equal_file.read_bytes() == equal_request
        assert b"9007199254740993.0" in equal_response
        assert_json_equal(
            semantic_json(equal_response),
            {"n": Decimal("9007199254740993.0")},
            "file caller exact equal-number response",
        )
        totals["local_success"] += 1

        caller_process = run(
            [sys.executable, str(CALLER), str(executable), str(equal_file)],
            timeout=10,
            check=False,
        )
        assert caller_process.returncode == 0, caller_process.stderr.decode(errors="replace")
        assert caller_process.stderr == b""
        assert caller_process.stdout == equal_response
        totals["local_success"] += 1

        try:
            caller.call_component(executable, {"mode": "pointer", "doc": 1.0, "pointer": ""})
        except TypeError as exc:
            assert "Python float is not accepted" in str(exc)
        else:
            raise AssertionError("object caller silently accepted a Python float")

        print(
            json.dumps(
                {
                    "status": "PASS",
                    "platform": sys.platform,
                    "comparator_regressions": 7,
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
