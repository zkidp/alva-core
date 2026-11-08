"""Repeat only the existing non-scientific toy canary, with safe diagnostics."""
import argparse
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks.context_flash_pilot import runner
from benchmarks.context_flash_resume.transport import DiagnosticAPI, diagnostic


def run(args):
    if args.output.exists(): raise RuntimeError("CANARY_OUTPUT_ALREADY_EXISTS")
    observed = []
    class ObservedAPI(DiagnosticAPI):
        def __init__(self, path):
            super().__init__(path)
            observed.append(self)
    status = "FAIL"
    try:
        with patch.object(runner, "API", ObservedAPI): runner.canary(args)
        status = "PASS"
    finally:
        value = {"status": status, "requests": sum(a.submitted_chat_requests for a in observed),
                 "transport_failures": [v for a in observed for v in a.failures]}
        with args.output.with_suffix(".diagnostics.json").open("x", encoding="utf-8") as stream: json.dump(value, stream, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args())
