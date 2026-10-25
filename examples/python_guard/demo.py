#!/usr/bin/env python3
"""Exercise all three Guard CLI operations on a disposable public Python fixture."""

from __future__ import annotations

import difflib
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="alva-python-guard-demo-") as temp:
        directory = Path(temp)
        project = directory / "project"
        shutil.copytree(ROOT / "tests" / "python_guard" / "fixture", project,
                        ignore=shutil.ignore_patterns("__pycache__"))
        scratch = directory / "scratch"
        scratch.mkdir()
        policy = {
            "schema": 1, "project_root": str(project), "scratch_root": str(scratch),
            "files": ["calc.py", "tests/test_calc.py"], "editable": ["calc.py"], "excluded": {},
            "scratch_outputs": ["__pycache__", "tests/__pycache__"],
            "python": sys.executable, "trusted_project": True, "environment": {},
            "checks": [{"id": "unit", "argv": ["$PYTHON", "-I", "-m", "unittest", "discover", "-s", "tests"]}],
            "limits": {"max_files": 100, "max_source_bytes": 1000000, "max_patch_bytes": 10000,
                       "wall_seconds": 30, "output_bytes_per_stream": 16384, "max_command_invocations": 8,
                       "max_direct_processes": 1, "address_space_bytes": None, "cpu_seconds": None},
        }
        policy_path = directory / "approved-policy.json"
        policy_path.write_text(json.dumps(policy), encoding="utf-8")
        policy_id = "sha256:" + hashlib.sha256(policy_path.read_bytes()).hexdigest()
        store = directory / "evidence"

        def cli(operation, request):
            path = directory / (operation + "-request.json")
            path.write_text(json.dumps(request), encoding="utf-8")
            response = subprocess.run([sys.executable, "-m", "integrations.python_guard", "--store", str(store),
                "--policy", str(policy_path), operation, "--request", str(path)], cwd=ROOT,
                capture_output=True, text=True, timeout=45)
            return response.returncode, json.loads(response.stdout)

        snapshot_request = {"project_root": str(project), "policy_id": policy_id, "files": policy["files"]}
        code, snapshot = cli("snapshot", snapshot_request)
        assert code == 0, snapshot
        original = {p.relative_to(project): p.read_bytes() for p in project.rglob("*.py")}
        old = (project / "calc.py").read_bytes().decode("utf-8")

        def verify(new):
            patch = "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                                fromfile="a/calc.py", tofile="b/calc.py"))
            response = cli("verify", {"snapshot_id": snapshot["snapshot_id"], "policy_id": policy_id,
                "patch_utf8": patch, "expected_files": {"calc.py": "sha256:" + hashlib.sha256(old.encode()).hexdigest()}})
            assert original == {p.relative_to(project): p.read_bytes() for p in project.rglob("*.py")}
            return response

        good_code, good = verify("def total(values):\n    return sum(values) + 0\n")
        bad_code, bad = verify("def total(values):\n    return 1\n")
        assert good_code == 0 and good["checks_status"] == "PASS", good
        assert bad_code == 1 and bad["checks_status"] == "FAIL", bad
        # This is the caller's concurrent edit, never an action performed by Guard.
        (project / "calc.py").write_bytes(b"# later source revision\n" + old.encode())
        _, current = cli("snapshot", snapshot_request)
        stale_code, stale = cli("report", {"verification_id": good["verification_id"],
                                           "current_snapshot_id": current["snapshot_id"]})
        assert stale_code == 2 and stale["applicability_status"] == "STALE", stale
        print(json.dumps({"status": "PASS", "real_cli_operations": ["snapshot", "verify", "report"],
                          "valid_patch": good["checks_status"], "behavioral_error": bad["checks_status"],
                          "historical_checks": stale["checks_status"], "later_applicability": stale["applicability_status"],
                          "source_unchanged_by_both_verifications": True,
                          "new_regression": bad["regression"][1]["classification"]}, indent=2))


if __name__ == "__main__":
    main()
