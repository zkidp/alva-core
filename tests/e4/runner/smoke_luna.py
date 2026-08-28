"""Minimal E4 Luna smoke: ONE real model call against the pinned evaluated
model, verifying model pin, protocol, telemetry/usage recording, termination,
and a deterministic final reply.

Credentials are environment-only (OPENAI_API_KEY). The key is never written
to any file. Exit 0 on PASS, 1 on FAIL.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from luna_relay import LunaRelay, MODEL, PROTOCOL


def _run(tool_schema, out_path):
    schema = json.loads(Path(tool_schema).read_text(encoding="utf-8"))
    tools = schema["tools"] if isinstance(schema, dict) and "tools" in schema else schema
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    telemetry = out.with_name("telemetry.jsonl")
    fingerprint = out.with_name("fingerprint.json")

    relay = LunaRelay(tools, telemetry, fingerprint)
    instructions = "Reply with exactly OK. Do not call any tool."
    step = relay.start("smoke", instructions=instructions)

    ok = step["type"] == "final" and (step.get("text") or "").strip() == "OK"
    result = {
        "status": "PASS" if ok else "FAIL",
        "model_pinned": MODEL,
        "protocol": PROTOCOL,
        "termination": step["type"],
        "final_text": (step.get("text") or "")[:200],
        "fingerprint": json.loads(fingerprint.read_text(encoding="utf-8")),
        "telemetry_lines": len(telemetry.read_text(encoding="utf-8").splitlines()),
    }
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if ok else 1


def main_with_args(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tool-schema", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    return _run(args.tool_schema, args.out)


def main():
    return main_with_args(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
