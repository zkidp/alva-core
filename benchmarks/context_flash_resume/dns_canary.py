"""Existing toy canary over the scoped, normally TLS-verified provider route."""
import argparse
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks.context_flash_pilot import runner
from benchmarks.context_flash_resume.dns_route import RoutedAPI
from integrations.codex.maintenance_host import sha


def run(args):
    if args.output.exists(): raise RuntimeError("EXISTING_CANARY_OUTPUT")
    instances = []
    class API(RoutedAPI):
        def __init__(self, path):
            super().__init__(path, address=args.address)
            instances.append(self)
    status = "FAIL"
    try:
        with patch.object(runner, "API", API): runner.canary(args)
        status = "PASS"
    finally:
        data = {"status": status, "address_sha256": sha(args.address.encode()), "route_seconds": 300,
                "requests": sum(a.submitted_chat_requests for a in instances),
                "probes": [a.route_probe for a in instances], "diagnostics": [e for a in instances for e in a.failures]}
        with args.output.with_suffix(".route.json").open("x", encoding="utf-8") as stream: json.dump(data, stream, indent=2)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--credentials", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--address", required=True)
    run(p.parse_args())
