"""Real AppServer/SSH T+N dispatch probe; deliberately never calls turn/start."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks.maintenance_interface_comparison.pilot import HERE, Slot, host, save, Remote, NAMES


def main(args):
    registered = json.loads((HERE / "REGISTRATION.json").read_text())
    rows = []
    for arm in ("T", "N"):
        entry = {"id": "probe-" + arm, "task": "MM07", "arm": arm}
        slot = h = None
        row = {"arm": arm, "generation_calls": 0}
        try:
            slot = Slot(args.output, entry, registered, args)
            h, c, thread = host(slot)
            revision = slot.dispatch("revision", {})
            read = slot.dispatch("read", {"revision": revision["revision"], "path": "src/model.alva", "count": 30})
            assert "content" in read
            assert slot.dispatch("doc", {"path": "SKILL.md"})["content"] == registered["docs"]["SKILL.md"]
            if arm == "T":
                source = slot.dispatch("read", {"revision": revision["revision"], "path": "src/model.alva", "count": 200})["content"]
                changed = slot.dispatch("write", {"revision": revision["revision"], "path": "src/model.alva", "content": source})
                assert changed["accepted"]
            else:
                def call(name, arguments):
                    return c.rpc("mcpServer/tool/call", {"threadId": thread["thread"]["id"], "server": "alva", "tool": name, "arguments": arguments})
                begun = call("begin_transaction", {"project": "/work/project/alva.toml"})
                # AppServer's envelope may wrap the MCP result; inspect only public data.
                save(slot.path / "begin-probe.json", begun)
                structured = begun.get("structuredContent", begun.get("result", {}).get("structuredContent", {}))
                if not structured:
                    raise RuntimeError("UNRECOGNIZED_TOOL_CALL_ENVELOPE:" + json.dumps(begun)[:1200])
                tx = structured["transaction_id"]
                inspected = call("inspect_entity", {"transaction_id": tx, "entity": "store.model.xml_error"})
                assert not inspected.get("isError"), inspected
                call("abort_transaction", {"transaction_id": tx})
            checked = slot.dispatch("check", {})
            tested = slot.dispatch("test", {})
            assert checked["status"] == "PASS" and tested["status"] == "TEST_FAIL"
            row.update(status="PASS", actual_model=thread["model"], native_tools=20 if arm == "N" else 0,
                       candidate_unchanged=True, baseline_check=checked["status"], baseline_test=tested["status"])
        except Exception as exc:
            row.update(status="BLOCKED", reason=type(exc).__name__ + ":" + str(exc))
        finally:
            if h:
                h.close()
            if slot:
                try:
                    slot.close()
                except Exception as exc:
                    row.update(status="BLOCKED", cleanup_error=str(exc))
                if hasattr(slot, "context"):
                    slot.context.cleanup()
        rows.append(row)
        print(json.dumps(row), flush=True)
    save(args.output / "PROBE.json", {"rows": rows, "generation_calls": 0,
        "status": "PASS" if all(r["status"] == "PASS" for r in rows) else "BLOCKED"})


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--connection", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    main(p.parse_args())
