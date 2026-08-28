from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from arm_runtime import E4Runtime, HYBRID, TEXT, TEXT_VERIFY


class FakeCompiler:
    def __init__(self):
        self.checks = 0
        self.fail = False

    def check_project(self):
        self.checks += 1
        if self.fail:
            return {"ok": False, "error_code": "E_PROJECT_CHECK", "message": "project check failed"}
        return {"ok": True, "result": {"diagnostics": []}}

    def project_air_to_text(self):
        return {"src/main.alva": b"semantic\n"}


class ProjectionFailCompiler(FakeCompiler):
    def project_air_to_text(self):
        raise RuntimeError("projection failed")


class FakeSemantic:
    def __init__(self):
        self.started = 0
        self.calls = []
        self.closes = []

    def start(self):
        self.started += 1
        return {"ok": True, "result": {"started": True}}

    def call(self, tool, arguments):
        self.calls.append((tool, arguments))
        return {"ok": True, "result": {"tool": tool}}

    def close(self, *, abort):
        self.closes.append(abort)


class ArmRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.root = Path(self.temp.name)
        (self.root / "src").mkdir()
        (self.root / "src/main.alva").write_bytes(b"base\n")
        (self.root / "alva.toml").write_bytes(b'[project]\nname="x"\n[modules]\n"x"="src/main.alva"\n')
        self.allowed = ["src/main.alva"]

    def tearDown(self):
        self.temp.cleanup()

    def test_text_arm_has_no_session_or_semantic_tools(self):
        compiler = FakeCompiler()
        runtime = E4Runtime(TEXT, self.root, self.allowed, compiler)
        self.assertTrue(runtime.call("write_file", path="src/main.alva", content="text\n")["ok"])
        self.assertTrue(runtime.call("check_project")["ok"])
        self.assertEqual(runtime.call("begin_patch_session")["error_code"], "E_UNKNOWN_TOOL")
        self.assertEqual(runtime.call("inspect_project")["error_code"], "E_UNKNOWN_TOOL")

    def test_control_arm_requires_session_and_rechecks_after_write(self):
        compiler, semantic = FakeCompiler(), FakeSemantic()
        runtime = E4Runtime(TEXT_VERIFY, self.root, self.allowed, compiler, semantic)
        self.assertEqual(runtime.call("write_file", path="src/main.alva", content="x\n")["error_code"], "E_NO_PATCH_SESSION")
        self.assertTrue(runtime.call("begin_patch_session")["ok"])
        self.assertTrue(runtime.call("write_file", path="src/main.alva", content="x\n")["ok"])
        self.assertEqual(runtime.call("inspect_project")["error_code"], "E_TEXT_NOT_CHECKED")
        self.assertTrue(runtime.call("check_project")["ok"])
        self.assertTrue(runtime.call("inspect_project")["ok"])
        self.assertGreaterEqual(semantic.started, 2)

    def test_hybrid_semantic_mutation_projects_to_text(self):
        compiler, semantic = FakeCompiler(), FakeSemantic()
        runtime = E4Runtime(HYBRID, self.root, self.allowed, compiler, semantic)
        runtime.call("begin_patch_session")
        self.assertTrue(runtime.call("rename_entity", entity="x", new_name="y")["ok"])
        self.assertEqual(runtime.call("write_file", path="src/main.alva", content="bad\n")["error_code"], "E_MIXED_EDIT_CONFLICT")
        self.assertTrue(runtime.call("commit_patch")["ok"])
        self.assertEqual((self.root / "src/main.alva").read_bytes(), b"semantic\n")
        self.assertIn(("check_transaction", {}), semantic.calls)
        self.assertIn(("commit_transaction", {}), semantic.calls)

    def test_discard_restores_text_and_aborts_semantics(self):
        compiler, semantic = FakeCompiler(), FakeSemantic()
        runtime = E4Runtime(HYBRID, self.root, self.allowed, compiler, semantic)
        runtime.call("begin_patch_session")
        runtime.call("write_file", path="src/main.alva", content="changed\n")
        self.assertTrue(runtime.call("discard_patch")["ok"])
        self.assertEqual((self.root / "src/main.alva").read_bytes(), b"base\n")
        self.assertTrue(semantic.closes[-1])

    def test_failed_check_does_not_commit(self):
        compiler, semantic = FakeCompiler(), FakeSemantic()
        runtime = E4Runtime(TEXT_VERIFY, self.root, self.allowed, compiler, semantic)
        runtime.call("begin_patch_session")
        runtime.call("write_file", path="src/main.alva", content="broken\n")
        compiler.fail = True
        result = runtime.call("commit_patch")
        self.assertFalse(result["ok"])
        self.assertTrue(runtime.active)

    def test_post_commit_projection_failure_poisons_runtime(self):
        compiler, semantic = ProjectionFailCompiler(), FakeSemantic()
        runtime = E4Runtime(HYBRID, self.root, self.allowed, compiler, semantic)
        runtime.call("begin_patch_session")
        runtime.call("rename_entity", entity="x", new_name="y")
        result = runtime.call("commit_patch")
        self.assertEqual(result["error_code"], "E_COMMIT_PROJECTION_DIVERGENCE")
        self.assertEqual(runtime.call("inspect_project")["error_code"],
                         "E_RUNTIME_POISONED")
        self.assertEqual(runtime.prepare_final_verifier()["error_code"],
                         "E_RUNTIME_POISONED")


if __name__ == "__main__":
    unittest.main()
