"""Test the already frozen runtime bytes in a disposable tree, without models.

An inherited dependency has CRLF in the approved Windows/WSL execution tree but
LF in its Git blob. A fresh checkout is NOT the frozen runtime. Do not accept
either hash: decode only the exact pre-generation transport and check its hash.
This CI-only consumer does not alter the freeze, runner or repository files.
"""
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
FREEZE_COMMIT = "c79b8ebd3464075d45b0d3f0bb3cffa900cf6cca"
FREEZE_PATH = "benchmarks/p28_optional_descriptor/FREEZE.json"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    frozen_bytes = subprocess.check_output(["git", "show", FREEZE_COMMIT + ":" + FREEZE_PATH], cwd=ROOT)
    assert (ROOT / FREEZE_PATH).read_bytes() == frozen_bytes, "Frozen package changed"
    frozen = json.loads(frozen_bytes)
    payloads = {p: base64.b64decode(v, validate=True) for p, v in frozen["runtime_bytes"].items()}
    assert set(payloads) == set(frozen["files"])
    for p, data in payloads.items():
        assert digest(data) == frozen["files"][p], "Frozen transport hash mismatch: " + p
    for p, expected in (("benchmarks/native_prospective/FREEZE.json", frozen["p26_freeze_sha256"]),
                        ("benchmarks/p27_bottleneck/NEXT-EXPERIMENT.json", frozen["design_sha256"])):
        payloads[p] = (ROOT / p).read_bytes()
        assert digest(payloads[p]) == expected, p
    payloads[FREEZE_PATH] = frozen_bytes
    with tempfile.TemporaryDirectory(prefix="p28-exact-frozen-runtime-") as tmp:
        for name, data in payloads.items():
            path = PurePosixPath(name)
            assert not path.is_absolute() and all(part not in ("", ".", "..") for part in name.split("/"))
            assert "\\" not in name and ":" not in name
            out = Path(tmp).joinpath(*path.parts)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run([sys.executable, "-m", "unittest", "benchmarks.p28_optional_descriptor.test_pilot", "-v"], cwd=tmp, env=env)
        assert result.returncode == 0, "Frozen runtime tests failed"
    print("EXACT_FROZEN_RUNTIME_PASS; no checkout hash alternatives; generation calls=0", flush=True)


if __name__ == "__main__":
    main()
