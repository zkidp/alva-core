"""Four-arm E4 tool dispatcher and text/AIR synchronisation state machine."""

from __future__ import annotations

import json
import subprocess
import tempfile
import time
import tomllib
from pathlib import Path
from typing import Protocol

from text_workspace import TextWorkspace, dispatch as dispatch_text


TEXT = "TEXT"
TEXT_VERIFY = "TEXT_VERIFY"
HYBRID = "HYBRID"
FULL_ALVA = "FULL_ALVA"
ARMS = frozenset({TEXT, TEXT_VERIFY, HYBRID, FULL_ALVA})

TEXT_TOOLS = frozenset({"read_file", "list_files", "write_file", "apply_patch"})
CONTROL_TOOLS = frozenset({
    "resolve_entity", "inspect_project", "inspect_module", "inspect_function",
    "inspect_entity", "inspect_body", "inspect_test", "inspect_change_impact",
    "inspect_schema_gaps", "preview_semantic_diff",
})
AFFORDANCE_TOOLS = frozenset({
    "applicable_operations", "describe_operation", "migrate_signature",
    "rename_entity", "set_effect",
})


def _ok(result=None):
    return {"ok": True, "result": {} if result is None else result}


def _error(code, message):
    return {"ok": False, "error_code": code, "message": message}


class SemanticProtocol(Protocol):
    def start(self) -> dict: ...
    def call(self, tool: str, arguments: dict) -> dict: ...
    def close(self, *, abort: bool) -> None: ...


class CompilerBridge:
    """Host-only conversion/check bridge; no host paths enter tool output."""

    def __init__(self, alva: str | Path, workspace: str | Path) -> None:
        self.alva = str(alva)
        self.workspace = Path(workspace).resolve(strict=True)
        self.manifest = self.workspace / "alva.toml"
        if not self.manifest.is_file():
            raise ValueError("workspace has no alva.toml")
        with self.manifest.open("rb") as stream:
            raw = tomllib.load(stream)
        modules = raw.get("modules")
        if not isinstance(modules, dict) or not modules:
            raise ValueError("manifest has no modules")
        self.module_paths = {str(name): str(path).replace("\\", "/")
                             for name, path in modules.items()}

    def _run(self, arguments: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            [self.alva, *arguments], cwd=self.workspace,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", timeout=120,
        )

    def _sanitize(self, value):
        """Remove host workspace paths from model-visible diagnostics."""
        if isinstance(value, str):
            redacted = value.replace(str(self.workspace), "<workspace>")
            redacted = redacted.replace(str(self.workspace).replace("\\", "/"),
                                        "<workspace>")
            return redacted
        if isinstance(value, list):
            return [self._sanitize(item) for item in value]
        if isinstance(value, dict):
            return {key: self._sanitize(item) for key, item in value.items()}
        return value

    def _diagnostics(self, process: subprocess.CompletedProcess) -> dict:
        output = self._sanitize((process.stdout + process.stderr)[-12000:])
        try:
            parsed = self._sanitize(
                json.loads(process.stdout) if process.stdout.strip() else [])
        except json.JSONDecodeError:
            parsed = []
        return {
            "ok": process.returncode == 0,
            "result": {"diagnostics": parsed, "summary": output},
            **({} if process.returncode == 0 else {
                "error_code": "E_PROJECT_CHECK", "message": "project check failed"
            }),
        }

    def refresh_air(self) -> dict:
        export_dir = self.workspace / ".e4-air-export"
        export_dir.mkdir(exist_ok=True)
        process = self._run([
            "air", "export", str(self.manifest), "--out-dir", str(export_dir),
            "--authoritative",
        ])
        if process.returncode != 0:
            return self._diagnostics(process)
        return _ok({"air_refreshed": True})

    def check_project(self) -> dict:
        refreshed = self.refresh_air()
        if not refreshed["ok"]:
            return refreshed
        process = self._run(["project", "check", "--file", str(self.manifest), "--json"])
        return self._diagnostics(process)

    def project_air_to_text(self) -> dict[str, bytes]:
        current = self.workspace / "alva-air" / "current"
        try:
            generation = int(current.read_text(encoding="utf-8").splitlines()[0])
        except (OSError, ValueError, IndexError) as exc:
            raise RuntimeError("authoritative AIR pointer is invalid") from exc
        graph = self.workspace / "alva-air" / f"gen-{generation}.air"
        with tempfile.TemporaryDirectory(prefix="e4-projection-", dir=self.workspace.parent) as temp:
            process = self._run(["air", "import", str(graph), "--out-dir", temp])
            if process.returncode != 0:
                raise RuntimeError("AIR projection failed")
            projected = {}
            for module, rel in self.module_paths.items():
                source = Path(temp) / f"{module}.alva"
                if not source.is_file():
                    raise RuntimeError("AIR projection is incomplete")
                projected[rel] = source.read_bytes()
            extras = {path.name for path in Path(temp).glob("*.alva")} - {
                f"{module}.alva" for module in self.module_paths
            }
            if extras:
                raise RuntimeError("AIR projection contains unexpected modules")
            return projected


