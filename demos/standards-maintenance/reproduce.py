#!/usr/bin/env python3
"""SM-001 release before/after acceptance; no checkout changes or downloads."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SUFFIX = ".exe" if os.name == "nt" else ""


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


JSON = load_module("sm_json", REPO / "tests/json_patch/run_tests.py")
CALLER = load_module("sm_caller", REPO / "examples/json_patch_component/call_component.py")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Session:
    def __init__(self, root, offline):
        self.root = root
        self.cwd = root / "unrelated cwd"
        self.cwd.mkdir()
        self.env = os.environ.copy()
        # Never reuse a caller-selected target, which could mask a stale binary.
        self.env.pop("CARGO_TARGET_DIR", None)
        if offline:
            self.env["CARGO_NET_OFFLINE"] = "true"
        self.report = {"status": "RUNNING", "started_utc": datetime.now(timezone.utc).isoformat(),
                       "platform": platform.platform(), "offline_requested": offline,
                       "commands": [], "versions": {}, "costs": {}}
        self.started = time.monotonic()

    def save(self):
        self.report["costs"]["runner_elapsed_seconds"] = round(time.monotonic() - self.started, 3)
        self.report["costs"]["subprocess_wait_seconds"] = round(
            sum(x["elapsed_seconds"] for x in self.report["commands"]), 3)
        (self.root / "RESULTS.json").write_text(
            json.dumps(self.report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    def run(self, command, *, payload=None, timeout=600, check=True):
        command = [str(x) for x in command]
        ordinal = len(self.report["commands"]) + 1
        print(f"[{ordinal}] cwd={self.cwd} $ {subprocess.list2cmdline(command)}", flush=True)
        started = time.monotonic()
        record = {"command": command, "cwd": str(self.cwd)}
        try:
            result = subprocess.run(command, cwd=self.cwd, env=self.env, input=payload,
                                    capture_output=True, timeout=timeout, check=False)
            record.update(exit_code=result.returncode,
                          stdout=result.stdout.decode("utf-8", "replace"),
                          stderr=result.stderr.decode("utf-8", "replace"))
        except (OSError, subprocess.TimeoutExpired) as exc:
            record["infrastructure_error"] = str(exc)
            raise
        finally:
            record["elapsed_seconds"] = round(time.monotonic() - started, 3)
            if payload is not None:
                record["input"] = payload.decode("utf-8", "replace")
            self.report["commands"].append(record)
            self.save()
        if check and result.returncode:
            raise RuntimeError(f"command {ordinal} failed ({result.returncode}):\n{record['stderr']}")
        return result

    def build(self, source, label):
        dest = self.root / label
        dest.mkdir()
        manifest = source / "alva/Cargo.toml"
        target = dest / "compiler"
        identity = self.run(["git", "-C", source, "rev-parse", "HEAD"]).stdout.decode().strip()
        dirty = self.run(["git", "-C", source, "status", "--porcelain"]).stdout.decode()
        component = source / "examples/json_patch_component"
        inputs = [component / "alva.lib.toml", *sorted((component / "src").glob("*.alva")),
                  *sorted((source / "alva/src").rglob("*.rs")),
                  *sorted((source / "alva/src/std_src").glob("*.alva")),
                  manifest, source / "alva/Cargo.lock"]
        input_hashes = {str(p.relative_to(source)): sha(p) for p in inputs}
        version = {"source_commit": identity, "source_dirty": bool(dirty),
                   "input_sha256": input_hashes, "source": str(source)}
        self.report["versions"][label] = version
        self.run(["cargo", "build", "--manifest-path", manifest, "--locked", "--target-dir", target])
        compiler = target / "debug" / f"alva{SUFFIX}"
        # Adapter is outside Core; reusable modules are never copied or vendored.
        app = dest / "app"
        app.mkdir()
        shutil.copyfile(component / "src/main.alva", app / "main.alva")
        dependency = component / "alva.lib.toml"
        (app / "alva.toml").write_text(
            '[project]\nname = "json_patch_component"\n[modules]\n'
            '"json_patch.main" = "main.alva"\n[dependencies]\n'
            f'json_patch = {json.dumps(dependency.as_posix())}\n', encoding="utf-8")
        self.run([compiler, "project", "check", app / "alva.toml"])
        self.run([compiler, "project", "build", app / "alva.toml", "--out-dir", dest / "gen"])
        crate = dest / "gen/json_patch_component"
        self.run(["cargo", "build", "--manifest-path", crate / "Cargo.toml", "--release", "--locked"])
        binary = crate / "target/release" / f"json_patch_component{SUFFIX}"
        version.update(binary=str(binary), binary_sha256=sha(binary),
                       generated_lock_sha256=sha(crate / "Cargo.lock"),
                       generated_lock=(crate / "Cargo.lock").read_text(encoding="utf-8"),
                       consumer_manifest=(app / "alva.toml").read_text(encoding="utf-8"))
        if input_hashes != {str(p.relative_to(source)): sha(p) for p in inputs}:
            raise AssertionError("build modified selected source inputs")
        return binary, compiler, target

    def acceptance(self, binary, label):
        cases = JSON.semantic_json((HERE / "acceptance/cases.json").read_bytes())
        rows = []
        self.report["versions"].setdefault(label, {}).update(binary=str(binary), binary_sha256=sha(binary))
        self.report["versions"][label]["acceptance"] = rows
        for case in cases:
            payload = JSON.encode_json(case["request"])
            completed = self.run([binary], payload=payload, timeout=10, check=False)
            reject = "error" in case or (label == "before" and case.get("new"))
            row = {"id": case["id"], "passed": False}
            rows.append(row)
            stderr = completed.stderr.decode("utf-8", "strict")
            if reject:
                marker = "mode must be pointer or patch" if label == "before" and case.get("new") else case["error"]
                assert completed.returncode == 1, f"{case['id']}: abnormal/incorrect exit {completed.returncode}"
                assert not completed.stdout, f"{case['id']}: rejected request leaked a result"
                assert "panicked" not in stderr and marker in stderr, f"{case['id']}: unclassified rejection {stderr!r}"
            else:
                assert completed.returncode == 0 and not completed.stderr, f"{case['id']}: {stderr}"
                JSON.assert_json_equal(JSON.semantic_json(completed.stdout), case["expected"], case["id"])
            row["passed"] = True
        self.save()
        print(f"{label}: {len(rows)} acceptance dispositions PASS", flush=True)

    def regressions(self, binary, label):
        result = self.run([sys.executable, REPO / "tests/json_patch/run_tests.py", "--binary", binary])
        summary = json.loads(result.stdout)
        self.report["versions"][label]["original_json_regressions"] = summary
        print(f"{label}: original regressions {summary['totals']}", flush=True)

    def consumer(self, source, compiler):
        app = self.root / "independent consumer"
        app.mkdir()
        shutil.copyfile(HERE / "consumer/main.alva", app / "main.alva")
        dependency = source / "examples/json_patch_component/alva.lib.toml"
        (app / "alva.toml").write_text(
            '[project]\nname = "schema_selection"\n[modules]\n'
            '"consumer.main" = "main.alva"\n[dependencies]\n'
            f'json_patch = {json.dumps(dependency.as_posix())}\n', encoding="utf-8")
        self.run([compiler, "project", "check", app / "alva.toml"])
        self.run([compiler, "project", "build", app / "alva.toml", "--out-dir", app / "gen"])
        crate = app / "gen/schema_selection"
        self.run(["cargo", "build", "--manifest-path", crate / "Cargo.toml", "--release", "--locked"])
        binary = crate / "target/release" / f"schema_selection{SUFFIX}"
        payload = b'{"doc":{"$defs":{"count":{"minimum":9007199254740993.0}}},"pointer":"#/$defs/count"}'
        result = self.run([binary], payload=payload, timeout=10)
        JSON.assert_json_equal(JSON.semantic_json(result.stdout),
                               JSON.semantic_json(b'{"minimum":9007199254740993.0}'), "consumer")
        assert b"9007199254740993.0" in result.stdout
        # The existing caller must wait and accept exact bytes, and never adopt errors.
        previous = Path.cwd()
        os.chdir(self.cwd)
        try:
            accepted = CALLER.call_component_bytes(binary, payload)
            assert accepted == result.stdout
            try:
                CALLER.call_component_bytes(binary, b'{"doc":{},"pointer":"#/%GG"}')
            except RuntimeError as exc:
                assert "percent escape" in str(exc)
            else:
                raise AssertionError("consumer adopted a rejection")
        finally:
            os.chdir(previous)
        self.report["consumer"] = {"status": "PASS", "outside_core": True,
                                   "library": str(dependency), "vendor": False,
                                   "binary": str(binary), "binary_sha256": sha(binary),
                                   "input": payload.decode(), "stdout": result.stdout.decode(),
                                   "caller_accepts_exact_and_rejects_error": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    before = parser.add_mutually_exclusive_group(required=True)
    before.add_argument("--before", type=Path, help="explicit baseline checkout")
    before.add_argument("--before-binary", type=Path, help="supplied baseline release component")
    after = parser.add_mutually_exclusive_group()
    after.add_argument("--after", type=Path, help="explicit modified checkout")
    after.add_argument("--after-binary", type=Path, help="supplied modified release component")
    parser.add_argument("--baseline-only", action="store_true")
    parser.add_argument("--offline", action="store_true", help="require existing Cargo caches")
    parser.add_argument("--work-parent", type=Path, help="parent for a fresh retained temporary directory")
    args = parser.parse_args()
    if not args.baseline_only and not (args.after or args.after_binary):
        parser.error("provide --after or --after-binary, or --baseline-only")
    root = Path(tempfile.mkdtemp(prefix="sm-", dir=args.work_parent)).resolve()
    print(f"Artifacts retained at {root}", flush=True)
    session = Session(root, args.offline)
    try:
        for command in (["rustc", "--version", "--verbose"], ["cargo", "--version"], [sys.executable, "--version"]):
            session.run(command)
        JSON.assert_comparator_regressions()
        for label in (["before"] if args.baseline_only else ["before", "after"]):
            source = getattr(args, label)
            supplied = getattr(args, label + "_binary")
            if source:
                source = source.resolve()
                assert not root.is_relative_to(source), "isolation root must be outside source checkout"
                binary, compiler, target = session.build(source, label)
            else:
                binary = supplied.resolve()
            session.acceptance(binary, label)
            session.regressions(binary, label)
            if source:
                session.run(["cargo", "test", "--manifest-path", source / "alva/Cargo.toml",
                             "--locked", "--target-dir", target])
            if label == "after":
                if source:
                    session.consumer(source, compiler)
                else:
                    session.report["consumer"] = {"status": "NOT_RUN", "reason": "binary-only mode cannot establish source-library consumption"}
        session.report["status"] = "BASELINE_CAPTURED" if args.baseline_only else "PASS"
    except Exception as exc:
        session.report.update(status="FAIL", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        session.save()
        print(f"Results: {root / 'RESULTS.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
