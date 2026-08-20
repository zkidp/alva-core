#!/usr/bin/env python3
"""Capability catalog AEP regression (pre-RFC; no number).

Covers the minimal AEP surface:
  describe_capability(name)
  list_capabilities(category=builtin|operator|all)

Locked principles: compiler-owned registry; no fuzzy; declared synonyms only
(sorted->sort, &&->and, ||->or); no applicability; no entity navigation;
list is category-scoped and bounded; read-only / zero side effects; A1
non-leak.

Usage: ALVA=<alva-exe> python tests/air/capability_catalog_test.py
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.join(HERE, "rfc0005_fixture", "alva.toml")


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

    def rev():
        return a.tool("inspect_project")["result"]["project_revision"]

    rev0 = rev()

    # registration: discoverable through describe_operation
    r = a.tool("describe_operation", name="describe_capability")
    check("D1 describe_capability registered",
          r.get("ok") and r["result"]["name"] == "describe_capability", r)
    r = a.tool("describe_operation", name="list_capabilities")
    check("D1b list_capabilities registered",
          r.get("ok") and r["result"]["name"] == "list_capabilities", r)

    # positive knowledge
    r = a.tool("describe_capability", name="sort")
    check("D2 describe sort -> supported canonical sort",
          r.get("ok") and r["result"]["supported"] is True
          and r["result"]["canonical_name"] == "sort"
          and r["result"]["category"] == "builtin"
          and r["result"]["arity"] == "unary"
          and r["result"]["mapping_kind"] == "canonical", r)

    # alias canonicalization
    r = a.tool("describe_capability", name="to_string")
    check("D3 alias to_string -> canonical to-string",
          r.get("ok") and r["result"]["supported"] is True
          and r["result"]["canonical_name"] == "to-string"
          and r["result"]["mapping_kind"] == "alias", r)

    # declared synonyms are AUTHORITATIVE CORRECTIONS, not executable forms
    r = a.tool("describe_capability", name="sorted")
    check("D4 declared synonym sorted -> supported false + canonical_alternative sort",
          r.get("ok") and r["result"]["supported"] is False
          and r["result"]["canonical_alternative"] == "sort"
          and r["result"]["mapping_kind"] == "declared_synonym", r)
    r = a.tool("describe_capability", name="&&")
    check("D4b declared synonym && -> supported false + canonical_alternative and",
          r.get("ok") and r["result"]["supported"] is False
          and r["result"]["canonical_alternative"] == "and"
          and r["result"]["mapping_kind"] == "declared_synonym", r)

    # negative knowledge (no fuzzy)
    r = a.tool("describe_capability", name="removefunction")
    check("D5 removefunction -> supported false + declared_alternatives",
          r.get("ok") and r["result"]["supported"] is False
          and r["result"]["canonical_alternative"] is None
          and "declared_alternatives" in r["result"], r)
    r = a.tool("describe_capability", name="filter")
    check("D5b filter -> supported false (no fuzzy alternative)",
          r.get("ok") and r["result"]["supported"] is False, r)
    check("D6 capability queries are read-only (hash unchanged)", rev() == rev0, rev())

    # list: category-scoped + bounded + concise
    r = a.tool("list_capabilities", category="operator")
    ops = r["result"]["capabilities"]
    check("D7 list operator (13) bounded",
          r.get("ok") and r["result"]["count"] == 13
          and len(ops) == 13
          and "and" in ops and "+" in ops and "&&" not in ops, r)
    r = a.tool("list_capabilities", category="builtin")
    bs = r["result"]["capabilities"]
    check("D8 list builtin (29) category-scoped",
          r.get("ok") and r["result"]["count"] == 29
          and "sort" in bs and "len" in bs, r)
    r = a.tool("list_capabilities", category="all")
    check("D9 list all = 42", r.get("ok") and r["result"]["count"] == 42, r)
    r = a.tool("list_capabilities", category="bogus")
    check("D10 bad category -> E_AEP_BAD_REQUEST",
          not r.get("ok") and r["error_code"] == "E_AEP_BAD_REQUEST", r)
    check("D10b failed list read-only", rev() == rev0, rev())

    # A1 non-leak
    for name in ("sort", "removefunction"):
        s = json.dumps(a.tool("describe_capability", name=name))
        check(f"D11 A1 non-leak describe {name}",
              "inspect_change_impact" not in s
              and "inspect_schema_gaps" not in s, s[:200])
    s = json.dumps(a.tool("list_capabilities", category="operator"))
    check("D12 A1 non-leak list", "inspect_change_impact" not in s, s[:200])

    a.close()
    print(f"Capability catalog AEP regressions PASSED ({checks} checks)")


if __name__ == "__main__":
    main()
