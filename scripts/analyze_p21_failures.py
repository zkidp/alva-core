"""Read-only P21 archive/source analysis. No evaluator replay or model calls."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from integrations.benchmark_runtime_v2.freeze import pack_git, canonical
P21 = ROOT / "benchmarks/cross_language"
BASE = "ecadfea51ccd147f99f58ec5e891869744bc664c"
TEXT = ["05-HE41-B", "06-HE3-B", "07-HE42-B"]
NATIVE = ["04-HE23-C", "08-HE42-C", "10-HE3-C", "12-HE41-C"]


def sha(data): return hashlib.sha256(data).hexdigest()
def load(path): return json.loads(path.read_text(encoding="utf-8"))
def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def diagnostics(response):
    text = response.get("check", {}).get("stdout", "")
    if not text: return []
    try:
        return [{"code": d.get("code"), "message": d.get("message")} for d in json.loads(text)]
    except (ValueError, TypeError):
        return [{"message": "Non-JSON diagnostic", "sha256": sha(text.encode())}]


def analyze(archive):
    result = {"base": BASE, "model_generation_calls": 0, "input_token_calls": 0,
              "historical_evaluator_replays": 0, "text": [], "aep": [], "newline": []}
    history = load(P21 / "FREEZE.json")
    for name in ("tests/integrations/codex_native_test.py", "feasibility/native_api/run.py"):
        blob = subprocess.check_output(["git", "-C", str(ROOT), "show", BASE + ":" + name])
        assert b"\r" not in blob
        crlf = blob.replace(b"\n", b"\r\n")
        result["newline"].append({"path": name, "git_blob_sha256": sha(blob), "git_blob_bytes": len(blob),
                                  "crlf_sha256": sha(crlf), "crlf_bytes": len(crlf),
                                  "lf_count": blob.count(b"\n"), "historical_sha256": history["files"][name],
                                  "historical_matches_git_blob": history["files"][name] == sha(blob),
                                  "historical_matches_crlf": history["files"][name] == sha(crlf)})
    source = (P21 / "common.py").read_text(encoding="utf-8")
    result["historical_execution_finding"] = {"direct_host_subprocess": "subprocess.run(list(map(str, argv))" in source,
                                             "python_isolated_interpreter_not_os_sandbox": '"-I", "-c", script' in source}
    expected = load(P21 / "ARCHIVE.json")["sha256"]
    if not archive or not archive.is_file():
        result.update(archive_status="UNAVAILABLE", limitation="Public evidence only; first edit arguments/check sequence cannot be fully reconstructed.")
        public = load(P21 / "RESULTS.json")
        result["public_summary"] = [{"slot": r["slot"], "final": r["final"]["status"], "stop": r.get("stop_reason")} for r in public if r["slot"] in TEXT + NATIVE]
        return result
    if sha(archive.read_bytes()) != expected: raise ValueError("Historical archive SHA mismatch; do not substitute")
    result.update(archive_status="SHA256_VERIFIED", archive_sha256=expected)
    with zipfile.ZipFile(archive) as z:
        result["archive_entries"] = len(z.namelist())
        for slot in TEXT:
            row = json.loads(z.read("slots/" + slot + "/result.json"))
            events = row["tools"]
            first = next((i for i, e in enumerate(events) if e["action"] == "edit" and e["response"].get("accepted")), None)
            checks = [{"callback_ordinal": i + 1, "status": e["response"].get("status"), "diagnostics": diagnostics(e["response"])}
                      for i, e in enumerate(events) if e["action"] in ("check", "test")]
            forms = Counter(d["message"] for check in checks for d in check["diagnostics"])
            first_event = events[first] if first is not None else None
            edit_source = first_event["arguments"]["content"] if first_event else None
            result["text"].append({"slot": slot, "first_edit_callback": first + 1 if first is not None else None,
                                    "first_edit_source": edit_source,
                                    "first_edit_sha256": sha(edit_source.encode()) if edit_source else None,
                                    "usage_before_first_edit": first_event.get("observed_usage_before") if first_event else None,
                                    "checks": checks, "diagnostic_repetitions": dict(forms),
                                    "final_status": row["final"]["status"], "final_diagnostics": diagnostics(row["final"]),
                                    "stop": row["stop_reason"], "terminal": row["terminal_status"],
                                    "categories": ["UNSUPPORTED_GENERATED_SYNTAX_NOT_MISSING_LANGUAGE_CAPABILITY", "DIAGNOSTICS_NOT_CLOSED_BEFORE_STOP"],
                                    "capability_basis": "Frozen qualification has Text and AEP witnesses for this exact bounded task."})
        required = {"describe_operation": ["name"], "describe_construction": ["kind"],
                    "inspect_function": ["name"], "inspect_entity": ["entity"], "create_call": ["name"]}
        for slot in NATIVE:
            records = json.loads(z.read("slots/" + slot + "/aep-tools.json"))
            row = json.loads(z.read("slots/" + slot + "/result.json"))
            progress = []
            schemas = []
            for i, event in enumerate(records):
                req, answer = event["request"], event["response"]
                tool = req["tool"]
                missing = [name for name in required.get(tool, []) if name not in req]
                category = "SUCCESS" if answer["ok"] else "ORDINARY_AEP_REJECTION"
                if missing: category = "MISSING_REQUIRED_FIELD_OR_WRONG_PARAMETER_KEY"
                elif answer.get("error_code") == "E_AEP_UNKNOWN_TOOL": category = "OPERATION_NAME_GUESS_FAILED"
                if tool == "describe_operation" and answer["ok"]:
                    name = req.get("name")
                    schemas.append({"operation": name, "ordinal": i + 1,
                                    "later_invoked": any(r["request"]["tool"] == name for r in records[i+1:])})
                progress.append({"ordinal": i + 1, "tool": tool,
                                 "argument_keys": sorted(k for k in req if k not in ("tool", "request_id", "project")),
                                 "missing_fields": missing,
                                 "requested_name": req.get("name"),
                                 "ok": answer["ok"], "category": category,
                                 "error_code": answer.get("error_code"), "message": answer.get("message")})
            count = Counter(r["request"]["tool"] for r in records)
            target_edits = sum(r["response"]["ok"] and r["request"]["tool"] in ("replace_expression", "append_step", "change_field") for r in records)
            detached = sum(r["response"]["ok"] and r["request"]["tool"] == "create_call" for r in records) if not target_edits else None
            result["aep"].append({"slot": slot, "interface": "THIN_JSON_BRIDGE_NOT_NATIVE_MCP_SKILL",
                                   "progress": progress, "schemas": schemas,
                                   "transaction_begun": any(r["request"]["tool"] == "begin_transaction" and r["response"]["ok"] for r in records),
                                   "successful_target_edits": target_edits, "detached_call_nodes": detached,
                                   "transaction_checks": count["check_transaction"], "commit_attempts": count["commit_transaction"],
                                   "successful_commits": row["successful_commits"], "stop": row["stop_reason"],
                                   "classification": "DISCOVERY_ARGUMENT_USE_NOT_CLOSED; NO_COMMITTED_CANDIDATE",
                                   "target_unsupported": False, "basis": "Frozen AEP qualification witness passed; this trace does not reach commit."})
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.archive)
    save(args.output, result)
    bundle = pack_git(ROOT, BASE, ["tests/integrations/codex_native_test.py", "feasibility/native_api/run.py"])
    (args.output.parent / "FREEZE-V2-EXAMPLE.json").write_bytes(canonical(bundle) + b"\n")
    print(json.dumps({"archive": result["archive_status"], "text_cases": len(result["text"]), "aep_cases": len(result["aep"]), "newline": result["newline"]}, indent=2))
