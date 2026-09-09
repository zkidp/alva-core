#!/usr/bin/env python3
"""Live WF-01 entry calibration plus source revision/arm boundary tests."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("workbench", ROOT / "scripts/source_workbench.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class HostTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="wf02-host-")
        self.base = Path(self.tmp.name)
        self.project = self.base / "project"
        shutil.copytree(ROOT / "examples/build_system", self.project,
                        ignore=shutil.ignore_patterns("out", "__pycache__", "alva-air"))
        self.binary = os.environ["ALVA_BIN"]
        self.host = mod.Workbench(self.project, self.binary, "T+V", self.base / "out")

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, tool, **args):
        return self.host.handle(dict(tool=tool, **args))

    def revision(self):
        r = self.call("revision")
        self.assertTrue(r["ok"], r)
        return r["source_revision"]

    def test_current_observation_and_stale_rejection(self):
        rev = self.revision()
        r = self.call("observe", revision=rev, view="inspect_function", args={"name": "build.store.read_config_hash"})
        self.assertTrue(r["ok"] and r["result"].get("ok"), r)
        self.assertEqual(r["source_revision"], rev)
        self.assertGreater(r["accounting"]["child_cpu_seconds"], 0)
        patch = self.call("edit", revision=rev, path="src/store.alva",
                          old='(string "default")', new='(string "wf02-calibration")')
        self.assertTrue(patch["ok"], patch)
        new = patch["source_revision"]
        self.assertNotEqual(rev, new)
        stale = self.call("observe", revision=rev, view="inspect_project", args={})
        self.assertFalse(stale["ok"])
        self.assertEqual(stale["result"]["error"], "STALE_SOURCE_REVISION")
        current = self.call("observe", revision=new, view="inspect_body", args={"function": "build.store.read_config_hash"})
        self.assertTrue(current["ok"] and current["result"]["ok"], current)
        self.assertIn("wf02-calibration", json.dumps(current))
        self.assertFalse((self.project / "alva-air").exists())

    def test_change_during_observation_never_returns_view(self):
        old = self.host.observe
        def racing(files, request):
            r = old(files, request)
            with (self.project / "src/store.alva").open("a") as f:
                f.write("\n;; concurrent calibration edit\n")
            return r
        self.host.observe = racing
        r = self.call("observe", revision=self.revision(), view="inspect_project", args={})
        self.assertFalse(r["ok"])
        self.assertEqual(r["result"], {"error": "SOURCE_CHANGED_DURING_OPERATION"})

    def test_arm_and_mutation_denial(self):
        rev = self.revision()
        for tool in ("commit_transaction", "stage_text_patch", "change_field"):
            self.assertFalse(self.call(tool, revision=rev)["ok"])
            self.assertFalse(self.call("observe", revision=rev, view=tool, args={})["ok"])
        self.host.arm = "T"
        self.assertFalse(self.call("observe", revision=rev, view="inspect_project", args={})["ok"])
        self.assertNotIn("observe", self.call("tools")["result"])

    def test_air_and_path_rejection(self):
        rev = self.revision()
        for path in ("../escape.alva", "alva-air/current.alva", "tests/config_cases.py"):
            self.assertFalse(self.call("edit", revision=rev, path=path, old="", new="x")["ok"])
        (self.project / "alva-air").mkdir()
        self.assertFalse(self.call("revision")["ok"])

    def test_identical_common_tools_and_repairable_syntax(self):
        rev = self.revision()
        p = self.call("read", revision=rev, path="src/model.alva")
        self.host.arm = "T"
        q = self.call("read", revision=rev, path="src/model.alva")
        self.assertEqual(p["result"], q["result"])
        r = self.call("edit", revision=rev, path="alva.toml", old="[project]", new="[broken")
        self.assertTrue(r["ok"], r)
        broken = self.revision()
        self.assertFalse(self.call("check", revision=broken)["ok"])
        r = self.call("edit", revision=broken, path="alva.toml", old="[broken", new="[project]")
        self.assertTrue(r["ok"], r)
        self.assertEqual(self.revision(), rev)

    def test_live_jsonl_and_wf01_build_acceptance(self):
        # Real process wire, not merely calling a mock Python method.
        rev = self.revision()
        audit = self.base / "audit.jsonl"
        args = [sys.executable, str(ROOT / "scripts/source_workbench.py"),
                "--project", str(self.project), "--binary", self.binary,
                "--arm", "T+V", "--out", str(self.base / "native"),
                "--audit", str(audit), "--acceptance",
                str(ROOT / "examples/build_system/tests/config_cases.py")]
        requests = [{"tool": "environment"}, {"tool": "check", "revision": rev},
                    {"tool": "observe", "revision": rev, "view": "inspect_module", "args": {"name": "build.model"}},
                    {"tool": "build", "revision": rev}, {"tool": "test", "revision": rev}]
        p = subprocess.run(args, input="".join(json.dumps(r) + "\n" for r in requests),
                           text=True, capture_output=True, timeout=180)
        self.assertEqual(p.returncode, 0, p.stderr)
        rows = [json.loads(l) for l in p.stdout.splitlines()]
        self.assertEqual(len(rows), len(requests))
        self.assertTrue(all(r["ok"] for r in rows), rows)
        for i in (1, 3, 4):
            self.assertEqual(rows[i]["result"]["returncode"], 0, rows[i])
        self.assertIn("11 scenario groups PASS", rows[4]["result"]["stdout"])
        self.assertEqual(len(audit.read_text().splitlines()), len(rows) + 1)
        self.assertEqual(self.revision(), rev)

    def test_common_editor_byte_equivalence(self):
        other = self.base / "other"
        shutil.copytree(self.project, other)
        t = mod.Workbench(other, self.binary, "T", self.base / "other-out")
        rev = self.revision()
        request = dict(tool="edit", revision=rev, path="src/store.alva",
                       old='(string "default")', new='(string "shared-editor")')
        a, b = self.host.handle(request), t.handle(request)
        self.assertTrue(a["ok"] and b["ok"], (a, b))
        self.assertEqual(a["source_revision"], b["source_revision"])
        self.assertEqual(a["result"], b["result"])
        self.assertEqual(a["accounting"]["category"], "ordinary_text_edit")
        for rel in self.host.snapshot()[1]:
            self.assertEqual((self.project / rel).read_bytes(), (other / rel).read_bytes())

    def test_symlink_and_external_module_denial(self):
        (self.project / "link.alva").symlink_to(self.base / "outside.alva")
        self.assertFalse(self.call("revision")["ok"])
        (self.project / "link.alva").unlink()
        rev = self.revision()
        patch = self.call("edit", revision=rev, path="alva.toml",
                          old='"src/model.alva"', new='"../outside.alva"')
        self.assertTrue(patch["ok"])
        r = self.call("observe", revision=patch["source_revision"], view="inspect_project", args={})
        self.assertFalse(r["ok"])
        self.assertEqual(r["result"]["error"], "MODULE_MUST_BE_LOCAL_CAPTURED_SOURCE")


if __name__ == "__main__":
    unittest.main()
