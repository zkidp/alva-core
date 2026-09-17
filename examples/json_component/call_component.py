#!/usr/bin/env python3
"""Small fail-closed caller for the generated ALVA JSON component."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def validate_completed(completed: subprocess.CompletedProcess[bytes]) -> int:
    """Validate termination and the complete response before accepting a result."""
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"component failed with exit {completed.returncode}: {detail}")
    if not completed.stdout:
        raise RuntimeError("component returned empty stdout")
    try:
        response = json.loads(completed.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("component returned invalid or truncated JSON") from exc
    if not isinstance(response, dict) or set(response) != {"result"}:
        raise RuntimeError("component response must contain exactly an integer result field")
    result = response["result"]
    if isinstance(result, bool) or not isinstance(result, int):
        raise RuntimeError("component result is not an integer")
    return result


def call_component(executable: Path, request: dict[str, Any], timeout: float = 5.0) -> int:
    completed = subprocess.run(
        [str(executable)],
        input=json.dumps(request, separators=(",", ":")).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    return validate_completed(completed)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit(f"usage: {sys.argv[0]} COMPONENT INTEGER [INTEGER ...]")
    value = call_component(
        Path(sys.argv[1]), {"op": "sum", "values": [int(item) for item in sys.argv[2:]]}
    )
    print(value)
