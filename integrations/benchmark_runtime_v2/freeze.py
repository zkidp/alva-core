"""v2: Git blobs -> exact base64 transport -> strict runtime bytes, no EOL fallback."""
from __future__ import annotations
import base64
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def relative(name: str) -> str:
    path = PurePosixPath(name)
    if not name or "\\" in name or ":" in name or path.is_absolute() or any(p in ("", ".", "..") for p in name.split("/")):
        raise ValueError("Unsafe input path")
    return name


def pack_git(repo: Path, commit: str, paths: list[str]) -> dict:
    resolved = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "--verify", commit + "^{commit}"], text=True).strip()
    entries = []
    for name in sorted(paths):
        relative(name)
        tree = subprocess.check_output(["git", "-C", str(repo), "ls-tree", resolved, "--", name], text=True).strip()
        if not tree:
            raise ValueError("Missing Git input: " + name)
        meta, actual_name = tree.split("\t", 1)
        mode, kind, oid = meta.split()
        if actual_name != name or kind != "blob" or mode not in ("100644", "100755"):
            raise ValueError("Only regular Git blobs are supported")
        data = subprocess.check_output(["git", "-C", str(repo), "cat-file", "blob", oid])
        entries.append({"path": name, "origin": {"kind": "git_blob", "commit": resolved, "oid": oid, "mode": mode},
                        "length": len(data), "sha256": sha(data), "base64": base64.b64encode(data).decode("ascii")})
    payload = {"schema": "alva-benchmark-freeze/v2", "byte_policy": "exact-git-blob-no-normalization", "entries": entries}
    return {"payload": payload, "payload_sha256": sha(canonical(payload))}


def decode(bundle: dict, expected_id: str) -> dict[str, bytes]:
    payload = bundle["payload"]
    actual = sha(canonical(payload))
    if actual != expected_id or bundle["payload_sha256"] != expected_id:
        raise ValueError("Bundle identity mismatch")
    if payload["schema"] != "alva-benchmark-freeze/v2" or payload["byte_policy"] != "exact-git-blob-no-normalization":
        raise ValueError("Unknown byte policy")
    files = {}
    for item in payload["entries"]:
        name = relative(item["path"])
        if name in files:
            raise ValueError("Duplicate input")
        data = base64.b64decode(item["base64"], validate=True)
        if len(data) != item["length"] or sha(data) != item["sha256"]:
            raise ValueError("Blob byte mismatch")
        files[name] = data
    return files


def materialize(bundle: dict, expected_id: str, destination: Path) -> None:
    files = decode(bundle, expected_id)
    if destination.is_symlink() or destination.exists():
        raise ValueError("A new runtime directory is required")
    destination.mkdir(parents=True)
    for name, data in files.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    verify_runtime(bundle, expected_id, destination)


def verify_runtime(bundle: dict, expected_id: str, destination: Path) -> None:
    files = decode(bundle, expected_id)
    if destination.is_symlink():
        raise ValueError("Symlink runtime root")
    actual = {}
    for path in destination.rglob("*"):
        if path.is_symlink():
            raise ValueError("Symlink runtime input")
        if path.is_file():
            actual[path.relative_to(destination).as_posix()] = path.read_bytes()
    if actual != files:
        raise ValueError("Runtime input set/bytes differ from frozen transport")
