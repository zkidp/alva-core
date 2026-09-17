#!/usr/bin/env python3
"""Linux-only cross-process regressions for the bounded benchmark driver."""

from __future__ import annotations

import json
import os
import signal
import stat
import tempfile
import time
from pathlib import Path

import benchmark

TIMEOUT = 0.75
CAP = 64 * 1024


def helper(root: Path, name: str, body: str) -> Path:
    path = root / name
    path.write_text(f"#!/usr/bin/env python3\n{body}\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def run(path: Path, payload: bytes = b"") -> dict:
    started = time.monotonic()
    result = benchmark.run_bounded(
        path, payload, timeout_seconds=TIMEOUT, output_bytes=CAP, cleanup_seconds=0.75
    )
    assert time.monotonic() - started < 3.0, path.name
    assert len(result["stdout"]) <= CAP
    assert len(result["stderr"]) <= CAP
    return result


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="json-patch-driver-limits-") as temp_text:
        root = Path(temp_text)
        no_read = helper(root, "no_read.py", "import time; time.sleep(20)")
        output_first = helper(
            root, "output_first.py",
            "import sys; sys.stdout.buffer.write(b'o' * 131072); sys.stdout.buffer.flush(); sys.stdin.buffer.read()",
        )
        early_exit = helper(root, "early_exit.py", "import sys; sys.stdin.close(); raise SystemExit(0)")
        closed_output = helper(root, "closed_output.py", "import os, time; os.close(1); os.close(2); time.sleep(20)")
        child_pid = root / "descendant.pid"
        descendant = helper(
            root, "descendant.py",
            "import os, pathlib, time\n"
            f"pid_file = pathlib.Path({str(child_pid)!r})\n"
            "pid = os.fork()\n"
            "if pid == 0:\n"
            "    pid_file.write_text(str(os.getpid()))\n"
            "    time.sleep(20)\n"
            "else:\n"
            "    raise SystemExit(0)",
        )
        stdout_spam = helper(root, "stdout_spam.py", "import sys; sys.stdout.buffer.write(b'x' * 131072)")
        stderr_spam = helper(root, "stderr_spam.py", "import sys; sys.stderr.buffer.write(b'x' * 131072)")
        success = helper(root, "success.py", "import sys; sys.stdout.write('{}')")
        nonzero = helper(root, "nonzero.py", "import sys; sys.stderr.write('ordinary failure'); raise SystemExit(7)")
        signaler = helper(root, "signaler.py", "import os, signal; os.kill(os.getpid(), signal.SIGTERM)")

        large_payload = b"p" * (1024 * 1024)
        outcomes = {
            "no_read_large_stdin": run(no_read, large_payload),
            "output_before_stdin": run(output_first, large_payload),
            "early_stdin_close": run(early_exit, large_payload),
            "closed_output_alive": run(closed_output),
            "descendant_holds_output": run(descendant),
            "stdout_limit": run(stdout_spam),
            "stderr_limit": run(stderr_spam),
            "success": run(success),
            "nonzero": run(nonzero),
            "signal": run(signaler),
        }
        expected = {
            "no_read_large_stdin": "external_timeout",
            "output_before_stdin": "external_output_limit",
            "early_stdin_close": "success",
            "closed_output_alive": "external_timeout",
            "descendant_holds_output": "external_timeout",
            "stdout_limit": "external_output_limit",
            "stderr_limit": "external_output_limit",
            "success": "success",
            "nonzero": "other_failure",
            "signal": "signal_termination",
        }
        actual = {name: benchmark.classify(result) for name, result in outcomes.items()}
        assert actual == expected, actual
        assert outcomes["early_stdin_close"]["stdin_broken_pipe"]
        assert outcomes["stdout_limit"]["stdout_bytes_read"] > CAP
        assert outcomes["stderr_limit"]["stderr_bytes_read"] > CAP

        for _ in range(50):
            if child_pid.exists():
                break
            time.sleep(0.02)
        assert child_pid.exists()
        descendant_pid = int(child_pid.read_text())
        try:
            os.kill(descendant_pid, 0)
        except ProcessLookupError:
            pass
        else:
            status = Path(f"/proc/{descendant_pid}/status")
            assert status.exists() and "State:\tZ" in status.read_text(), descendant_pid

        public = {
            name: {
                "classification": actual[name],
                "elapsed_ns": result["elapsed_ns"],
                "stdin_bytes_sent": result["stdin_bytes_sent"],
                "stdout_bytes_read": result["stdout_bytes_read"],
                "stderr_bytes_read": result["stderr_bytes_read"],
            }
            for name, result in outcomes.items()
        }
        print(json.dumps({"status": "PASS", "outcomes": public}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
