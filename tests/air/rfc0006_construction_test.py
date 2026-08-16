#!/usr/bin/env python3
"""RFC-0006 / AEP-0003 v0.1 compiler-level regression: Typed Semantic
Construction.

Covers the 12 pre-agent gates from the RFC-0006 review plus v0.1-specific
contracts:

  C1  describe_construction schema for every v0.1 kind
  C2  alias canonicalization (result_err -> err) advertises AND executes
  C3  missing operand -> structured E_AEP_CONSTRUCTION_INCOMPLETE
  C4  wrong child type -> structured E_AEP_CONSTRUCTION_TYPE_MISMATCH
  C5  wrong expected_type -> typed mismatch
  C6  stale/nonexistent revision -> deterministic failure
  C7  source string -> E_AEP_CONSTRUCTION_NO_SOURCE
  C8  failed construction -> transaction semantic hash unchanged
  C9  same semantic input -> deterministic AIR revision
  C10 constructed node -> inspect_entity reflects expected kind/children
  C11 check_transaction succeeds for valid construction
  C12 existing create_* behavior -> zero regression

  C13 unknown kind -> E_AEP_CONSTRUCTION_UNKNOWN_KIND + candidates
  C14 range is a fold sub-form (validated, zero side effects)
  C15 candidate_bindings bounded (total/returned/truncated, items <= 8)
  C16 describe_construction concise by default (no items unless asked)

Usage: ALVA=<alva-exe> python tests/air/rfc0006_construction_test.py
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.join(HERE, "rfc0005_fixture", "alva.toml")

V0_1_KINDS = [
    "field", "record", "record_update", "veclit", "fold",
    "match", "ok", "err", "not", "range",
]


def fail(msg):
    print(f"FAIL: {msg}", flush=True)
    raise SystemExit(1)


class Agent:
    def __init__(self, alva, project):
        self.proc = subprocess.Popen(
            [alva, "agent"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace")
        self.tool("begin_transaction", project=project)

    def tool(self, tool_name, **kw):
        payload = {"tool": tool_name}
        payload.update(kw)
        self.proc.stdin.write(json.dumps(payload) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            fail(f"alva agent closed while processing {payload}")
        try:
            return json.loads(line)
        except Exception:
            fail(f"non-JSON agent response: {line!r}")

    def close(self):
        try:
            self.proc.stdin.write(json.dumps({"tool": "abort_transaction"}) + "\n")
            self.proc.stdin.flush()
        except Exception:
            pass
        self.proc.kill()


def main():
    alva = os.environ.get("ALVA")
    if not alva:
        fail("ALVA env var required")
    a = Agent(alva, PROJECT)
    checks = 0

    def check(name, cond, detail=""):
        nonlocal checks
        checks += 1
        print(("PASS" if cond else "FAIL"), name)
        if not cond:
            print("   ", detail)
            a.close()
            raise SystemExit(1)

    def project_rev():
        r = a.tool("inspect_project")
        if not r.get("ok"):
            fail(f"inspect_project failed: {r}")
        return r["result"]["project_revision"]

    def lit(kind, value):
        r = a.tool("create_literal", type=kind, value=value)
        check(f"create_literal {kind}={value}", r.get("ok"), r)
        return r["result"]["revision"]

    # C1: describe_construction schema for every v0.1 kind.
    for k in V0_1_KINDS:
        r = a.tool("describe_construction", kind=k)
        ok = (
            r.get("ok")
            and r["result"]["canonical_kind"] == k
            and isinstance(r["result"]["required_children"], list)
            and isinstance(r["result"]["optional_children"], list)
            and "result_type_rule" in r["result"]
        )
        check(f"C1 describe {k} schema", ok, r)

    # C16: describe_construction concise by default.
    r = a.tool("describe_construction", kind="fold")
    cb = r["result"]["candidate_bindings"]
    check("C16 concise default (no items, has total)",
          "items" not in cb and "total" in cb, cb)
    r = a.tool("describe_construction", kind="fold", include_candidates=True)
    cb = r["result"]["candidate_bindings"]
    check("C16 include_candidates returns items",
          "items" in cb and "total" in cb and "returned" in cb and "truncated" in cb, cb)
    check("C15 candidate_bindings bounded <= 8",
          len(cb["items"]) <= 8 and cb["returned"] == len(cb["items"]), cb)

    # C7: source string forbidden.
    r = a.tool("construct_expression", kind="err", source="(err (int 1))")
    check("C7 source string -> E_AEP_CONSTRUCTION_NO_SOURCE",
          not r.get("ok") and r["error_code"] == "E_AEP_CONSTRUCTION_NO_SOURCE", r)

    # C13: unknown kind recovery.
    r = a.tool("construct_expression", kind="create_fold", value="x")
    check("C13 unknown kind -> structured candidates",
          not r.get("ok")
          and r["error_code"] == "E_AEP_CONSTRUCTION_UNKNOWN_KIND"
          and "candidates" in r["result"]
          and any("fold" in c for c in r["result"]["candidates"]), r)

    # C3: missing operand -> structured incomplete.
    rev_before = project_rev()
    r = a.tool("construct_expression", kind="err")
    incomplete_ok = (
        not r.get("ok")
        and r["error_code"] == "E_AEP_CONSTRUCTION_INCOMPLETE"
        and r["result"]["missing"] == ["value"]
        and "provided" in r["result"]
        and "candidate_bindings" in r["result"]
    )
    check("C3 missing operand -> E_AEP_CONSTRUCTION_INCOMPLETE", incomplete_ok, r)
    check("C8 failed construction leaves hash unchanged",
          project_rev() == rev_before, project_rev())

    # C2: alias canonicalization (result_err -> err).
    r = a.tool("describe_construction", kind="result_err")
    check("C2 alias describe -> canonical err",
          r.get("ok") and r["result"]["canonical_kind"] == "err", r)
    lit_str = lit("string", "boom")
    r = a.tool("construct_expression", kind="result_err", value=lit_str,
               expected_type="(result string string)")
    check("C2 alias construct result_err executes",
          r.get("ok") and r["result"]["kind"] == "err"
          and r["result"]["result_type"] == "result ? string", r)
    err_rev = r["result"]["revision"]

    # C10: constructed node reflects kind/children.
    r = a.tool("inspect_entity", entity=err_rev)
    check("C10 inspect_entity reflects constructed err node",
          r.get("ok")
          and r["result"]["kind"] == "err"
          and r["result"]["slots"].get("value", [])[0] == lit_str, r)

    # C9: determinism (same semantic input -> same revision).
    r2 = a.tool("construct_expression", kind="err", value=lit_str,
                expected_type="(result string string)")
    check("C9 deterministic AIR revision",
          r2.get("ok") and r2["result"]["revision"] == err_rev, r2)

    # C4: wrong child type -> structured type mismatch.
    r = a.tool("resolve_entity", name="a_fn", kind="function")
    check("C4 resolve a_fn", r.get("ok"), r)
    fn_entity = r["result"]["entity"]
    r = a.tool("construct_expression", kind="field", name="x", value=fn_entity)
    check("C4 wrong child type -> E_AEP_CONSTRUCTION_TYPE_MISMATCH",
          not r.get("ok")
          and r["error_code"] == "E_AEP_CONSTRUCTION_TYPE_MISMATCH"
          and r["result"]["argument"] == "value", r)

    # C6: nonexistent revision -> deterministic failure.
    r = a.tool("construct_expression", kind="err", value="deadbeef")
    check("C6 nonexistent revision -> deterministic failure",
          not r.get("ok") and r["error_code"] in (
              "E_AEP_ENTITY_NOT_FOUND", "E_AEP_STALE_REVISION"), r)
    check("C8 failed construct (stale rev) leaves hash unchanged",
          project_rev() == rev_before, project_rev())

    # C5: wrong expected_type -> typed mismatch.
    lit_true = lit("bool", "true")
    r = a.tool("construct_expression", kind="not", value=lit_true,
               expected_type="string")
    check("C5 wrong expected_type -> E_AEP_CONSTRUCTION_TYPE_MISMATCH",
          not r.get("ok")
          and r["error_code"] == "E_AEP_CONSTRUCTION_TYPE_MISMATCH"
          and r["result"]["expected"] == "string"
          and r["result"]["actual"] == "bool", r)
    check("C8 failed construct (expected_type) leaves hash unchanged",
          project_rev() == rev_before, project_rev())

    # C5b: correct expected_type succeeds.
    r = a.tool("construct_expression", kind="not", value=lit_true,
               expected_type="bool")
    check("C5b correct expected_type succeeds",
          r.get("ok") and r["result"]["kind"] == "not"
          and r["result"]["result_type"] == "bool", r)

    # C14: range is a fold sub-form (validated, no node created).
    start = lit("i64", "0")
    end = lit("i64", "5")
    rev_before_range = project_rev()
    r = a.tool("construct_expression", kind="range",
               range_start=start, range_end=end)
    check("C14 range sub-form validates",
          r.get("ok")
          and r["result"]["kind"] == "range"
          and r["result"]["range_start"] == start
          and r["result"]["range_end"] == end, r)
    check("C14 range construct has zero side effects",
          project_rev() == rev_before_range, project_rev())

    # C11: check_transaction succeeds after valid constructions.
    r = a.tool("check_transaction")
    check("C11 check_transaction succeeds for valid construction",
          r.get("ok"), r)

    # C12: existing create_* behavior is unchanged.
    r = a.tool("create_call", name="len", args=[lit("i64", "3")])
    check("C12 create_call regression", r.get("ok"), r)
    r = a.tool("create_binary", op="+", left=lit("i64", "1"),
               right=lit("i64", "2"))
    check("C12 create_binary regression", r.get("ok"), r)

    # fold construction (required children all present).
    acc_init = lit("i64", "0")
    body = lit("i64", "1")
    r = a.tool(
        "construct_expression", kind="fold", index="i", acc_name="out",
        range_start=start, range_end=end, acc_type="i64",
        acc_init=acc_init, body=body, expected_type="i64")
    check("C11b fold construction succeeds",
          r.get("ok")
          and r["result"]["kind"] == "fold"
          and r["result"]["result_type"] == "i64", r)

    # veclit construction.
    r = a.tool("construct_expression", kind="veclit", elem_type="string",
               items=[], expected_type="(vec string)")
    check("C11c veclit construction succeeds",
          r.get("ok") and r["result"]["result_type"] == "vec string", r)

    a.close()
    print(f"RFC-0006 construction regressions PASSED ({checks} checks)")


if __name__ == "__main__":
    main()
