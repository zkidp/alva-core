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


def child_limits(memory_bytes: int, timeout_seconds: float):
    def apply() -> None:
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        cpu_seconds = max(1, math.ceil(timeout_seconds))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))

    return apply


def run_bounded(
    command: Path | list[str],
    payload: bytes,
    *,
    timeout_seconds: float = TIMEOUT_SECONDS,
    memory_bytes: int = MEMORY_BYTES,
    output_bytes: int = OUTPUT_BYTES,
    cleanup_seconds: float = 2.0,
) -> dict[str, Any]:
    """Run one process group under one wall deadline.

    The deadline starts immediately before Popen. Python cannot interrupt a Popen
    blocked inside the OS, but stdin delivery, output capture, child execution,
    and normal reaping all share the remaining deadline after Popen returns.
    Cleanup after a forced termination has a separate, bounded allowance.
    """
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.perf_counter_ns()
    deadline = time.monotonic() + timeout_seconds
    argv = [str(command)] if isinstance(command, Path) else [str(item) for item in command]
    process = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=child_limits(memory_bytes, timeout_seconds),
        start_new_session=True,
    )
    spawn_elapsed_ns = time.perf_counter_ns() - start
    assert process.stdin is not None and process.stdout is not None and process.stderr is not None
    selector = selectors.DefaultSelector()
    streams = {process.stdout: bytearray(), process.stderr: bytearray()}
    totals = {process.stdout: 0, process.stderr: 0}
    stdin_offset = 0
    stdin_broken_pipe = False
    termination = "exit"
    returncode: int | None = None

    def kill_group() -> None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def close_stdin() -> None:
        try:
            selector.unregister(process.stdin)
        except (KeyError, ValueError):
            pass
        if not process.stdin.closed:
            process.stdin.close()

    def read_ready(stream: Any) -> bool:
        nonlocal termination
        try:
            chunk = os.read(stream.fileno(), 65536)
        except BlockingIOError:
            return False
        if not chunk:
            try:
                selector.unregister(stream)
            except (KeyError, ValueError):
                pass
            return False
        totals[stream] += len(chunk)
        target = streams[stream]
        remaining = max(0, output_bytes - len(target))
        target.extend(chunk[:remaining])
        if totals[stream] > output_bytes:
            termination = "output_limit"
            kill_group()
            return True
        return False

    try:
        for stream in (process.stdin, process.stdout, process.stderr):
            os.set_blocking(stream.fileno(), False)
        if payload:
            selector.register(process.stdin, selectors.EVENT_WRITE)
        else:
            process.stdin.close()
        selector.register(process.stdout, selectors.EVENT_READ)
        selector.register(process.stderr, selectors.EVENT_READ)

        while selector.get_map() or process.poll() is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                termination = "timeout"
                kill_group()
                break
            events = selector.select(remaining)
            for key, mask in events:
                if key.fileobj is process.stdin and mask & selectors.EVENT_WRITE:
                    try:
                        sent = os.write(process.stdin.fileno(), payload[stdin_offset : stdin_offset + 65536])
                        stdin_offset += sent
                        if stdin_offset == len(payload):
                            close_stdin()
                    except (BrokenPipeError, OSError):
                        stdin_broken_pipe = True
                        close_stdin()
                elif key.fileobj in streams and mask & selectors.EVENT_READ:
                    if read_ready(key.fileobj):
                        break
            if termination != "exit":
                break
            if process.poll() is not None and not selector.get_map():
                break

        compute_elapsed_ns = time.perf_counter_ns() - start
        cleanup_deadline = time.monotonic() + cleanup_seconds
        if termination != "exit":
            kill_group()
        close_stdin()
        while selector.get_map() and time.monotonic() < cleanup_deadline:
            events = selector.select(max(0.0, cleanup_deadline - time.monotonic()))
            if not events:
                break
            for key, mask in events:
                if key.fileobj in streams and mask & selectors.EVENT_READ:
                    read_ready(key.fileobj)
        try:
            returncode = process.wait(timeout=max(0.0, cleanup_deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            kill_group()
            try:
                returncode = process.wait(timeout=max(0.0, cleanup_deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                returncode = process.poll()
    finally:
        if process.poll() is None:
            kill_group()
            try:
                process.wait(timeout=cleanup_seconds)
            except subprocess.TimeoutExpired:
                pass
        selector.close()
        for stream in (process.stdin, process.stdout, process.stderr):
            try:
                stream.close()
            except OSError:
                pass
    elapsed = time.perf_counter_ns() - start
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    stdout = bytes(streams[process.stdout])
    stderr = bytes(streams[process.stderr])
    return {
        "elapsed_ns": elapsed,
        "compute_elapsed_ns": compute_elapsed_ns,
        "cleanup_elapsed_ns": elapsed - compute_elapsed_ns,
        "spawn_elapsed_ns": spawn_elapsed_ns,
        "cpu_user_ns": round((after.ru_utime - before.ru_utime) * 1_000_000_000),
        "cpu_system_ns": round((after.ru_stime - before.ru_stime) * 1_000_000_000),
        "returncode": returncode,
        "termination": termination,
        "stdin_bytes_sent": stdin_offset,
        "stdin_broken_pipe": stdin_broken_pipe,
        "stdout_bytes_read": totals[process.stdout],
        "stderr_bytes_read": totals[process.stderr],
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
        return "signal_termination"
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


def rss_kib(executable: Path, payload: bytes) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile() as timing:
        run = run_bounded(["/usr/bin/time", "-v", "-o", timing.name, str(executable)], payload)
        timing.seek(0)
        value = None
        for line in timing.read().decode("utf-8", errors="replace").splitlines():
            if "Maximum resident set size (kbytes)" in line:
                value = int(line.rsplit(":", 1)[1].strip())
                break
    return {
        "value_kib": value,
        "reason": None if value is not None else f"bounded_run_{classify(run)}",
        "scope": "GNU time reported maximum RSS for measured executable",
        "run": public_run(run),
    }


def validate_run(run: dict[str, Any], record: dict[str, Any], root: Path) -> None:
    category = classify(run)
    assert category == record["expected_status"], (record["name"], category, run["stderr"])
    if category == "success":
        expected = parse_json((root / record["expected"]).read_bytes())
        actual = parse_json(run["stdout"])
        assert equal_json(actual, expected), record["name"]
    else:
        assert run["stdout"] == b"", record["name"]


def correctness(executable: Path, payload: bytes, record: dict[str, Any], root: Path) -> dict[str, Any]:
    run = run_bounded(executable, payload)
    validate_run(run, record, root)
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
        "schema": 2,
        "host": {"platform": platform.platform(), "machine": platform.machine(), "python": platform.python_version()},
        "limits": {
            "wall_seconds": TIMEOUT_SECONDS,
            "cleanup_seconds": 2.0,
            "address_space_bytes": MEMORY_BYTES,
            "stdout_capture_bytes": OUTPUT_BYTES,
            "stderr_capture_bytes": OUTPUT_BYTES,
            "aggregate_capture_bytes": 2 * OUTPUT_BYTES,
        },
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
        case["pre_warmup_observation"] = {
            name: public_run(run_bounded(executable, payload)) for name, executable in executables.items()
        }
        for iteration in range(WARMUPS):
            order = list(executables.items()) if iteration % 2 == 0 else list(reversed(executables.items()))
            for _, executable in order:
                validate_run(run_bounded(executable, payload), record, args.workloads)
        samples: dict[str, list[dict[str, Any]]] = {name: [] for name in executables}
        for iteration in range(MEASUREMENTS):
            order = list(executables.items()) if iteration % 2 == 0 else list(reversed(executables.items()))
            for name, executable in order:
                measured = run_bounded(executable, payload)
                validate_run(measured, record, args.workloads)
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
