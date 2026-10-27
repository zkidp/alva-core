"""P25 public engineering witnesses. Run ONLY inside P22/P23 Linux isolation.

Never include this file, its expressions or vectors in future model inputs.
The initial programs remain the exact unchanged P24 Git blobs.
"""

import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.path.insert(0, "/input/tests/mcp")
from mcp_protocol_test import Mcp, MODERN_META, structured

ADDED = {
    "create_reference",
    "create_literal",
    "create_binary",
    "create_call",
    "create_if",
    "replace_expression",
}
CLOSED = {
    "append_step",
    "create_block",
    "create_binding",
    "delete_entity",
    "inspect_change_impact",
    "inspect_schema_gaps",
}
TRANSCRIPT = []
TOOL_SCHEMAS = {}


class Client:
    def __init__(self, project, label, modern=False):
        self.m = Mcp(Path("/sdk/alva"))
        self.ordinal = 0
        self.label = label
        self.modern = modern
        if modern:
            self.rpc("server/discover", {"_meta": MODERN_META})
        else:
            self.rpc(
                "initialize",
                {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "p25-public-fixture", "version": "1"},
                },
            )
        listing = self.rpc("tools/list", {"_meta": MODERN_META} if modern else {})
        self.schemas = {tool["name"]: tool["inputSchema"] for tool in listing["tools"]}
        if not TOOL_SCHEMAS:
            TOOL_SCHEMAS.update(self.schemas)
        else:
            assert self.schemas == TOOL_SCHEMAS, "Legacy/modern/session schema drift"
        assert len(self.schemas) == 20
        assert ADDED <= self.schemas.keys() and not CLOSED.intersection(self.schemas)
        self.tx = self.call("begin_transaction", project=str(project))["transaction_id"]

    def rpc(self, method, params):
        self.ordinal += 1
        response = self.m.request(
            {"jsonrpc": "2.0", "id": self.ordinal, "method": method, "params": params}
        )
        assert "error" not in response, response
        return response["result"]

    def raw(self, operation, arguments):
        self.ordinal += 1
        answer = self.m.tool(self.ordinal, operation, arguments, modern=self.modern)
        TRANSCRIPT.append(
            {
                "session": self.label,
                "operation": operation,
                "arguments": arguments,
                "response": answer,
            }
        )
        return answer

    def call(self, operation, expected=True, **arguments):
        if operation != "begin_transaction":
            arguments = {"transaction_id": self.tx, **arguments}
        answer = self.raw(operation, arguments)
        assert bool(answer.get("isError")) != expected, (operation, answer)
        return structured(answer) if expected else answer

    def close(self):
        self.m.close()


def invoke(argv, expected_success=True):
    p = subprocess.run(argv, capture_output=True, text=True, timeout=60)
    assert (p.returncode == 0) == expected_success, (
        argv,
        p.returncode,
        p.stdout,
        p.stderr,
    )
    return {"argv": argv, "exit": p.returncode, "stdout": p.stdout, "stderr": p.stderr}


def manifest(directory):
    return {
        p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(directory.rglob("*"))
        if p.is_file()
    }


def int_(c, n):
    return c.call("create_literal", type="i64", value=str(n))["revision"]


def bool_(c, b):
    return c.call("create_literal", type="bool", value=str(b).lower())["revision"]


def ref(c, name):
    return c.call("create_reference", name=name)["revision"]


def call(c, name, *args):
    return c.call("create_call", name=name, args=list(args))["revision"]


def binary(c, op, left, right):
    return c.call("create_binary", op=op, left=left, right=right)["revision"]


def if_(c, cond, then, otherwise):
    return c.call("create_if", **{"cond": cond, "then": then, "else": otherwise})[
        "revision"
    ]


