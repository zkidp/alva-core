"""Materialize exactly the pre-execution runtime, not permissive EOL hashes."""
import base64
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile


def main():
    root = Path(__file__).resolve().parents[2]
    names = ("benchmarks/p32_native_mm01/FREEZE.json", "benchmarks/mm01_pilot/FREEZE.json")
    content = {p: subprocess.check_output(["git", "show", "HEAD:" + p], cwd=root) for p in names}
    f = json.loads(content[names[0]])
    with tempfile.TemporaryDirectory(prefix="p32-exact-runtime-") as tmp:
        for name, encoded in f["runtime_bytes"].items():
            p = PurePosixPath(name)
            assert not p.is_absolute() and ".." not in p.parts and "\\" not in name and ":" not in name
            data = base64.b64decode(encoded, validate=True)
            assert hashlib.sha256(data).hexdigest() == f["files"][name]
            out = Path(tmp) / p
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
        for name, data in content.items():
            out = Path(tmp) / name
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
        subprocess.run([sys.executable, "-m", "unittest", "benchmarks.p32_native_mm01.test_pilot", "-v"], cwd=tmp, check=True)
    print("P32 EXACT_RUNTIME_PASS; model generation calls=0")


if __name__ == "__main__":
    main()
