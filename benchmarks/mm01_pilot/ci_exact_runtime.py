"""Consume only exact frozen runtime bytes; never accept alternate EOL hashes."""
import base64
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile


def main():
    root = Path(__file__).resolve().parents[2]
    name = "benchmarks/mm01_pilot/FREEZE.json"
    data = subprocess.check_output(["git", "show", "HEAD:" + name], cwd=root)
    assert (root / name).read_bytes() == data
    f = json.loads(data)
    with tempfile.TemporaryDirectory(prefix="mm01-exact-runtime-") as tmp:
        for p, encoded in f["runtime_bytes"].items():
            path = PurePosixPath(p)
            assert not path.is_absolute() and ".." not in path.parts and "\\" not in p and ":" not in p
            payload = base64.b64decode(encoded, validate=True)
            assert hashlib.sha256(payload).hexdigest() == f["files"][p]
            out = Path(tmp) / p
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(payload)
        out = Path(tmp) / name
        out.write_bytes(data)
        subprocess.run([sys.executable, "-m", "unittest", "benchmarks.mm01_pilot.test_pilot", "-v"], cwd=tmp, check=True)
    print("EXACT_RUNTIME_PASS; model generation calls=0")


if __name__ == "__main__":
    main()
