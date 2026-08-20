#!/usr/bin/env python3
"""RFC-0007 / AEP-0004 compiler-level regression: Typed Semantic Operand
Grounding.

Locked contracts (2026-08-17 review):
  1. semantic identity != current revision (candidates carry BOTH);
  2. semantic handles resolve against the CURRENT staged transaction;
  3. 0/1/>1 matches -> NOT_FOUND / success / AMBIGUOUS (never silent pick);
  4. stale bare revision -> E_AEP_OPERAND_STALE + structured recovery
     (no silent refresh);
  5. semantic handle allows call-time resolution by design;
  6. expected_type is a CONSTRAINT (E_AEP_OPERAND_TYPE_MISMATCH), not a
     search hint or cast;
  7. operand resolution completes before materialize (zero side effects);
  8. candidate_bindings items carry current_revision + semantic_handle.

Usage: ALVA=<alva-exe> python tests/air/rfc0007_operand_test.py
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.join(HERE, "rfc0007_fixture", "alva.toml")


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
        return r["result"]["project_revision"]

    def lit(kind, value):
        r = a.tool("create_literal", type=kind, value=value)
        check(f"create_literal {kind}={value}", r.get("ok"), r)
        return r["result"]["revision"]

    rev0 = project_rev()

    # O1: candidate_bindings items carry current_revision + semantic_handle.
    r = a.tool("describe_construction", kind="fold", include_candidates=True)
    items = r["result"]["candidate_bindings"]["items"]
    check("O1 candidates have current_revision + semantic_handle",
          items and all(
              "current_revision" in it and "semantic_handle" in it
              and it["semantic_handle"]["symbol"] == it["name"]
              for it in items), items)
    tmp_handles = [it["semantic_handle"] for it in items
                   if it["semantic_handle"]["symbol"] == "tmp"]
    check("O1 tmp semantic_handle scoped to a fixture function",
          tmp_handles and all(
              h["scope"] in ("rfc0007.a.normalize", "rfc0007.a.other")
              for h in tmp_handles), items)
    # O12: the aep.py CLI forwards key=value as strings, so a string
    # include_candidates="true" must ALSO return candidate items (otherwise the
    # semantic-handle affordance is unreachable in the real agent environment).
    r = a.tool("describe_construction", kind="fold", include_candidates="true")
    cb = r["result"]["candidate_bindings"]
    check("O12 string include_candidates=true returns items",
          "items" in cb and cb["items"], cb)
    handle_tmp = {"symbol": "tmp", "scope": "rfc0007.a.normalize",
                  "expected_type": "i64"}

    # O2: semantic handle resolves against the current staged graph -> ok.
    r = a.tool("construct_expression", kind="err", value=handle_tmp)
    check("O2 semantic handle resolves to current revision",
          r.get("ok") and r["result"]["kind"] == "err", r)
    rev0 = project_rev()

    # O3: ambiguity -> E_AEP_OPERAND_AMBIGUOUS + candidates (no silent pick).
    r = a.tool("construct_expression", kind="err", value={"symbol": "tmp"})
    amb_ok = (
        not r.get("ok")
        and r["error_code"] == "E_AEP_OPERAND_AMBIGUOUS"
        and len(r["result"]["candidates"]) >= 2
        and any("rfc0007.a.normalize" in c["scope"] for c in r["result"]["candidates"])
        and any("rfc0007.a.other" in c["scope"] for c in r["result"]["candidates"])
    )
    check("O3 ambiguous -> E_AEP_OPERAND_AMBIGUOUS", amb_ok, r)
    check("O7 failed ambiguity leaves hash unchanged", project_rev() == rev0, project_rev())

    # O4: scope disambiguates.
    r = a.tool("construct_expression", kind="err",
               value={"symbol": "tmp", "scope": "rfc0007.a.normalize"})
    check("O4 scope disambiguates (normalize.tmp i64)",
          r.get("ok") and r["result"]["kind"] == "err", r)
    rev0 = project_rev()
    r = a.tool("construct_expression", kind="err",
               value={"symbol": "tmp", "scope": "rfc0007.a.other"})
    check("O4b scope disambiguates (other.tmp string)",
          r.get("ok") and r["result"]["kind"] == "err", r)
    rev0 = project_rev()

    # O5: no match -> E_AEP_OPERAND_NOT_FOUND.
    r = a.tool("construct_expression", kind="err", value={"symbol": "nosuch"})
    check("O5 no match -> E_AEP_OPERAND_NOT_FOUND",
          not r.get("ok") and r["error_code"] == "E_AEP_OPERAND_NOT_FOUND", r)
    check("O7 failed not-found leaves hash unchanged", project_rev() == rev0, project_rev())

    # O6: expected_type is a CONSTRAINT (not coercion / search hint).
    r = a.tool("construct_expression", kind="err",
               value={"symbol": "tmp", "scope": "rfc0007.a.normalize",
                      "expected_type": "string"})
    check("O6 expected_type constraint -> E_AEP_OPERAND_TYPE_MISMATCH",
          not r.get("ok") and r["error_code"] == "E_AEP_OPERAND_TYPE_MISMATCH"
          and r["result"]["expected"] == "string"
          and r["result"]["actual"] == "i64", r)
    check("O7 failed type constraint leaves hash unchanged", project_rev() == rev0, project_rev())

    # O6b: matching expected_type passes.
    r = a.tool("construct_expression", kind="err",
               value={"symbol": "tmp", "scope": "rfc0007.a.normalize",
                      "expected_type": "i64"})
    check("O6b matching expected_type passes",
          r.get("ok") and r["result"]["kind"] == "err", r)
    rev0 = project_rev()

    # O9: bare revision operands still work (RFC-0006 compatibility).
    l = lit("string", "x")
    r = a.tool("construct_expression", kind="err", value=l)
    check("O9 bare revision operand works", r.get("ok"), r)
    rev0 = project_rev()

    # O7/contract-4: bare nonexistent revision keeps the existing
    # E_AEP_ENTITY_NOT_FOUND contract (strict, structured payload); the
    # E_AEP_OPERAND_STALE classifier is covered by Rust unit tests
    # (stale_revision) because the AEP surface cannot easily produce a stale
    # entity-carrying revision (most edits mutate in place).
    r = a.tool("construct_expression", kind="err", value="deadbeef")
    check("O7 bare nonexistent revision -> E_AEP_ENTITY_NOT_FOUND",
          not r.get("ok") and r["error_code"] == "E_AEP_ENTITY_NOT_FOUND"
          and "candidates" in r["result"], r)
    check("O7 failed not-found (bare) leaves hash unchanged",
          project_rev() == rev0, project_rev())

    # R11 (D02 signature): replace_expression with a missing/stale parent now
    # returns structured candidates (one-shot correction) instead of a bare
    # error that invites repeated retries.
    l3 = lit("i64", "1")
    r = a.tool("replace_expression", parent="deadbeef", child=l3, position="value")
    check("R11 replace_expression missing parent -> structured recovery",
          not r.get("ok") and r["error_code"] == "E_AEP_ENTITY_NOT_FOUND"
          and "candidates" in r["result"], r)
    check("R11 failed replace leaves hash unchanged", project_rev() == rev0, project_rev())

    a.close()
    print(f"RFC-0007 operand grounding regressions PASSED ({checks} checks)")


if __name__ == "__main__":
    main()
