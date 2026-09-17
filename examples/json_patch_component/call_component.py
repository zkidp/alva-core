#!/usr/bin/env python3
"""Fail-closed caller for the generated ALVA JSON Pointer/Patch CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any


def _reject_non_json_constant(text: str) -> None:
    raise ValueError(f"non-JSON numeric constant: {text}")


def _parse_json_exact(data: bytes | str) -> Any:
    return json.loads(
        data,
        parse_float=Decimal,
        parse_int=int,
        parse_constant=_reject_non_json_constant,
    )


def _encode_object_value(value: Any) -> bytes:
    """Encode the convenience object API without stringifying or rounding numbers."""
    if value is None:
        return b"null"
    if type(value) is bool:
        return b"true" if value else b"false"
    if type(value) is int:
        return str(value).encode("ascii")
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("non-finite Decimal is not JSON")
        return str(value).encode("ascii")
    if type(value) is float:
        raise TypeError("Python float is not accepted; use Decimal or the text/file API")
    if type(value) is str:
        return json.dumps(value, ensure_ascii=False).encode("utf-8")
    if type(value) is list:
        return b"[" + b",".join(_encode_object_value(item) for item in value) + b"]"
    if type(value) is dict:
        parts = []
        for key, item in value.items():
            if type(key) is not str:
                raise TypeError("JSON object keys must be strings")
            parts.append(_encode_object_value(key) + b":" + _encode_object_value(item))
        return b"{" + b",".join(parts) + b"}"
    raise TypeError(f"unsupported JSON value type: {type(value).__name__}")


def call_component_bytes(
    executable: Path, request_utf8: bytes, timeout: float = 5.0
) -> bytes:
    """Send exact UTF-8 JSON bytes and return exact successful stdout bytes."""
    try:
        request_value = _parse_json_exact(request_utf8)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("request is not valid UTF-8 JSON") from exc
    if not isinstance(request_value, dict):
        raise ValueError("request must contain one JSON object")
    completed = subprocess.run(
        [str(executable)],
        input=request_utf8,
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
        _parse_json_exact(completed.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError("component returned invalid or truncated JSON") from exc
    return completed.stdout


def call_component_text(
    executable: Path, request_text: str, timeout: float = 5.0
) -> str:
    """Send an exact JSON string and return the exact successful JSON string."""
    return call_component_bytes(executable, request_text.encode("utf-8"), timeout).decode(
        "utf-8"
    )


def call_component_file(
    executable: Path, request_path: Path, timeout: float = 5.0
) -> bytes:
    """Send a request file's exact bytes and return exact successful stdout bytes."""
    return call_component_bytes(executable, request_path.read_bytes(), timeout)


def call_component(
    executable: Path, request: dict[str, Any], timeout: float = 5.0
) -> Any:
    """Convenience object API: exact int/Decimal supported; Python float rejected."""
    response = call_component_bytes(executable, _encode_object_value(request), timeout)
    return _parse_json_exact(response)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(f"usage: {sys.argv[0]} COMPONENT REQUEST.json")
    try:
        response = call_component_file(Path(sys.argv[1]), Path(sys.argv[2]))
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        raise SystemExit(str(exc)) from None
    sys.stdout.buffer.write(response)
