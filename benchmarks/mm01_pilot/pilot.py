"""MM01 two-slot adapter over the existing P21/P26 controller and P23 service.

prepare never starts a model turn. run requires a clean, pushed freeze and an
exclusive attempt ledger. No historical candidate or trajectory is consumed.
"""
import argparse
import base64
import copy
import difflib
import json
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import time
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks.native_prospective import pilot as old
from integrations.benchmark_runtime_v2.freeze import canonical, decode, pack_git, sha

HERE = Path(__file__).resolve().parent
BASE = "8df4d24a55f1176a9fc8b9eaf5292c8b088ff5b4"
BRANCH = "codex/mm01-maintenance-model-pilot"
CONFIG = dict(old.CONFIG, token_observation_threshold=600000)
PATHS = ("alva.toml", "src/app.alva", "src/model.alva")
save = old.save
TOOLS = [{"name": "study", "description": (
    "Isolated maintenance workbench. arguments is a JSON-encoded object. revision:{} returns source revision/files. "
    "read:{revision,path,start?:1,count?:120}, count 1..200, returns exact lines/EOF/next_start. "
    "search:{revision,text}. diff:{revision} returns baseline Git diff in T. "
    "T edit:{revision,path,old,new} applies exactly one unique exact text replacement in src/*.alva. "
    "S edits only through native MCP; its source projection may remain unchanged. "
    "check:{} is ordinary project check; test:{} builds and runs isolated independent task/regression tests, returns only combined result plus compiler diagnostics. "
    "doc:{path} reads language.md (both) or official Skill paths (S). finish:{} hands off final state. "
    "No shell, arbitrary paths, evaluator source, network or CLI fallback."),
    "inputSchema": {"type": "object", "properties": {
        "action": {"type": "string", "enum": ["revision", "read", "search", "edit", "diff", "check", "test", "doc", "finish"]},
        "arguments": {"type": "string"}}, "required": ["action", "arguments"], "additionalProperties": False}}]
INSTRUCTIONS = (
    "Use only study and, in S, the ALVA native MCP tools. No shell, apply_patch, web, other directories, sessions or delegation. "
    "The complete approved candidate is /work/project/alva.toml inside Linux isolation, NOT the Windows working directory. "
    "Only alva.toml, src/app.alva and src/model.alva are candidate inputs. The manifest is protected; source edits may change src/*.alva. "
    "Preserve public non-target requirements; no raw AIR or generated code edits. "
    "Both conditions may read the original sources and language.md. Use study check/test for compiler/build/independent evaluation. "
    "Tests expose only bounded pass/fail and ordinary compiler diagnostics, not hidden assertions. "
    "T uses revision-bound exact source editing and ordinary Git diff. S uses only native MCP for mutation and the official ALVA Skill; no CLI fallback. "
    "The SDK is preflighted; doctor readiness is host-confirmed. S begins source-only; its first commit creates AIR authority without rewriting source. "
    "One task turn; at most 80 model tool calls, 480 active-turn seconds, 600000 cumulative reported tokens (observation threshold, not provider hard cap), 20 seconds interrupt confirmation grace. "
    "Use finish when handing off. Do not access any other material or delegate.")


def valid(action, args):
    required = {"revision": {}, "diff": {"revision": str}, "read": {"revision": str, "path": str},
                "search": {"revision": str, "text": str}, "edit": {"revision": str, "path": str, "old": str, "new": str},
                "doc": {"path": str}, "check": {}, "test": {}, "finish": {}}
    if action not in required or not isinstance(args, dict):
        return {"error": "INVALID_ARGUMENTS"}
    for key, typ in required[action].items():
        if key not in args:
            return {"error": "MISSING_REQUIRED_ARGUMENT", "argument": key}
        if type(args[key]) is not typ:
            return {"error": "INVALID_ARGUMENT_TYPE", "argument": key}
    allowed = set(required[action]) | ({"start", "count"} if action == "read" else set())
    if set(args) - allowed:
        return {"error": "UNKNOWN_ARGUMENT", "arguments": sorted(set(args) - allowed)}
    return None


