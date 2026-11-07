"""Real owned Linux T/N qualification; deterministic witnesses, zero models."""
import argparse
import copy
import json
from pathlib import Path
import re
from types import SimpleNamespace

from benchmarks.compact_deepseek.runtime import Slot
from benchmarks.compact_maintenance.contract import study_tools
from benchmarks.maintenance_interface_comparison import pilot as prior
from benchmarks.maintenance_design import witnesses as old_witnesses
from benchmarks.p37_maintenance_qualification import witnesses as p37
from integrations.benchmark_runtime_v2.freeze import decode, sha, canonical

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent


def design():
    value = json.loads((HERE.parent / "compact_maintenance/REGISTRATION.json").read_bytes())
    value = copy.deepcopy(value)
    value.update(schema="compact-deepseek-design/v1", model="deepseek-flash", provider="deepseek",
                 transport="official Chat Completions HTTP; one initial user turn plus tool continuations",
                 api_parameters={"thinking": {"type": "enabled"}, "reasoning_effort": "low", "max_tokens": 8192,
                                 "stream": False}, request_timeout_seconds=90)
    return value


def end_form(text, start):
    depth, quote, escape, comment = 0, False, False, False
    for i in range(start, len(text)):
        c = text[i]
        if comment:
            comment = c != "\n"
        elif quote:
            if escape: escape = False
            elif c == "\\": escape = True
            elif c == '"': quote = False
        elif c == ';': comment = True
        elif c == '"': quote = True
        elif c == '(': depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0: return i + 1
    raise ValueError("Unclosed deterministic witness")


def replacement(task):
    source = decode(task["bundle"], task["bundle"]["payload_sha256"])
    public = task["public_task"]
    changed = old_witnesses.text_change(public["id"], source) if public["id"] in ("MM01", "MM02") else p37.text_change(public, source)
    paths = [p for p in source if source[p] != changed[p]]
    assert len(paths) == 1
    text = changed[paths[0]].decode()
    name = public["target"].rsplit(".", 1)[1]
    start = re.search(r"\(fn\s+" + re.escape(name) + r"(?=\s|\))", text).start()
    body = text.index("(body", start)
    assert body < end_form(text, start)
    return changed, text[body:end_form(text, body)]


def main(args):
    frozen = design()
    args.output.mkdir(parents=True, exist_ok=False)
    rows = []
    for ident, task in frozen["tasks"].items():
        changed, fragment = replacement(task)
        for arm in ("T", "N"):
            entry = {"id": "probe-" + ident + "-" + arm, "task": ident, "arm": arm}
            slot = None
            row = dict(entry)
            try:
                slot = Slot(args.output, entry, frozen, SimpleNamespace(connection=args.connection))
                initial = slot.tool("study_check", {})
                assert initial["status"] == "PASS", initial
                unmet = slot.tool("study_test", {})
                assert unmet["status"] == "TEST_FAIL", unmet
                for name, text in frozen["docs"].items():
                    assert slot.tool("study_doc", {"path": name})["content"] == text
                assert len(study_tools(arm)) == (10 if arm == "T" else 8)
                if arm == "N":
                    def call(name, **kw):
                        answer = slot.tool(name, kw)
                        assert not answer.get("isError"), answer
                        return answer["structuredContent"]
                    tx = call("begin_transaction", project="/work/project/alva.toml")["transaction_id"]
                    body = call("read_function", transaction_id=tx, function=task["public_task"]["target"])
                    call("replace_function_body", transaction_id=tx, function=task["public_task"]["target"],
                         expected_body_revision=body["body_revision"], body=fragment)
                    assert call("check_transaction", transaction_id=tx) == {"problems": []}
                    call("preview_semantic_diff", transaction_id=tx)
                    commit = call("commit_transaction", transaction_id=tx)
                    row["commit"] = commit
                    row["native_schemas"] = slot.native.schemas
                else:
                    original = decode(task["bundle"], task["bundle"]["payload_sha256"])
                    for path, data in changed.items():
                        if data != original[path]:
                            rev = slot.tool("study_revision", {})["revision"]
                            assert slot.tool("study_write", {"revision": rev, "path": path, "content": data.decode()})["accepted"]
                assert slot.tool("study_test", {})["status"] == "PASS"
                slot.tool("study_finish", {})
            finally:
                if slot:
                    slot.close()
            evidence = json.loads(slot.evidence.read_bytes())
            outcome = prior.score(task, evidence)
            assert outcome["correct"], outcome
            if arm == "N":
                assert outcome["air_published"] and outcome["fresh_project_revision"] == row["commit"]["revision"]
            evaluations = [c["evaluation"] for c in evidence["calls"] if c.get("action") == "test"]
            assert evaluations[0]["goal"]["status"] == "TEST_FAIL" and evaluations[0]["regression"]["status"] == "PASS"
            row.update(status="PASS", outcome=outcome, evidence_sha256=sha(slot.evidence.read_bytes()),
                       cleanup=json.loads((slot.path / "cleanup.json").read_bytes()))
            rows.append(row)
            print(json.dumps({"id": entry["id"], "status": "PASS"}), flush=True)
    result = {"status": "PASS", "model_generation_calls": 0, "input_token_api_calls": 0,
              "design_sha256": sha(canonical(frozen)), "rows": rows}
    (args.output / "PREFLIGHT.json").write_bytes(json.dumps(result, indent=2).encode() + b"\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--connection", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    main(p.parse_args())
