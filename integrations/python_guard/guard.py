"""Host-policy-bound snapshot / verify / report implementation."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import stat
import tempfile
import time
from pathlib import Path

from .patch import GuardError, apply_patch, relative_path
from .runner import execute


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise GuardError("INVALID_JSON", f"duplicate key: {key}")
        result[key] = value
    return result


def load_json(data: bytes):
    try:
        return json.loads(data, object_pairs_hook=unique_object)
    except (ValueError, UnicodeError) as exc:
        raise GuardError("INVALID_JSON", str(exc)) from exc


def policy_identity(path: Path) -> str:
    return digest(path.read_bytes())


def is_link(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


class Guard:
    def __init__(self, store: Path, policy_file: Path | None = None):
        self.store = store.absolute()
        self.policy = None
        self.policy_id = None
        self.policy_bytes = None
        if policy_file is not None:
            self.policy_bytes = policy_file.read_bytes()
            self.policy_id = digest(self.policy_bytes)
            self.policy = load_json(self.policy_bytes)
            self._validate_policy(self.policy)
            root = Path(self.policy["project_root"])
            for name, path in (("store", self.store), ("policy", policy_file.absolute()),
                               ("scratch_root", Path(self.policy["scratch_root"]))):
                if within(path.resolve(), root):
                    raise GuardError("UNSAFE_STORAGE", f"{name} must be outside project")
        # Refuse links in the private evidence store, including its parent chain.
        for part in (self.store, *self.store.parents):
            if part.exists() and is_link(part.lstat()):
                raise GuardError("UNSUPPORTED_FILE", "linked evidence storage")
        if policy_file is not None:
            self.store.mkdir(mode=0o700, parents=True, exist_ok=True)
        elif not self.store.is_dir():
            raise GuardError("EVIDENCE_UNAVAILABLE", "report store does not exist")
        for name in ("snapshots", "verifications", "blobs"):
            directory = self.store / name
            if directory.exists() and is_link(directory.lstat()):
                raise GuardError("UNSUPPORTED_FILE", "linked evidence storage")
            if policy_file is not None:
                directory.mkdir(exist_ok=True)
            elif not directory.is_dir():
                raise GuardError("EVIDENCE_UNAVAILABLE", "incomplete report store")

    @staticmethod
    def _validate_policy(policy: dict) -> None:
        required = {"schema", "project_root", "files", "editable", "excluded", "scratch_outputs",
                    "scratch_root", "python", "environment", "checks", "limits", "trusted_project"}
        if not isinstance(policy, dict) or set(policy) != required or policy["schema"] != 1:
            raise GuardError("POLICY_UNAVAILABLE", "policy fields/schema must match version 1")
        for key in ("project_root", "scratch_root", "python"):
            path = Path(policy[key])
            if not path.is_absolute():
                raise GuardError("POLICY_UNAVAILABLE", f"{key} requires an absolute path")
        root = Path(policy["project_root"])
        if not root.is_dir() or is_link(root.lstat()):
            raise GuardError("UNSUPPORTED_FILE", "project root must be a real directory")
        policy["project_root"] = str(root.resolve())
        if type(policy["trusted_project"]) is not bool:
            raise GuardError("POLICY_UNAVAILABLE", "trusted_project must be explicit boolean")
        for key in ("files", "editable", "scratch_outputs"):
            values = policy[key]
            if not isinstance(values, list) or len(set(values)) != len(values):
                raise GuardError("POLICY_UNAVAILABLE", f"{key} must be a unique list")
            for value in values:
                relative_path(value)
        if not set(policy["editable"]) <= set(policy["files"]):
            raise GuardError("POLICY_UNAVAILABLE", "editable paths must be declared input paths")
        if len({name.casefold() for name in policy["files"]}) != len(policy["files"]):
            raise GuardError("POLICY_UNAVAILABLE", "case-colliding paths unsupported")
        if any(other.startswith(name + "/") for name in policy["files"] for other in policy["files"]):
            raise GuardError("POLICY_UNAVAILABLE", "file/directory path collision")
        excluded = policy["excluded"]
        if not isinstance(excluded, dict) or any(not isinstance(v, str) or not v for v in excluded.values()):
            raise GuardError("POLICY_UNAVAILABLE", "exclusions require explicit reasons")
        for name in excluded:
            relative_path(name)
        for name in policy["files"]:
            if any(name == x or name.startswith(x + "/") for x in (*excluded, *policy["scratch_outputs"])):
                raise GuardError("POLICY_UNAVAILABLE", "guarded files cannot be excluded or scratch outputs")
        environment = policy["environment"]
        allowed_env = {"LANG", "LC_ALL", "TZ", "PYTHONHASHSEED", "PATH"}
        if not isinstance(environment, dict) or not set(environment) <= allowed_env or any(
            not isinstance(v, str) or "\x00" in v for v in environment.values()
        ):
            raise GuardError("POLICY_UNAVAILABLE", "only explicitly approved non-secret environment keys supported")
        checks = policy["checks"]
        if not isinstance(checks, list) or len({c["id"] for c in checks}) != len(checks):
            raise GuardError("POLICY_UNAVAILABLE", "checks require unique IDs")
        for check in checks:
            if set(check) != {"id", "argv"} or not isinstance(check["id"], str):
                raise GuardError("POLICY_UNAVAILABLE", "invalid check")
            if check["id"] == "syntax" or not check["id"]:
                raise GuardError("POLICY_UNAVAILABLE", "syntax ID is reserved")
            argv = check["argv"]
            if not isinstance(argv, list) or not argv or any(not isinstance(x, str) or "\x00" in x for x in argv):
                raise GuardError("POLICY_UNAVAILABLE", "checks require argv arrays")
            if argv[0] != "$PYTHON" and not Path(argv[0]).is_absolute():
                raise GuardError("POLICY_UNAVAILABLE", "executable must be absolute or $PYTHON")
        limits = policy["limits"]
        keys = {"max_files", "max_source_bytes", "max_patch_bytes", "wall_seconds", "output_bytes_per_stream",
                "max_command_invocations", "max_direct_processes", "address_space_bytes", "cpu_seconds"}
        if not isinstance(limits, dict) or set(limits) != keys:
            raise GuardError("POLICY_UNAVAILABLE", "complete limits required")
        for key, value in limits.items():
            if value is None and key in {"address_space_bytes", "cpu_seconds"}:
                continue
            if type(value) not in (int, float) or value <= 0 or value != value or value == float("inf"):
                raise GuardError("POLICY_UNAVAILABLE", f"invalid limit: {key}")
            if key != "wall_seconds" and type(value) is not int:
                raise GuardError("POLICY_UNAVAILABLE", f"integer limit required: {key}")
        if limits["max_direct_processes"] != 1:
            raise GuardError("POLICY_UNAVAILABLE", "MVP executes one direct command at a time")

    def _policy_request(self, request: dict) -> dict:
        if self.policy is None or request.get("policy_id") != self.policy_id:
            raise GuardError("POLICY_UNAVAILABLE", "host-approved policy identity required")
        # Reconstruct from approved bytes; mutating an API-returned dictionary
        # must never broaden the policy associated with an unchanged identity.
        approved = load_json(self.policy_bytes)
        self._validate_policy(approved)
        return approved

    @staticmethod
    def _scan(root: Path, policy: dict, scratch: bool = False) -> tuple[list[dict], dict[str, bytes]]:
        if not root.is_dir() or is_link(root.lstat()):
            raise GuardError("UNSUPPORTED_FILE", "project root changed")
        manifest = []
        contents = {}
        total = 0
        allowed = set(policy["files"])
        omitted = [*policy["excluded"], *(policy["scratch_outputs"] if scratch else [])]

        def visit(directory: Path) -> None:
            nonlocal total
            for path in sorted(directory.iterdir()):
                name = path.relative_to(root).as_posix()
                if any(name == x or name.startswith(x + "/") for x in omitted):
                    continue
                relative_path(name)
                info = path.lstat()
                if is_link(info):
                    raise GuardError("UNSUPPORTED_FILE", f"links/reparse points unsupported: {name}")
                if stat.S_ISDIR(info.st_mode):
                    visit(path)
                    continue
                if not stat.S_ISREG(info.st_mode):
                    raise GuardError("UNSUPPORTED_FILE", name)
                if name not in allowed:
                    raise GuardError("UNDECLARED_FILE", name)
                remaining = policy["limits"]["max_source_bytes"] - total
                if info.st_size > remaining or len(manifest) >= policy["limits"]["max_files"]:
                    raise GuardError("INPUT_LIMIT", name)
                with path.open("rb") as stream:
                    data = stream.read(remaining + 1)
                after = path.lstat()
                if is_link(after) or (info.st_ino, info.st_size, info.st_mtime_ns) != (
                    after.st_ino, after.st_size, after.st_mtime_ns
                ):
                    raise GuardError("UNSTABLE_CAPTURE", name)
                if len(data) > remaining:
                    raise GuardError("INPUT_LIMIT", name)
                try:
                    data.decode("utf-8")
                except UnicodeError as exc:
                    raise GuardError("UNSUPPORTED_FILE", f"UTF-8 input required: {name}") from exc
                total += len(data)
                manifest.append({"path": name, "sha256": digest(data), "bytes": len(data),
                                 "executable": bool(info.st_mode & 0o111)})
                contents[name] = data
        visit(root)
        return sorted(manifest, key=lambda x: x["path"]), contents

    def _put_blob(self, data: bytes) -> str:
        identity = digest(data)
        path = self.store / "blobs" / identity[7:]
        if path.exists():
            if is_link(path.lstat()) or path.read_bytes() != data:
                raise GuardError("EVIDENCE_TAMPERED", "existing blob differs")
        else:
            with path.open("xb") as stream:
                stream.write(data)
        return identity

    def _save(self, kind: str, value: dict) -> str:
        data = canonical(value)
        identity = digest(data)
        path = self.store / ("snapshots" if kind == "snapshot" else "verifications") / (identity[7:] + ".json")
        if path.exists():
            if is_link(path.lstat()) or path.read_bytes() != data:
                raise GuardError("EVIDENCE_TAMPERED", "existing record differs")
        else:
            with path.open("xb") as stream:
                stream.write(data)
        return kind + ":" + identity[7:]

    def _load(self, identity: str, kind: str) -> dict:
        import re
        if not isinstance(identity, str) or not re.fullmatch(kind + r":[0-9a-f]{64}", identity):
            raise GuardError("INVALID_ID", kind)
        key = identity.split(":")[1]
        path = self.store / ("snapshots" if kind == "snapshot" else "verifications") / (key + ".json")
        try:
            if is_link(path.lstat()):
                raise GuardError("EVIDENCE_TAMPERED", identity)
            data = path.read_bytes()
        except OSError as exc:
            raise GuardError("EVIDENCE_UNAVAILABLE", identity) from exc
        if digest(data) != "sha256:" + key:
            raise GuardError("EVIDENCE_TAMPERED", identity)
        return load_json(data)

    def _snapshot(self, identity: str) -> tuple[dict, dict[str, bytes]]:
        record = self._load(identity, "snapshot")
        policy_blob = self.store / "blobs" / record["policy_id"][7:]
        if not policy_blob.is_file() or is_link(policy_blob.lstat()) or digest(policy_blob.read_bytes()) != record["policy_id"]:
            raise GuardError("EVIDENCE_TAMPERED", "policy bytes")
        contents = {}
        for row in record["manifest"]:
            name = relative_path(row["path"])
            path = self.store / "blobs" / row["sha256"][7:]
            try:
                if is_link(path.lstat()):
                    raise GuardError("EVIDENCE_TAMPERED", name)
                data = path.read_bytes()
            except OSError as exc:
                raise GuardError("EVIDENCE_UNAVAILABLE", name) from exc
            if digest(data) != row["sha256"] or len(data) != row["bytes"]:
                raise GuardError("EVIDENCE_TAMPERED", name)
            contents[name] = data
        if digest(canonical(record["manifest"])) != record["tree_digest"]:
            raise GuardError("EVIDENCE_TAMPERED", "manifest")
        return record, contents

    @staticmethod
    def _environment(policy: dict) -> dict:
        python = Path(policy["python"])
        commands = {policy["python"], *(c["argv"][0] for c in policy["checks"] if c["argv"][0] != "$PYTHON")}
        return {"python": str(python), "host_platform": platform.platform(),
                "executables": {x: digest(Path(x).read_bytes()) if Path(x).is_file() else None for x in sorted(commands)},
                "approved_environment": policy["environment"],
                "external_dependencies_content_locked": False,
                "resource_limits": policy["limits"], "backend": "trusted-local"}

    def snapshot(self, request: dict) -> dict:
        policy = self._policy_request(request)
        if Path(request["project_root"]).resolve() != Path(policy["project_root"]) or request["files"] != policy["files"]:
            raise GuardError("POLICY_UNAVAILABLE", "root/files differ from approved policy")
        for key, value in request.get("limits", {}).items():
            if key not in {"max_files", "max_source_bytes"} or value > policy["limits"][key]:
                raise GuardError("INPUT_LIMIT", "snapshot cannot expand approved limits")
        capture_policy = policy | {"limits": policy["limits"] | request.get("limits", {})}
        root = Path(policy["project_root"])
        manifest, contents = self._scan(root, capture_policy)
        second, _ = self._scan(root, capture_policy)
        if manifest != second:
            raise GuardError("UNSTABLE_CAPTURE", "manifest changed during capture")
        missing = set(policy["files"]) - set(contents) - set(policy["editable"])
        if missing:
            raise GuardError("UNSUPPORTED_FILE", "missing protected inputs: " + ", ".join(sorted(missing)))
        for data in contents.values():
            self._put_blob(data)
        self._put_blob(self.policy_bytes)
        record = {"schema": 1, "policy_id": self.policy_id, "policy": policy,
                  "project_root": policy["project_root"], "manifest": manifest,
                  "tree_digest": digest(canonical(manifest)), "environment": self._environment(policy),
                  "excluded": policy["excluded"], "capture_method": "copy bytes plus second full manifest comparison"}
        identity = self._save("snapshot", record)
        return record | {"snapshot_id": identity}

    @staticmethod
    def _applicability(snapshot: dict) -> tuple[str, str]:
        try:
            current, _ = Guard._scan(Path(snapshot["project_root"]), snapshot["policy"])
            return ("CURRENT", "MANIFEST_MATCH") if current == snapshot["manifest"] else ("STALE", "SOURCE_CHANGED")
        except (GuardError, OSError):
            return "STALE", "SOURCE_MANIFEST_UNAVAILABLE_OR_CHANGED"

    @staticmethod
    def _materialize(root: Path, contents: dict[str, bytes], manifest: list[dict]) -> None:
        root.mkdir()
        modes = {r["path"]: r["executable"] for r in manifest}
        for name, data in contents.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            if os.name != "nt":
                path.chmod(0o700 if modes.get(name) else 0o600)

    def verify(self, request: dict) -> dict:
        policy = self._policy_request(request)
        snap, originals = self._snapshot(request["snapshot_id"])
        if snap["policy_id"] != self.policy_id or snap["project_root"] != policy["project_root"]:
            raise GuardError("POLICY_UNAVAILABLE", "snapshot policy/root mismatch")
        patch = request["patch_utf8"]
        if not isinstance(patch, str) or len(patch.encode("utf-8")) > policy["limits"]["max_patch_bytes"]:
            raise GuardError("INPUT_LIMIT", "patch size")
        changes = apply_patch(patch, originals)
        if not set(changes) <= set(policy["editable"]):
            raise GuardError("PROTECTED_FILE", ", ".join(sorted(set(changes) - set(policy["editable"]))))
        expected = request["expected_files"]
        actual = {name: digest(originals[name]) if name in originals else None for name in changes}
        if expected != actual:
            raise GuardError("PREIMAGE_MISMATCH", "expected_files must exactly match all affected snapshot files")
        limits = dict(policy["limits"])
        for key, value in request.get("limits", {}).items():
            if key not in {"wall_seconds", "output_bytes_per_stream"} or type(value) not in (int, float) or not 0 < value <= limits[key]:
                raise GuardError("INPUT_LIMIT", "verify cannot expand approved limits")
            if key == "output_bytes_per_stream" and type(value) is not int:
                raise GuardError("INPUT_LIMIT", "output limit requires integer")
            limits[key] = value
        candidate = dict(originals)
        for name, data in changes.items():
            if data is None:
                candidate.pop(name)
            else:
                candidate[name] = data
        if len(candidate) > limits["max_files"] or sum(map(len, candidate.values())) > limits["max_source_bytes"]:
            raise GuardError("INPUT_LIMIT", "candidate tree exceeds bounds")
        old_modes = {r["path"]: r["executable"] for r in snap["manifest"]}
        candidate_manifest = [{"path": name, "sha256": digest(data), "bytes": len(data),
                               "executable": old_modes.get(name, False)} for name, data in sorted(candidate.items())]
        environment = self._environment(policy)
        result = {"schema": 1, "snapshot_id": request["snapshot_id"], "policy_id": self.policy_id,
                  "patch_sha256": self._put_blob(patch.encode("utf-8")),
                  "candidate_manifest": candidate_manifest, "candidate_tree_digest": digest(canonical(candidate_manifest)),
                  "environment": environment, "environment_digest": digest(canonical(environment)),
                  "limits": limits, "checks": [], "regression": [], "reasons": [],
                  "checks_status": "UNKNOWN", "applicability_status": "UNKNOWN",
                  "execution": {"backend": "trusted-local", "sandbox": False, "max_direct_processes": 1,
                                "descendant_process_count_enforced": False, "external_side_effects_rollback": False}}
        for data in candidate.values():
            self._put_blob(data)
        applicability, reason = self._applicability(snap)
        if applicability != "CURRENT":
            result["reasons"].append(reason)
        elif not policy["trusted_project"]:
            result["reasons"].append("UNTRUSTED_EXECUTION_UNSUPPORTED")
        elif environment != snap["environment"]:
            result["reasons"].append("ENVIRONMENT_CHANGED_SINCE_SNAPSHOT")
        elif not Path(policy["python"]).is_file():
            result["reasons"].append("PYTHON_UNAVAILABLE")
        else:
            self._run_checks(result, policy, limits, originals, candidate, snap["manifest"], candidate_manifest)
        if self._environment(policy) != environment:
            result["checks_status"] = "UNKNOWN"
            result["reasons"].append("EXECUTION_ENVIRONMENT_CHANGED")
        result["applicability_status"], reason = self._applicability(snap)
        result["applicability_reason"] = reason
        result["applicability_as_of"] = "verification completion; use a new snapshot for a later comparison"
        identity = self._save("verification", result)
        return result | {"verification_id": identity}

    def _run_checks(self, result, policy, limits, originals, candidate, baseline_manifest, candidate_manifest) -> None:
        scratch_parent = Path(policy["scratch_root"])
        if not scratch_parent.is_dir() or is_link(scratch_parent.lstat()):
            result["reasons"].append("SCRATCH_ENVIRONMENT_UNAVAILABLE")
            return
        compile_code = "import pathlib,sys; [compile(pathlib.Path(p).read_bytes(),p,'exec') for p in sys.argv[1:]]"
        with tempfile.TemporaryDirectory(prefix="alva-guard-", dir=scratch_parent) as directory:
            workspace = Path(directory)
            trees = {"baseline": workspace / "baseline", "candidate": workspace / "candidate"}
            manifests = {"baseline": baseline_manifest, "candidate": candidate_manifest}
            self._materialize(trees["baseline"], originals, baseline_manifest)
            self._materialize(trees["candidate"], candidate, candidate_manifest)
            operations = [{"id": "syntax", "argv": ["$PYTHON", "-I", "-c", compile_code]}] + policy["checks"]
            overall_deadline = time.monotonic() + limits["wall_seconds"]
            stopped = False
            for check in operations:
                for arm, tree in trees.items():
                    remaining = overall_deadline - time.monotonic()
                    if stopped or len(result["checks"]) >= limits["max_command_invocations"] or remaining <= 0:
                        result["checks"].append({"id": check["id"], "arm": arm, "status": "NOT_RUN", "reason": "VERIFICATION_BUDGET"})
                        continue
                    argv = [policy["python"] if x == "$PYTHON" else x for x in check["argv"]]
                    if check["id"] == "syntax":
                        argv += [r["path"] for r in manifests[arm] if r["path"].endswith(".py")]
                    aux = workspace / (arm + "-environment")
                    aux.mkdir(exist_ok=True)
                    env = {"PATH": str(Path(policy["python"]).parent) + os.pathsep + os.defpath,
                           "HOME": str(aux), "USERPROFILE": str(aux), "TMPDIR": str(aux),
                           "TMP": str(aux), "TEMP": str(aux), "PYTHONDONTWRITEBYTECODE": "1",
                           "PYTHONHASHSEED": "0", **policy["environment"]}
                    if os.name == "nt" and "SystemRoot" in os.environ:
                        env["SystemRoot"] = os.environ["SystemRoot"]
                    row = execute(argv, tree, env, limits | {"wall_seconds": remaining})
                    row.update(id=check["id"], arm=arm)
                    try:
                        after, _ = self._scan(tree, policy, scratch=True)
                        if after != manifests[arm]:
                            raise GuardError("CHECK_MODIFIED_INPUT", arm)
                    except (GuardError, OSError):
                        row.update(status="UNKNOWN", reason="CHECK_MODIFIED_INPUT")
                    result["checks"].append(row)
                    if row["status"] == "UNKNOWN":
                        # A modified/unsafe environment cannot be reused as fresh evidence.
                        result["reasons"].append(row["reason"])
                        stopped = True
            rows = result["checks"]
            candidates = [r for r in rows if r["arm"] == "candidate"]
            if len(candidates) != len(operations) or any(r["status"] in {"UNKNOWN", "NOT_RUN"} for r in rows):
                result["checks_status"] = "UNKNOWN"
            else:
                result["checks_status"] = "FAIL" if any(r["status"] == "FAIL" for r in candidates) else "PASS"
            for check in operations:
                selected = {r["arm"]: r for r in rows if r["id"] == check["id"]}
                b, c = selected.get("baseline", {}).get("status"), selected.get("candidate", {}).get("status")
                if b not in {"PASS", "FAIL"} or c not in {"PASS", "FAIL"}:
                    classification = "UNKNOWN"
                elif b == "PASS" and c == "FAIL":
                    classification = "NEW_REGRESSION"
                elif b == "FAIL" and c == "FAIL":
                    classification = "BASELINE_AND_CANDIDATE_FAIL"
                elif b == "FAIL":
                    classification = "BASELINE_FAILURE_CLOSED"
                else:
                    classification = "BOTH_PASS"
                result["regression"].append({"id": check["id"], "baseline": b, "candidate": c,
                                             "classification": classification,
                                             "limitation": "same failing command does not prove the same underlying defect"})

    def report(self, request: dict) -> dict:
        identity = request["verification_id"]
        result = self._load(identity, "verification")
        snap, _ = self._snapshot(result["snapshot_id"])
        # Verify all content-addressed candidate and patch evidence before showing a green result.
        for row in result["candidate_manifest"]:
            path = self.store / "blobs" / row["sha256"][7:]
            if not path.is_file() or is_link(path.lstat()) or digest(path.read_bytes()) != row["sha256"]:
                raise GuardError("EVIDENCE_TAMPERED", row["path"])
        path = self.store / "blobs" / result["patch_sha256"][7:]
        if not path.is_file() or is_link(path.lstat()) or digest(path.read_bytes()) != result["patch_sha256"]:
            raise GuardError("EVIDENCE_TAMPERED", "patch")
        if request.get("current_snapshot_id"):
            current, _ = self._snapshot(request["current_snapshot_id"])
            if current["project_root"] != snap["project_root"] or current["policy_id"] != snap["policy_id"]:
                raise GuardError("POLICY_UNAVAILABLE", "current snapshot has different root/policy")
            live, reason = self._applicability(current)
            result["applicability_status"] = "CURRENT" if live == "CURRENT" and current["tree_digest"] == snap["tree_digest"] else "STALE"
            result["applicability_reason"] = "SOURCE_CHANGED" if current["tree_digest"] != snap["tree_digest"] else reason
            result["applicability_as_of"] = "supplied current snapshot comparison (including live byte check)"
            result["current_snapshot_id"] = request["current_snapshot_id"]
        else:
            result["recorded_applicability_status"] = result["applicability_status"]
            if result["applicability_status"] != "STALE":
                result["applicability_status"] = "UNKNOWN"
                result["applicability_reason"] = "CURRENT_SNAPSHOT_REQUIRED"
            result["applicability_as_of"] = "stored historical evidence only; no live source check requested"
        return result | {"verification_id": identity, "evidence_integrity": "PASS"}
