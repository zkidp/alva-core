#!/usr/bin/env python3
"""RFC-0005 / AEP-0002 v0.1 regression: Intent -> Applicable Semantic Operations.

Covers: entity resolution (exact / ambiguous / unknown / qualified / kind
filter), applicable_operations by kind, describe_operation vs executor,
unknown-tool recovery, invalid-position hint, A1 feature-gate non-leak, and
read-only guarantee of the discovery APIs.

Usage: ALVA=<alva-exe> python tests/air/rfc0005_aep_test.py
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

    # 1) exact entity resolution
    r = a.tool("resolve_entity", name="Job")
    check("R1 exact resolve Job -> record",
          r["ok"] and r["result"]["kind"] == "record"
          and r["result"]["module"] == "rfc0005.a"
          and r["result"]["display"] == "rfc0005.a.Job", r)

    # 2) ambiguous same-name entity
    r = a.tool("resolve_entity", name="Shared")
    check("R2 ambiguous Shared -> candidates, no silent pick",
          not r["ok"] and "E_AEP_AMBIGUOUS_ENTITY" in r["message"]
          and "rfc0005.a.Shared" in r["message"] and "rfc0005.b.Shared" in r["message"],
          r)

    # 3) unknown entity -> candidates
    r = a.tool("resolve_entity", name="NoSuchThing")
    check("R3 unknown entity -> candidates",
          not r["ok"] and "E_AEP_ENTITY_NOT_FOUND" in r["message"]
          and "candidates=" in r["message"], r)

    # 4) qualified name disambiguation
    r = a.tool("resolve_entity", name="rfc0005.b.Shared")
    check("R4 qualified resolves exactly",
          r["ok"] and r["result"]["display"] == "rfc0005.b.Shared"
          and r["result"]["module"] == "rfc0005.b", r)

    # 5) kind filter rejects wrong kind
    r = a.tool("resolve_entity", name="a_fn", kind="record")
    check("R5 kind=record on function -> not found",
          not r["ok"] and "E_AEP_ENTITY_NOT_FOUND" in r["message"], r)
    r = a.tool("resolve_entity", name="a_fn", kind="function")
    check("R5b kind=function on function -> ok",
          r["ok"] and r["result"]["kind"] == "function", r)

    # 6) record entity -> record ops only
    jid = a.tool("resolve_entity", name="Job")["result"]["entity"]
    r = a.tool("applicable_operations", entity=jid)
    res = r["result"]
    check("R6 record applicable ops",
          r["ok"] and res["kind"] == "record"
          and "add_field" in res["mutation"]
          and "update_record_fields" in res["mutation"]
          and "append_step" not in res["mutation"], r)

    # 7) function entity -> function ops, no record-only mutation
    fid = a.tool("resolve_entity", name="rfc0005.a.a_fn")["result"]["entity"]
    r = a.tool("applicable_operations", entity=fid)
    res = r["result"]
    check("R7 function applicable ops",
          r["ok"] and res["kind"] == "function"
          and "append_step" in res["mutation"]
          and "add_param" in res["mutation"]
          and "add_field" not in res["mutation"], r)

    # 8) describe_operation matches executor schema
    r = a.tool("describe_operation", name="update_record_fields")
    check("R8 describe update_record_fields args",
          r["ok"] and [x["name"] for x in r["result"]["arguments"]] == ["type", "base", "updates"],
          r)

    # 9) typo operation -> stable closest candidates
    r = a.tool("describe_operation", name="replace_expre")
    check("R9 typo -> closest candidates",
          not r["ok"] and "E_AEP_UNKNOWN_TOOL" in r["message"]
          and "replace_expression" in r["message"], r)

    # 10) unknown tool fallback -> candidates
    r = a.tool("appnd_step")  # typo
    check("R10 unknown tool fallback candidates",
          not r["ok"] and "E_AEP_UNKNOWN_TOOL" in r["message"]
          and "append_step" in r["message"], r)

    # 11) A1 default-off: never leaked through discovery APIs
    r = a.tool("applicable_operations", entity=jid)
    res = r["result"]
    allops = res["inspection"] + res["mutation"] + res["transaction"]
    check("R11 A1 tools not leaked in applicable_operations",
          "inspect_change_impact" not in allops and "inspect_schema_gaps" not in allops, r)
    r = a.tool("describe_operation", name="inspect_change_impact")
    check("R11b A1 describe gated",
          not r["ok"] and "E_AEP_UNKNOWN_TOOL" in r["message"]
          and "inspect_change_impact" not in r["message"].split("candidates=")[1], r)
    r = a.tool("resolve_entity", name="inspect_change_impact")
    check("R11c A1 resolve gated",
          not r["ok"] and "E_AEP_ENTITY_NOT_FOUND" in r["message"], r)

    # 12) discovery APIs are read-only (project revision unchanged)
    p0 = a.tool("inspect_project")
    a.tool("resolve_entity", name="Job")
    a.tool("applicable_operations", entity=jid)
    a.tool("describe_operation", name="add_field")
    p1 = a.tool("inspect_project")
    check("R12 discovery APIs read-only",
          p0["result"] == p1["result"], (p0, p1))

    # 13) invalid position -> expected-shape recovery hint
    lit = a.tool("create_literal", type="i64", value="7")
    r = a.tool("replace_expression", parent=lit["result"]["revision"],
               child=lit["result"]["revision"], position="bogus")
    check("R13 invalid position hint",
          not r["ok"] and "use describe_operation name=replace_expression" in r["message"],
          r)

    a.close()
    print(f"RFC-0005 AEP regressions PASSED ({checks} checks)")


if __name__ == "__main__":
    main()
