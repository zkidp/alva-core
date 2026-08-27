#!/usr/bin/env python3
"""Generate the deterministic 96-slot execution schedule.

Seed is frozen (20260827). The shuffle interleaves arms and groups so
provider-side time drift is not systematically bound to an arm. The
schedule hash is part of EXECUTION-FREEZE.json.

Usage: python generate_schedule.py --manifests <run-manifests-dir>
       --out <execution-schedule.json> [--seed 20260827]
"""

import argparse
import hashlib
import json
import os
import random


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifests", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=20260827)
    args = ap.parse_args()
    index = json.load(open(os.path.join(args.manifests,
                                        "MANIFEST-INDEX.json"),
                           encoding="utf-8"))
    slots = list(index["manifests"])
    rng = random.Random(args.seed)
    rng.shuffle(slots)
    schedule = {
        "seed": args.seed,
        "count": len(slots),
        "slots": [{"slot": i + 1, "task_id": s["task_id"],
                   "group": s["group"], "arm": s["arm"], "rep": s["rep"],
                   "manifest": s["manifest"], "sha256": s["sha256"]}
                  for i, s in enumerate(slots)],
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(schedule, fh, indent=2)
    blob = json.dumps(schedule, sort_keys=True).encode()
    print("schedule sha256:", hashlib.sha256(blob).hexdigest())
    arms = [s["arm"] for s in schedule["slots"]]
    print("first 12 arms:", "".join("H" if a == "HIGH" else "L"
                                    for a in arms[:12]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