def witness(c, case):
    if case == "HE41":
        return binary(c, "*", ref(c, "n"), ref(c, "n"))
    if case == "HE23":
        return call(c, "len", ref(c, "s"))
    if case == "HE42":
        length = call(c, "len", ref(c, "xs"))
        last = binary(c, "-", length, int_(c, 1))
        empty = c.call(
            "construct_expression", kind="veclit", elem_type="i64", items=[]
        )["revision"]
        prefix = call(c, "solve", call(c, "slice", ref(c, "xs"), int_(c, 0), last))
        item = binary(c, "+", call(c, "get", ref(c, "xs"), last), int_(c, 1))
        return if_(
            c,
            binary(c, "==", length, int_(c, 0)),
            empty,
            call(c, "append", prefix, item),
        )
    if case == "HE3":
        total = binary(
            c, "+", ref(c, "total"), call(c, "get", ref(c, "xs"), ref(c, "j"))
        )
        end = binary(c, "+", ref(c, "i"), int_(c, 1))
        prefix = c.call(
            "construct_expression",
            kind="fold",
            index="j",
            acc_name="total",
            acc_type="i64",
            range_start=int_(c, 0),
            range_end=end,
            acc_init=int_(c, 0),
            body=total,
        )["revision"]
        negative = binary(c, "<", prefix, int_(c, 0))
        body = if_(c, ref(c, "found"), bool_(c, True), negative)
        return c.call(
            "construct_expression",
            kind="fold",
            index="i",
            acc_name="found",
            acc_type="bool",
            range_start=int_(c, 0),
            range_end=call(c, "len", ref(c, "xs")),
            acc_init=bool_(c, False),
            body=body,
        )["revision"]
    raise AssertionError(case)


# The established bounded, independent public behavior vectors; no reference
# implementation is executed to determine their expected results.
VECTORS = {
    "HE41": [
        (0, 0),
        (1, 1),
        (2, 4),
        (3, 9),
        (10, 100),
        (101, 10201),
        (10000, 100000000),
    ],
    "HE23": [
        ("", 0),
        ("abc", 3),
        ("a b", 3),
        ("\n\t", 2),
        ("a" * 64, 64),
        ("1234567", 7),
    ],
    "HE42": [
        ([], []),
        ([1, 2, 3], [2, 3, 4]),
        ([-1, 0, 1], [0, 1, 2]),
        ([5, 5], [6, 6]),
        ([-1000, 1000], [-999, 1001]),
        (list(range(16)), list(range(1, 17))),
    ],
    "HE3": [
        ([], False),
        ([1, 2, 3], False),
        ([1, 2, -4, 5], True),
        ([-1, 5], True),
        ([2, -2], False),
        ([0, 0], False),
        ([5, -2, -3, -1, 2], True),
        ([1, -1, 1], False),
    ],
}


def rust(value):
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, int):
        return str(value) + "i64"
    if isinstance(value, str):
        return json.dumps(value) + ".to_string()"
    return "vec![" + ",".join(rust(x) for x in value) + "]"


def behavior(project, case, baseline=False):
    output = "/work/generated/" + case + ("-baseline" if baseline else "-final")
    check = invoke(
        ["/sdk/alva", "project", "check", str(project / "alva.toml"), "--json"]
    )
    build = invoke(
        [
            "/sdk/alva",
            "project",
            "build",
            str(project / "alva.toml"),
            "--out-dir",
            output,
        ]
    )
    crate = Path(output) / "bench"
    code = "\n#[cfg(test)] mod p25_independent { use super::bench::solve;\n"
    for i, (x, expected) in enumerate(VECTORS[case]):
        code += f"#[test] fn vector_{i}() {{ assert_eq!(solve({rust(x)}),{rust(expected)}); }}\n"
    code += "}\n"
    with (crate / "src/lib.rs").open("a") as f:
        f.write(code)
    result = invoke(
        [
            "/sdk/toolchain/bin/cargo",
            "test",
            "--offline",
            "--manifest-path",
            str(crate / "Cargo.toml"),
        ],
        not baseline,
    )
    return {
        "check": check,
        "build": build,
        "test": result,
        "vector_count": len(VECTORS[case]),
        "independent_test_sha256": hashlib.sha256(code.encode()).hexdigest(),
    }


