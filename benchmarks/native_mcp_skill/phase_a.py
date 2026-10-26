"""Real Windows Codex Host -> explicit WSL Linux P23 -> native MCP; zero turns."""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from integrations.benchmark_runtime_v2.freeze import pack_git, materialize

BASE = "ca930db61823c8318f1126f5649d1863f10fcc37"


def linux(path):
    path = str(Path(path).resolve()).replace("\\", "/")
    assert path[1:3] == ":/"
    return "/mnt/" + path[0].lower() + path[2:]


def main(args):
    assert (
        os.name == "nt"
    ), "This connection fixture explicitly selects Windows Host + WSL Linux"
    assert re.fullmatch(
        r"[a-z0-9-]+", args.attempt
    ), "Safe development attempt label required"
    runtime = ROOT / ".local/native-mcp-skill" / args.attempt
    runtime.mkdir(parents=True, exist_ok=False)
    # Reuse the already validated P0 transport class, not its historical gate.
    spec = importlib.util.spec_from_file_location(
        "p0_transport", ROOT / "tests/integrations/codex_native_test.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    bundle = pack_git(
        ROOT,
        BASE,
        [
            "tests/project/alva.toml",
            "tests/project/src/app.alva",
            "tests/project/src/model.alva",
        ],
    )
    (runtime / "bundle.json").write_text(json.dumps(bundle), encoding="utf-8")
    config = {
        "bundle": linux(runtime / "bundle.json"),
        "bundle_id": bundle["payload_sha256"],
        "alva": args.alva,
        "toolchain": args.toolchain,
        "registry": args.registry,
        "ready": linux(runtime / "ready.json"),
        "evidence": linux(runtime / "proxy-evidence.json"),
    }
    (runtime / "proxy-config.json").write_text(json.dumps(config), encoding="utf-8")
    paths = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", BASE, "integrations/codex"],
        cwd=ROOT,
        text=True,
    ).splitlines()
    materialize(
        pack_git(ROOT, BASE, paths),
        pack_git(ROOT, BASE, paths)["payload_sha256"],
        runtime / "public-plugin",
    )
    marketplace = runtime / "public-plugin/integrations/codex"
    wiring = {
        "mcpServers": {
            "alva": {
                "command": "wsl.exe",
                "args": [
                    "--distribution",
                    args.distro,
                    "--exec",
                    "python3",
                    linux(ROOT / "benchmarks/native_mcp_skill/proxy.py"),
                    "--config",
                    linux(runtime / "ready.json"),
                ],
            }
        }
    }
    (marketplace / "plugins/alva/.mcp.json").write_text(
        json.dumps(wiring), encoding="utf-8"
    )
    env = dict(os.environ)
    env["CODEX_HOME"] = str(runtime / "codex-home")
    env.pop("CLAUDE_PROJECT_DIR", None)
    Path(env["CODEX_HOME"]).mkdir()
    empty = runtime / "empty"
    empty.mkdir()
    codex = shutil.which("codex")

    def command(argv):
        p = subprocess.run(
            argv, env=env, cwd=empty, capture_output=True, text=True, timeout=120
        )
        assert p.returncode == 0, (p.stdout, p.stderr)
        return json.loads(p.stdout)

    command([codex, "plugin", "marketplace", "add", str(marketplace), "--json"])
    installed = command([codex, "plugin", "add", "alva@alva", "--json"])
    canonical = pack_git(
        ROOT,
        BASE,
        [
            "integrations/skills/alva/SKILL.md",
            *[
                "integrations/skills/alva/references/" + p
                for p in ("workflow.md", "diagnostics.md", "examples.md")
            ],
        ],
    )
    from integrations.benchmark_runtime_v2.freeze import decode, sha

    skill_hashes = {}
    for name, data in decode(canonical, canonical["payload_sha256"]).items():
        relative = name.removeprefix("integrations/skills/alva/")
        actual = Path(installed["installedPath"]) / "skills/alva" / relative
        assert actual.read_bytes() == data, relative
        skill_hashes[relative] = sha(data)
    service_argv = [
        "wsl.exe",
        "--distribution",
        args.distro,
        "--exec",
        "python3",
        linux(ROOT / "benchmarks/native_mcp_skill/proxy.py"),
    ]
    service = subprocess.Popen(
        [
            *service_argv,
            "--role",
            "server",
            "--config",
            linux(runtime / "proxy-config.json"),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    deadline = time.monotonic() + 15
    while not (runtime / "ready.json").is_file():
        assert service.poll() is None, service.communicate()
        assert time.monotonic() < deadline, "Isolated service startup timeout"
        time.sleep(0.05)
    host = module.AppServer(
        codex,
        env,
        empty,
        extra_args=["-c", "features.shell_tool=false", "-c", 'web_search="disabled"'],
    )
    record = {
        "status": "FAIL_CLOSED",
        "generation_calls": 0,
        "input_token_calls": 0,
        "base": BASE,
        "skill_sha256": skill_hashes,
        "calls": [],
        "bundle_id": bundle["payload_sha256"],
    }
    try:
        host.request(
            "initialize",
            {
                "clientInfo": {"name": "p24-native-isolated-fixture", "version": "1"},
                "capabilities": {"experimentalApi": True},
            },
        )
        host.send({"method": "initialized", "params": {}})
        skills = host.request(
            "skills/list", {"cwds": [str(empty)], "forceReload": True}
        )
        assert any(
            s.get("pluginId") == "alva@alva" and s["enabled"]
            for row in skills["data"]
            for s in row["skills"]
        ), skills
        thread = host.request(
            "thread/start",
            {
                "cwd": str(empty),
                "approvalPolicy": "never",
                "sandbox": "read-only",
                "ephemeral": True,
            },
        )
        servers = host.request(
            "mcpServerStatus/list", {"threadId": thread["thread"]["id"]}
        )["data"]
        server = next(s for s in servers if s.get("pluginId") == "alva@alva")
        assert server.get("toolsError") is None, server
        record["tools"] = server["tools"]

        def call(operation, **arguments):
            answer = host.request(
                "mcpServer/tool/call",
                {
                    "threadId": thread["thread"]["id"],
                    "server": server["name"],
                    "tool": operation,
                    "arguments": arguments,
                },
            )
            assert not answer.get("isError"), answer
            record["calls"].append(
                {
                    "operation": operation,
                    "arguments": arguments,
                    "result": answer["structuredContent"],
                }
            )
            return answer["structuredContent"]

        tx = call("begin_transaction", project="/work/project/tests/project/alva.toml")[
            "transaction_id"
        ]

        def tool(operation, **arguments):
            return call(operation, transaction_id=tx, **arguments)

        entity = tool("resolve_entity", name="demo.app.run", kind="function")["entity"]
        tool("applicable_operations", entity=entity)
        tool("describe_operation", name="change_field")
        body = tool("inspect_body", function="demo.app.run")["body"]
        literal = re.search(r"literal value=a rev=([0-9a-f]{64})", body)
        assert literal, body
        tool(
            "change_field",
            entity=literal.group(1),
            field="value",
            value="native-host-isolated",
        )
        tool("preview_semantic_diff")
        tool("check_transaction")
        tool("commit_transaction")
    except BaseException:
        host.close()
        aborted = subprocess.run(
            [
                *service_argv,
                "--role",
                "abort",
                "--config",
                linux(runtime / "ready.json"),
            ],
            capture_output=True,
            timeout=30,
        )
        assert aborted.returncode == 0, "Isolated service abort unconfirmed"
        service.communicate(timeout=15)
        raise
    else:
        host.close()
    verify = subprocess.run(
        [*service_argv, "--role", "verify", "--config", linux(runtime / "ready.json")],
        capture_output=True,
        timeout=30,
    )
    assert verify.returncode == 0, (verify.stdout, verify.stderr)
    stdout, stderr = service.communicate(timeout=15)
    assert service.returncode == 0, (stdout, stderr)
    proxy = json.loads((runtime / "proxy-evidence.json").read_text())
    assert proxy["status"] == "PASS", proxy
    record.update(
        status="PASS",
        proxy=proxy,
        codex=subprocess.check_output([codex, "--version"], text=True).strip(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "generation_calls": 0,
                "native_calls": len(record["calls"]),
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--distro", default="Ubuntu-26.04")
    parser.add_argument("--alva", required=True)
    parser.add_argument("--toolchain", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attempt", default="phase-a")
    main(parser.parse_args())
