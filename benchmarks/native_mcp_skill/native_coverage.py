"""Check the actual native MCP entry points on new public stubs, no model."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from integrations.benchmark_runtime_v2.freeze import pack_git
from integrations.benchmark_runtime_v2.persistent import PersistentSandbox
from integrations.benchmark_runtime_v2.sandbox import SDK


def run(args):
    tasks = json.loads(
        (ROOT / "benchmarks/native_mcp_skill/SELECTION.json").read_text()
    )["tasks"]
    paths = [
        f'benchmarks/native_mcp_skill/inputs/{t["id"]}/{p}'
        for t in tasks
        for p in ("alva.toml", "src/task.alva")
    ]
    bundle = pack_git(args.repo, args.commit, paths)
    sdk = SDK(args.alva, args.toolchain, args.registry)
    rows = []
    with PersistentSandbox(bundle, bundle["payload_sha256"], sdk) as box:
        for task in tasks:
            row = {"task": task["id"], "calls": []}
            project = f'/work/project/benchmarks/native_mcp_skill/inputs/{task["id"]}/alva.toml'
            row["initial_project_check"] = box.run(
                ["/sdk/alva", "project", "check", project, "--json"]
            )
            with box.mcp() as mcp:
                mcp.request(
                    "initialize",
                    {
                        "protocolVersion": "2025-11-25",
                        "capabilities": {},
                        "clientInfo": {"name": "native-coverage", "version": "1"},
                    },
                )
                tools = mcp.request("tools/list")["tools"]
                names = {t["name"] for t in tools}
                row["advertised_names"] = sorted(names)

                def call(operation, **arguments):
                    answer = mcp.tool(operation, arguments)
                    row["calls"].append(
                        {"name": operation, "arguments": arguments, "response": answer}
                    )
                    return answer

                begun = call("begin_transaction", project=project)
                assert not begun["isError"], begun
                tx = begun["structuredContent"]["transaction_id"]

                def tool(operation, **arguments):
                    return call(operation, transaction_id=tx, **arguments)

                original = tool("inspect_body", function="bench.solve")
                assert not original["isError"], original
                fn = tool("inspect_entity", entity="bench.solve")["structuredContent"]
                tool("applicable_operations", entity="bench.solve")
                for operation in (
                    "create_reference",
                    "create_literal",
                    "create_binary",
                    "create_call",
                    "replace_expression",
                ):
                    description = tool("describe_operation", name=operation)
                    assert not description["isError"], description
                    assert operation not in names
                    answer = tool(operation)
                    assert answer["isError"] and "E_MCP_UNKNOWN_TOOL" in json.dumps(
                        answer
                    ), answer
                desc = tool(
                    "describe_construction", kind="veclit", include_candidates=True
                )
                row["veclit_description"] = desc
                detached = tool(
                    "construct_expression",
                    kind="veclit",
                    elem_type="(prim i64)",
                    items=[],
                )
                row["detached"] = detached
                assert not detached["isError"], detached
                node = detached["structuredContent"]["revision"]
                change = tool(
                    "change_field", entity=fn["revision"], field="body", value=node
                )
                row["field_is_not_slot_replacement"] = change
                assert change["isError"], change
                assert "E_AEP_002" in json.dumps(
                    change
                ) and "does not allow field 'body'" in json.dumps(change), change
                unchanged = tool("inspect_body", function="bench.solve")
                assert (
                    original["structuredContent"] == unchanged["structuredContent"]
                ), unchanged
                tool("check_transaction")
                tool("abort_transaction")
                row["body_unchanged"] = True
                row["commits"] = 0
            rows.append(row)
    return {
        "status": "NATIVE_MCP_ENTRY_POINT_GAP_OBSERVED",
        "generation_calls": 0,
        "input_token_calls": 0,
        "input_commit": args.commit,
        "binary_sha256": hashlib.sha256(sdk.alva.read_bytes()).hexdigest(),
        "input_bundle_sha256": bundle["payload_sha256"],
        "rows": rows,
        "scope": "Observed callable surface and attempted slot attachment; not a proof about every imaginable program, and not an ALVA language expressibility failure.",
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, default=ROOT)
    p.add_argument("--commit", required=True)
    p.add_argument("--alva", type=Path, required=True)
    p.add_argument("--toolchain", type=Path, required=True)
    p.add_argument("--registry", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = run(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "tasks": len(result["rows"]),
                "generation_calls": 0,
            }
        )
    )
