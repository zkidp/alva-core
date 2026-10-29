"""Derive public scope evidence from local engineering records, no execution."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks.p33_shared_scope import reproduce as r


def follow(nodes, function, edges):
    name = function.rsplit(".", 1)[1]
    node = next(n for n in nodes.values() if n["kind"] == "function" and n["fields"].get("name") == name)
    for edge in edges:
        node = nodes[node["slots"][edge["slot"]][edge["index"]]]
    return node


def publish(folder):
    summary = json.loads((folder / "RESULTS.json").read_text())
    assert r.sha((folder / "raw.json").read_bytes()) == summary["raw_sha256"]
    assert r.sha((r.HERE / "reproduce.py").read_bytes()) == summary["driver_sha256"]
    r.validate(summary)
    raw = json.loads((folder / "raw.json").read_text())
    sharing = {}
    for label in ("MM02_original", "nonshared_alpha_control"):
        row = summary["rows"][label]
        data = raw[label]
        nodes = {}
        for function, path in row["sharing"]["paths_from_function_roots"].items():
            if path is not None:
                # Independently traverse the actual recorded graph; not merely
                # compare revision strings printed in two body renderings.
                before = follow(data["initial_graphs"][function], function, path)
                assert before == row["sharing"]["parent"]
                after = follow(data["staged_graphs"][function], function, path)
                assert r.if_revision(after) == after["revision"]
                nodes[function] = after
        sharing[label] = {"initial": row["sharing"], "staged_parents_at_same_paths": nodes,
            "changed_functions": row["changed_functions"], "preview": row["preview"],
            "observed_functions": list(row["before_body_hashes"])}
    original = sharing["MM02_original"]["staged_parents_at_same_paths"]
    assert original[r.TARGET] == original[r.OTHER]
    assert original[r.TARGET]["revision"] != r.SHARED
    validation = {"status": "PASS", "model_generation_calls": 0, "input_token_calls": 0,
        "p29_original_result_reproduced": True, "historical_inputs_modified": False,
        "raw_hash_verified": True, "parent_content_hash_recomputed": True,
        "initial_and_staged_reference_paths_verified": True,
        "preview_lists_all_observed_changed_functions_in_this_component": True,
        "nonshared_control": "ESTABLISHED_FOR_THIS_PARENT; other descendant nodes may still be shared",
        "no_core_or_interface_change": True}
    r.prior.save(r.HERE / "RESULTS.json", summary)
    r.prior.save(r.HERE / "SHARING.json", sharing)
    r.prior.save(r.HERE / "VALIDATION.json", validation)
    print("P33 public evidence verified; no model / candidate execution")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("folder", type=Path)
    publish(p.parse_args().folder)
