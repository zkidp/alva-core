#!/usr/bin/env python3
"""Public, self-contained AEP regression for RFC-0003 create_query.

Runs entirely on tests/codegen/query and drives `alva agent` directly over
its JSON-lines protocol (no benchmarks/ac fixtures, no network gateway), so
it is part of the public snapshot CI. Also asserts RFC-0002 A1 tools are
experimental/default-off on this tree.

Usage: ALVA=<alva-exe> python tests/air/query_aep_test.py
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile


def fail(msg):
    print(f"FAIL: {msg}", flush=True)
    raise SystemExit(1)


class Agent:
    """Minimal AEP client over `alva agent` stdin/stdout JSON lines."""

    def __init__(self, alva, project):
        self.proc = subprocess.Popen(
            [alva, "agent"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.tool("begin_transaction", project=project)

    def _call(self, payload):
        self.proc.stdin.write(json.dumps(payload) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            fail(f"alva agent closed while processing {payload}")
        try:
            return json.loads(line)
        except Exception:
            fail(f"non-JSON agent response: {line!r}")

    def tool(self, tool, **params):
        req = {"tool": tool}
        req.update(params)
        resp = self._call(req)
        if not resp.get("ok"):
            fail(f"{tool} failed: {resp.get('message')} (params={params})")
        return resp

    def tool_raw(self, tool, **params):
        req = {"tool": tool}
        req.update(params)
        return self._call(req)

    def result(self, resp):
        """Return the `result` field as a Python object (already JSON object
        in the direct protocol; tolerate string form for robustness)."""
        r = resp.get("result")
        if isinstance(r, dict):
            return r
        if isinstance(r, str):
            if r in ("", "null"):
                return {}
            try:
                return json.loads(r)
            except Exception:
                return r
        return {}

    def close(self):
        try:
            self.tool("abort_transaction")
        finally:
            self.proc.stdin.close()
            self.proc.wait(timeout=10)


def setup(alva, project):
    state = tempfile.mkdtemp(prefix="alva-query-aep-proj-")
    work = os.path.join(state, "work")
    shutil.copytree(os.path.dirname(project), work)
    return os.path.join(work, os.path.basename(project))


def main():
    alva = os.environ.get("ALVA")
    if not alva:
        fail("set ALVA to the alva executable")
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    project = os.path.join(root, "tests", "codegen", "query", "alva.toml")
    work = setup(alva, project)
    ag = Agent(alva, work)

    def body_block(function):
        b = ag.result(ag.tool("inspect_body", function=function))
        m = re.search(r"^\(block rev=(\w+)", b["body"])
        if not m:
            fail(f"no body block found for {function}")
        return m.group(1)

    body = ag.result(ag.tool("inspect_body", function="query.x.has"))
    m = re.search(r"left:\(\(ref name=xs rev=(\w+)", body["body"])
    if not m:
        fail("no xs ref found in query.x.has body")
    xs_rev = m.group(1)
    m = re.search(r"right:\(\(ref name=x rev=(\w+)", body["body"])
    if not m:
        fail("no x ref found in query.x.has body")
    x_rev = m.group(1)

    # contains
    contains = ag.result(ag.tool("create_query", kind="contains",
                                 collection=xs_rev, target=x_rev))
    ag.tool("replace_expression", parent=body_block("query.x.has"),
            child=contains["revision"], position="step")
    ck = ag.result(ag.tool("check_transaction"))
    if ck.get("problems") != []:
        fail("check_transaction should pass after contains attach")

    # any
    lit = ag.result(ag.tool("create_literal", type="i64", value="3"))
    e_ref = ag.result(ag.tool("create_reference", name="e"))
    pred = ag.result(ag.tool("create_binary", op=">",
                             left=e_ref["revision"], right=lit["revision"]))
    anyq = ag.result(ag.tool("create_query", kind="any", collection=xs_rev,
                             elem_var="e", predicate=pred["revision"]))
    ag.tool("replace_expression", parent=body_block("query.x.any_gt"),
            child=anyq["revision"], position="step")
    ck = ag.result(ag.tool("check_transaction"))
    if ck.get("problems") != []:
        fail("check_transaction should pass after any attach")

    # find
    findq = ag.result(ag.tool("create_query", kind="find", collection=xs_rev,
                              elem_var="e", predicate=pred["revision"]))
    ag.tool("replace_expression", parent=body_block("query.x.find_gt"),
            child=findq["revision"], position="step")
    ck = ag.result(ag.tool("check_transaction"))
    if ck.get("problems") != []:
        fail("check_transaction should pass after find attach")

    # structural rejections with exact error codes
    r = ag.tool_raw("create_query", kind="bogus", collection=xs_rev,
                    target=x_rev)
    if r.get("ok") or "E_QUERY_UNKNOWN_KIND" not in r.get("message", ""):
        fail(f"unknown kind should be rejected: {r}")
    r = ag.tool_raw("create_query", kind="contains", collection=xs_rev)
    if r.get("ok") or "E_QUERY_TARGET_MISSING" not in r.get("message", ""):
        fail(f"contains without target should be rejected: {r}")
    r = ag.tool_raw("create_query", kind="find", collection=xs_rev,
                    elem_var="e")
    if r.get("ok") or "E_QUERY_PREDICATE_MISSING" not in r.get("message", ""):
        fail(f"find without predicate should be rejected: {r}")
    r = ag.tool_raw("create_query", kind="any", collection=xs_rev,
                    predicate=pred["revision"])
    if r.get("ok") or "E_QUERY_ELEM_VAR_MISSING" not in r.get("message", ""):
        fail(f"any without elem_var should be rejected: {r}")
    for bad in ("__acc1", "x-y", "if"):
        r = ag.tool_raw("create_query", kind="any", collection=xs_rev,
                        elem_var=bad, predicate=pred["revision"])
        if r.get("ok") or "E_QUERY_ELEM_VAR_INVALID" not in r.get("message", ""):
            fail(f"invalid elem_var '{bad}' should be rejected: {r}")

    # RFC-0002 A1 tools are experimental/default-off on the public snapshot
    r = ag.tool_raw("inspect_change_impact", entity="type:query.x.Item")
    if r.get("ok") or "E_AEP_UNKNOWN_TOOL" not in r.get("message", ""):
        fail(f"inspect_change_impact should be default-off: {r}")
    r = ag.tool_raw("inspect_schema_gaps", entity="type:query.x.Item")
    if r.get("ok") or "E_AEP_UNKNOWN_TOOL" not in r.get("message", ""):
        fail(f"inspect_schema_gaps should be default-off: {r}")

    ag.close()
    print("QUERY AEP SMOKE PASSED (contains/any/find + rejections + A1 default-off)")


if __name__ == "__main__":
    main()
