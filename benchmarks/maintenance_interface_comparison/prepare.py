"""Register known-task exploratory comparison; no model calls or solution mounts."""
import copy
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks.p34_scope_guard.cases import case
from benchmarks.maintenance_design import witnesses
from benchmarks.p37_maintenance_qualification import assertions
from integrations.benchmark_runtime_v2.freeze import canonical, sha, decode

HERE = Path(__file__).parent


def prepare():
    tasks = {}
    for ident, label in (("MM01", "MM01_VALID"), ("MM02", "MM02_SHARED")):
        c = case(label)
        tasks[ident] = {"public_task": {k: c["task"][k] for k in ("id", "target", "requirement")},
            "bundle": c["bundle"], "policy": c["policy"], "crate": c["task"]["crate"],
            "assertions": {"goal": witnesses.goals(ident), "regression": witnesses.regressions(ident)}}
    registry = json.loads((ROOT / "benchmarks/p37_maintenance_qualification/CANDIDATE-REGISTRY.json").read_text())
    bundles = json.loads((ROOT / "benchmarks/p37_maintenance_qualification/TASK-BUNDLES.json").read_text())
    for c in registry["candidates"]:
        ident = c["id"]
        tasks[ident] = {"public_task": json.loads((ROOT / "benchmarks/p37_maintenance_qualification/public" / ident / "task.json").read_text()),
            "bundle": bundles[ident], "policy": c["guard_policy"], "crate": c["crate"],
            "assertions": {"goal": assertions.goals(ident), "regression": assertions.regressions(ident)}}
    docs = {"language.md": (ROOT / "alva/README.md").read_text(encoding="utf-8")}
    for name in ("SKILL.md", "references/workflow.md", "references/diagnostics.md", "references/examples.md"):
        docs[name] = (ROOT / "integrations/skills/alva" / name).read_text(encoding="utf-8")
    groups = [(task, rep) for task in tasks for rep in (1, 2)]
    random.Random(20261107).shuffle(groups)
    schedule = []
    for task, rep in groups:
        for arm in (("T", "N") if rep == 1 else ("N", "T")):
            schedule.append({"id": f'{len(schedule)+1:02d}-{task}-r{rep}-{arm}', "task": task,
                             "repeat": rep, "arm": arm})
    result = {"schema": "mic01-registration/v1", "base": "b7a8cf86094c8e85a2f22025508088579cdf9476",
        "task_provenance": "six known author-familiar tasks; not a fresh-task benchmark",
        "model": "gpt-5.6-sol", "provider": "openai", "effort": "low",
        "limits": {"wall_observation_seconds": 480, "tool_callback_limit": 80,
                   "token_observation_threshold": 600000, "interrupt_grace_seconds": 20,
                   "model_turns_per_slot": 1, "concurrency": 1, "max_slots": 24},
        "docs": docs, "tasks": tasks, "schedule": schedule, "model_generation_calls": 0}
    for t in tasks.values():
        decode(t["bundle"], t["bundle"]["payload_sha256"])
        t["input_paths"] = sorted(decode(t["bundle"], t["bundle"]["payload_sha256"]))
    path = HERE / "REGISTRATION.json"
    path.write_bytes(json.dumps(result, indent=2, ensure_ascii=True).encode() + b"\n")
    print(json.dumps({"tasks": len(tasks), "slots": len(schedule), "registration_sha256": sha(path.read_bytes()),
                      "model_generation_calls": 0}))


if __name__ == "__main__":
    prepare()
