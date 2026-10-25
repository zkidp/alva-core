"""Bounded trusted-local command runner. A temporary tree is not a sandbox."""

from __future__ import annotations

import ctypes
import hashlib
import os
import queue
import re
import signal
import subprocess
import threading
import time
from pathlib import Path


class WindowsJob:
    """Own descendants for cleanup; no claim of hostile-code isolation."""

    def __init__(self, process: subprocess.Popen):
        from ctypes import wintypes

        class Basic(ctypes.Structure):
            _fields_ = [("per_process", ctypes.c_int64), ("per_job", ctypes.c_int64),
                        ("flags", wintypes.DWORD), ("min_ws", ctypes.c_size_t),
                        ("max_ws", ctypes.c_size_t), ("active", wintypes.DWORD),
                        ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD),
                        ("scheduling", wintypes.DWORD)]

        class Counters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in
                        ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]

        class Extended(ctypes.Structure):
            _fields_ = [("basic", Basic), ("io", Counters), ("process_memory", ctypes.c_size_t),
                        ("job_memory", ctypes.c_size_t), ("peak_process", ctypes.c_size_t),
                        ("peak_job", ctypes.c_size_t)]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.kernel = kernel
        self.handle = kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise OSError(ctypes.get_last_error(), "CreateJobObjectW")
        limits = Extended()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            self.close()
            raise OSError(ctypes.get_last_error(), "SetInformationJobObject")
        if not kernel.AssignProcessToJobObject(self.handle, wintypes.HANDLE(int(process._handle))):
            self.close()
            raise OSError(ctypes.get_last_error(), "AssignProcessToJobObject")

    def kill(self) -> None:
        if self.handle:
            self.kernel.TerminateJobObject(self.handle, 1)

    def close(self) -> None:
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def redact(text: str) -> str:
    return re.sub(r"(?i)(api[_-]?key|password|secret|authorization|token)(\s*[:=]\s*)[^\s,;]+",
                  r"\1\2[REDACTED]", text)


def execute(argv: list[str], cwd: Path, environment: dict[str, str], limits: dict) -> dict:
    started = time.monotonic()
    deadline = started + limits["wall_seconds"]
    row = {"argv": argv, "status": "UNKNOWN", "returncode": None, "reason": None,
           "backend": "trusted-local", "sandbox": False, "max_direct_processes": 1,
           "descendant_process_count_enforced": False, "spawn_seconds": None}
    if os.name == "nt" and (limits.get("address_space_bytes") or limits.get("cpu_seconds")):
        return row | {"reason": "UNSUPPORTED_RESOURCE_LIMIT", "elapsed_seconds": 0}

    def child_limits() -> None:
        import resource
        if limits.get("address_space_bytes"):
            size = limits["address_space_bytes"]
            resource.setrlimit(resource.RLIMIT_AS, (size, size))
        if limits.get("cpu_seconds"):
            size = limits["cpu_seconds"]
            resource.setrlimit(resource.RLIMIT_CPU, (size, size))

    process = None
    job = None
    streams = {"stdout": bytearray(), "stderr": bytearray()}
    counts = {name: 0 for name in streams}
    hashes = {name: hashlib.sha256() for name in streams}
    events: queue.Queue = queue.Queue(maxsize=16)
    stop = threading.Event()
    readers: list[threading.Thread] = []

    def read_stream(pipe, name: str) -> None:
        try:
            while not stop.is_set():
                data = os.read(pipe.fileno(), 8192)
                while not stop.is_set():
                    try:
                        events.put((name, data), timeout=0.05)
                        break
                    except queue.Full:
                        pass
                if not data:
                    return
        except OSError:
            return

    def kill() -> None:
        if job:
            job.kill()
        elif process:
            if os.name == "posix":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            elif process.poll() is None:
                process.kill()

    try:
        kwargs = {"start_new_session": True, "preexec_fn": child_limits} if os.name == "posix" else {}
        process = subprocess.Popen(argv, cwd=cwd, env=environment, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
        row["spawn_seconds"] = time.monotonic() - started
        if os.name == "nt":
            job = WindowsJob(process)
        for name in streams:
            thread = threading.Thread(target=read_stream, args=(getattr(process, name), name), daemon=True)
            thread.start()
            readers.append(thread)
        eof: set[str] = set()
        while len(eof) < 2 or process.poll() is None:
            if time.monotonic() >= deadline:
                row["reason"] = "TIMEOUT"
                break
            try:
                name, chunk = events.get(timeout=min(0.05, max(0.001, deadline - time.monotonic())))
            except queue.Empty:
                continue
            if not chunk:
                eof.add(name)
                continue
            counts[name] += len(chunk)
            hashes[name].update(chunk)
            remaining = max(0, limits["output_bytes_per_stream"] - len(streams[name]))
            streams[name].extend(chunk[:remaining])
            if counts[name] > limits["output_bytes_per_stream"]:
                row["reason"] = "OUTPUT_LIMIT"
                break
        row["returncode"] = process.poll()
        if row["reason"] is None:
            row["status"] = "PASS" if row["returncode"] == 0 else "FAIL"
            row["reason"] = "EXIT" if row["returncode"] >= 0 else "SIGNAL_TERMINATION"
            stderr = bytes(streams["stderr"])
            if b"SyntaxError:" not in stderr and (b"ModuleNotFoundError:" in stderr or b"ImportError:" in stderr):
                row.update(status="UNKNOWN", reason="MISSING_OR_UNUSABLE_DEPENDENCY")
        kill()  # Dispose of any owned background descendants even after success.
    except (OSError, subprocess.SubprocessError) as exc:
        row.update(status="UNKNOWN", reason="EXECUTION_ENVIRONMENT_UNAVAILABLE", error=redact(str(exc)))
    finally:
        row["compute_elapsed_seconds"] = time.monotonic() - started
        kill()
        stop.set()
        if process:
            try:
                process.wait(timeout=2)
                row["returncode"] = process.returncode
            except subprocess.TimeoutExpired:
                row.update(status="UNKNOWN", reason="CLEANUP_FAILED")
            for thread in readers:
                thread.join(timeout=0.25)
            for pipe in (process.stdout, process.stderr):
                if pipe:
                    pipe.close()
        if job:
            job.close()
    row["elapsed_seconds"] = time.monotonic() - started
    for name, data in streams.items():
        row[name] = {"text": redact(bytes(data).decode("utf-8", errors="replace")),
                     "bytes_read": counts[name], "bytes_retained": len(data),
                     "sha256_read": hashes[name].hexdigest(),
                     "truncated": counts[name] > len(data)}
    return row
