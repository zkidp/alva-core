"""Independent retained-evidence checks; never an input to the mechanisms."""
import argparse
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from integrations.benchmark_runtime_v2.freeze import sha


def validate(directory):
    result = json.loads((directory / "RESULTS.json").read_text())
    manifest = json.loads((directory / "ARCHIVE.json").read_text())
    assert sha((directory / "RAW.zip").read_bytes()) == manifest["sha256"]
    assert (directory / "RAW.zip").stat().st_size == manifest["bytes"]
    checked = []
    with zipfile.ZipFile(directory / "RAW.zip") as z:
        assert sorted(z.namelist()) == [f"C{i}-raw.json" for i in range(1, 5)]
        for row in result["rows"]:
            data = z.read(row["id"] + "-raw.json")
            raw = json.loads(data)
            record = {"id": row["id"], "raw_sha256": sha(data), "status": row["status"]}
            if row["status"] != "EXECUTED":
                assert raw.get("error")
                record["blocker_retained"] = True
                checked.append(record)
                continue
            for mode in ("quarantine", "guarded"):
                evidence, reported = raw[mode], row[mode]
                assert evidence["before"] == reported["before"]
                assert evidence["staged"] == reported["staged"]
                assert evidence["fresh"] == reported["fresh"]
                commit_calls = [c for c in evidence["calls"] if c["operation"] == "commit_transaction"]
                assert len(commit_calls) == 1
                assert evidence["commit"] == commit_calls[0]["response"]
                assert reported["committed"] == (not evidence["commit"].get("isError", False))
                original = reported["before"]["functions"]
                staged = reported["staged"]["functions"]
                fresh = reported["fresh"]["functions"]
                expected = staged if reported["committed"] else original
                assert {f: n["body"] for f, n in expected.items()} == {f: n["body"] for f, n in fresh.items()}
                if reported["committed"]:
                    assert reported["commit"]["revision"] == reported["fresh"]["project_revision"]
                    assert "alva-air/current" in evidence["authority"]
                if mode == "guarded":
                    decisions = [e["decision"] for e in evidence["ledger"] if e["event"] == "scope_decision"]
                    assert decisions == [reported["guard"]]
                    dispatch = [e for e in evidence["ledger"] if e["event"] == "native_dispatch" and
                                e.get("params", {}).get("name") == "commit_transaction"]
                    assert len(dispatch) == reported["guard_native_commit_dispatches"] == int(reported["committed"])
            text = raw["text_evaluation"]
            native = raw["native_evaluation"]
            assert text["observations"] == native["observations"] == row["native_candidate"]["observations"]
            assert row["guarded_authority"]["status"] == raw["final_evaluation"]["status"]
            for key in ("baseline", "text_evaluation", "native_evaluation", "final_evaluation"):
                evaluation = raw[key]
                assert evaluation["check"]["exit"] == evaluation["build"]["exit"] == 0
                assert "test result:" in evaluation["tests"]["stdout"]
            record.update(actual_commit_and_fresh_checked=True, independent_evaluations_checked=True,
                          actual_guard_dispatch_checked=True, same_text_native_observations=True)
            checked.append(record)
    return {"archive_integrity": "PASS", "wave_code": result["code_commit"], "records": checked}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("directory", type=Path)
    args = p.parse_args()
    print(json.dumps(validate(args.directory), indent=2))