def coding_case(case):
    project = Path("/work/project/benchmarks/native_mcp_skill/inputs") / case
    before = manifest(project / "src")
    row = {
        "case": case,
        "status": "FAIL",
        "baseline": behavior(project, case, baseline=True),
    }
    c = Client(project / "alva.toml", case + "-construct", modern=case == "HE3")
    try:
        for operation in sorted(ADDED):
            schema = c.schemas[operation]
            assert "transaction_id" in schema["required"]
            c.call("describe_operation", name=operation)
        entity = c.call("resolve_entity", name="bench.solve", kind="function")["entity"]
        discovered = c.call("applicable_operations", entity=entity)
        advertised = set(
            sum(
                [
                    discovered.get(k, [])
                    for k in ("inspection", "mutation", "context_operations")
                ],
                [],
            )
        )
        assert advertised <= c.schemas.keys() and ADDED <= advertised, discovered
        original_body = c.call("inspect_body", function="bench.solve")
        fn = c.call("inspect_entity", entity="bench.solve")
        block = fn["slots"]["body"][0]
        if case in ("HE42", "HE3"):
            c.call(
                "describe_construction",
                kind="veclit" if case == "HE42" else "fold",
                include_candidates=True,
            )
        if case == "HE41":
            for operation in sorted(CLOSED):
                refused = c.call("describe_operation", expected=False, name=operation)
                assert "E_MCP_OPERATION_NOT_EXPOSED" in json.dumps(refused)
                assert c.call(operation, expected=False)["isError"]
            missing = c.raw("create_literal", {"type": "i64", "value": "0"})
            wrong_tx = c.raw(
                "create_literal",
                {"transaction_id": "not-current", "type": "i64", "value": "0"},
            )
            assert "E_MCP_TRANSACTION_REQUIRED" in json.dumps(missing)
            assert "E_MCP_TRANSACTION_NOT_FOUND" in json.dumps(wrong_tx)
            bad = c.call("create_reference", name="p25_intentionally_missing_symbol")[
                "revision"
            ]
            c.call("replace_expression", parent=block, child=bad, position="step")
            assert c.call("check_transaction", expected=False)["isError"]
            assert c.call("commit_transaction", expected=False)["isError"]
            assert not (project / "alva-air/current").exists()
            valid = witness(c, case)
            stale = c.call(
                "replace_expression",
                expected=False,
                parent=fn["revision"],
                child=valid,
                position="body",
            )
            assert "E_AEP_OPERAND_STALE" in json.dumps(stale), stale
            block = c.call("inspect_entity", entity="bench.solve")["slots"]["body"][0]
            row["invalid_transaction_rejected_repairable"] = True
            row["old_revision_rejected"] = stale
            # Anonymous historical nodes retain the existing detached-node
            # allowance. Observe it separately; do not claim universal stale
            # rejection or change AIR semantics in this exposure-only repair.
            state = c.call("inspect_project")["project_revision"]
            anonymous = c.raw(
                "replace_expression",
                {
                    "transaction_id": c.tx,
                    "parent": fn["slots"]["body"][0],
                    "child": valid,
                    "position": "step",
                },
            )
            assert c.call("inspect_project")["project_revision"] == state
            row["old_anonymous_block_observation"] = {
                "response": anonymous,
                "current_program_unchanged": True,
            }
        else:
            valid = witness(c, case)
        c.call("replace_expression", parent=block, child=valid, position="step")
        assert c.call("preview_semantic_diff")["diff"].strip()
        c.call("check_transaction")
        c.call("commit_transaction")
        row["published_air"] = manifest(project / "alva-air")
        assert manifest(project / "src") == before
    finally:
        c.close()
    fresh = Client(project / "alva.toml", case + "-reread")
    try:
        reread = fresh.call("inspect_body", function="bench.solve")
        assert reread != original_body
        row["fresh_process_body"] = reread
        fresh.call("abort_transaction")
    finally:
        fresh.close()
    row["final_behavior"] = behavior(project, case)
    assert manifest(project / "src") == before
    row.update(
        status="SUPPORTED",
        source_unchanged=True,
        protocol="modern" if case == "HE3" else "legacy",
    )
    return row


def stale_base():
    project = Path("/work/stale-guard")
    shutil.copytree("/input/benchmarks/native_mcp_skill/inputs/HE41", project)
    a = Client(project / "alva.toml", "winner")
    b = Client(project / "alva.toml", "stale-base")
    try:
        for client, value in ((a, "1"), (b, "2")):
            body = client.call("inspect_body", function="bench.solve")["body"]
            rev = re.search(r"literal value=0 rev=([0-9a-f]{64})", body).group(1)
            client.call("change_field", entity=rev, field="value", value=value)
            client.call("check_transaction")
        a.call("commit_transaction")
        published = manifest(project / "alva-air")
        conflict = b.call("commit_transaction", expected=False)
        assert "E_AEP_CONFLICT" in json.dumps(conflict), conflict
        assert manifest(project / "alva-air") == published
        b.call("abort_transaction")
        return {
            "status": "PASS",
            "accepted_stale_writes": 0,
            "authority_unchanged_after_rejection": True,
            "published_air": published,
            "response": conflict,
        }
    finally:
        a.close()
        b.close()


