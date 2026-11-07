"""Windows controller / owned Linux service, shared typed study contract."""
import json
from pathlib import Path
import queue
import subprocess
import threading
from unittest.mock import patch

from benchmarks.maintenance_interface_comparison import pilot as prior
from benchmarks.compact_maintenance.contract import decode_call, NATIVE_TOOLS

HERE = Path(__file__).parent


class Native:
    def __init__(self, slot):
        self.seq = 0
        self.lines = queue.Queue()
        self.stderr = bytearray()
        remote_service = slot.remote.root + "/benchmarks/compact_deepseek/service.py"
        self.process = subprocess.Popen(slot.remote.argv(["python3", remote_service,
            "--config", slot.remote.path(slot.ready), "--role", "mcp"]),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def reader():
            while line := self.process.stdout.readline(1024**2 + 1):
                self.lines.put(line)
            self.lines.put(None)
        def errors():
            while chunk := self.process.stderr.read(4096):
                if len(self.stderr) < 65536:
                    self.stderr.extend(chunk)
        self.reader = threading.Thread(target=reader, daemon=True)
        self.errors = threading.Thread(target=errors, daemon=True)
        self.reader.start(); self.errors.start()
        try:
            self.request("initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                                        "clientInfo": {"name": "compact-api-study", "version": "1"}})
            self.schemas = self.request("tools/list")["tools"]
            if tuple(t["name"] for t in self.schemas) != NATIVE_TOOLS:
                raise RuntimeError("UNEXPECTED_NATIVE_TOOL_EXPOSURE")
        except BaseException:
            self.close()
            raise

    def request(self, method, params=None):
        self.seq += 1
        request = {"jsonrpc": "2.0", "id": self.seq, "method": method, "params": params or {}}
        self.process.stdin.write(json.dumps(request).encode() + b"\n")
        self.process.stdin.flush()
        try:
            line = self.lines.get(timeout=45)
        except queue.Empty:
            raise RuntimeError("NATIVE_RPC_TIMEOUT_NO_REPLAY") from None
        if not line or len(line) > 1024**2:
            raise RuntimeError("NATIVE_RPC_CLOSED_OR_UNBOUNDED")
        result = json.loads(line)
        if result.get("id") != self.seq or "error" in result:
            raise RuntimeError("NATIVE_RPC_INVALID_RESPONSE")
        return result["result"]

    def close(self):
        if not self.process.stdin.closed:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.process.kill(); self.process.wait(timeout=5)
            raise RuntimeError("NATIVE_RELAY_CLEANUP_UNCONFIRMED") from None
        self.reader.join(timeout=2); self.errors.join(timeout=2)
        if self.process.returncode or self.reader.is_alive() or self.errors.is_alive():
            raise RuntimeError("NATIVE_RELAY_CLEANUP_UNCONFIRMED")


class Slot(prior.Slot):
    def __init__(self, output, entry, frozen, args):
        # Constructor owns exactly the same pidfd/tombstone Linux owner;
        # only service module and work/output paths change for this new study.
        self.native = None
        with patch.object(prior, "HERE", HERE):
            super().__init__(output, entry, frozen, args)
        if entry["arm"] == "N":
            try:
                self.native = Native(self)
            except BaseException:
                super().close()
                raise

    def tool(self, name, arguments):
        if name.startswith("study_"):
            try:
                action, detail = decode_call(self.entry["arm"], name, arguments)
            except ValueError as e:
                return {"error": str(e)}
            return self.dispatch(action, detail)
        if not self.native or name not in NATIVE_TOOLS:
            return {"error": "TOOL_NOT_EXPOSED"}
        if not isinstance(arguments, dict):
            return {"error": "ARGUMENTS_MUST_BE_OBJECT"}
        return self.native.request("tools/call", {"name": name, "arguments": arguments})

    def close(self):
        try:
            if self.native:
                self.native.close()
        finally:
            super().close()
