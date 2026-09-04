#!/usr/bin/env python3
"""RFC-0005 / AEP-0002 v0.1 regression: Intent -> Applicable Semantic Operations.

Covers: entity resolution (exact / ambiguous / unknown / qualified / kind /
module-exact / direct-ID display), strict applicable_operations (entity ops vs
context ops), describe_operation == executor contract, alias canonicalization
and execution, structured recovery payloads (unknown tool / ambiguous entity /
invalid argument), A1 feature-gate non-leak, and read-only discovery.

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

    def args_of(r):
        return [x["name"] for x in r["result"]["arguments"]]

    # --- entity resolution ------------------------------------------------

    # R1 exact entity resolution
    r = a.tool("resolve_entity", name="Job")
    check("R1 exact resolve Job -> record",
          r["ok"] and r["error_code"] == "ok"
          and r["result"]["kind"] == "record"
          and r["result"]["module"] == "rfc0005.a"
          and r["result"]["display"] == "rfc0005.a.Job", r)
    jid = r["result"]["entity"]

    # R2 ambiguous same-name entity -> structured candidates, no silent pick
    r = a.tool("resolve_entity", name="Shared")
    cands = r["result"].get("candidates", [])
    check("R2 ambiguous Shared -> structured candidates",
          not r["ok"] and r["error_code"] == "E_AEP_AMBIGUOUS_ENTITY"
          and r["result"].get("requested") == "Shared"
          and any("rfc0005.a.Shared" in c for c in cands)
          and any("rfc0005.b.Shared" in c for c in cands), r)

    # R3 unknown entity -> structured candidates
    r = a.tool("resolve_entity", name="NoSuchThing")
    check("R3 unknown entity -> structured candidates",
          not r["ok"] and r["error_code"] == "E_AEP_ENTITY_NOT_FOUND"
          and r["result"].get("requested") == "NoSuchThing"
          and "candidates" in r["result"], r)

    # R4 qualified name disambiguation
    r = a.tool("resolve_entity", name="rfc0005.b.Shared")
    check("R4 qualified resolves exactly",
          r["ok"] and r["result"]["display"] == "rfc0005.b.Shared"
          and r["result"]["module"] == "rfc0005.b", r)

    # R5 kind filter rejects wrong kind
    r = a.tool("resolve_entity", name="a_fn", kind="record")
    check("R5 kind=record on function -> not found",
          not r["ok"] and r["error_code"] == "E_AEP_ENTITY_NOT_FOUND"
          and r["result"].get("requested") == "a_fn", r)
    r = a.tool("resolve_entity", name="a_fn", kind="function")
    check("R5b kind=function on function -> ok",
          r["ok"] and r["result"]["kind"] == "function", r)

    # R16 module filter is exact, not prefix
    r = a.tool("resolve_entity", name="Shared", module="rfc0005.a")
    check("R16a module exact resolves",
          r["ok"] and r["result"]["display"] == "rfc0005.a.Shared"
          and r["result"]["module"] == "rfc0005.a", r)
    r = a.tool("resolve_entity", name="Shared", module="rfc0005")
    check("R16b module prefix must not match -> not found",
          not r["ok"] and r["error_code"] == "E_AEP_ENTITY_NOT_FOUND", r)

    # R17 direct-ID display matches name-based display
    r2 = a.tool("resolve_entity", name=jid)
    check("R17 direct-ID display == name display",
          r2["ok"] and r2["result"]["entity"] == jid
          and r2["result"]["display"] == "rfc0005.a.Job"
          and r2["result"]["module"] == "rfc0005.a", r2)

    prepared = a.tool(
        "prepare_edit",
        entity="rfc0005.a.Job",
        kind="record",
        operation="update_record_fields",
    )
    check(
        "R17b prepare_edit combines resolution, context, and operation schema",
        prepared["ok"]
        and prepared["result"]["kind"] == "record"
        and prepared["result"]["display"] == "rfc0005.a.Job"
        and "update_record_fields" in prepared["result"]["applicable_operations"]
        and prepared["result"]["selected_operation"]["name"] == "update_record_fields",
        prepared,
    )

    # --- applicable_operations: strict applicability ----------------------

    # R6 record entity -> record ops only; expression ops are context, not entity
    r = a.tool("applicable_operations", entity=jid)
    res = r["result"]
    mutation = res["mutation"]
    context = res["context_operations"]
    check("R6 record applicable ops strict",
          r["ok"] and res["kind"] == "record"
          and "add_field" in mutation
          and "update_record_fields" in mutation
          and "append_step" not in mutation
          and "add_record_field" not in mutation
          and "replace_expression" not in mutation
          and "add_call_arg" not in mutation
          and "replace_expression" in context
          and "add_record_field" in context, r)

    # R7 function entity -> function ops, no record-only mutation
    fid = a.tool("resolve_entity", name="rfc0005.a.a_fn")["result"]["entity"]
    r = a.tool("applicable_operations", entity=fid)
    res = r["result"]
    check("R7 function applicable ops strict",
          r["ok"] and res["kind"] == "function"
          and "append_step" in res["mutation"]
          and "add_param" in res["mutation"]
          and "set_effect" in res["mutation"]
          and "add_field" not in res["mutation"]
          and "update_record_fields" not in res["mutation"], r)

    # --- describe_operation == executor contract --------------------------

    # R8 describe matches executor schema
    r = a.tool("describe_operation", name="update_record_fields")
    check("R8 describe update_record_fields args",
          r["ok"] and args_of(r) == ["type", "base", "updates"], r)

    # R8b-e registry-executor contract: canonical request keys match executors
    r = a.tool("describe_operation", name="change_field")
    check("R8b change_field contract entity/field/value",
          r["ok"] and args_of(r) == ["entity", "field", "value"], r)
    r = a.tool("describe_operation", name="rename_entity")
    check("R8c rename_entity contract entity/new_name",
          r["ok"] and args_of(r) == ["entity", "new_name"], r)
    r = a.tool("describe_operation", name="add_call_arg")
    check("R8d add_call_arg contract call/arg",
          r["ok"] and args_of(r) == ["call", "arg"], r)
    r = a.tool("describe_operation", name="set_effect")
    check("R8e set_effect contract function/effect (no pure/io aliases)",
          r["ok"] and args_of(r) == ["function", "effect"]
          and r["result"]["aliases"] == [], r)

    # --- alias canonicalization and execution -----------------------------

    # R14 alias resolves through describe (canonical name returned)
    r = a.tool("describe_operation", name="replace_expr")
    check("R14 alias replace_expr -> canonical replace_expression",
          r["ok"] and r["result"]["name"] == "replace_expression"
          and "replace_expr" in r["result"]["aliases"], r)

    # R15 alias truly executes (not UNKNOWN_TOOL, not just described)
    lit1 = a.tool("create_literal", type="i64", value="1")["result"]["revision"]
    bnd = a.tool("create_binding", name="alias_probe",
                 type_name="i64", value=lit1)["result"]["revision"]
    lit2 = a.tool("create_literal", type="i64", value="2")["result"]["revision"]
    r = a.tool("replace_expr", parent=bnd, child=lit2, position="value")
    check("R15 alias replace_expr executes",
          r["ok"] and "new_revision" in r["result"], r)

    # --- structured recovery hints ----------------------------------------

    # R9 typo operation -> structured closest candidates
    r = a.tool("describe_operation", name="replace_expre")
    check("R9 typo -> structured candidates",
          not r["ok"] and r["error_code"] == "E_AEP_UNKNOWN_TOOL"
          and r["result"].get("requested") == "replace_expre"
          and "replace_expression" in r["result"]["candidates"], r)

    # R10 unknown tool fallback -> structured candidates
    r = a.tool("appnd_step")
    check("R10 unknown tool fallback -> structured candidates",
          not r["ok"] and r["error_code"] == "E_AEP_UNKNOWN_TOOL"
          and r["result"].get("requested") == "appnd_step"
          and "append_step" in r["result"]["candidates"], r)

    # R13 invalid position -> structured recovery hint
    r = a.tool("replace_expression", parent=bnd,
               child=lit2, position="bogus")
    rec = r["result"].get("recovery", {})
    positions = r["result"].get("expected_positions", [])
    check("R13 invalid position -> structured recovery",
          not r["ok"] and r["error_code"] == "E_AEP_OP"
          and r["result"].get("operation") == "replace_expression"
          and r["result"].get("argument") == "position"
          and positions == ["body", "value"]  # binding parent: body + value
          and "step" not in positions
          and "target" not in positions
          and all("steps/" not in p and "args/" not in p for p in positions)
          and rec.get("tool") == "describe_operation"
          and rec.get("name") == "replace_expression", r)

    # R18 describe advertises exactly the executable position vocabulary
    r = a.tool("describe_operation", name="replace_expression")
    positions = r["result"].get("expected_positions", [])
    check("R18 describe position vocabulary == executor contract",
          r["ok"]
          and "step" in positions and "arg" in positions and "value" in positions
          and "target" not in positions
          and all("steps/" not in p and "args/" not in p for p in positions)
          and "steps/0" not in r["result"]["arguments"][2]["shape"], r)

    # R19 advertised position truly executes (block + step)
    blk = a.tool("create_block")["result"]["revision"]
    r = a.tool("replace_expression", parent=blk,
               child=lit2, position="step")
    check("R19 advertised position=step executes on block",
          r["ok"] and "new_revision" in r["result"], r)

    # --- A1 feature gate: never leaked through discovery ------------------

    r = a.tool("applicable_operations", entity=jid)
    res = r["result"]
    allops = (res["inspection"] + res["mutation"] + res["context_operations"])
    check("R11 A1 tools not leaked in applicable_operations",
          "inspect_change_impact" not in allops
          and "inspect_schema_gaps" not in allops, r)
    r = a.tool("describe_operation", name="inspect_change_impact")
    check("R11b A1 describe gated (no candidate leak)",
          not r["ok"] and r["error_code"] == "E_AEP_UNKNOWN_TOOL"
          and "inspect_change_impact" not in r["result"]["candidates"], r)
    r = a.tool("resolve_entity", name="inspect_change_impact")
    check("R11c A1 resolve gated",
          not r["ok"] and r["error_code"] == "E_AEP_ENTITY_NOT_FOUND", r)

    # --- discovery APIs are read-only -------------------------------------

    p0 = a.tool("inspect_project")
    a.tool("resolve_entity", name="Job")
    a.tool("applicable_operations", entity=jid)
    a.tool("describe_operation", name="add_field")
    a.tool("describe_operation", name="replace_expr")
    p1 = a.tool("inspect_project")
    check("R12 discovery APIs read-only",
          p0["result"] == p1["result"], (p0, p1))

    a.close()
    print(f"RFC-0005 AEP regressions PASSED ({checks} checks)")


if __name__ == "__main__":
    main()
