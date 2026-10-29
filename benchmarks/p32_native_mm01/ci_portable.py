"""Additive CI fixture adaptation; frozen execution/test bytes stay unchanged.

The trusted AppServer Host is Windows-to-WSL. On POSIX CI only, its pure policy
unit test uses an explicit path-mapper stub; no Host/backend is executed there.
The real Windows mapping rejects POSIX inputs, tested separately. Every frozen
runtime byte is still verified/materialized exactly before running the suite.
"""
import base64
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile

RUNNER = '''import os, unittest
from pathlib import Path
from unittest.mock import patch
from benchmarks.p32_native_mm01 import test_pilot as tests
from benchmarks.p32_native_mm01 import pilot
if os.name != "nt":
 original = tests.Tests.test_scoped_host_and_transport
 def policy_with_windows_transport_fixture(self):
  with patch.object(pilot.old, "linux", side_effect=lambda p: "/mnt/c/explicit-policy-fixture/" + Path(p).name) as mapper:
   original(self)
   self.assertEqual(mapper.call_count, 2)
 tests.Tests.test_scoped_host_and_transport = policy_with_windows_transport_fixture
 class PlatformBoundary(unittest.TestCase):
  def test_posix_is_not_a_windows_host(self):
   with self.assertRaises(ValueError): pilot.old.linux("/tmp/not-a-windows-host")
 suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(tests.Tests), unittest.defaultTestLoader.loadTestsFromTestCase(PlatformBoundary)])
else:
 suite = unittest.defaultTestLoader.loadTestsFromTestCase(tests.Tests)
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
'''


def main():
    root = Path(__file__).resolve().parents[2]
    names = ("benchmarks/p32_native_mm01/FREEZE.json", "benchmarks/mm01_pilot/FREEZE.json")
    content = {p: subprocess.check_output(["git", "show", "HEAD:" + p], cwd=root) for p in names}
    frozen = json.loads(content[names[0]])
    with tempfile.TemporaryDirectory(prefix="p32-portable-exact-runtime-") as tmp:
        for name, encoded in frozen["runtime_bytes"].items():
            path = PurePosixPath(name)
            assert not path.is_absolute() and ".." not in path.parts and "\\" not in name and ":" not in name
            data = base64.b64decode(encoded, validate=True)
            assert hashlib.sha256(data).hexdigest() == frozen["files"][name]
            out = Path(tmp) / path
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
        for name, data in content.items():
            out = Path(tmp) / name
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
        subprocess.run([sys.executable, "-c", RUNNER], cwd=tmp, check=True)
    print("P32 PORTABLE_EXACT_RUNTIME_PASS; POSIX policy fixture is not a supported AppServer Host; model calls=0")


if __name__ == "__main__":
    main()
