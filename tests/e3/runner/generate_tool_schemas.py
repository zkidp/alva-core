#!/usr/bin/env python3
"""Generate frozen OpenAI-style tool schemas per arm from the aep.rs
registry (host-side prep; run at the freeze commit).

Usage: python generate_tool_schemas.py --aep <alva/src/aep.rs> --out-dir <dir>
"""

import argparse
import json
import os
import re


def parse_specs(src):
    specs = []
    i = 0
    while True:
        j = src.find("spec(", i)
        if j < 0:
            break
        depth, k, quote = 1, j + 5, None
        while k < len(src):
            if quote:
                if src[k] == quote and src[k - 1] != "\\":
                    quote = None
                k += 1
                continue
            if src[k] in "\"'":
                quote = src[k]
                k += 1
                continue
            if src[k] == "(":
                depth += 1
            elif src[k] == ")":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        block = src[j:k + 1]
        m = re.match(r'spec\(\s*"([a-z_0-9]+)"', block)
        if m:
            inner = block[len("spec("):-1]
            args = _split_top(inner)
            gate = args[-1].strip() if args else ""
            specs.append({
                "name": m.group(1),
                "gated": gate.startswith("Some("),
                "gate_raw": gate,
                "args": args,
                "block": block,
            })
        i = k + 1
    return specs


def _split_top(s):
    parts, depth, cur, quote = [], 0, "", None
    for ch in s:
        if quote:
            cur += ch
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
            cur += ch
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
            continue
        cur += ch
    if cur.strip():
        parts.append(cur)
    return parts


def schema_for(spec):
    # parse arguments from the spec(...) block: arg("name","shape",required)
    properties = {}
    required = []
    for am in re.finditer(r'arg\(\s*"([^"]+)"\s*,\s*"([^"]*)"\s*,\s*(true|false)',
                          spec["block"]):
        name, shape, req = am.group(1), am.group(2), am.group(3)
        properties[name] = {"type": "string", "description": shape}
        if req == "true":
            required.append(name)
    example = re.search(r'"[a-z_0-9]+ [^"]*"', spec["block"])
    description = (example.group(0).strip('"')
                   if example else f"{spec['name']} operation")
    return {
        "type": "function",
        "function": {
            "name": spec["name"],
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aep", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    src = open(args.aep, encoding="utf-8").read()
    specs = parse_specs(src)
    # Run env sets GATE_A1=1, so A1-gated tools are visible in BOTH arms;
    # only the E3 HIGH gate is absent in LOW.
    low = [schema_for(s) for s in specs
           if "GATE_E3_HIGH" not in s["gate_raw"]]
    high = [schema_for(s) for s in specs]
    os.makedirs(args.out_dir, exist_ok=True)
    for name, tools in (("TOOLS-LOW.json", low), ("TOOLS-HIGH.json", high)):
        with open(os.path.join(args.out_dir, name), "w",
                  encoding="utf-8") as fh:
            json.dump({"count": len(tools), "tools": tools}, fh, indent=2)
    print(f"LOW tools: {len(low)} | HIGH tools: {len(high)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
