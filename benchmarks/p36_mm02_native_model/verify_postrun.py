"""Check this technical fix against the immutable pre-fix scientific snapshot."""
import base64
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent
BEFORE = "3991160cb8e62fb8750073a663d29c275fa729cd"


def verify():
    names = ("FREEZE.json", "ARCHIVE.json", "RESULTS.json", "ANALYSIS.json", "VALIDATION.json", "REPORT.md")
    for name in names:
        original = subprocess.check_output(["git", "show", BEFORE + ":benchmarks/p36_mm02_native_model/" + name], cwd=ROOT)
        assert original == (HERE / name).read_bytes(), name
    frozen = json.loads((HERE / "FREEZE.json").read_text())
    for name, digest in frozen["files"].items():
        assert hashlib.sha256(base64.b64decode(frozen["runtime_bytes"][name])).hexdigest() == digest, name
    for name in ("pilot.py", "remote.py"):
        path = "benchmarks/p36_mm02_native_model/" + name
        assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() != frozen["files"][path]
    # The actual original controlled archive is local only; CI does not invent it.
    archive = ROOT / ".local/p36-mm02-model/execution-01/RAW.zip"
    if archive.exists():
        expected = json.loads((HERE / "ARCHIVE.json").read_text())["sha256"]
        assert hashlib.sha256(archive.read_bytes()).hexdigest() == expected
    print("P36_SCIENTIFIC_RESULT_UNCHANGED; current pilot/remote are post-run code; model calls=0")


if __name__ == "__main__":
    verify()
