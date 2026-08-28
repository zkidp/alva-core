import json
import unittest
from pathlib import Path

from generate_tool_schemas import OUT, build_surfaces, main


class ToolSchemaTests(unittest.TestCase):
    def test_exact_surfaces(self):
        surfaces = build_surfaces()
        names = {arm: [x["function"]["name"] for x in tools]
                 for arm, tools in surfaces.items()}
        self.assertEqual(len(names["TEXT"]), 5)
        self.assertEqual(len(names["TEXT_VERIFY"]), 18)
        self.assertEqual(len(names["HYBRID"]), 23)
        self.assertEqual(len(names["FULL_ALVA"]), 42)
        self.assertNotIn("begin_transaction", names["TEXT_VERIFY"])
        self.assertNotIn("commit_transaction", names["HYBRID"])
        self.assertNotIn("migrate_signature", names["TEXT_VERIFY"])
        self.assertIn("migrate_signature", names["HYBRID"])

    def test_generation_is_deterministic(self):
        main()
        first = {path.name: path.read_bytes() for path in OUT.glob("*.json")}
        main()
        second = {path.name: path.read_bytes() for path in OUT.glob("*.json")}
        self.assertEqual(first, second)
        manifest = json.loads((OUT / "SCHEMA-MANIFEST.json").read_text())
        self.assertEqual(set(manifest["arms"]), {"TEXT", "TEXT_VERIFY", "HYBRID", "FULL_ALVA"})


if __name__ == "__main__":
    unittest.main()
