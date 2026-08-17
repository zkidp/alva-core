#!/usr/bin/env python3
"""Layer A — semantic handle canonicalization hardening (no RFC number).

Deterministic representation normalization ONLY (quotes / prefixes /
entity-path suffixes / display / qualified / entity id). NEVER semantic
guessing:
  0 exact matches -> NOT_FOUND
  1 exact match   -> canonicalize
  >1 exact match  -> E_AEP_ENTITY_AMBIGUOUS (no silent pick)
Entity exists but wrong kind for the op -> E_AEP_ENTITY_KIND_MISMATCH
(NAVIGATION preserved as a typed mismatch, not silently "fixed").

Usage: ALVA=<alva-exe> python tests/air/handle_canonical_test.py
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

    # 1) qualified display name (H1 display-name-as-id for inspect_entity)
    r = a.tool("inspect_function", name="rfc0005.a.a_fn")
    check("C1 qualified function name resolves", r.get("ok"), r)
    r = a.tool("inspect_entity", entity="rfc0005.a.a_fn")
    check("C2 display name as entity id (H1) resolves", r.get("ok")
          and r["result"]["kind"] == "function", r)

    # 2) quoting / prefix / path-suffix normalization
    r = a.tool("inspect_function", name="'rfc0005.a.a_fn'")
    check("C3 shell-quoted name resolves", r.get("ok"), r)
    r = a.tool("inspect_function", name="function:rfc0005.a.a_fn")
    check("C4 function: prefix resolves", r.get("ok"), r)
    r = a.tool("inspect_body", function="module:rfc0005.a/fn:a_fn")
    check("C5 entity-path resolves", r.get("ok"), r)
    r = a.tool("inspect_body", function="module:rfc0005.a/fn:a_fn/body")
    check("C6 entity-path with /body suffix resolves", r.get("ok"), r)
    r = a.tool("inspect_module", name="module:rfc0005.a")
    check("C7 module: prefix resolves", r.get("ok"), r)
    r = a.tool("inspect_module", name="rfc0005.a")
    check("C8 bare module name resolves", r.get("ok"), r)

    # 3) ambiguity: Shared exists in rfc0005.a AND rfc0005.b
    r = a.tool("inspect_entity", entity="Shared")
    amb = (
        not r.get("ok")
        and r["error_code"] == "E_AEP_ENTITY_AMBIGUOUS"
        and len(r["result"]["candidates"]) >= 2
        and any("rfc0005.a.Shared" in c for c in r["result"]["candidates"])
        and any("rfc0005.b.Shared" in c for c in r["result"]["candidates"])
    )
    check("C9 unqualified Shared -> AMBIGUOUS (no silent pick)", amb, r)
    check("C9b failed ambiguity leaves hash unchanged", rev() == rev0, rev())

    # 4) NAVIGATION preserved as typed kind mismatch (module name to
    #    inspect_function must NOT be silently "fixed")
    r = a.tool("inspect_function", name="rfc0005.a")
    check("C10 module name to inspect_function -> KIND_MISMATCH",
          not r.get("ok") and r["error_code"] == "E_AEP_ENTITY_KIND_MISMATCH"
          and r["result"]["kind"] == "module"
          and r["result"]["expected"] == "function", r)
    check("C10b failed kind mismatch leaves hash unchanged", rev() == rev0, rev())

    # 5) true unknown stays NOT_FOUND with candidates
    r = a.tool("inspect_function", name="no_such_fn")
    check("C11 unknown stays E_AEP_ENTITY_NOT_FOUND",
          not r.get("ok") and r["error_code"] == "E_AEP_ENTITY_NOT_FOUND", r)
    check("C11b failed unknown leaves hash unchanged", rev() == rev0, rev())

    # 6) RFC-0007 operand path: quoted revision handle normalizes
    r = a.tool("create_literal", type="string", value="x")
    lit = r["result"]["revision"]
    r = a.tool("construct_expression", kind="err", value=f"'{lit}'")
    check("C12 construct child with quoted revision resolves",
          r.get("ok") and r["result"]["kind"] == "err", r)

    a.close()
    print(f"Layer A handle canonicalization regressions PASSED ({checks} checks)")


if __name__ == "__main__":
    main()
