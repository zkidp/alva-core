#!/usr/bin/env python3
"""Sequential Linux process-boundary benchmark for ALVA and fixed Rust reference."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import resource
import selectors
import signal
import subprocess
import tempfile
import time
from decimal import Decimal
from pathlib import Path
from typing import Any


TIMEOUT_SECONDS = 10.0
MEMORY_BYTES = 512 * 1024 * 1024
OUTPUT_BYTES = 16 * 1024 * 1024
WARMUPS = 3
MEASUREMENTS = 30


def parse_json(data: bytes) -> Any:
    return json.loads(data, parse_int=Decimal, parse_float=Decimal)


def equal_json(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return left is None and right is None
    if type(left) is bool or type(right) is bool:
        return type(left) is bool and type(right) is bool and left is right
    if isinstance(left, Decimal) or isinstance(right, Decimal):
        return isinstance(left, Decimal) and isinstance(right, Decimal) and left == right
    if type(left) is str or type(right) is str:
        return type(left) is str and type(right) is str and left == right
    if type(left) is list or type(right) is list:
        return type(left) is list and type(right) is list and len(left) == len(right) and all(
            equal_json(a, b) for a, b in zip(left, right)
        )
    if type(left) is dict or type(right) is dict:
        return type(left) is dict and type(right) is dict and left.keys() == right.keys() and all(
            equal_json(left[key], right[key]) for key in left
        )
    return False


def child_limits() -> None:
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY_BYTES, MEMORY_BYTES))
    resource.setrlimit(resource.RLIMIT_CPU, (math.ceil(TIMEOUT_SECONDS), math.ceil(TIMEOUT_SECONDS) + 1))


def run_bounded(executable: Path, payload: bytes) -> dict[str, Any]:
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.perf_counter_ns()
    process = subprocess.Popen(
        [str(executable)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=child_limits,
        start_new_session=True,
    )
    assert process.stdin is not None and process.stdout is not None and process.stderr is not None
    try:
        process.stdin.write(payload)
        process.stdin.close()
        selector = selectors.DefaultSelector()
        streams = {process.stdout: bytearray(), process.stderr: bytearray()}
        for stream in streams:
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ)
        deadline = time.monotonic() + TIMEOUT_SECONDS
        termination = "exit"
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                termination = "timeout"
                os.killpg(process.pid, signal.SIGKILL)
                break
            for key, _ in selector.select(remaining):
                chunk = os.read(key.fd, 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                target = streams[key.fileobj]
                target.extend(chunk)
                if len(target) > OUTPUT_BYTES:
                    termination = "output_limit"
                    os.killpg(process.pid, signal.SIGKILL)
                    break
            if termination != "exit":
                break
        returncode = process.wait(timeout=2)
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
    elapsed = time.perf_counter_ns() - start
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    stdout = bytes(streams[process.stdout])
    stderr = bytes(streams[process.stderr])
    return {
        "elapsed_ns": elapsed,
        "cpu_user_ns": round((after.ru_utime - before.ru_utime) * 1_000_000_000),
        "cpu_system_ns": round((after.ru_stime - before.ru_stime) * 1_000_000_000),
        "returncode": returncode,
        "termination": termination,
        "stdout": stdout,
        "stderr": stderr,
    }


def classify(run: dict[str, Any]) -> str:
    if run["termination"] == "timeout":
        return "external_timeout"
    if run["termination"] == "output_limit":
        return "external_output_limit"
    if run["returncode"] == 0:
        return "success"
    stderr = run["stderr"].decode("utf-8", errors="replace")
    if "panicked at" in stderr:
        return "panic"
    if run["returncode"] < 0:
        return "signal_or_memory_kill"
    if "json.patch" in stderr or "json.pointer" in stderr:
        return "spec_rejection"
    return "other_failure"


def public_run(run: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in run.items()
        if key not in {"stdout", "stderr"}
    } | {
        "stdout_bytes": len(run["stdout"]),
        "stderr_bytes": len(run["stderr"]),
        "classification": classify(run),
    }


def nearest_rank(values: list[int], fraction: float) -> int:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)]


def summarize(samples: list[dict[str, Any]]) -> dict[str, Any]:
    elapsed = [sample["elapsed_ns"] for sample in samples]
    cpu = [sample["cpu_user_ns"] + sample["cpu_system_ns"] for sample in samples]
    return {
        "n": len(samples),
        "quantile_method": "nearest-rank",
        "elapsed_ns": {
            "min": min(elapsed),
            "p50": nearest_rank(elapsed, 0.50),
            "p90": nearest_rank(elapsed, 0.90),
            "p95": nearest_rank(elapsed, 0.95),
            "max": max(elapsed),
        },
        "child_cpu_ns": {
            "min": min(cpu),
            "p50": nearest_rank(cpu, 0.50),
            "p90": nearest_rank(cpu, 0.90),
            "p95": nearest_rank(cpu, 0.95),
            "max": max(cpu),
        },
    }


def rss_kib(executable: Path, payload: bytes) -> int | None:
    with tempfile.NamedTemporaryFile() as timing:
        completed = subprocess.run(
            ["/usr/bin/time", "-v", "-o", timing.name, str(executable)],
            input=payload,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=TIMEOUT_SECONDS,
            check=False,
            preexec_fn=child_limits,
        )
        timing.seek(0)
        for line in timing.read().decode("utf-8", errors="replace").splitlines():
            if "Maximum resident set size (kbytes)" in line:
                return int(line.rsplit(":", 1)[1].strip())
    return None


def correctness(executable: Path, payload: bytes, record: dict[str, Any], root: Path) -> dict[str, Any]:
    run = run_bounded(executable, payload)
    category = classify(run)
    assert category == record["expected_status"], (record["name"], category, run["stderr"])
    if category == "success":
        expected = parse_json((root / record["expected"]).read_bytes())
        actual = parse_json(run["stdout"])
        assert equal_json(actual, expected), record["name"]
    else:
        assert run["stdout"] == b"", record["name"]
    return public_run(run)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workloads", type=Path, required=True)
    parser.add_argument("--alva", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.workloads / "manifest.json").read_text(encoding="utf-8"))
    executables = {"alva": args.alva.resolve(), "rust_reference": args.reference.resolve()}
    result: dict[str, Any] = {
        "schema": 1,
        "host": {"platform": platform.platform(), "machine": platform.machine(), "python": platform.python_version()},
        "limits": {"wall_seconds": TIMEOUT_SECONDS, "address_space_bytes": MEMORY_BYTES, "capture_bytes": OUTPUT_BYTES},
        "schedule": {"warmups": WARMUPS, "measurements": MEASUREMENTS, "order": "alternating per iteration"},
        "binaries": {
            name: {"path": str(path), "sha256": file_sha256(path), "bytes": path.stat().st_size}
            for name, path in executables.items()
        },
        "workloads": [],
        "compatibility_cases": [],
    }

    for record in manifest["workloads"]:
        payload = (args.workloads / record["request"]).read_bytes()
        case: dict[str, Any] = {"name": record["name"], "shape": record["shape"], "input_bytes": len(payload)}
        case["correctness"] = {
            name: correctness(executable, payload, record, args.workloads)
            for name, executable in executables.items()
        }
        case["first_invocation"] = {
            name: public_run(run_bounded(executable, payload)) for name, executable in executables.items()
        }
        for iteration in range(WARMUPS):
            order = list(executables.items()) if iteration % 2 == 0 else list(reversed(executables.items()))
            for _, executable in order:
                assert classify(run_bounded(executable, payload)) == record["expected_status"]
        samples: dict[str, list[dict[str, Any]]] = {name: [] for name in executables}
        for iteration in range(MEASUREMENTS):
            order = list(executables.items()) if iteration % 2 == 0 else list(reversed(executables.items()))
            for name, executable in order:
                measured = run_bounded(executable, payload)
                assert classify(measured) == record["expected_status"]
                samples[name].append(public_run(measured))
        case["measurements"] = samples
        case["summary"] = {name: summarize(rows) for name, rows in samples.items()}
        case["peak_rss_kib"] = {name: rss_kib(executable, payload) for name, executable in executables.items()}
        alva_p50 = case["summary"]["alva"]["elapsed_ns"]["p50"]
        rust_p50 = case["summary"]["rust_reference"]["elapsed_ns"]["p50"]
        case["alva_over_rust_p50"] = alva_p50 / rust_p50
        result["workloads"].append(case)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for compatibility in manifest["compatibility_cases"]:
        payload = compatibility["request_utf8"].encode("utf-8")
        result["compatibility_cases"].append(
            {
                "name": compatibility["name"],
                "reason": compatibility["reason"],
                "direct_performance_eligible": False,
                "outcomes": {
                    name: public_run(run_bounded(executable, payload))
                    for name, executable in executables.items()
                },
            }
        )
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "workloads": len(result["workloads"]), "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
