"""Trusted-host CLI. Never grant the candidate agent write access to this process/state."""

import argparse
import json
from pathlib import Path

from integrations.python_guard import GuardError
from .workflow import CandidateSession


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["prepare", "verify", "report"])
    parser.add_argument("--control", type=Path, required=True)
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--approved-policy-id")
    parser.add_argument("--candidate", type=Path)
    args = parser.parse_args()
    try:
        if args.operation == "prepare":
            if not all((args.policy, args.candidate, args.approved_policy_id)):
                parser.error("prepare requires --policy, --approved-policy-id and --candidate")
            result = CandidateSession.prepare(args.control, args.policy, args.candidate, args.approved_policy_id).description()
            code = 0
        else:
            result = getattr(CandidateSession(args.control), args.operation)()
            code = 0 if (result["checks_status"] == "PASS" and result["applicability_status"] == "CURRENT"
                         and result.get("candidate_matches_verified_patch", True)) else (1 if result["checks_status"] == "FAIL" else 2)
    except (GuardError, OSError, KeyError, TypeError, ValueError) as exc:
        result = {"checks_status": "UNKNOWN", "applicability_status": "UNKNOWN",
                  "reason": exc.code if isinstance(exc, GuardError) else "WORKFLOW_UNAVAILABLE"}
        code = 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
