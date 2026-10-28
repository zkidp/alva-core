"""Small source workbench, run ONLY by the P23 isolated process owner.

No evaluator, witness, generic shell, AIR mutation or host path access.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

PATHS = ("alva.toml", "src/app.alva", "src/model.alva")


def revision():
    return hashlib.sha256(json.dumps([(p, hashlib.sha256(Path(p).read_bytes()).hexdigest())
                                     for p in PATHS], separators=(",", ":")).encode()).hexdigest()


def dispatch(action, args):
    current = revision()
    if action == "revision":
        return {"revision": current, "files": list(PATHS), "authority": "SOURCE"}
    if args.get("revision") != current:
        return {"error": "STALE_REVISION", "current_revision": current}
    if action == "diff":
        rows = []
        for name in PATHS:
            p = subprocess.run(["/usr/bin/git", "diff", "--no-index", "--", "/input/" + name,
                                "/work/project/" + name], capture_output=True, text=True)
            if p.returncode not in (0, 1):
                raise RuntimeError("GIT_DIFF_FAILURE:" + p.stderr)
            rows.append(p.stdout)
        text = "".join(rows)
        return {"revision": current, "diff": text} if len(text.encode()) <= 65536 else {"error": "DIFF_TOO_BROAD"}
    if action == "search":
        return {"revision": current, "matches": [
            {"path": name, "line": i, "text": line}
            for name in PATHS for i, line in enumerate(Path(name).read_text().splitlines(), 1)
            if args["text"] in line]}
    name = args.get("path")
    if name not in PATHS:
        return {"error": "PATH_NOT_ALLOWED"}
    path = Path(name)
    if path.is_symlink():
        raise RuntimeError("UNEXPECTED_SYMLINK")
    text = path.read_bytes().decode("utf-8")
    if action == "read":
        lines = text.splitlines(keepends=True)
        start, count = args.get("start", 1), args.get("count", 120)
        if type(start) is not int or type(count) is not int or not 1 <= start <= max(1, len(lines)) or not 1 <= count <= 200:
            return {"error": "INVALID_READ_RANGE", "legal_start": [1, max(1, len(lines))], "legal_count": [1, 200]}
        end = min(len(lines), start + count - 1)
        return {"revision": current, "content": "".join(lines[start - 1:end]), "actual_start": start,
                "actual_end": end, "eof": end == len(lines), "next_start": None if end == len(lines) else end + 1}
    if action == "edit":
        if name == "alva.toml":
            return {"error": "PROTECTED_PATH"}
        old, new = args["old"], args["new"]
        if not old or text.count(old) != 1:
            return {"error": "EXACT_EDIT_PRECONDITION", "occurrences": text.count(old)}
        changed = text.replace(old, new, 1).encode()
        if len(changed) > 65536:
            return {"error": "SOURCE_LIMIT"}
        path.write_bytes(changed)
        return {"accepted": True, "revision": revision(), "path": name}
    return {"error": "UNKNOWN_ACTION"}


if __name__ == "__main__":
    for line in sys.stdin:
        p = json.loads(line)
        args = p["arguments"]
        action = args.pop("_action", p["action"])
        try:
            answer = dispatch(action, args)
        except (KeyError, TypeError, ValueError) as exc:
            answer = {"error": "INVALID_ARGUMENTS", "message": str(exc)}
        print(json.dumps(answer), flush=True)