def cli_parity():
    """Direct existing CLI Gateway, one corresponding coding witness."""
    project = Path("/work/cli-parity")
    shutil.copytree("/input/benchmarks/native_mcp_skill/inputs/HE41", project)
    p = subprocess.Popen(
        ["/sdk/alva", "agent"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    ordinal = 0

    def send(operation, **arguments):
        nonlocal ordinal
        ordinal += 1
        request = {"request_id": str(ordinal), "tool": operation, **arguments}
        p.stdin.write(json.dumps(request) + "\n")
        p.stdin.flush()
        response = json.loads(p.stdout.readline())
        TRANSCRIPT.append(
            {"session": "direct-CLI-parity", "request": request, "response": response}
        )
        assert response["ok"], response
        return response["result"]

    try:
        send("begin_transaction", project=str(project / "alva.toml"))
        for name in sorted(ADDED):
            send("describe_operation", name=name)
        n = send("create_reference", name="n")["revision"]
        square = send("create_binary", op="*", left=n, right=n)["revision"]
        block = send("inspect_entity", entity="bench.solve")["slots"]["body"][0]
        send("replace_expression", parent=block, child=square, position="step")
        send("check_transaction")
        send("commit_transaction")
    finally:
        p.stdin.close()
        p.wait(timeout=10)
        assert p.returncode == 0, p.stderr.read()
    return {"status": "PASS", "behavior": behavior(project, "HE41")}


def checker_limit():
    """Record a concrete existing check limitation; no AIR/Core repair here."""
    project = Path("/work/checker-observation")
    shutil.copytree("/input/benchmarks/native_mcp_skill/inputs/HE41", project)
    c = Client(project / "alva.toml", "existing-checker-observation")
    try:
        block = c.call("inspect_entity", entity="bench.solve")["slots"]["body"][0]
        string = c.call(
            "create_literal", type="string", value="intentional-return-type-observation"
        )["revision"]
        c.call("replace_expression", parent=block, child=string, position="step")
        body = c.call("inspect_body", function="bench.solve")
        check = c.raw("check_transaction", {"transaction_id": c.tx})
        c.call("abort_transaction")
        assert not (project / "alva-air/current").exists()
        return {
            "status": "OBSERVATION_NOT_A_PASS_GUARANTEE",
            "declared_return": "i64",
            "staged_body": body,
            "check_response": check,
            "committed": False,
            "scope": "Existing checker behavior observed during development; not repaired, not counted as a rejection test or task result.",
        }
    finally:
        c.close()


def main():
    record = {
        "schema": "p25-native-mcp-closure/v1",
        "generation_calls": 0,
        "input_token_calls": 0,
        "cases": [],
    }
    try:
        for case in ("HE41", "HE23", "HE42", "HE3"):
            try:
                record["cases"].append(coding_case(case))
            except Exception as exc:
                record["cases"].append(
                    {
                        "case": case,
                        "status": (
                            "UNSUPPORTED"
                            if "E_MCP_UNKNOWN_TOOL" in str(exc)
                            else "FAIL"
                        ),
                        "error": repr(exc),
                    }
                )
        if all(row["status"] == "SUPPORTED" for row in record["cases"]):
            record["stale_base_guard"] = stale_base()
            record["cli_parity"] = cli_parity()
            record["existing_checker_observation"] = checker_limit()
            record["status"] = "PASS"
        else:
            record["status"] = "FAIL"
    except Exception as exc:
        record.update(status="FAIL", error=repr(exc))
    record["calls"] = TRANSCRIPT
    record["tool_schemas"] = TOOL_SCHEMAS
    print(json.dumps(record))
    return 0  # Host rejects FAIL; retain bounded diagnostic evidence even then.


if __name__ == "__main__":
    main()
