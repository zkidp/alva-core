import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from integrations.benchmark_runtime_v2.freeze import pack_git, materialize, verify_runtime, decode
from integrations.benchmark_runtime_v2.sandbox import LinuxSandbox, Unsupported

PATHS = ["tests/integrations/codex_native_test.py", "feasibility/native_api/run.py"]


class FreezeTests(unittest.TestCase):
    def test_actual_lf_crlf_checkouts_produce_identical_exact_bundle(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            example = json.loads((ROOT / "evidence/benchmark-hardening/FREEZE-V2-EXAMPLE.json").read_text(encoding="utf-8"))
            bundles = []
            for setting in ("false", "true"):
                checkout = root / setting
                subprocess.run(["git", "clone", "-q", "--no-checkout", "--shared", str(ROOT), str(checkout)], check=True)
                subprocess.run(["git", "-C", str(checkout), "-c", "core.autocrlf=" + setting, "checkout",
                                "ecadfea51ccd147f99f58ec5e891869744bc664c", "--", *PATHS], check=True)
                working = (checkout / PATHS[0]).read_bytes()
                self.assertEqual(b"\r\n" in working, setting == "true")
                bundle = pack_git(checkout, "ecadfea51ccd147f99f58ec5e891869744bc664c", PATHS)
                bundles.append(bundle)
                self.assertEqual(bundle, example)
                destination = root / (setting + "-runtime")
                materialize(bundle, bundle["payload_sha256"], destination)
                for path, expected in decode(bundle, bundle["payload_sha256"]).items():
                    self.assertEqual((destination / path).read_bytes(), expected)
                    self.assertNotIn(b"\r\n", expected)
                # Deliberate runtime EOL conversion must fail, not select a variant.
                target = destination / PATHS[0]
                target.write_bytes(target.read_bytes().replace(b"\n", b"\r\n"))
                with self.assertRaises(ValueError):
                    verify_runtime(bundle, bundle["payload_sha256"], destination)
            self.assertEqual(bundles[0], bundles[1])

    def test_transport_tamper_and_runtime_extra_file_reject(self):
        bundle = pack_git(ROOT, "ecadfea51ccd147f99f58ec5e891869744bc664c", PATHS)
        changed = copy.deepcopy(bundle)
        changed["payload"]["entries"][0]["base64"] = "eA=="
        with self.assertRaises(ValueError):
            decode(changed, bundle["payload_sha256"])
        with tempfile.TemporaryDirectory() as name:
            destination = Path(name) / "runtime"
            materialize(bundle, bundle["payload_sha256"], destination)
            (destination / "extra.py").write_bytes(b"pass\n")
            with self.assertRaises(ValueError):
                verify_runtime(bundle, bundle["payload_sha256"], destination)

    def test_unsupported_windows_never_launches(self):
        with patch("sys.platform", "win32"), patch("subprocess.run") as execute:
            with self.assertRaises(Unsupported):
                LinuxSandbox()
            execute.assert_not_called()

    def test_missing_linux_backend_never_falls_back(self):
        with patch("sys.platform", "linux"), patch("shutil.which", return_value=None), patch("subprocess.run") as execute:
            with self.assertRaises(Unsupported):
                LinuxSandbox()
            execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
