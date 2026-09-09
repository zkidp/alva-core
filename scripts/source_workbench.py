#!/usr/bin/env python3
"""Source-authoritative JSONL development host; optional read-only ALVA views.

This is a controlled local tool runner, NOT a security sandbox for untrusted
programs. Run each comparison in an isolated checkout/container. No model API.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time
import tomllib


COMMON = {
    "environment": {},
    "revision": {},
    "read": {"revision": "sha256", "path": "relative path", "start_line": "1-based integer", "line_count": "1..100"},
    "search": {"revision": "sha256", "text": "literal substring"},
    "edit": {"revision": "sha256", "path": "relative .alva/alva.toml",
             "old": "exact unique substring; empty only for new file", "new": "replacement"},
    "check": {"revision": "sha256"},
    "build": {"revision": "sha256"},
    "test": {"revision": "sha256"},
}
VIEWS = {"inspect_project": set(), "inspect_module": {"name"},
         "inspect_function": {"name"}, "inspect_body": {"function"},
         "resolve_entity": {"name", "kind", "module"}}
IGNORED = {".git", "out", "target", "__pycache__"}


class Rejected(Exception):
    pass


class Workbench:
    def __init__(self, project, binary, arm, output, acceptance=None, task=None):
        self.project = Path(project).resolve()
        self.binary = str(Path(binary).resolve())
        self.binary_hash = hashlib.sha256(Path(self.binary).read_bytes()).hexdigest()
        self.arm = arm
        self.output = Path(output).resolve()
        self.acceptance = str(Path(acceptance).resolve()) if acceptance else None
        self.task = task
        if self.output.is_relative_to(self.project):
            raise Rejected("BUILD_OUTPUT_MUST_BE_OUTSIDE_SOURCE")
        if self.acceptance and Path(self.acceptance).is_relative_to(self.project):
            raise Rejected("ACCEPTANCE_MUST_BE_HOST_OWNED_OUTSIDE_SOURCE")
        self.built_revision = None
        self.build_exe = None

    def snapshot(self):
        if (self.project / "alva-air").exists():
            raise Rejected("SOURCE_AUTHORITY_REQUIRED_NO_AIR")
        files = {}
        for directory, dirs, names in os.walk(self.project, followlinks=False):
            for name in dirs + names:
                if (Path(directory) / name).is_symlink():
                    raise Rejected("SYMLINK_NOT_ALLOWED")
            dirs[:] = sorted(d for d in dirs if d not in IGNORED)
            for name in sorted(names):
                path = Path(directory) / name
                files[path.relative_to(self.project).as_posix()] = path.read_bytes()
        if "alva.toml" not in files:
            raise Rejected("MANIFEST_MISSING")
        try:
            manifest = tomllib.loads(files["alva.toml"].decode())
        except (ValueError, UnicodeError):
            manifest = None  # Ordinary editing must be able to repair syntax.
        digest = hashlib.sha256(json.dumps(
            [(p, hashlib.sha256(b).hexdigest()) for p, b in sorted(files.items())],
            separators=(",", ":")).encode()).hexdigest()
        return digest, files, manifest

    @staticmethod
    def validate_manifest(files, manifest):
        if not manifest or not isinstance(manifest.get("modules"), dict):
            raise Rejected("INVALID_MANIFEST")
        for rel in manifest["modules"].values():
            if not isinstance(rel, str) or rel not in files or not rel.endswith(".alva"):
                raise Rejected("MODULE_MUST_BE_LOCAL_CAPTURED_SOURCE")

    def command(self, args, cwd=None):
        p = subprocess.run(args, cwd=cwd, text=True, capture_output=True, timeout=180)
        return {"returncode": p.returncode, "stdout": p.stdout, "stderr": p.stderr}

    def observe(self, files, request):
        view = request["view"]
        args = request.get("args", {})
        if view not in VIEWS or not isinstance(args, dict) or set(args) - VIEWS[view]:
            raise Rejected("READ_ONLY_VIEW_ALLOWLIST")
        if not all(isinstance(v, str) for v in args.values()):
            raise Rejected("VIEW_ARGUMENTS_MUST_BE_STRINGS")
        # Fresh process for each observation: parsing/indexing is never hidden
        # behind an unaccounted stale persistent cache. One live transaction.
        with tempfile.TemporaryDirectory(prefix="alva-source-view-") as tmp:
            root = Path(tmp)
            for rel, data in files.items():
                target = root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            calls = [dict(tool="begin_transaction", project=str(root / "alva.toml")),
                     dict(tool=view, **args), dict(tool="abort_transaction")]
            wire = "".join(json.dumps(dict(request_id=str(i), **r)) + "\n"
                           for i, r in enumerate(calls))
            p = subprocess.run([self.binary, "agent"], input=wire, text=True,
                               capture_output=True, timeout=120)
            rows = [json.loads(line) for line in p.stdout.splitlines() if line.strip()]
            if p.returncode or len(rows) != 3 or not rows[0].get("ok") or not rows[2].get("ok"):
                raise Rejected("OBSERVATION_IMPORT_OR_ABORT_FAILED")
            if (root / "alva-air").exists():
                raise Rejected("OBSERVATION_CREATED_AIR")
            return rows[1]

    def handle(self, request):
        start = time.perf_counter()
        cpu = time.process_time()
        child = resource.getrusage(resource.RUSAGE_CHILDREN)
        revision = None
        tool = request.get("tool") if isinstance(request, dict) else None
        category = "read"
        try:
            if not isinstance(request, dict):
                raise Rejected("REQUEST_MUST_BE_OBJECT")
            if hashlib.sha256(Path(self.binary).read_bytes()).hexdigest() != self.binary_hash:
                raise Rejected("COMPILER_BINARY_CHANGED")
            if tool == "tools":
                result = dict(COMMON)
                if self.arm == "T+V":
                    result["observe"] = {"revision": "sha256", "view": list(VIEWS), "args": "object"}
                return self.response(True, result, start, cpu, child, category, revision)
            allowed = set(COMMON) | ({"observe"} if self.arm == "T+V" else set())
            if tool not in allowed:
                raise Rejected("TOOL_NOT_ALLOWED_FOR_ARM")
            fields = {"tool"} | set(COMMON.get(tool, {}))
            if tool == "observe":
                fields |= {"revision", "view", "args"}
            if set(request) - fields:
                raise Rejected("UNKNOWN_ARGUMENT")
            revision, files, manifest = self.snapshot()
            if tool not in {"revision", "environment"} and request.get("revision") != revision:
                raise Rejected("STALE_SOURCE_REVISION")
            if tool == "environment":
                result = {"compiler_sha256": self.binary_hash,
                          "compiler_version": self.command([self.binary, "--version"]),
                          "python": sys.version, "arm": self.arm, "authority": "SOURCE"}
            elif tool == "revision":
                result = {"files": sorted(files)}
            elif tool == "read":
                start_line, line_count = request.get("start_line", 1), request.get("line_count", 100)
                if type(start_line) is not int or type(line_count) is not int or start_line < 1 or not 1 <= line_count <= 100:
                    raise Rejected("INVALID_READ_RANGE")
                lines = files[request["path"]].decode().splitlines(keepends=True)
                result = {"text": "".join(lines[start_line - 1:start_line - 1 + line_count]),
                          "start_line": start_line, "total_lines": len(lines)}
            elif tool == "search":
                result = [{"path": p, "line": i, "text": line}
                          for p, data in sorted(files.items())
                          for i, line in enumerate(data.decode(errors="replace").splitlines(), 1)
                          if request["text"] in line]
            elif tool == "edit":
                category = "ordinary_text_edit"
                rel, old, new = request["path"], request["old"], request["new"]
                target = (self.project / rel).resolve()
                if not target.is_relative_to(self.project) or target == self.project:
                    raise Rejected("PATH_ESCAPE")
                if not (rel == "alva.toml" or rel.endswith(".alva")) or any(p in IGNORED | {"alva-air"} for p in Path(rel).parts):
                    raise Rejected("EDIT_PATH_NOT_ALLOWED")
                if rel in files:
                    text = files[rel].decode()
                    if not old or text.count(old) != 1:
                        raise Rejected("EXACT_UNIQUE_MATCH_REQUIRED")
                    data = text.replace(old, new, 1).encode()
                else:
                    if old or target.exists():
                        raise Rejected("NEW_FILE_REQUIRES_EMPTY_OLD")
                    data = new.encode()
                if self.snapshot()[0] != revision:
                    raise Rejected("SOURCE_CHANGED_DURING_OPERATION")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                self.built_revision = None
                revision = self.snapshot()[0]
                result = {"written": rel}
            elif tool == "observe":
                category = "semantic_observation"
                self.validate_manifest(files, manifest)
                result = self.observe(files, request)
            elif tool in {"check", "build"}:
                category = "verification"
                self.validate_manifest(files, manifest)
                args = [self.binary, "project", tool, str(self.project / "alva.toml")]
                if tool == "check":
                    args += ["--json"]
                else:
                    args += ["--test", "--out-dir", str(self.output)]
                result = self.command(args)
                if tool == "build" and result["returncode"] == 0:
                    self.built_revision = revision
                    self.build_exe = self.output / manifest["project"]["name"] / "target/debug" / manifest["project"]["name"]
            else:
                category = "verification"
                if not self.acceptance or self.built_revision != revision:
                    raise Rejected("CURRENT_BUILD_AND_HOST_ACCEPTANCE_REQUIRED")
                args = [sys.executable, self.acceptance, "--exe", str(self.build_exe)]
                if self.task:
                    args += ["--task", self.task]
                result = self.command(args)
            if self.snapshot()[0] != revision:
                raise Rejected("SOURCE_CHANGED_DURING_OPERATION")
            return self.response(True, result, start, cpu, child, category, revision)
        except (Rejected, KeyError, ValueError, TypeError, OSError, subprocess.TimeoutExpired) as e:
            return self.response(False, {"error": str(e)}, start, cpu, child, category, revision)

    @staticmethod
    def response(ok, result, start, cpu, child, category, revision):
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        encoded = json.dumps(result, ensure_ascii=False).encode()
        if len(encoded) > 16384:
            status_fields = {k: result[k] for k in ("returncode", "ok", "error_code") if isinstance(result, dict) and k in result}
            result = {**status_fields, "truncated": True, "full_result_utf8_bytes": len(encoded),
                      "full_result_sha256": hashlib.sha256(encoded).hexdigest(),
                      "preview": encoded[:12000].decode(errors="replace"),
                      "instruction": "Narrow the read/search/view; omitted content is not supplied."}
        return {"ok": ok, "source_revision": revision, "result": result,
                "accounting": {"category": category, "wall_seconds": time.perf_counter() - start,
                               "host_cpu_seconds": time.process_time() - cpu,
                               "child_cpu_seconds": after.ru_utime + after.ru_stime - child.ru_utime - child.ru_stime,
                               "transactional_text_edits": 0, "semantic_mutations": 0}}


def main():
    startup = time.perf_counter()
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--binary", required=True)
    ap.add_argument("--arm", choices=["T", "T+V"], required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--audit", required=True)
    ap.add_argument("--acceptance")
    ap.add_argument("--task")
    args = ap.parse_args()
    host = Workbench(args.project, args.binary, args.arm, args.out, args.acceptance, args.task)
    audit = Path(args.audit).resolve()
    if audit.is_relative_to(host.project):
        raise Rejected("AUDIT_MUST_BE_OUTSIDE_SOURCE")
    with audit.open("x", encoding="utf-8") as log:
        log.write(json.dumps({"event": "host_start", "arm": args.arm,
                              "compiler_sha256": host.binary_hash,
                              "startup_wall_seconds": time.perf_counter() - startup}) + "\n")
        log.flush()
        for line in sys.stdin:
            try:
                request = json.loads(line)
            except ValueError:
                request = None
            answer = host.handle(request)
            row = {"request": request, "response": answer}
            wire = json.dumps(answer, ensure_ascii=False)
            row["response_utf8_bytes"] = len(wire.encode())
            log.write(json.dumps(row, ensure_ascii=False) + "\n")
            log.flush()
            print(wire, flush=True)


if __name__ == "__main__":
    main()
