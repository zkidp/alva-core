#!/usr/bin/env python3
"""Diagnostic golden test checker (strict).

Expected format (.expected.json):

    {
      "allow_extra": false,       // optional; defaults to false
      "diagnostics": [
        {"code": "E_TYPE_001", "module": "demo", "function": "main"}
      ]
    }

Rules:
  - default (allow_extra=false): EXACT — the actual diagnostic code multiset
    and count must equal the expected ones, and every expected diagnostic must
    match a DISTINCT actual diagnostic (field-wise subset match, recursive).
  - allow_extra=true: every expected diagnostic must match a distinct actual;
    additional actual diagnostics are permitted.
  - before comparison, both sides are sorted by a canonical key
    (code, module, function, span start, message), so compiler output order is
    irrelevant; the protocol is "compare sorted by code/span".
  - a diagnostic is a match if all fields present in the expected entry are
    equal in the actual entry (recursive subset match).
  - the same actual diagnostic can never satisfy two expected entries.

Other invariants kept from the previous checker:
  - `alva check --json` must exit non-zero;
  - the compiler must not panic (stderr/stdout must not contain
    'panicked'/'overflow'/'stack overflow');
  - at least one diagnostic must be emitted.

Usage:
  python golden_check.py <alva> <fixture.alva>...
  python golden_check.py --self-test
"""

import json
import os
import subprocess
import sys


def subset_match(actual, expected):
    """Recursive subset match: every key/value in expected must appear in actual."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        for k, v in expected.items():
            if k not in actual:
                return False
            if not subset_match(actual[k], v):
                return False
        return True
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return False
        if not expected:
            return True
        return all(any(subset_match(x, y) for x in actual) for y in expected)
    return actual == expected


def diag_sort_key(d):
    span = d.get("span")
    if not isinstance(span, dict):
        span = {}
    start = span.get("start")
    if not isinstance(start, dict):
        start = {}
    return (
        d.get("code", ""),
        d.get("module", ""),
        d.get("function", ""),
        start.get("line", 0),
        start.get("column", 0),
        d.get("message", ""),
    )


def match_distinct(actuals, expecteds):
    """Every expected must match a distinct actual (backtracking)."""
    n_actual = len(actuals)
    used = [False] * n_actual

    def rec(i):
        if i == len(expecteds):
            return True
        for j, a in enumerate(actuals):
            if not used[j] and subset_match(a, expecteds[i]):
                used[j] = True
                if rec(i + 1):
                    return True
                used[j] = False
        return False

    return rec(0)


def compare(actual, expected_spec):
    """Strict comparison. Returns (ok, reason)."""
    if not isinstance(actual, list) or not actual:
        return False, "no diagnostics emitted"
    if not isinstance(expected_spec, dict) or "diagnostics" not in expected_spec:
        return False, (
            "expected file must use the strict format "
            '{"allow_extra": bool, "diagnostics": [...]}'
        )
    allow_extra = bool(expected_spec.get("allow_extra", False))
    expecteds = expected_spec["diagnostics"]
    if not isinstance(expecteds, list):
        return False, "'diagnostics' must be a list"
    for exp in expecteds:
        if not isinstance(exp, dict) or "code" not in exp:
            return False, "each expected diagnostic must declare a 'code'"

    # Canonical sort by code/span so output order never matters.
    actual_sorted = sorted(actual, key=diag_sort_key)
    expected_sorted = sorted(expecteds, key=diag_sort_key)

    if not match_distinct(actual_sorted, expected_sorted):
        return False, "an expected diagnostic has no distinct actual match"

    if allow_extra:
        return True, ""

    if len(actual_sorted) != len(expected_sorted):
        return False, (
            f"exact mode: expected {len(expected_sorted)} diagnostics, "
            f"got {len(actual_sorted)}"
        )
    actual_codes = sorted(d.get("code", "") for d in actual_sorted)
    expected_codes = sorted(d.get("code", "") for d in expected_sorted)
    if actual_codes != expected_codes:
        return False, (
            "exact mode: diagnostic code multiset mismatch "
            f"expected={expected_codes} actual={actual_codes}"
        )
    return True, ""


def run_compiler(alva, path):
    env = dict(os.environ)
    env_path = path[:-5] + ".env"
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return subprocess.run(
        [alva, "check", path, "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


def check_one(path, alva):
    expected_path = path[:-5] + ".expected.json"
    with open(expected_path, encoding="utf-8") as fh:
        expected_spec = json.load(fh)
    proc = run_compiler(alva, path)
    if proc.returncode == 0:
        print(f"FAIL {path}: expected compile error, got success")
        return False
    low = (proc.stderr + proc.stdout).lower()
    if "panicked" in low or "overflow" in low or "stack overflow" in low:
        print(f"FAIL {path}: compiler panicked\n{proc.stderr[-500:]}")
        return False
    try:
        actual = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        print(f"FAIL {path}: cannot parse diagnostics JSON: {e}\n{proc.stdout[-500:]}")
        return False
    ok, reason = compare(actual, expected_spec)
    if not ok:
        print(f"FAIL {path}: {reason}")
        print(f"  expected: {json.dumps(expected_spec, ensure_ascii=False)}")
        print(f"  actual:   {json.dumps(actual, ensure_ascii=False)}")
        return False
    print(f"PASS golden {os.path.basename(path)}")
    return True


def self_test():
    """Unit tests for the strict matching semantics."""
    cases = []

    def case(name, fn):
        cases.append((name, fn))

    d1 = {"code": "E_TYPE_001", "function": "main"}
    d2 = {"code": "E_NAME_001", "function": "main"}
    d1b = {"code": "E_TYPE_001", "function": "other"}

    case("exact pass", lambda: compare([d1, d2], {"allow_extra": False, "diagnostics": [d1, d2]})[0])
    case("exact fails on extra", lambda: not compare([d1, d2], {"allow_extra": False, "diagnostics": [d1]})[0])
    case("exact fails on missing", lambda: not compare([d1], {"allow_extra": False, "diagnostics": [d1, d2]})[0])
    case("exact fails on code multiset", lambda: not compare([d1], {"allow_extra": False, "diagnostics": [d1b]})[0])
    case("allow_extra passes", lambda: compare([d1, d2], {"allow_extra": True, "diagnostics": [d1]})[0])
    case("distinct actuals enforced",
         lambda: not compare([d1], {"allow_extra": False, "diagnostics": [d1, d1b]})[0])
    case("old array format rejected",
         lambda: not compare([d1], [d1])[0])
    case("order independent",
         lambda: compare([d1, d2], {"allow_extra": False, "diagnostics": [d2, d1]})[0])

    failed = 0
    for name, fn in cases:
        try:
            ok = fn()
        except Exception as e:  # noqa: BLE001
            print(f"FAIL self-test {name}: raised {e!r}")
            failed += 1
            continue
        if not ok:
            print(f"FAIL self-test {name}")
            failed += 1
        else:
            print(f"PASS self-test {name}")
    if failed:
        sys.exit(1)
    print(f"self-test OK ({len(cases)} cases)")


def main():
    if sys.argv[1:] == ["--self-test"]:
        self_test()
        return
    alva = sys.argv[1]
    paths = sys.argv[2:]
    ok = True
    for p in paths:
        if not os.path.exists(p[:-5] + ".expected.json"):
            print(f"SKIP {p}: no .expected.json")
            continue
        ok = check_one(p, alva) and ok
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