class E4Runtime:
    """Arm-specific tool surface with one auditable, fail-closed state."""

    def __init__(
        self,
        arm: str,
        workspace: str | Path,
        allowed_files: list[str],
        compiler: CompilerBridge,
        semantic: SemanticProtocol | None = None,
    ) -> None:
        if arm not in ARMS or arm == FULL_ALVA:
            raise ValueError("E4Runtime is for the three text-facing arms")
        self.arm = arm
        self.compiler = compiler
        self.semantic = semantic
        if arm != TEXT and semantic is None:
            raise ValueError("control-plane arms require a semantic session")
        self.text = TextWorkspace(
            workspace, allowed_files, require_session=arm != TEXT
        )
        self.active = False
        self.text_dirty = False
        self.semantic_dirty = False
        self.checked = False
        self.closed = False
        self.poisoned = False
        self.call_log: list[dict] = []

    def _record(self, tool: str, arguments: dict, result: dict, started: float) -> dict:
        self.call_log.append({
            "ordinal": len(self.call_log) + 1,
            "tool": tool,
            "args": arguments,
            "ok": bool(result.get("ok")),
            "error_code": result.get("error_code"),
            "message": result.get("message"),
            "result": result.get("result"),
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "elapsed_s": round(time.monotonic() - started, 3),
            "arm": self.arm,
        })
        return result

    def _restart_semantic(self) -> dict:
        if self.semantic is None:
            return _ok()
        self.semantic.close(abort=True)
        result = self.semantic.start()
        return result

    def _check_current_text(self) -> dict:
        result = self.compiler.check_project()
        if not result["ok"]:
            self.checked = False
            return result
        self.text_dirty = False
        self.checked = True
        if self.arm != TEXT:
            restarted = self._restart_semantic()
            if not restarted.get("ok"):
                self.checked = False
                return restarted
        return result

    def begin_patch_session(self) -> dict:
        if self.arm == TEXT:
            return _error("E_UNKNOWN_TOOL", "tool is not available")
        result = self.text.begin_patch_session()
        if not result["ok"]:
            return result
        checked = self.compiler.check_project()
        if not checked["ok"]:
            self.text.discard_patch()
            return checked
        started = self.semantic.start()
        if not started.get("ok"):
            self.text.discard_patch()
            return started
        self.active = True
        self.checked = True
        return _ok({"session_active": True})

    def check_project(self) -> dict:
        if self.arm == TEXT:
            return self._check_current_text()
        if not self.active:
            return _error("E_NO_PATCH_SESSION", "begin_patch_session is required")
        if self.semantic_dirty:
            result = self.semantic.call("check_transaction", {})
            self.checked = bool(result.get("ok"))
            return result
        return self._check_current_text()

    def commit_patch(self) -> dict:
        if self.arm == TEXT:
            return _error("E_UNKNOWN_TOOL", "tool is not available")
        if not self.active:
            return _error("E_NO_PATCH_SESSION", "begin_patch_session is required")
        if self.text_dirty:
            checked = self._check_current_text()
            if not checked["ok"]:
                return checked
        if self.semantic_dirty:
            checked = self.semantic.call("check_transaction", {})
            if not checked.get("ok"):
                return checked
            committed = self.semantic.call("commit_transaction", {})
            if not committed.get("ok"):
                return committed
            try:
                self.text.replace_from_host(self.compiler.project_air_to_text())
            except Exception:
                # The AIR commit is already durable. Cross-representation
                # rollback cannot be claimed, so poison this disposable run
                # workspace and prevent any verifier/model continuation.
                self.semantic.close(abort=False)
                self.poisoned = True
                return _error("E_COMMIT_PROJECTION_DIVERGENCE",
                              "committed AIR could not be projected to text")
            self.semantic.close(abort=False)
        else:
            self.semantic.close(abort=True)
        result = self.text.commit_patch()
        if result["ok"]:
            self.active = False
            self.checked = True
        return result

    def discard_patch(self) -> dict:
        if self.arm == TEXT:
            return _error("E_UNKNOWN_TOOL", "tool is not available")
        if not self.active:
            return _error("E_NO_PATCH_SESSION", "begin_patch_session is required")
        self.semantic.close(abort=True)
        result = self.text.discard_patch()
        if result["ok"]:
            self.active = False
            self.text_dirty = self.semantic_dirty = False
            self.checked = False
        return result

    def call(self, tool: str, **arguments) -> dict:
        started = time.monotonic()
        if self.closed:
            return self._record(tool, arguments, _error("E_RUNTIME_CLOSED", "runtime is closed"), started)
        if self.poisoned:
            return self._record(tool, arguments, _error(
                "E_RUNTIME_POISONED", "runtime state is not recoverable"), started)
        if tool == "begin_patch_session":
            return self._record(tool, arguments, self.begin_patch_session(), started)
        if tool == "check_project":
            return self._record(tool, arguments, self.check_project(), started)
        if tool == "commit_patch":
            return self._record(tool, arguments, self.commit_patch(), started)
        if tool == "discard_patch":
            return self._record(tool, arguments, self.discard_patch(), started)
        if tool in TEXT_TOOLS:
            if tool in {"write_file", "apply_patch"} and self.semantic_dirty:
                result = _error("E_MIXED_EDIT_CONFLICT", "text edits cannot follow semantic mutation")
            else:
                result = dispatch_text(self.text, tool, arguments)
                if result.get("ok") and tool in {"write_file", "apply_patch"}:
                    self.text_dirty = True
                    self.checked = False
            return self._record(tool, arguments, result, started)
        if tool in CONTROL_TOOLS:
            if self.arm == TEXT:
                result = _error("E_UNKNOWN_TOOL", "tool is not available")
            elif not self.active:
                result = _error("E_NO_PATCH_SESSION", "begin_patch_session is required")
            elif self.text_dirty:
                result = _error("E_TEXT_NOT_CHECKED", "check_project is required after text edits")
            else:
                result = self.semantic.call(tool, arguments)
            return self._record(tool, arguments, result, started)
        if tool in AFFORDANCE_TOOLS:
            if self.arm != HYBRID:
                result = _error("E_UNKNOWN_TOOL", "tool is not available")
            elif not self.active:
                result = _error("E_NO_PATCH_SESSION", "begin_patch_session is required")
            elif self.text_dirty:
                result = _error("E_TEXT_NOT_CHECKED", "check_project is required after text edits")
            else:
                result = self.semantic.call(tool, arguments)
                if result.get("ok") and tool in {"migrate_signature", "rename_entity", "set_effect"}:
                    self.semantic_dirty = True
                    self.checked = False
            return self._record(tool, arguments, result, started)
        return self._record(tool, arguments, _error("E_UNKNOWN_TOOL", "tool is not available"), started)

    def prepare_final_verifier(self) -> dict:
        """Make final text authoritative before the arm-blind verifier."""
        if self.poisoned:
            return _error("E_RUNTIME_POISONED", "runtime state is not recoverable")
        if self.active:
            return _error("E_UNCOMMITTED_PATCH", "patch session is still active")
        if self.arm == TEXT or not self.checked:
            return self.compiler.check_project()
        return _ok({"ready": True})

    def close(self) -> None:
        if self.closed:
            return
        if self.active and self.semantic is not None:
            self.semantic.close(abort=True)
        self.closed = True
