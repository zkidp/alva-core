"""Trusted-host persistent Linux workspace and native MCP stdio transport.

No model/provider/harness logic. No host execution or mount fallback.
"""
from __future__ import annotations

import json
from functools import wraps
import os
from pathlib import Path
import selectors
import shutil
import signal
import subprocess
import tempfile
import threading
import time

from .freeze import decode, materialize
from .sandbox import LinuxSandbox, SDK, Unsupported


class Closed(RuntimeError):
    """Unusable workspace: execution outcome may be unknown. Never retry."""


def _serialized(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self.lock:
            return method(self, *args, **kwargs)
    return call


class _Process:
    def __init__(self, owner, argv):
        self.owner = owner
        self.sel = selectors.DefaultSelector()
        self.out = bytearray()
        self.err = bytearray()
        self.total = 0
        self.closed = False
        self.stopped = threading.Event()
        self.watchdog = None
        try:
            self.p = subprocess.Popen(owner._command(argv), stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      start_new_session=True, close_fds=True,
                                      env=owner.backend.launch_env)
        except BaseException:
            self.sel.close()
            raise
        # Register immediately so a later transport-setup failure is killable.
        owner.process = self
        for stream, label in ((self.p.stdout, "out"), (self.p.stderr, "err")):
            os.set_blocking(stream.fileno(), False)
            self.sel.register(stream, selectors.EVENT_READ, label)
        os.set_blocking(self.p.stdin.fileno(), False)
        def watchdog():
            if not self.stopped.wait(max(0, owner.deadline - time.monotonic())):
                owner.poisoned = True
                try:
                    os.killpg(self.p.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

        self.watchdog = threading.Thread(target=watchdog, daemon=True)
        self.watchdog.start()

    def pump(self, deadline, pending=b""):
        if self.owner.poisoned or time.monotonic() >= min(deadline, self.owner.deadline):
            raise Closed("WALL_OR_RPC_LIMIT; no retry")
        if pending:
            try:
                written = os.write(self.p.stdin.fileno(), pending)
                pending = pending[written:]
            except BlockingIOError:
                pass
            except BrokenPipeError as exc:
                raise Closed("STDIN_BROKEN; outcome unknown") from exc
        for key, _ in self.sel.select(.01):
            chunk = os.read(key.fd, 4096)
            if not chunk:
                self.sel.unregister(key.fileobj)
                continue
            self.total += len(chunk)
            if self.total > self.owner.output_limit:
                raise Closed("SESSION_OUTPUT_LIMIT")
            (self.out if key.data == "out" else self.err).extend(chunk)
        return pending

    def shutdown(self, graceful=False, completion_deadline=None):
        if self.closed:
            return
        try:
            if graceful:
                self.p.stdin.close()
                end = min(self.owner.deadline, completion_deadline or time.monotonic() + 5)
                while self.p.poll() is None or self.sel.get_map():
                    self.pump(end)
                if self.p.returncode != 0:
                    raise Closed("ABNORMAL_EXIT:" + str(self.p.returncode) + "; stderr="
                                 + bytes(self.err[:4096]).decode("utf-8", errors="replace"))
            # Always remove descendants, including after a normal MCP EOF.
        finally:
            try:
                os.killpg(self.p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                self.p.wait(timeout=5)
                end = time.monotonic() + 5
                while self.sel.get_map() and time.monotonic() < end:
                    for key, _ in self.sel.select(.01):
                        if not os.read(key.fd, 4096):
                            self.sel.unregister(key.fileobj)
                if self.sel.get_map():
                    raise Closed("TERMINATION_UNCONFIRMED")
            except subprocess.TimeoutExpired as exc:
                raise Closed("TERMINATION_UNCONFIRMED; workspace unusable") from exc
            finally:
                self.closed = True
                self.stopped.set()
                if self.watchdog and self.watchdog.is_alive():
                    self.watchdog.join(timeout=1)
                self.sel.close()
                for stream in (self.p.stdin, self.p.stdout, self.p.stderr):
                    stream.close()
                self.owner.process = None


class PersistentSandbox:
    """One trusted host, one slot, one active process. Disposable persistent AIR.

    bundle/expected_id and SDK are host-approved, never candidate arguments.
    Only /work and /tmp are writable. New processes reuse /work, not /tmp.
    Any transport/execution failure poisons the entire workspace.
    """
    def __init__(self, bundle: dict, expected_id: str, sdk: SDK | None = None,
                 wall_seconds=120, rpc_seconds=15, output_limit=8 * 1024**2):
        self.backend = LinuxSandbox(sdk, wall_seconds, output_limit)
        if rpc_seconds <= 0:
            raise ValueError("Positive RPC limit required")
        files = decode(bundle, expected_id)
        if sum(map(len, files.values())) > 16 * 1024**2:
            raise ValueError("Input limit")
        self.temp = tempfile.TemporaryDirectory(prefix="alva-persistent-v1-")
        self.root = Path(self.temp.name)
        self.work = self.root / "work"
        self.input = self.root / "input"
        self.work.mkdir()
        self.process = None
        self.poisoned = False
        self.closed = False
        self.rpc_seconds = rpc_seconds
        self.output_limit = output_limit
        self.deadline = time.monotonic() + wall_seconds
        try:
            materialize(bundle, expected_id, self.input)
            materialize(bundle, expected_id, self.work / "project")
            if sdk:
                if any(p.is_symlink() for p in sdk.registry.rglob("*")):
                    raise Unsupported("Registry symlinks unsupported")
                shutil.copytree(sdk.registry, self.work / "cargo/registry")
        except BaseException:
            self.temp.cleanup()
            raise
        # Input/SDK setup is trusted preparation, not live process wall time.
        self.deadline = time.monotonic() + wall_seconds

    def _command(self, argv):
        if self.closed or self.poisoned or self.process is not None:
            raise Closed("WORKSPACE_CLOSED_OR_BUSY")
        if time.monotonic() >= self.deadline:
            raise Closed("WORKSPACE_WALL_LIMIT")
        if not argv or not argv[0].startswith("/"):
            raise ValueError("Explicit sandbox executable required")
        b = self.backend
        args = b._base() + ["--ro-bind", str(self.input), "/input",
                            "--bind", str(self.work), "/work"]
        if b.sdk:
            args += ["--ro-bind", str(b.sdk.alva.resolve()), "/sdk/alva",
                     "--ro-bind", str(b.sdk.rust_toolchain.resolve()), "/sdk/toolchain"]
        return [b.prlimit, "--cpu=90:90", "--as=4294967296:4294967296",
                "--fsize=268435456:268435456", "--nofile=256:256", "--nproc=128:128", "--",
                *args, "--chdir", "/work/project", "--remount-ro", "/", "--", *argv]

    def _fail(self, exc):
        self.poisoned = True
        if self.process:
            self.process.shutdown()
        raise Closed(str(exc)) from exc

    def mcp(self):
        if not self.backend.sdk:
            raise Unsupported("Native MCP requires approved SDK")
        return NativeMCP(self)

    def run(self, argv):
        """Trusted host command, inside the same workspace boundary; no shell added.

        argv must not contain host-only reference material. An exit != 0
        fails closed, not a successful evaluation or automatically retried call.
        """
        try:
            proc = _Process(self, argv)
            proc.shutdown(graceful=True, completion_deadline=self.deadline)
            return {"exit": proc.p.returncode, "stdout": bytes(proc.out).decode("utf-8"),
                    "stderr": bytes(proc.err).decode("utf-8")}
        except Exception as exc:
            self._fail(exc)

    def close(self):
        try:
            if self.process:
                self.process.shutdown()
        finally:
            self.closed = True
            self.temp.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class NativeMCP:
    """Serialized newline JSON-RPC over the real `alva mcp` stdio process.

    No request replay, auto-restart or transaction ID translation. JSON-RPC
    errors fail the session; ordinary MCP tool isError results remain evidence.
    """
    def __init__(self, owner):
        self.owner = owner
        self.lock = threading.RLock()
        self.next_id = 0
        self.closed = False
        try:
            self.process = _Process(owner, ["/sdk/alva", "mcp"])
        except Exception as exc:
            owner._fail(exc)

    @_serialized
    def request(self, method, params=None):
        if self.closed:
            raise Closed("SESSION_CLOSED")
        self.next_id += 1
        request = {"jsonrpc": "2.0", "id": self.next_id, "method": method, "params": params or {}}
        pending = json.dumps(request, allow_nan=False, separators=(",", ":")).encode() + b"\n"
        if len(pending) > 1024**2:
            raise ValueError("RPC request limit")
        deadline = time.monotonic() + self.owner.rpc_seconds
        p = self.process
        try:
            if p.out or self.owner.poisoned:
                raise Closed("UNSOLICITED_OUTPUT_OR_EXPIRED_WORKSPACE")
            while pending or b"\n" not in p.out:
                pending = p.pump(deadline, pending)
                if p.p.poll() is not None:
                    raise Closed("MCP_EXIT_BEFORE_RESPONSE; outcome unknown")
            line, _, rest = p.out.partition(b"\n")
            p.out = bytearray(rest)
            response = json.loads(line)
            if (not isinstance(response, dict) or response.get("jsonrpc") != "2.0"
                    or type(response.get("id")) is not int or response["id"] != self.next_id
                    or "error" in response or "result" not in response):
                raise Closed("INVALID_OR_FAILED_RPC:" + str(response)[:500])
            return response["result"]
        except Exception as exc:
            self.closed = True
            self.owner._fail(exc)

    @_serialized
    def notify(self, method, params=None):
        """Bounded JSON-RPC notification (e.g. notifications/initialized)."""
        if self.closed:
            raise Closed("SESSION_CLOSED")
        pending = json.dumps({"jsonrpc": "2.0", "method": method, "params": params or {}},
                             allow_nan=False, separators=(",", ":")).encode() + b"\n"
        if len(pending) > 1024**2:
            raise ValueError("RPC request limit")
        deadline = time.monotonic() + self.owner.rpc_seconds
        try:
            while pending:
                pending = self.process.pump(deadline, pending)
                if self.process.p.poll() is not None:
                    raise Closed("MCP_EXIT_DURING_NOTIFICATION")
        except Exception as exc:
            self.closed = True
            self.owner._fail(exc)

    def tool(self, name, arguments):
        return self.request("tools/call", {"name": name, "arguments": arguments})

    @_serialized
    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            if self.process.p.poll() is not None:
                raise Closed("MCP_EXIT_BEFORE_CLOSE")
            self.process.shutdown(graceful=True)
            if self.process.out:
                raise Closed("UNEXPECTED_TRAILING_STDOUT")
        except Exception as exc:
            self.owner._fail(exc)

    def __enter__(self):
        return self

    def __exit__(self, kind, *_):
        if kind:
            self.closed = True
            self.owner.poisoned = True
            self.process.shutdown()
        else:
            self.close()
