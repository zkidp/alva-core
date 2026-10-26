"""Persist actual unit-test log; no external APIs or candidate execution."""
import argparse
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    log = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent), pattern="test_freeze.py")
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    from integrations.benchmark_runtime_v2.freeze import pack_git
    bundle = pack_git(ROOT, "ecadfea51ccd147f99f58ec5e891869744bc664c", ["tests/integrations/codex_native_test.py", "feasibility/native_api/run.py"])
    report = {"platform": sys.platform, "tests": result.testsRun, "passed": result.wasSuccessful(),
              "log": log.getvalue(), "bundle_sha256": bundle["payload_sha256"],
              "generation_calls": 0, "input_token_calls": 0}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(log.getvalue())
    raise SystemExit(0 if result.wasSuccessful() else 1)
