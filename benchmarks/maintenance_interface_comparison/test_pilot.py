"""No-generation controls for schedule, input boundary, scoring and limits."""
import copy
import json
from pathlib import Path
import unittest

from benchmarks.maintenance_interface_comparison import pilot, service
from integrations.benchmark_runtime_v2.freeze import canonical, decode, sha
from benchmarks.cross_language.controller import simulated_validation


class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = json.loads((pilot.HERE / "REGISTRATION.json").read_text())

    def test_exact_known_task_inputs_and_counterbalance(self):
        self.assertEqual(len(self.r["tasks"]), 6)
        schedule = self.r["schedule"]
        self.assertEqual(len(schedule), 24)
        self.assertEqual(len({s["id"] for s in schedule}), 24)
        for task in self.r["tasks"].values():
            source = decode(task["bundle"], task["bundle"]["payload_sha256"])
            self.assertEqual(sorted(source), task["input_paths"])
            self.assertTrue(all(p == "alva.toml" or p.endswith(".alva") for p in source))
            self.assertTrue(task["assertions"]["goal"] and task["assertions"]["regression"])
            self.assertNotIn("witness", json.dumps(task["public_task"]).lower())
            compile(service.inside_source(task["input_paths"]), "isolated-source-editor", "exec")
        for task in self.r["tasks"]:
            rows = [s for s in schedule if s["task"] == task]
            self.assertEqual([s["arm"] for s in rows if s["repeat"] == 1], ["T", "N"])
            self.assertEqual([s["arm"] for s in rows if s["repeat"] == 2], ["N", "T"])

    def test_whole_file_editor_has_protected_manifest_and_revision(self):
        code = service.inside_source(["alva.toml", "src/model.alva"])
        self.assertIn('if name == "alva.toml": return {"error":"PROTECTED_PATH"}', code)
        self.assertLess(code.index('if args.get("revision") != current:'), code.index('if action == "write":'))
        self.assertIn('path.write_bytes(changed)', code)

    def test_equal_documentation_and_no_oracle_in_task_prompt(self):
        self.assertEqual(set(self.r["docs"]), {"language.md", "SKILL.md", "references/workflow.md", "references/diagnostics.md", "references/examples.md"})
        for task in self.r["tasks"].values():
            text = json.dumps(task["public_task"])
            self.assertNotIn("#[test]", text)
            self.assertNotIn("assert_eq!", text)
            self.assertNotIn("assertions", text)
        self.assertIn("full official Skill", (pilot.HERE / "PROTOCOL.md").read_text())

    def test_shared_scope_and_exact_test_receipt(self):
        before = {"modules": {}, "functions": {"m.f": {"body": "a", "fields": {}, "metadata_slots": {}, "entity": "f"},
                                                       "m.g": {"body": "b", "fields": {}, "metadata_slots": {}, "entity": "g"}}}
        after = copy.deepcopy(before)
        after["functions"]["m.f"]["body"] = "c"
        task = {"policy": {"authorized_functions": ["m.f"]}, "public_task": {"target": "m.f"}}
        evidence = {"initial_authority": before, "final_authority": after, "final_files": {},
                    "final": {"status": "PASS", "tested_snapshot_sha256": sha(canonical({})),
                              "goal": {"status": "PASS"}, "regression": {"status": "PASS"}}}
        self.assertTrue(pilot.score(task, evidence)["correct"])
        after["functions"]["m.g"]["body"] = "d"
        self.assertFalse(pilot.score(task, evidence)["correct"])
        after["functions"]["m.g"]["body"] = "b"
        evidence["final"]["tested_snapshot_sha256"] = "wrong"
        self.assertFalse(pilot.score(task, evidence)["correct"])

    def test_controller_interrupt_and_missing_usage(self):
        self.assertEqual(simulated_validation()["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
