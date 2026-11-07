"""Export exact executed Python bytes without altering source/task/history files.

Windows checkout converted some Python files to CRLF before runtime pinning.
Recover only a recorded hash match from the fixed Git blob or its CRLF checkout
form. This never normalizes ALVA programs, bundles, assertions JSON or evidence.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent


def export(commit, destination):
    if destination.exists():
        raise ValueError("Fresh export directory required; never overwrite a checkout")
    destination.mkdir(parents=True)
    frozen = json.loads((HERE / "FREEZE.json").read_text())
    counts = {"git_blob_exact": 0, "recorded_crlf_checkout": 0}
    for name, expected in frozen["runtime_files"].items():
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or path.suffix != ".py":
            raise ValueError("Unexpected runtime path")
        data = subprocess.check_output(["git", "show", commit + ":" + name], cwd=ROOT)
        if hashlib.sha256(data).hexdigest() == expected:
            counts["git_blob_exact"] += 1
        else:
            data = data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError("No exact recorded Python-runtime byte match: " + name)
            counts["recorded_crlf_checkout"] += 1
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return counts


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--commit", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(export(args.commit, args.output)))
