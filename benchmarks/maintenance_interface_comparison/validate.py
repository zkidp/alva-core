"""Independent result/evidence consistency audit; no task repair or model calls."""
import argparse
import base64
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from integrations.benchmark_runtime_v2.freeze import canonical, sha

HERE = Path(__file__).parent


def audit(directory):
    frozen = json.loads((HERE / "FREEZE.json").read_text())
    batch = json.loads((directory / "RESULTS.json").read_text())
    records = []
    by_id = {r["id"]: r for r in batch["rows"]}
    assert len(by_id) == len(batch["rows"])
    assert len(by_id) <= 24
    for entry in frozen["schedule"]:
        if entry["id"] not in by_id:
            continue
        path = directory / entry["id"]
        r = json.loads((path / "record.json").read_text())
        assert r["model_tasks_started"] in (0, 1)
        assert r["task"] == entry["task"] and r["arm"] == entry["arm"] and r["repeat"] == entry["repeat"]
        checked = {"id": entry["id"], "record_sha256": sha((path / "record.json").read_bytes())}
        if (path / "cleanup.json").exists():
            cleanup = json.loads((path / "cleanup.json").read_text())
            assert cleanup.get("confirmed") is True
            checked["owner_cleanup_confirmed"] = True
        else:
            assert r.get("infrastructure_hold")
        evidence_path = path / "linux.json"
        if not evidence_path.exists():
            assert r.get("infrastructure_hold")
            checked["incomplete_infrastructure_evidence"] = True
            records.append(checked)
            continue
        e = json.loads(evidence_path.read_text())
        assert e["status"] == "CLOSED"
        snapshot = {p: base64.b64decode(v) for p, v in e["final_files"].items()}
        receipt = sha(canonical({p: sha(data) for p, data in snapshot.items()}))
        assert e["final"]["tested_snapshot_sha256"] == receipt
        checked.update(exact_test_snapshot_bound=True, linux_evidence_sha256=sha(evidence_path.read_bytes()))
        if r.get("outcome", {}).get("correct"):
            assert r["terminal_status"] == "completed" and not r.get("infrastructure_hold")
            assert e["final"]["goal"]["status"] == e["final"]["regression"]["status"] == "PASS"
            a, b = e["initial_authority"], e["final_authority"]
            assert a["modules"] == b["modules"] and set(a["functions"]) == set(b["functions"])
            changed = []
            for name in a["functions"]:
                before, after = a["functions"][name], b["functions"][name]
                assert {k: v for k, v in before.items() if k != "body"} == {k: v for k, v in after.items() if k != "body"}
                if before["body"] != after["body"]:
                    changed.append(name)
            assert changed == frozen["tasks"][entry["task"]]["policy"]["authorized_functions"]
            if entry["arm"] == "N":
                commits = [c for c in e["calls"] if c.get("request", {}).get("method") == "tools/call" and
                    c["request"]["params"]["name"] == "commit_transaction" and not c.get("response", {}).get("isError")]
                assert commits and "alva-air/current" in snapshot
                assert commits[-1]["response"]["structuredContent"]["revision"] == b["project_revision"]
                original = frozen["tasks"][entry["task"]]["bundle"]
                for item in original["payload"]["entries"]:
                    assert snapshot[item["path"]] == base64.b64decode(item["base64"])
            checked["successful_completion_conjunction_verified"] = True
        records.append(checked)
    assert sum(r["model_tasks_started"] for r in batch["rows"]) == batch["model_tasks_started"]
    return {"status": "PASS", "scope": "retained evidence consistency, not independent human oracle review",
            "model_slots_started": batch["model_tasks_started"], "observed_records": len(records),
            "generation_calls_by_this_validator": 0, "records": records}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("directory", type=Path)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    result = audit(args.directory)
    if args.output:
        args.output.write_bytes(json.dumps(result, indent=2).encode() + b"\n")
    print(json.dumps(result, indent=2))
