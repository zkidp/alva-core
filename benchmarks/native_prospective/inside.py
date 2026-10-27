"""Trusted bounded text/CLI adapter; executes only within P23 namespaces."""

import json
from pathlib import Path
import subprocess
import sys


def main():
    agent = None
    try:
        for line in sys.stdin:
            p = json.loads(line)
            action, args = p["action"], p["arguments"]
            try:
                if action == "read":
                    name = args.get("path")
                    if name not in ("alva.toml", "src/task.alva"):
                        answer = {"error": "PATH_NOT_ALLOWED"}
                    else:
                        answer = {"content": Path(name).read_text()}
                elif action == "edit":
                    if args.get("path") != "src/task.alva" or not isinstance(
                        args.get("content"), str
                    ):
                        answer = {"error": "INVALID_EDIT"}
                    elif len(args["content"].encode()) > 65536:
                        answer = {"error": "SOURCE_LIMIT"}
                    else:
                        Path("src/task.alva").write_text(
                            args["content"], encoding="utf-8"
                        )
                        answer = {"accepted": True}
                elif action == "aep":
                    request = dict(args)
                    request.pop("request_id", None)
                    if request.get("tool") == "begin_transaction":
                        if agent is None:
                            agent = subprocess.Popen(
                                ["/sdk/alva", "agent"],
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL,
                                text=True,
                            )
                        request["project"] = "/work/project/alva.toml"
                    if agent is None:
                        answer = {"error": "BEGIN_TRANSACTION_FIRST"}
                    else:
                        request["request_id"] = "prospective"
                        agent.stdin.write(json.dumps(request) + "\n")
                        agent.stdin.flush()
                        answer = json.loads(agent.stdout.readline())
                else:
                    answer = {"error": "UNKNOWN_ACTION"}
            except (ValueError, TypeError, KeyError) as exc:
                answer = {"error": "INVALID_ARGUMENTS", "message": str(exc)}
            print(json.dumps(answer), flush=True)
    finally:
        if agent:
            agent.stdin.close()
            agent.wait(timeout=5)


if __name__ == "__main__":
    main()
