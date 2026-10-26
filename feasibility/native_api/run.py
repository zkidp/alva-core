#!/usr/bin/env python3
"""One deterministic case, real CLI AEP sessions; never starts a model."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def manifest(path):
    return {p.relative_to(path).as_posix(): digest(p.read_bytes())
            for p in sorted(path.rglob("*")) if p.is_file()}


class Unsupported(Exception):
    pass


class Agent:
    def __init__(self, binary, project, log, label):
        self.p = subprocess.Popen([str(binary), "agent"], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, encoding="utf-8")
        self.log, self.label = log, label
        self.call("begin_transaction", project=str(project / "alva.toml"))

    def call(self, tool, expected=True, **args):
        request = {"request_id": str(len(self.log) + 1), "tool": tool, **args}
        self.p.stdin.write(json.dumps(request) + "\n")
        self.p.stdin.flush()
        line = self.p.stdout.readline()
        assert line, (tool, "agent exited", self.p.poll())
        answer = json.loads(line)
        self.log.append({"session": self.label, "request": request, "response": answer})
        if expected is not None:
            assert answer["ok"] == expected, (tool, answer)
        return answer

    def result(self, tool, **args):
        return self.call(tool, **args)["result"]

    def nodes(self, function):
        result = []
        seen = set()

        def walk(entity):
            node = self.result("inspect_entity", entity=entity)
            if node["revision"] in seen:
                return
            seen.add(node["revision"])
            result.append(node)
            for children in node["slots"].values():
                for child in children:
                    walk(child)

        walk(function)
        return result

    def close(self):
        if self.p.poll() is None:
            self.p.stdin.close()
            try:
                self.p.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.p.kill()
                self.p.wait(timeout=10)
        assert self.p.returncode == 0, self.p.stderr.read()


def execute(binary, scratch, record):
    env = dict(os.environ)
    env["CARGO_NET_OFFLINE"] = "true"
    env["CARGO_TARGET_DIR"] = str(scratch / "cargo-target")
    # No hidden profile/Rust flags used to influence this generated build.
    env.pop("RUSTFLAGS", None)
    env.pop("CARGO_ENCODED_RUSTFLAGS", None)

    def run(argv, expected=0):
        p = subprocess.run([str(a) for a in argv], cwd=scratch, env=env,
                           capture_output=True, text=True, encoding="utf-8", timeout=240)
        row = {"argv": [str(a) for a in argv], "exit": p.returncode,
               "stdout": p.stdout, "stderr": p.stderr}
        record["commands"].append(row)
        if expected is not None:
            assert p.returncode == expected, row
        return row

    record["toolchain"] = {name: run([name, "--version"])["stdout"].strip()
                           for name in ("rustc", "cargo", "python")}
    projects = {}
    for label in ("structured", "text"):
        path = scratch / label
        path.mkdir()
        shutil.copy2(ROOT / "tests/project/alva.toml", path / "alva.toml")
        shutil.copytree(ROOT / "tests/project/src", path / "src")
        projects[label] = path
    original = manifest(projects["structured"] / "src")
    record["initial_source"] = original

    def check(path, expected=0):
        return run([binary, "project", "check", path / "alva.toml", "--json"], expected)

    def behavior(path, label, target):
        out = scratch / ("build-" + label)
        run([binary, "project", "build", path / "alva.toml", "--out-dir", out])
        crate = out / "demo"
        extra = (HERE / "behavior.rs").read_text(encoding="utf-8") if target else '''
#[cfg(test)] mod independent_baseline {
    use super::{demo_app, demo_model};
    #[test] fn original_behavior() {
        assert_eq!(demo_app::run(), 6);
        for (s, expected) in [(5,6), (0,1), (-9,-8)] {
            let m = demo_model::touch_size(demo_model::make_meta("k".into(), s, "e".into()));
            assert_eq!(m.size, expected);
            assert_eq!(m.key, "k"); assert_eq!(m.etag, "e");
        }
    }
}
'''
        # Add host-owned assertions to a disposable generated crate only.
        with (crate / "src/lib.rs").open("a", encoding="utf-8") as f:
            f.write(extra)
        return run(["cargo", "test", "--manifest-path", crate / "Cargo.toml"])

    baseline = projects["structured"]
    check(baseline)
    behavior(baseline, "baseline", False)
    record["baseline_behavior"] = "PASS: unary +1, metadata, run=6"
    # Ordinary source path, same fixed task and independent target evaluator.
    text = projects["text"]
    model = text / "src/model.alva"
    app = text / "src/app.alva"
    source = model.read_text(encoding="utf-8")
    before = "(fn touch_size\n    (params\n      (param m Meta))"
    assert source.count(before) == 1
    source = source.replace(before, before[:-1] + "\n      (param delta (prim i64)))")
    model.write_text(source, encoding="utf-8")
    row = check(text, None)
    assert row["exit"] != 0
    record["text_intermediate_invalid"] = True
    source = source.replace('(size (+ (field (ref m) "size") (int 1)))',
                            '(size (+ (field (ref m) "size") (ref delta)))')
    model.write_text(source, encoding="utf-8")
    a = app.read_text(encoding="utf-8")
    old = '(call demo.model.make_meta (string "a") (int 5) (string "e1"))'
    assert a.count(old) == 1
    app.write_text(a.replace(old, old + ' (int 1)'), encoding="utf-8")
    check(text)
    behavior(text, "text", True)
    record["text_behavior"] = "PASS"
    record["text_final_source"] = manifest(text / "src")
    record["text_patch"] = {p: {"before": (baseline / "src" / p).read_text(encoding="utf-8"),
                                "after": (text / "src" / p).read_text(encoding="utf-8")}
                            for p in ("model.alva", "app.alva")}

    sessions = []
    try:
        initial = Agent(binary, baseline, record["aep"], "initialize-authority")
        sessions.append(initial)
        for entity in ("demo.model.touch_size", "demo.app.run"):
            initial.result("applicable_operations", entity=entity)
        for name in ("add_param", "create_reference", "replace_expression",
                     "create_literal", "add_call_arg", "rename_entity"):
            answer = initial.call("describe_operation", expected=None, name=name)
            if not answer["ok"]:
                raise Unsupported("Missing public operation: " + name)
        initial.result("describe_construction", kind="field", include_candidates=True)
        record["before_initial_commit"] = manifest(baseline / "alva-air")
        assert not record["before_initial_commit"]
        initial.result("check_transaction")
        initial.result("commit_transaction")
        authority = baseline / "alva-air"
        record["base_authority"] = manifest(authority)
        record["base_current"] = (authority / "current").read_text()
        tx = Agent(binary, baseline, record["aep"], "api-evolution")
        stale = Agent(binary, baseline, record["aep"], "stale-rename")
        sessions.extend([tx, stale])
        stale.result("rename_entity", entity="demo.app.run", new_name="run_legacy")
        stale.result("check_transaction")
        tx.result("add_param", function="demo.model.touch_size", name="delta", type="i64")
        tx.call("check_transaction", expected=False)
        tx.call("commit_transaction", expected=False)
        assert manifest(authority) == record["base_authority"]
        record["invalid_commit_no_publication"] = True
        nodes = tx.nodes("demo.model.touch_size")
        plus = [n for n in nodes if n["fields"].get("op") == "+"]
        assert len(plus) == 1, nodes
        ref = tx.result("create_reference", name="delta")["revision"]
        tx.result("replace_expression", parent=plus[0]["revision"], child=ref, position="right")
        calls = [n for n in tx.nodes("demo.app.run")
                 if n["fields"].get("name") == "demo.model.touch_size"]
        assert len(calls) == 1, calls
        one = tx.result("create_literal", type="i64", value="1")["revision"]
        tx.result("add_call_arg", call=calls[0]["revision"], arg=one)
        record["preview"] = tx.result("preview_semantic_diff")
        tx.result("check_transaction")
        assert manifest(authority) == record["base_authority"]
        assert manifest(baseline / "src") == original
        tx.result("commit_transaction")
        record["committed_authority"] = manifest(authority)
        record["committed_current"] = (authority / "current").read_text()
        assert record["base_current"] != record["committed_current"]
        refused = stale.call("commit_transaction", expected=False)
        assert "E_AEP_CONFLICT" in json.dumps(refused), refused
        assert manifest(authority) == record["committed_authority"]
        stale.result("abort_transaction")
        record["stale_commit"] = "REJECTED: E_AEP_CONFLICT; authority unchanged"
        fresh = Agent(binary, baseline, record["aep"], "reread-authority")
        sessions.append(fresh)
        fn = fresh.result("inspect_entity", entity="demo.model.touch_size")
        assert len(fn["slots"]["params"]) == 2, fn
        record["reloaded_touch_size"] = fn
        record["reloaded_body"] = fresh.result("inspect_body", function="demo.model.touch_size")
        fresh.result("abort_transaction")
        check(baseline)
        behavior(baseline, "structured", True)
        record["structured_behavior"] = "PASS"
        assert manifest(baseline / "src") == original
        record["source_projection_unchanged"] = True
        record["repairable_invalid_staging"] = True
        record["status"] = "SUPPORTED"
    finally:
        for session in sessions:
            session.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    binary = args.binary.resolve()
    record = {"case": "metadata-signed-delta-api", "status": "FAILED",
              "model_generation_calls": 0, "input_token_api_calls": 0,
              "binary_sha256": digest(binary.read_bytes()), "commands": [], "aep": [],
              "input_hashes": {p.relative_to(ROOT).as_posix(): digest(p.read_bytes())
                               for p in [HERE / "CASE.md", HERE / "behavior.rs", HERE / "run.py",
                                         ROOT / "tests/project/alva.toml",
                                         ROOT / "tests/project/src/model.alva",
                                         ROOT / "tests/project/src/app.alva"]}}
    with tempfile.TemporaryDirectory(prefix="alva-native-api-") as temp:
        scratch = Path(temp)
        try:
            execute(binary, scratch, record)
        except Unsupported as exc:
            record.update(status="UNSUPPORTED", reason=str(exc))
        except Exception as exc:
            record.update(status="FAILED", reason=repr(exc))
        # Public deterministic tool evidence only, no user paths/environment.
        serialized = json.dumps(record, ensure_ascii=False, indent=2)
        for source, replacement in ((str(scratch), "<SCRATCH>"),
                                    (str(ROOT), "<REPO>"), (str(binary), "<ALVA>")):
            serialized = serialized.replace(json.dumps(source)[1:-1], replacement)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(json.dumps({"status": record["status"], "reason": record.get("reason"),
                      "aep_calls": len(record["aep"]), "commands": len(record["commands"])}))
    return 1 if record["status"] == "FAILED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
