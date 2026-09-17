#!/usr/bin/env python3
"""Linux-only checks for benchmark timeout/output/process-failure classification."""

from __future__ import annotations

import json
import stat
import tempfile
from pathlib import Path

import benchmark


def helper(root: Path, name: str, body: str) -> Path:
    path = root / name
    path.write_text(f"#!/usr/bin/env python3\n{body}\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="json-patch-driver-limits-") as temp_text:
        root = Path(temp_text)
        sleeper = helper(root, "sleeper.py", "import time; time.sleep(20)")
        spammer = helper(root, "spammer.py", "import sys; sys.stdout.buffer.write(b'x' * (17 * 1024 * 1024))")
        signaler = helper(root, "signaler.py", "import os, signal; os.kill(os.getpid(), signal.SIGTERM)")
        outcomes = {
            "timeout": benchmark.classify(benchmark.run_bounded(sleeper, b"")),
            "output": benchmark.classify(benchmark.run_bounded(spammer, b"")),
            "signal": benchmark.classify(benchmark.run_bounded(signaler, b"")),
        }
        assert outcomes == {
            "timeout": "external_timeout",
            "output": "external_output_limit",
            "signal": "signal_or_memory_kill",
        }
        print(json.dumps({"status": "PASS", "outcomes": outcomes}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