class Slot(old.Slot):
    def __init__(self, runtime, entry, frozen, args):
        self.path = runtime / entry["id"]
        self.path.mkdir(parents=True, exist_ok=False)
        self.entry, self.frozen, self.calls = entry, frozen, 0
        self.ready, self.evidence = self.path / "ready.json", self.path / "linux.json"
        self.service = HERE / "service.py"
        self.config = {"bundle": frozen["task"]["bundle"], "arm": entry["arm"],
                       "vectors": frozen["assertions"], "docs": frozen["docs"],
                       "ready": old.linux(self.ready), "evidence": old.linux(self.evidence),
                       "observer_evidence": old.linux(self.path / "observer.jsonl"),
                       "alva": args.alva, "toolchain": args.toolchain, "registry": args.registry}
        save(self.path / "config.json", self.config)
        self.process = subprocess.Popen(["wsl.exe", "-d", "Ubuntu-26.04", "--exec", "python3",
            old.linux(self.service), "--role", "server", "--config", old.linux(self.path / "config.json")],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        deadline = time.monotonic() + 30
        while not self.ready.exists():
            if self.process.poll() is not None:
                raise old.InfrastructureError("SERVICE_EXIT:" + self.process.communicate()[1].decode(errors="replace")[-2000:])
            if time.monotonic() > deadline:
                self.process.kill(); self.process.communicate()
                raise old.InfrastructureError("SERVICE_READY_TIMEOUT")
            time.sleep(.05)

    def dispatch(self, action, args):
        if action in ("stop", "snapshot"):
            return super().dispatch(action, args)  # trusted control, not advertised
        error = valid(action, args)
        if error:
            return error
        self.calls += 1
        if self.calls > 80:
            return {"error": "MODEL_TOOL_LIMIT_NO_DISPATCH"}
        if action == "doc":
            docs = {"language.md": self.frozen["language"]}
            if self.entry["arm"] == "N":
                docs.update(self.frozen["docs"])
            return {"content": docs[args["path"]]} if args["path"] in docs else {"error": "DOC_PATH_NOT_ALLOWED"}
        if action in ("check", "test", "finish"):
            return super().dispatch(action, args)
        if self.entry["arm"] == "T":
            return super().dispatch("edit" if action == "edit" else "read", dict(args, _action=action))
        if action == "edit":
            return {"error": "NATIVE_MUTATION_REQUIRED"}
        snapshot = super().dispatch("snapshot", {})["files"]
        source = {p: base64.b64decode(snapshot[p]) for p in PATHS}
        rev = sha(json.dumps([(p, sha(source[p])) for p in PATHS], separators=(",", ":")).encode())
        if action == "revision":
            return {"revision": rev, "files": list(PATHS), "authority": "AIR" if "alva-air/current" in snapshot else "SOURCE"}
        if args["revision"] != rev:
            return {"error": "STALE_REVISION", "current_revision": rev}
        if action == "search":
            return {"revision": rev, "matches": [{"path": p, "line": i, "text": line}
                for p in PATHS for i, line in enumerate(source[p].decode().splitlines(), 1) if args["text"] in line]}
        if action == "diff":
            return {"source_projection_unchanged": all(source[p] == decode(self.frozen["task"]["bundle"], self.frozen["task"]["bundle"]["payload_sha256"])[p] for p in PATHS),
                    "authority_files": {p: sha(base64.b64decode(v)) for p, v in snapshot.items() if p.startswith("alva-air/")},
                    "note": "Use native preview_semantic_diff for staged semantic changes; source projection is not AIR authority."}
        if args["path"] not in source:
            return {"error": "PATH_NOT_ALLOWED"}
        lines = source[args["path"]].decode().splitlines(keepends=True)
        start, count = args.get("start", 1), args.get("count", 120)
        if type(start) is not int or type(count) is not int or not 1 <= start <= len(lines) or not 1 <= count <= 200:
            return {"error": "INVALID_READ_RANGE", "legal_start": [1, len(lines)], "legal_count": [1, 200]}
        end = min(len(lines), start + count - 1)
        return {"revision": rev, "content": "".join(lines[start - 1:end]), "actual_start": start, "actual_end": end,
                "eof": end == len(lines), "next_start": None if end == len(lines) else end + 1}


def host(slot):
    class C(old.Controller):
        def rpc(self, method, params, timeout=30):
            if method == "thread/start":
                params = copy.deepcopy(params)
                params["developerInstructions"] = slot.frozen["developer_instructions"]
                save(slot.path / "thread-start.json", params)
            return super().rpc(method, params, timeout)
        def interrupt(self):
            if self.interrupt_id is None and hasattr(self, "record"):
                self.record["first_interrupt_event_boundary"] = len(self.record["events"])
            return super().interrupt()
    with patch.object(old, "Controller", C), patch.object(old, "CONFIG", CONFIG), patch.object(old, "TOOLS", TOOLS):
        return old.host(slot)


def bind_runtime(frozen):
    names = ["benchmarks/native_prospective/pilot.py", "benchmarks/native_prospective/service.py",
             "benchmarks/cross_language/controller.py", "benchmarks/native_mcp_skill/proxy.py",
             "benchmarks/p28_optional_descriptor/observer.py", "tests/integrations/codex_native_test.py"]
    names += [p.relative_to(ROOT).as_posix() for p in (ROOT / "integrations/benchmark_runtime_v2").glob("*.py")]
    names += [p.relative_to(ROOT).as_posix() for p in HERE.glob("*.py")]
    frozen["files"] = {p: sha((ROOT / p).read_bytes()) for p in sorted(set(names))}
    frozen["runtime_bytes"] = {p: base64.b64encode((ROOT / p).read_bytes()).decode() for p in frozen["files"]}


def check_identity(frozen, args):
    assert old.sdk_identity(args) == frozen["sdk_identity"]
    exe = Path(shutil.which("codex"))
    assert sha(exe.read_bytes()) == frozen["codex_binary_sha256"]
    assert subprocess.check_output([str(exe), "--version"], text=True).strip() == frozen["codex"]


def prepare(args, runtime):
    from benchmarks.maintenance_design import witnesses
    task = next(c for c in json.loads((ROOT / "benchmarks/maintenance_design/TASK-CANDIDATES.json").read_text())["candidates"] if c["id"] == "MM01")
    task = {k: task[k] for k in ("id", "target", "requirement", "bundle", "functions", "public_inputs")}
    decode(task["bundle"], task["bundle"]["payload_sha256"])
    paths = ["integrations/skills/alva/" + p for p in ("SKILL.md", "references/workflow.md", "references/diagnostics.md", "references/examples.md")]
    docs_bundle = pack_git(ROOT, BASE, paths + ["alva/README.md"])
    docbytes = decode(docs_bundle, docs_bundle["payload_sha256"])
    docs = {p.removeprefix("integrations/skills/alva/"): docbytes[p].decode() for p in paths}
    prompt = ("MM01 existing-code maintenance.\n" + task["requirement"] +
              "\nProject: /work/project/alva.toml. Initial source-only input paths: alva.toml, src/app.alva, src/model.alva. "
              "Use the permitted tools to inspect and modify the existing project, then check/test and finish. "
              "Generic language documentation is available using study doc path language.md.\n")
    frozen = {"schema": "alva-mm01-pilot/v1", "base": BASE, "config": CONFIG, "tools": TOOLS,
              "task": task, "docs": docs, "docs_bundle": docs_bundle, "language": docbytes["alva/README.md"].decode(),
              "assertions": {"goal": witnesses.goals("MM01"), "regression": witnesses.regressions("MM01")},
              "developer_instructions": INSTRUCTIONS, "sdk_identity": old.sdk_identity(args),
              "codex": subprocess.check_output([shutil.which("codex"), "--version"], text=True).strip(),
              "codex_binary_sha256": sha(Path(shutil.which("codex")).read_bytes()),
              "binary_sha256": "29e5abd692206876a3929112e471cb99ce457d478dcd81c50cb006aa3b958257",
              "public_task_input": prompt,
              "schedule": [{"id": "MM01-T", "arm": "T", "condition": "T", "prompt": prompt},
                           {"id": "MM01-S", "arm": "N", "condition": "S", "prompt": prompt +
                            "\n$alva\nComplete official Skill and references follow verbatim:\n" +
                            "".join("\n--- " + name + " ---\n" + body for name, body in docs.items())}],
              "scope": {"editable_source": ["src/app.alva", "src/model.alva"], "protected": ["alva.toml"],
                        "native_store": "only native MCP writes alva-air/", "non_target": "public constructor/accessor/application/key/etag requirements; not gold patch equality"},
              "test_feedback": "project compiler diagnostics and combined independent behavior bool only; no assertion source, values or case outputs",
              "publication": {"T": "explicit finish, not each edit", "S": "actual changed AIR commit, not detached or no-op staging"},
              "stale_perturbations": "NOT_EXERCISED_CONFLICT_FREE_PAIR",
              "generation_calls_before_freeze": 0}
    runtime.mkdir(parents=True, exist_ok=False)
    validation = {"controller": old.simulated_validation(), "generation_calls": 0}
    for entry in frozen["schedule"]:
        slot = Slot(runtime, dict(entry, id="preflight-" + entry["condition"]), frozen, args)
        h = None
        try:
            h, c, thread, inventory = host(slot)
            if entry["arm"] == "N":
                assert len(inventory[0]["tools"]) == 20
                frozen["native_tools"] = inventory[0]["tools"]
                call = lambda name, arguments: c.rpc("mcpServer/tool/call", {"threadId": thread["thread"]["id"], "server": "alva", "tool": name, "arguments": arguments})
                b = call("begin_transaction", {"project": "/work/project/alva.toml"})
                assert not b.get("isError"), b
                tx = b["structuredContent"]["transaction_id"]
                assert not call("inspect_body", {"transaction_id": tx, "function": task["target"]}).get("isError")
                assert not call("abort_transaction", {"transaction_id": tx}).get("isError")
            else:
                assert not inventory
                rev = slot.dispatch("revision", {})["revision"]
                assert slot.dispatch("search", {"revision": rev, "text": "touch_size"})["matches"]
                assert slot.dispatch("search", {"revision": rev, "text": "synthetic_absent_38c9"})["matches"] == []
                assert slot.dispatch("read", {"revision": rev, "path": "src/model.alva", "count": 1})["next_start"] == 2
                assert slot.dispatch("read", {"revision": rev, "path": "../witnesses.py"})["error"] == "PATH_NOT_ALLOWED"
                assert slot.dispatch("edit", {"revision": rev, "path": "alva.toml", "old": "x", "new": "y"})["error"] == "PROTECTED_PATH"
                a = slot.dispatch("edit", {"revision": rev, "path": "src/model.alva", "old": '(version "0.1.0")', "new": '(version "0.1.0") '})
                assert a["accepted"]
                assert slot.dispatch("edit", {"revision": rev, "path": "src/model.alva", "old": "x", "new": "y"})["error"] == "STALE_REVISION"
                assert slot.dispatch("diff", {"revision": a["revision"]})["diff"]
                assert slot.dispatch("edit", {"revision": a["revision"], "path": "src/model.alva", "old": '(version "0.1.0") ', "new": '(version "0.1.0")'})["revision"] == rev
            assert slot.dispatch("check", {})["status"] == "PASS"
            assert slot.dispatch("test", {})["status"] == "TEST_FAIL"  # unchanged original requirement absent
        finally:
            if h:
                h.close()
            slot.close()
        evidence = json.loads(slot.evidence.read_text())
        assert evidence["status"] == "CLOSED" and not evidence.get("error") and not evidence.get("worker_error")
        assert evidence["initial_authority"] == evidence["final_authority"]
        assert evidence["final"]["regression"]["exit"] == 0 and evidence["final"]["goal"]["exit"] != 0
        assert set(evidence["final_files"]) == set(PATHS)
        validation[entry["condition"]] = {"status": "PASS", "actual_appserver": True, "model": thread["model"],
            "native_tools": len(inventory[0]["tools"]) if inventory else 0, "authority_unchanged": True,
            "baseline_check_build_regression": "PASS", "baseline_goal_expected_fail": True,
            "fresh_namespace": True, "generation_calls": 0}
    validation["status"] = "PASS"
    frozen["validation"] = validation
    frozen["status"] = "FROZEN_BEFORE_GENERATION"
    bind_runtime(frozen)
    save(HERE / "PREFLIGHT.json", validation)
    save(HERE / "FREEZE.json", frozen)
    print("MM01 preflight PASS. Commit/push freeze before any model turn.", flush=True)


def summarize(entry, record, evidence, observations):
    initial, final = evidence.get("initial_authority", {}), evidence.get("final_authority", {})
    before, after = initial.get("bodies", {}), final.get("bodies", {})
    target = "demo.model.touch_size"
    changed = bool(before.get(target) and after.get(target) and before[target] != after[target])
    operations = [c for c in evidence.get("calls", []) if c.get("request", {}).get("method") == "tools/call"]
    counts = {}
    for c in operations:
        n = c["request"]["params"]["name"]
        counts[n] = counts.get(n, 0) + 1
    compiled = evidence.get("final", {})
    status = lambda k: "UNKNOWN" if k not in compiled else "PASS" if compiled[k]["exit"] == 0 else "FAIL"
    snapshot = evidence.get("final_files", {})
    initial_files = decode(json.loads((HERE / "FREEZE.json").read_text())["task"]["bundle"], "6b2fbdf1d0b7929cc239a2db810a35549228a613d5a778f93e4ae3d0e39ac090")
    files_changed = [p for p, v in snapshot.items() if p not in initial_files or base64.b64decode(v) != initial_files[p]]
    published = "alva-air/current" in snapshot
    commits = sum(c["request"]["params"]["name"] == "commit_transaction" and not c["response"].get("isError") for c in operations)
    manifest_ok = snapshot.get("alva.toml") == base64.b64encode(initial_files["alva.toml"]).decode()
    scope = "PASS" if manifest_ok and status("regression") == "PASS" else "UNKNOWN" if status("regression") == "UNKNOWN" else "FAIL"
    valid_publication = entry["arm"] == "T" or (published and commits > 0 and changed)
    completed = changed and status("goal") == status("regression") == scope == "PASS" and valid_publication and record.get("terminal_status") == "completed"
    result = {k: record.get(k) for k in ("model_tasks_started", "freeze_commit", "tool_calls", "usage", "usage_complete", "terminal_status", "stop_reason", "interrupt_ack", "elapsed_seconds", "infrastructure_hold", "first_interrupt_event_boundary")}
    result.update(id=entry["id"], condition=entry["condition"], target_changed=changed,
        task_correctness=status("goal"), regression_correctness=status("regression"), scope_status=scope,
        independent_status=compiled.get("status", "UNKNOWN"), check=status("check"), build=status("build"),
        initial_authority=initial, final_authority=final, changed_files=files_changed,
        changed_bodies=[f for f in before if after.get(f) and after[f] != before[f]],
        native_commits=commits, native_operation_counts=counts,
        native_operation_errors=sum(bool(c["response"].get("isError")) for c in operations),
        air_authority_published=published, fresh_process_authority_reread="bodies" in final,
        source_projection_unchanged=all(snapshot.get(p) == base64.b64encode(v).decode() for p, v in initial_files.items()),
        text_evaluable_final_source=entry["arm"] == "T" and compiled.get("status") in ("PASS", "TEST_FAIL"),
        explicit_finish=any(e.get("method") == "item/tool/call" and e.get("params", {}).get("arguments", {}).get("action") == "finish" for e in record.get("events", [])),
        staged_target_change_observed=any(o["changed_from_transaction_start"] for o in observations),
        observer_calls=sum(o["observer_calls"] for o in observations), observer_is_model_feedback=False,
        stale_write="NOT_EXERCISED", recovery="NOT_EXERCISED", provider_requests=None, dollar_cost=None,
        hard_provider_token_cap=False, disposition="COMPLETED_CORRECT_MAINTENANCE" if completed else (
            "NO_COMMITTED_CANDIDATE" if entry["arm"] == "N" and not valid_publication else compiled.get("status", "UNKNOWN")))
    return result


def run(args, runtime):
    frozen = json.loads((HERE / "FREEZE.json").read_text())
    assert frozen["status"] == "FROZEN_BEFORE_GENERATION" and frozen["validation"]["status"] == "PASS"
    assert subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True) == ""
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    assert subprocess.check_output(["git", "ls-remote", "origin", "refs/heads/" + BRANCH], cwd=ROOT, text=True).split()[0] == head
    for p, digest in frozen["files"].items():
        assert sha((ROOT / p).read_bytes()) == digest, p
    check_identity(frozen, args)
    runtime.mkdir(parents=True, exist_ok=False)
    save(runtime / "STARTED.json", {"freeze_commit": head, "maximum_model_tasks": 2})
    public = []
    for entry in frozen["schedule"]:
        record = {"model_tasks_started": 0, "freeze_commit": head}
        slot = h = c = None
        print("START " + entry["id"], flush=True)
        try:
            slot = Slot(runtime, entry, frozen, args)
            h, c, thread, inventory = host(slot)
            assert (inventory[0]["tools"] if inventory else None) == (frozen["native_tools"] if entry["arm"] == "N" else None)
            save(slot.path / "turn-start.json", {"threadId": thread["thread"]["id"], "input": [{"type": "text", "text": entry["prompt"]}],
                    "effort": CONFIG["effort"], "approvalPolicy": "never", "sandboxPolicy": {"type": "readOnly"}})
            record["model_tasks_started"] = 1
            turn = c.rpc("turn/start", json.loads((slot.path / "turn-start.json").read_text()))
            c.bind(thread, turn)
            c.record = record
            with patch.object(old, "CONFIG", CONFIG):
                old.drive(c, slot, record)
        except Exception as exc:
            record["infrastructure_hold"] = type(exc).__name__ + ": " + str(exc)
            if c and c.turn_id:
                try:
                    c.interrupt()
                    deadline = time.monotonic() + 20
                    terminal = None
                    while time.monotonic() < deadline:
                        try:
                            terminal = c.observe(c.next(.5)) or terminal
                        except queue.Empty:
                            continue
                        if terminal and c.interrupt_ack:
                            break
                    record["termination_unconfirmed"] = not (terminal and c.interrupt_ack)
                except Exception:
                    record["termination_unconfirmed"] = True
        finally:
            if h:
                h.close()
            if slot:
                try:
                    slot.close()
                except Exception as exc:
                    record["infrastructure_hold"] = "CLEANUP:" + str(exc)
        evidence = json.loads(slot.evidence.read_text()) if slot and slot.evidence.exists() else {}
        if evidence.get("error") or evidence.get("worker_error"):
            record["infrastructure_hold"] = "SERVICE:" + str(evidence.get("error") or evidence.get("worker_error"))
        op = slot.path / "observer.jsonl" if slot else None
        observations = [json.loads(line) for line in op.read_text().splitlines()] if op and op.exists() else []
        public.append(summarize(entry, record, evidence, observations))
        save(runtime / entry["id"] / "record.json", record)
        save(runtime / "progress.json", [{k: r.get(k) for k in ("id", "model_tasks_started", "terminal_status", "infrastructure_hold")} for r in public])
        print("CLOSED " + entry["id"] + " " + public[-1]["disposition"], flush=True)
        if public[-1].get("infrastructure_hold"):
            break
    archive = runtime / "RAW.zip"
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(runtime.rglob("*")):
            if p.is_file() and p != archive and "model" not in p.relative_to(runtime).parts:
                z.write(p, p.relative_to(runtime).as_posix())
    save(HERE / "ARCHIVE.json", {"sha256": sha(archive.read_bytes()), "bytes": archive.stat().st_size,
        "entries": len(zipfile.ZipFile(archive).namelist()), "controlled_local_only": True})
    save(HERE / "RESULTS.json", {"status": "COMMON_INFRASTRUCTURE_HOLD" if any(r.get("infrastructure_hold") for r in public) else "CLOSED_COMPLETE",
         "freeze_commit": head, "scheduled": 2, "executed": sum(r["model_tasks_started"] for r in public), "slots": public})
    print("STOP; no extra model tasks.", flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("prepare", "run"))
    p.add_argument("--attempt", required=True)
    for name in ("alva", "toolchain", "registry"):
        p.add_argument("--" + name, required=True)
    args = p.parse_args()
    (prepare if args.mode == "prepare" else run)(args, ROOT / ".local/mm01-pilot" / args.attempt)
