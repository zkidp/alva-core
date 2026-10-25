"""Mechanical preparation and immutable hash manifest; never starts a model."""

import ast
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from integrations.python_guard.guard import canonical, digest
from integrations.python_guard_codex import CandidateSession
from integrations.python_guard_codex import TOOLS
from tasks import TASKS, MODEL, BUDGET, COMMON, ARMS

RUNTIME = ROOT / ".local/p3-execution"
REUSED = ["integrations/python_guard/" + name for name in ("__init__.py", "__main__.py", "guard.py", "patch.py", "runner.py")]
REUSED += ["integrations/python_guard_codex/workflow.py", "integrations/skills/python-guard/SKILL.md",
           "tests/integrations/codex_native_test.py", "examples/python_guard_codex/demo.py"]


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args])


def files_manifest(root):
    return {p.relative_to(root).as_posix(): {"sha256": digest(p.read_bytes()), "bytes": p.stat().st_size}
            for p in sorted(root.rglob("*")) if p.is_file() and "__pycache__" not in p.parts and ".git" not in p.parts}


def public_files():
    return {p.relative_to(ROOT).as_posix(): digest(p.read_bytes()) for p in sorted(HERE.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts and p.name not in {
                "EXECUTION-FREEZE.json", "RESULTS.json", "REPORT.md", "VALIDATION.json", "DETERMINISTIC.json"}
            and "results" not in p.parts}


def prepare():
    if (HERE / "EXECUTION-FREEZE.json").exists() or RUNTIME.exists():
        raise RuntimeError("Existing freeze/runtime: do not regenerate or overwrite")
    inputs = HERE / "inputs"
    if inputs.exists():
        raise RuntimeError("Existing inputs: inspect instead of replacing")
    inputs.mkdir()
    qualifications = []
    for task in TASKS:
        clone = ROOT / ".local" / ("upstream-" + task["repo"].split("/")[-1])
        actual = git(clone, "rev-parse", task["commit"]).decode().strip()
        assert actual == task["commit"]
        project = inputs / task["id"]
        project.mkdir()
        names = git(clone, "ls-tree", "-r", "--name-only", actual, task["prefix"]).decode().splitlines()
        # Real package sources, not reimplemented stand-ins. Boltons modules are
        # independently usable; the two selected modules have only stdlib imports.
        if task["package"] == "boltons":
            names = ["boltons/__init__.py", "boltons/strutils.py", "boltons/timeutils.py"]
        else:
            names = [name for name in names if name.endswith(".py")]
        for name in names:
            relative = name.removeprefix("src/")
            target = project / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(git(clone, "show", actual + ":" + name))
        (project / "LICENSE").write_bytes(git(clone, "show", actual + ":LICENSE"))
        descriptor = {key: task[key] for key in ("id", "repo", "commit", "issue", "editable", "statement")}
        if task["id"] == "BOLTONS-EXPORTS":
            # Read declarations mechanically, without importing a reference fix.
            tree = ast.parse((project / "boltons/strutils.py").read_bytes())
            exports = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                           and any(isinstance(t, ast.Name) and t.id == "__all__" for t in n.targets))
            probe = subprocess.run([sys.executable, "-I", "-c", "import sys; sys.path.insert(0,sys.argv[1]); from boltons import strutils; import json; print(json.dumps([n for n in strutils.__all__ if hasattr(strutils,n)]))", str(project)],
                capture_output=True, text=True, timeout=15, check=True)
            descriptor["existing_exports"] = json.loads(probe.stdout)
            assert len(descriptor["existing_exports"]) < len(exports)
        (project / "TASK.json").write_bytes(canonical(descriptor))
        (project / "test_pilot.py").write_bytes((HERE / "evaluator.py").read_bytes())
        rows = {}
        for group in ("regression", "task"):
            p = subprocess.run([sys.executable, "-I", "test_pilot.py", group], cwd=project,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, capture_output=True, timeout=30)
            rows[group] = {"returncode": p.returncode, "stdout_sha256": digest(p.stdout),
                           "stderr_sha256": digest(p.stderr), "stderr": p.stderr.decode("utf-8", "replace").replace(str(ROOT), "<checkout>")}
        assert rows["regression"]["returncode"] == 0, rows
        assert rows["task"]["returncode"] == 1, rows
        qualifications.append({"task": task["id"], "baseline_regression": "PASS", "baseline_task": "EXPECTED_FAIL",
                               "evaluator_rows": rows, "files": files_manifest(project)})
    # Source fixtures remain frozen and are never model-writable. Every run gets
    # its own real source, candidate, trusted policy, evidence and initial Git tree.
    RUNTIME.mkdir(parents=True)
    schedule = []
    for index, task in enumerate(TASKS):
        for arm in (("A", "B") if index % 2 == 0 else ("B", "A")):
            slot = f"{len(schedule)+1:02d}-{task['id']}-{arm}"
            root = RUNTIME / slot
            root.mkdir()
            source = root / "source"
            shutil.copytree(inputs / task["id"], source, ignore=shutil.ignore_patterns("__pycache__"))
            scratch = root / "check-scratch"
            scratch.mkdir()
            policy = {"schema": 1, "project_root": str(source), "scratch_root": str(scratch),
                      "files": sorted(files_manifest(source)), "editable": task["editable"], "excluded": {".git": "VCS metadata, never task input"},
                      "scratch_outputs": ["__pycache__", task["package"] + "/__pycache__"],
                      "python": sys.executable, "trusted_project": True, "environment": {},
                      "checks": [{"id": group, "argv": ["$PYTHON", "-I", "test_pilot.py", group]} for group in ("regression", "task")],
                      "limits": {"max_files": 100, "max_source_bytes": 2097152, "max_patch_bytes": 1048576,
                                 "wall_seconds": 30, "output_bytes_per_stream": 16384, "max_command_invocations": 8,
                                 "max_direct_processes": 1, "address_space_bytes": None, "cpu_seconds": None}}
            policy_file = root / "approved-policy.json"
            policy_file.write_bytes(canonical(policy))
            if arm == "B":
                session = CandidateSession.prepare(root / "control", policy_file, root / "candidate", digest(policy_file.read_bytes()))
                candidate = session.candidate
            else:
                candidate = root / "candidate"
                shutil.copytree(source, candidate)
            for args in (("init", "-q"), ("config", "core.autocrlf", "false"), ("add", ".")):
                subprocess.run(["git", "-C", str(candidate), *args], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(candidate), "-c", "user.name=Public Pilot", "-c", "user.email=pilot@example.invalid",
                            "commit", "-q", "-m", "Frozen upstream-derived input"], check=True, capture_output=True,
                           env={**os.environ, "GIT_AUTHOR_DATE": "2026-10-26T00:00:00Z", "GIT_COMMITTER_DATE": "2026-10-26T00:00:00Z"})
            prompt = COMMON + "\nTASK:\n" + task["statement"] + "\nCONDITION:\n" + ARMS[arm] + "\nBUDGET:\n" + canonical(BUDGET).decode()
            (root / "prompt.txt").write_bytes(prompt.encode("utf-8"))
            thread = {"cwd": str(candidate), "model": MODEL, "sandbox": "workspace-write", "approvalPolicy": "never",
                      "ephemeral": True, "dynamicTools": TOOLS if arm == "B" else [],
                      "developerInstructions": "Only this disposable candidate is writable. Do not delegate or request expanded permissions. Use the supplied task and normal development tools."}
            input_items = [{"type": "text", "text": prompt}]
            if arm == "B":
                input_items.insert(0, {"type": "skill", "name": "python-guard", "path": str(ROOT / "integrations/skills/python-guard/SKILL.md")})
            turn = {"input": input_items, "sandboxPolicy": {"type": "workspaceWrite", "writableRoots": [str(candidate)],
                    "networkAccess": False, "excludeTmpdirEnvVar": True, "excludeSlashTmp": True},
                    "approvalPolicy": "never", "effort": BUDGET["reasoning"]}
            (root / "thread-start-input.json").write_bytes(canonical(thread))
            (root / "turn-start-input.json").write_bytes(canonical(turn))
            schedule.append({"slot": slot, "task": task["id"], "arm": arm,
                             "policy_sha256": digest(policy_file.read_bytes()), "prompt_sha256": digest(prompt.encode()),
                             "initial_git_commit": git(candidate, "rev-parse", "HEAD").decode().strip(),
                             "source_manifest": files_manifest(source), "candidate_manifest": files_manifest(candidate),
                             "runtime_manifest": files_manifest(root)})
    freeze = {"schema": 1, "classification": "EXPLORATORY_PAIRED_PILOT_NOT_CONFIRMATORY",
              "base": "7168a2346b9f3656e0f8d68fbee294d525a292a0", "model": MODEL, "budget": BUDGET,
              "codex_version": subprocess.check_output([shutil.which("codex"), "--version"]).decode().strip(),
              "python_version": platform.python_version(), "platform": platform.platform(),
              "python_binary_sha256": digest(Path(sys.executable).read_bytes()),
              "codex_binary_sha256": digest(Path(shutil.which("codex")).read_bytes()),
              "reused_hashes": {name: digest((ROOT / name).read_bytes()) for name in REUSED},
              "schedule": schedule, "files": public_files(), "generation_turns_started": 0,
              "runtime_storage": "host-local .local/p3-execution; actual policy/prompt bytes exist and are hashed, not placeholders"}
    (HERE / "QUALIFICATION.json").write_bytes(canonical(qualifications))
    freeze["files"] = public_files()
    (HERE / "EXECUTION-FREEZE.json").write_bytes(canonical(freeze))
    print(json.dumps({"qualification": "6 baseline regressions PASS, 6 task checks expected FAIL", "slots": len(schedule),
                      "freeze_sha256": digest(canonical(freeze)), "generation_turns_started": 0}))


if __name__ == "__main__":
    prepare()
