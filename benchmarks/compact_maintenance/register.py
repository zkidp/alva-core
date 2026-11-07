"""Freeze study design and public/private input bindings, never runtime readiness."""
import copy
import json
from pathlib import Path
import random
import subprocess

from benchmarks.compact_maintenance.contract import COMMON_INSTRUCTIONS, NATIVE_TOOLS, study_tools
from integrations.benchmark_runtime_v2.freeze import canonical, decode, sha

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent
SELECTED = ("MM01", "MM02", "MM04", "MM07")


def registration():
    prior_path = ROOT / "benchmarks/maintenance_interface_comparison/REGISTRATION.json"
    prior = json.loads(prior_path.read_bytes())
    tasks = {name: copy.deepcopy(prior["tasks"][name]) for name in SELECTED}
    for task in tasks.values():
        assert sorted(decode(task["bundle"], task["bundle"]["payload_sha256"])) == task["input_paths"]
    docs = copy.deepcopy(prior["docs"])
    docs["maintenance-profile.md"] = (ROOT / "docs/declaration-body-edit-v1.md").read_text(encoding="utf-8")
    pairs = [(name, repeat) for name in SELECTED for repeat in (1, 2)]
    random.Random(20261108).shuffle(pairs)
    schedule = []
    for task, repeat in pairs:
        for arm in (("T", "N") if repeat == 1 else ("N", "T")):
            schedule.append({"id": f"{len(schedule)+1:02d}-{task}-r{repeat}-{arm}",
                             "task": task, "repeat": repeat, "arm": arm})
    return {"schema": "mic02-design/v1", "status": "DESIGN_REGISTERED_RUNTIME_NOT_FROZEN",
            "base": "0edae8ec2ebcba8e2b340fb329e82eed6730027c",
            "purpose": "Known-task diagnostic screening of a new interface bundle, not a fresh independent task benchmark.",
            "prior_registration_sha256": sha(subprocess.check_output(
                ["git", "show", "HEAD:benchmarks/maintenance_interface_comparison/REGISTRATION.json"], cwd=ROOT)),
            "prior_registration_hash_basis": "committed Git blob, independent of checkout line endings",
            "model": "gpt-5.6-sol", "effort": "low", "provider": "openai",
            "limits": {"max_slots": 16, "model_turns_per_slot": 1, "concurrency": 1,
                       "tool_callback_limit": 80, "wall_observation_seconds": 480,
                       "token_observation_threshold": 600000, "interrupt_grace_seconds": 20},
            "selection": {"tasks": list(SELECTED), "component_sources": 3, "independent_new_tasks": 0,
                          "basis": "Existing record update, original shared parser, graph/error completeness, and prior both-arm XML failure; outcomes already known to designers.",
                          "excluded": {"MM05": "shares build.model with MM04; bounded diagnostic budget",
                                       "MM06": "shares build.model with MM04; bounded diagnostic budget"}},
            "developer_instructions": COMMON_INSTRUCTIONS, "native_tools": list(NATIVE_TOOLS),
            "study_tools": {arm: study_tools(arm) for arm in ("T", "N")},
            "docs": docs, "doc_sha256": {name: sha(text.encode()) for name, text in docs.items()},
            "tasks": tasks, "schedule": schedule,
            "screen": {"minimum_both_success_pairs": 4, "minimum_relative_token_reduction": 0.25,
                       "primary_cost_statistic": "median of per-pair N_total_tokens / T_total_tokens on both-success pairs",
                       "completion_rule": "N correct count >= T correct count over all eight complete pairs",
                       "requires_all_16_valid_slots": True,
                       "dispositions": ["EXPLORATORY_FAVORABLE_SIGNAL", "NO_EXPLORATORY_FAVORABLE_SIGNAL",
                                        "INCONCLUSIVE_INSUFFICIENT_PAIRED_SUCCESSES", "INCONCLUSIVE_INFRASTRUCTURE"]},
            "runtime_freeze": None, "model_generation_calls": 0, "input_token_api_calls": 0}


def validate(value):
    expected = registration()
    if value != expected:
        raise ValueError("Registration drift: regenerate only before generation and disclose changes")
    assert len(value["schedule"]) == 16
    assert len({r["id"] for r in value["schedule"]}) == 16
    assert len({(r["task"], r["repeat"], r["arm"]) for r in value["schedule"]}) == 16
    return {"status": "DESIGN_VALIDATED", "runtime_ready": False, "generation_calls": 0,
            "registration_sha256": sha(canonical(value))}


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    path = HERE / "REGISTRATION.json"
    if args.check:
        print(json.dumps(validate(json.loads(path.read_bytes()))))
    else:
        if path.exists():
            raise RuntimeError("Registration already exists; never overwrite an existing design")
        path.write_bytes(json.dumps(registration(), indent=2, ensure_ascii=True).encode() + b"\n")
        print(json.dumps(validate(json.loads(path.read_bytes()))))
