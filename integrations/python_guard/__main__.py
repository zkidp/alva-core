"""JSON-file CLI; results stay local and no source changes are published."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .guard import Guard, GuardError, load_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--policy", type=Path, help="host-approved policy outside the project")
    parser.add_argument("operation", choices=["snapshot", "verify", "report"])
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args()
    try:
        request = load_json(args.request.read_bytes())
        result = getattr(Guard(args.store, args.policy), args.operation)(request)
        if args.operation == "snapshot":
            code = 0
        elif result["checks_status"] == "PASS" and result["applicability_status"] == "CURRENT":
            code = 0
        else:
            code = 1 if result["checks_status"] == "FAIL" else 2
    except (GuardError, OSError, KeyError, TypeError, UnicodeError, ValueError) as exc:
        reason = exc.code if isinstance(exc, GuardError) else "INVALID_INPUT_OR_ENVIRONMENT"
        unknown = reason in {"EVIDENCE_TAMPERED", "EVIDENCE_UNAVAILABLE", "UNSTABLE_CAPTURE"}
        result = {"status": "UNKNOWN" if unknown else "INPUT_REJECTED", "checks_status": "UNKNOWN",
                  "applicability_status": "UNKNOWN", "reason": reason, "detail": str(exc)}
        code = 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
