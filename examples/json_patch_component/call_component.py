#!/usr/bin/env python3
"""Fail-closed caller for the generated ALVA JSON Pointer/Patch CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def call_component(
    executable: Path, request: dict[str, Any], timeout: float = 5.0
) -> Any:
    completed = subprocess.run(
        [str(executable)],
        input=json.dumps(request, separators=(",", ":")).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"component rejected the request ({completed.returncode}): {detail}")
    if not completed.stdout:
        raise RuntimeError("component returned empty stdout")
    try:
        return json.loads(completed.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("component returned invalid or truncated JSON") from exc


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(f"usage: {sys.argv[0]} COMPONENT REQUEST.json")
    request_value = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    if not isinstance(request_value, dict):
        raise SystemExit("request file must contain one JSON object")
    print(json.dumps(call_component(Path(sys.argv[1]), request_value), separators=(",", ":")))
