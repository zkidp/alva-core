#!/usr/bin/env python3
"""Host-side hidden verifier for E3 candidates (zero-model, C1).

Runs against a COMMITTED authoritative store:
  1. `alva project check <alva.toml>`  (whole-program semantic check; reads
     the authoritative store when present)
  2. structural checks from the candidate checkspec via the agent protocol
     (inspect_function + deterministic body-tree parsing)
  3. optional build/test runner (reserved; pilots use project_check only)

Usage: ALVA=<alva-exe> hidden_verifier.py <project-dir> <checkspec.json>
Exit: 0 = PASS, 1 = FAIL, 2 = usage/input error.
"""

import json
import os
import re
import subprocess
import sys


def fail(msg):
    print(f"VERIFIER FAIL: {msg}", flush=True)
    raise SystemExit(1)


class Agent:
    def __init__(self, alva, project):
        env = dict(os.environ)
        env.pop("ALVA_AEP_ENABLE_E3_HIGH", None)
        env.setdefault("ALVA_AEP_ENABLE_EXPERIMENTAL_A1", "1")
        self.p = subprocess.Popen(
            [alva, "agent"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            text=True, encoding="utf-8", env=env,
        )
        self.project = project
        self.toml = os.path.join(project, "alva.toml")
        self.i = 0

    def call(self, tool, **kw):
        self.i += 1
        msg = {"request_id": str(self.i), "tool": tool}
        msg.update(kw)
        self.p.stdin.write(json.dumps(msg) + "\n")
        self.p.stdin.flush()
        line = self.p.stdout.readline()
        if not line.strip():
            raise RuntimeError("agent process closed")
        return json.loads(line)

    def ok(self, tool, **kw):
        r = self.call(tool, **kw)
        if not r.get("ok"):
            fail(f"{tool} {kw} -> {r.get('message')}")
        return r

    def close(self):
        self.p.stdin.close()
        self.p.wait()


def body_of(alva, project, fn):
    a = Agent(alva, project)
    a.ok("begin_transaction", project=a.toml)
    insp = a.ok("inspect_function", name=fn)
    a.close()
    return insp["result"]["view"], insp["result"]["body"]


def args_items(body, call_name):
    """All `args:(...)` groups of every `call name=<call_name>` node.

    In the body-tree serialization each slot child is its own
    `slot:((...))` group, so one argument == one `args:` group.
    """
    out = []
    for m in re.finditer(
        rf"call name={re.escape(call_name)} rev=[0-9a-f]{{64}}",
        body,
    ):
        open_idx = body.rfind("(", 0, m.start())
        if open_idx < 0:
            continue
        depth, j = 0, open_idx
        while j < len(body):
            if body[j] == "(":
                depth += 1
            elif body[j] == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        seg = body[open_idx:j + 1]
        groups, pos = [], 0
        while True:
            gi = seg.find("args:", pos)
            if gi < 0:
                break
            gstart = gi + len("args:")
            d2, k = 0, gstart
            while k < len(seg):
                if seg[k] == "(":
                    d2 += 1
                elif seg[k] == ")":
                    d2 -= 1
                    if d2 == 0:
                        break
                k += 1
            groups.append(seg[gstart:k + 1])
            pos = k + 1
        out.append(groups)
    return out


def literal_value(item):
    m = re.search(r"literal value=([^ )]+)", item)
    return m.group(1) if m else None


def run_checks(alva, project, checkspec):
    # 1. whole-program semantic check of the committed store.
    p = subprocess.run(
        [alva, "project", "check", os.path.join(project, "alva.toml")],
        capture_output=True, text=True,
    )
    if p.returncode != 0:
        fail(f"project check failed:\n{p.stdout[-800:]}\n{p.stderr[-800:]}")
    # 2. structural checks.
    for chk in checkspec.get("structural", []):
        kind = chk["kind"]
        if kind == "has_param":
            view, _ = body_of(alva, project, chk["function"])
            line = re.search(
                rf"param {re.escape(chk['param'])}:\s*([^\n]+)", view)
            if not line:
                fail(f"has_param: {chk['function']} lacks param "
                     f"{chk['param']}")
            if line.group(1).strip() != chk["type"]:
                fail(f"has_param: {chk['function']}.{chk['param']} type "
                     f"{line.group(1)!r} != {chk['type']!r}")
        elif kind == "call_arg_count":
            _, body = body_of(alva, project, chk["function"])
            groups = args_items(body, chk["call_name"])
            if not groups:
                fail(f"call_arg_count: no call {chk['call_name']} in "
                     f"{chk['function']}")
            for g in groups:
                if len(g) != chk["args"]:
                    fail(f"call_arg_count: {chk['function']} call "
                         f"{chk['call_name']} has {len(g)} args, expected "
                         f"{chk['args']}")
        elif kind == "call_arg_literal":
            _, body = body_of(alva, project, chk["function"])
            groups = args_items(body, chk["call_name"])
            if not groups:
                fail(f"call_arg_literal: no call {chk['call_name']} in "
                     f"{chk['function']}")
            for g in groups:
                idx = chk["arg_index"]
                if idx >= len(g):
                    fail(f"call_arg_literal: {chk['function']} call "
                         f"{chk['call_name']} arg {idx} missing")
                if literal_value(g[idx]) != str(chk["value"]):
                    fail(f"call_arg_literal: {chk['function']} call "
                         f"{chk['call_name']} arg {idx} value "
                         f"{literal_value(g[idx])!r} != {chk['value']!r}")
        elif kind == "body_literal_value":
            _, body = body_of(alva, project, chk["function"])
            m = re.search(r"steps:\(\(literal value=([^ )]+)", body)
            if not m or m.group(1) != str(chk["value"]):
                got = m.group(1) if m else "none"
                fail(f"body_literal_value: {chk['function']} value {got!r} "
                     f"!= {chk['value']!r}")
        else:
            fail(f"unknown structural check kind {kind!r}")
    print("VERIFIER PASS", flush=True)
    return 0


def main():
    if len(sys.argv) != 3:
        print("USAGE: hidden_verifier.py <project-dir> <checkspec.json>",
              file=sys.stderr)
        return 2
    alva = os.environ.get("ALVA")
    if not alva:
        print("set ALVA to the alva executable", file=sys.stderr)
        return 2
    project, spec_path = sys.argv[1], sys.argv[2]
    with open(spec_path, encoding="utf-8") as fh:
        checkspec = json.load(fh)
    return run_checks(alva, project, checkspec)


if __name__ == "__main__":
    sys.exit(main())
