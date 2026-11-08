"""Trusted local Linux transport; unchanged Host/Guard/evaluator implementation."""
import argparse
import copy
import json
from pathlib import Path
import sys
import time

from benchmarks.host_v3_acceptance.service import Session as BaseSession
from integrations.codex.maintenance_context import ContextHost, TOOLS, References
from integrations.codex.bounded_target_context import BoundedTargetHost
from integrations.codex.maintenance_host import tool_result, sha
from integrations.benchmark_runtime_v2.sandbox import SDK


EXTRA = [
 {"name": "search_source", "description": "Literal search across all public source. Exact matching lines, source hashes, and line positions; at most 40 hits, with explicit more_available.",
  "inputSchema": {"type": "object", "properties": {"text": {"type": "string", "minLength": 1, "maxLength": 200}}, "required": ["text"], "additionalProperties": False}},
 {"name": "list_symbols", "description": "Generic complete module, function and type-name catalog for this fixed source component. Names only, no task ranking.",
  "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}}]


def advertised_tools():
    result = copy.deepcopy(TOOLS + EXTRA)
    result[0]["description"] = "Read the authorized current target body/declaration and view_id for the shared protected change workflow. Context varies by acquisition condition."
    return result


class Session(BaseSession):
    def __init__(self, task, arm, sdk):
        super().__init__(task, "V4", sdk)
        self.condition = arm
        self.context = (BoundedTargetHost if arm == "C" else ContextHost)(self.host)
        self.source_ledger = []

    def tool(self, name, args):
        if name == "list_symbols":
            result = {"status": "SYMBOLS", "modules": self.task["policy"]["modules"]} if args == {} else {"status": "REJECTED", "reason": "INVALID_ARGUMENTS"}
        elif name == "search_source":
            if not isinstance(args, dict) or set(args) != {"text"} or not isinstance(args["text"], str) or not args["text"] or len(args["text"]) > 200:
                result = {"status": "REJECTED", "reason": "INVALID_ARGUMENTS"}
            else:
                hits = []
                for path, data in sorted(self.original.items()):
                    if not path.endswith(".alva"): continue
                    offset = 0
                    for i, line in enumerate(data.decode().splitlines(keepends=True), 1):
                        if args["text"] in line:
                            hits.append({"path": path, "line": i, "content": line, "source_sha256": sha(data), "byte_start": offset})
                        offset += len(line.encode())
                result = {"status": "SEARCH", "hits": hits[:40], "more_available": len(hits) > 40}
        else:
            result = self.context.invoke(name, args)
            if name == "read_target" and result.get("status") == "READY" and self.condition == "A":
                # Source acquisition baseline retains the same required target view,
                # body and declaration, but not automatic semantic direct context.
                result.pop("context", None)
            if name == "publish_change" and result.get("status") in ("PUBLISHED", "PUBLISHED_UNVERIFIED"):
                self.published.append(copy.deepcopy(result))
        self.calls.append({"name": name, "arguments": args, "trusted_result": copy.deepcopy(result)})
        return tool_result(result)["structuredContent"]


def serve(args):
    cfg = json.loads(args.freeze.read_bytes())
    sdk = SDK(args.alva, args.toolchain, args.registry)
    if sha(sdk.alva.read_bytes()) != cfg["sdk"]["alva_sha256"]: raise RuntimeError("BINARY_DRIFT")
    if sha((sdk.rust_toolchain / "bin/rustc").read_bytes()) != cfg["sdk"]["rustc_sha256"]: raise RuntimeError("RUSTC_DRIFT")
    if References().docs != cfg["reference_docs"]: raise RuntimeError("REFERENCE_DRIFT")
    session = Session(cfg["tasks"][args.task], args.arm, sdk)
    print(json.dumps({"ready": True, "tools": advertised_tools()}), flush=True)
    try:
        for line in sys.stdin:
            req = json.loads(line)
            if req["action"] == "finish":
                print(json.dumps(session.finish()), flush=True)
                break
            if req["action"] != "tool": raise RuntimeError("INVALID_TRANSPORT_ACTION")
            print(json.dumps(session.tool(req["name"], req["arguments"])), flush=True)
    finally: session.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for k in ("freeze", "alva", "toolchain", "registry"): p.add_argument("--" + k, type=lambda v: Path(v).resolve(), required=True)
    p.add_argument("--task", required=True)
    p.add_argument("--arm", choices=["A", "B", "C"], required=True)
    serve(p.parse_args())
