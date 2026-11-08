"""Small consumer packaging regressions; real execution is the Linux CI step."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import maintenance_consumer_walkthrough as demo


class ConsumerTests(unittest.TestCase):
    def test_operator_material_not_project_input(self):
        self.assertEqual(set(demo.INPUTS), {"alva.toml", "src/model.alva", "src/app.alva"})
        self.assertEqual(demo.POLICY["authorized_functions"], ["model.packs_required"])
        for name in demo.INPUTS:
            self.assertTrue((demo.SAMPLE / name).is_file())

    def test_authority_current_exact_format(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "alva-air").mkdir()
            revision = "a" * 64
            (root / "alva-air/current").write_text("1\n" + revision + "\n")
            (root / "alva-air/gen-1.air").write_bytes(b"fixture")
            files, actual, name = demo.authority_files(root)
            self.assertEqual(actual, revision)
            self.assertEqual(files[name], b"fixture")
            for bad in ["../1\n" + revision, "0\n" + revision, "1\nBAD", "1\n" + revision + "\nextra"]:
                (root / "alva-air/current").write_text(bad)
                with self.assertRaisesRegex(RuntimeError, "DEMO_INVALID_CURRENT"):
                    demo.authority_files(root)

    def test_unsupported_sandbox_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "must-not-exist"
            with patch.object(demo, "LinuxSandbox", side_effect=RuntimeError("UNSUPPORTED")):
                with self.assertRaisesRegex(RuntimeError, "UNSUPPORTED"):
                    demo.walkthrough(None, output)
            self.assertFalse(output.exists())

    def test_existing_output_is_never_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sentinel = root / "keep"
            sentinel.write_bytes(b"original")
            with patch.object(demo, "LinuxSandbox"):
                with self.assertRaises(FileExistsError):
                    demo.walkthrough(None, root)
            self.assertEqual(sentinel.read_bytes(), b"original")


if __name__ == "__main__":
    unittest.main()
