#!/usr/bin/env python3
"""Generate the fixed first-pass JSON Patch runtime workloads."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any


TARGETS = {"1k": 1024, "32k": 32 * 1024, "256k": 256 * 1024, "near1m": 960 * 1024}


def encode(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def request_for(doc: Any, patch: list[dict[str, Any]] | None = None, pointer: str | None = None) -> dict[str, Any]:
    if pointer is not None:
        return {"mode": "pointer", "doc": doc, "pointer": pointer}
    assert patch is not None
    return {"mode": "patch", "doc": doc, "patch": patch}


def fit(label: str, data: Any, patch: list[dict[str, Any]] | None = None, pointer: str | None = None) -> dict[str, Any]:
    doc = {"data": data, "padding": ""}
    request = request_for(doc, patch, pointer)
    target = TARGETS[label]
    missing = target - len(encode(request))
    if missing > 0:
        doc["padding"] = "x" * missing
    return request


def add_success(cases: list[dict[str, Any]], name: str, request: dict[str, Any], expected: Any, shape: str) -> None:
    cases.append({"name": name, "request": request, "expected": expected, "expected_status": "success", "shape": shape})


def add_failure(cases: list[dict[str, Any]], name: str, request: dict[str, Any], shape: str) -> None:
    cases.append({"name": name, "request": request, "expected_status": "spec_rejection", "shape": shape})


def build_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []

    for size in ("1k", "32k", "256k", "near1m"):
        data = {"target": {"value": 7}, "other": [1, 2, 3]}
        req = fit(size, data, pointer="/data/target/value")
        add_success(cases, f"pointer-object-{size}", req, 7, f"pointer/{size}")

    wide = {f"k{i:04d}": i for i in range(512)}
    for size in ("32k", "256k"):
        req = fit(size, wide, patch=[{"op": "replace", "path": "/data/k0256", "value": -1}])
        expected = copy.deepcopy(req["doc"])
        expected["data"]["k0256"] = -1
        add_success(cases, f"wide-object-replace-{size}", req, expected, f"wide-object/{size}")

    for size, count in (("32k", 1024), ("256k", 8192)):
        for position, path in (("head", "/data/0"), ("tail", "/data/-")):
            values = list(range(count))
            req = fit(size, values, patch=[{"op": "add", "path": path, "value": -1}])
            expected = copy.deepcopy(req["doc"])
            if position == "head":
                expected["data"].insert(0, -1)
            else:
                expected["data"].append(-1)
            add_success(cases, f"array-{position}-insert-{size}", req, expected, f"array-{position}/{size}")

    nested: Any = {"leaf": 1}
    tokens = ["leaf"]
    for depth in range(12):
        key = f"d{depth}"
        nested = {key: nested}
        tokens.insert(0, key)
    deep_path = "/data/" + "/".join(tokens)
    for size in ("32k", "256k"):
        req = fit(size, nested, patch=[{"op": "replace", "path": deep_path, "value": 2}])
        expected = copy.deepcopy(req["doc"])
        cursor = expected["data"]
        for token in tokens[:-1]:
            cursor = cursor[token]
        cursor["leaf"] = 2
        add_success(cases, f"deep-replace-{size}", req, expected, f"deep/{size}")

    for size in ("32k", "256k"):
        data = {"source": {"items": list(range(64)), "tag": "copy"}, "destination": None}
        req = fit(size, data, patch=[{"op": "copy", "from": "/data/source", "path": "/data/destination"}])
        expected = copy.deepcopy(req["doc"])
        expected["data"]["destination"] = copy.deepcopy(expected["data"]["source"])
        add_success(cases, f"copy-subtree-{size}", req, expected, f"copy/{size}")

    recursive = {"left": [{"n": i, "ok": True} for i in range(64)], "right": {"value": "same"}}
    for size in ("32k", "256k"):
        req = fit(size, recursive, patch=[{"op": "test", "path": "/data", "value": recursive}])
        add_success(cases, f"recursive-test-{size}", req, copy.deepcopy(req["doc"]), f"recursive-test/{size}")

    for size, operations in (("32k", 16), ("256k", 64)):
        data = {f"v{i}": i for i in range(operations)}
        patch = [{"op": "replace", "path": f"/data/v{i}", "value": -i} for i in range(operations)]
        req = fit(size, data, patch=patch)
        expected = copy.deepcopy(req["doc"])
        for i in range(operations):
            expected["data"][f"v{i}"] = -i
        add_success(cases, f"operation-sequence-{operations}-{size}", req, expected, f"sequence/{size}")

    first_fail = fit("32k", {"present": 1}, patch=[{"op": "remove", "path": "/data/missing"}])
    add_failure(cases, "first-operation-failure-32k", first_fail, "failure-first/32k")

    late_patch = [{"op": "add", "path": f"/data/v{i}", "value": i} for i in range(15)]
    late_patch.append({"op": "remove", "path": "/data/missing"})
    late_fail = fit("32k", {}, patch=late_patch)
    add_failure(cases, "late-operation-failure-32k", late_fail, "failure-late/32k")

    move_req = fit(
        "32k",
        {"source": {"value": 1}, "destination": None},
        patch=[{"op": "move", "from": "/data/source", "path": "/data/destination"}],
    )
    move_expected = copy.deepcopy(move_req["doc"])
    moved = move_expected["data"].pop("source")
    move_expected["data"]["destination"] = moved
    add_success(cases, "move-object-32k", move_req, move_expected, "move/32k")

    assert len(cases) == 21
    return cases


def write_case(output: Path, case: dict[str, Any]) -> dict[str, Any]:
    request_bytes = encode(case["request"])
    request_path = output / f"{case['name']}.request.json"
    request_path.write_bytes(request_bytes)
    record = {
        "name": case["name"],
        "shape": case["shape"],
        "request": request_path.name,
        "request_bytes": len(request_bytes),
        "request_sha256": hashlib.sha256(request_bytes).hexdigest(),
        "expected_status": case["expected_status"],
        "direct_performance_eligible": True,
    }
    if case["expected_status"] == "success":
        expected_bytes = encode(case["expected"])
        expected_path = output / f"{case['name']}.expected.json"
        expected_path.write_bytes(expected_bytes)
        record.update(
            expected=expected_path.name,
            expected_bytes=len(expected_bytes),
            expected_sha256=hashlib.sha256(expected_bytes).hexdigest(),
        )
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    records = [write_case(args.output, case) for case in build_cases()]
    compatibility = [
        {
            "name": "numeric-equivalent-1-vs-1.0",
            "request_utf8": '{"mode":"patch","doc":{"n":1},"patch":[{"op":"test","path":"/n","value":1.0}]}',
            "alva_expected": "success",
            "reason": "reference JSON-number equality may use different representation semantics",
        },
        {
            "name": "numeric-distinct-above-2p53",
            "request_utf8": '{"mode":"patch","doc":{"n":9007199254740993.0},"patch":[{"op":"test","path":"/n","value":9007199254740992.0}]}',
            "alva_expected": "spec_rejection",
            "reason": "separate exact-decimal compatibility check",
        },
    ]
    manifest = {
        "schema": 1,
        "generator": "benchmarks/json_patch/generate_workloads.py",
        "engineering_constructed": True,
        "workload_count": len(records),
        "workloads": records,
        "compatibility_cases": compatibility,
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": "PASS", "workloads": len(records), "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
