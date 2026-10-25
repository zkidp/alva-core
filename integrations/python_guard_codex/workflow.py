"""Host-owned session state and exact candidate diffs. No source apply endpoint.

Call from a trusted parent process, never from inside the agent's writable tree.
Filesystem authority is provided by the host sandbox, not by these path checks.
"""

from __future__ import annotations

from pathlib import Path

from integrations.python_guard import Guard, GuardError
from integrations.python_guard.guard import canonical, digest, is_link, load_json, within
from integrations.python_guard.patch import apply_patch


TOOLS = [{"name": name, "description": description,
          "inputSchema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False}}
         for name, description in (
             ("guard_verify", "Verify the current isolated candidate with the host-approved Python Guard policy. Never applies it to source."),
             ("guard_report", "Read the last Guard evidence and refresh source applicability. Does not rerun checks."))]


def exact_diff(originals: dict[str, bytes], candidate: dict[str, bytes]) -> str:
    """Full-file unified hunks preserve UTF-8, CRLF and absent final newlines."""
    result = []
    for name in sorted(originals.keys() | candidate.keys()):
        old, new = originals.get(name), candidate.get(name)
        if old == new:
            continue
        before = [] if old is None else old.decode("utf-8").splitlines(keepends=True)
        after = [] if new is None else new.decode("utf-8").splitlines(keepends=True)
        result.extend(["--- " + ("/dev/null" if old is None else "a/" + name) + "\n",
                       "+++ " + ("/dev/null" if new is None else "b/" + name) + "\n",
                       f"@@ -{1 if before else 0},{len(before)} +{1 if after else 0},{len(after)} @@\n"])
        for tag, lines in (("-", before), ("+", after)):
            for line in lines:
                result.append(tag + line)
                if not line.endswith("\n"):
                    result.append("\n\\ No newline at end of file\n")
    return "".join(result)


class CandidateSession:
    """One immutable base, one mutable candidate; a separately protected control dir."""

    def __init__(self, control: Path):
        self.control = control.resolve()
        for path in (control.absolute(), *control.absolute().parents):
            if path.exists() and is_link(path.lstat()):
                raise GuardError("UNSUPPORTED_FILE", "linked control storage")
        self.state = load_json((self.control / "session.json").read_bytes())
        self.candidate = Path(self.state["candidate"])
        self.policy_file = Path(self.state["policy_file"])
        self.guard = Guard(self.control / "evidence", self.policy_file)
        if self.guard.policy_id != self.state["policy_id"]:
            raise GuardError("POLICY_UNAVAILABLE", "approved policy changed; prepare a new session")
        self.snapshot, self.originals = self.guard._snapshot(self.state["snapshot_id"])
        self._separate_paths()

    def _separate_paths(self):
        root = Path(self.snapshot["project_root"])
        scratch = Path(self.guard.policy["scratch_root"]).resolve()
        candidate = self.candidate.resolve()
        # None of the authority locations may be below the writable candidate.
        for protected in (root, self.control, self.policy_file.resolve(), scratch):
            if within(protected, candidate) or within(candidate, protected):
                raise GuardError("UNSAFE_STORAGE", "candidate must be disjoint from source, policy, control and check scratch")

    @classmethod
    def prepare(cls, control: Path, policy_file: Path, candidate: Path, approved_policy_id: str):
        """Trusted host must obtain approved_policy_id from the user, not the agent."""
        control, policy_file, candidate = control.absolute(), policy_file.absolute(), candidate.absolute()
        if control.exists() or candidate.exists():
            raise GuardError("UNSAFE_STORAGE", "control and candidate must be new paths")
        # Check aliases/ancestor overlaps before creating anything.
        policy_bytes = policy_file.read_bytes()
        if digest(policy_bytes) != approved_policy_id:
            raise GuardError("POLICY_UNAVAILABLE", "policy bytes do not match explicit approval")
        policy = load_json(policy_bytes)
        Guard._validate_policy(policy)
        protected = [Path(policy["project_root"]), policy_file, Path(policy["scratch_root"])]
        for a, b in [(control, candidate), *((control, p) for p in protected), *((candidate, p) for p in protected)]:
            if within(a.resolve(), b.resolve()) or within(b.resolve(), a.resolve()):
                raise GuardError("UNSAFE_STORAGE", "overlapping workflow paths")
        for path in (control, candidate):
            for part in path.parents:
                if part.exists() and is_link(part.lstat()):
                    raise GuardError("UNSUPPORTED_FILE", "linked workflow storage")
        guard = Guard(control / "evidence", policy_file)
        snapshot = guard.snapshot({"project_root": policy["project_root"], "policy_id": approved_policy_id,
                                   "files": policy["files"]})
        _, originals = guard._snapshot(snapshot["snapshot_id"])
        Guard._materialize(candidate, originals, snapshot["manifest"])
        state = {"schema": 1, "candidate": str(candidate.resolve()), "policy_file": str(policy_file.resolve()),
                 "policy_id": approved_policy_id, "snapshot_id": snapshot["snapshot_id"]}
        (control / "session.json").write_bytes(canonical(state))
        return cls(control)

    def description(self):
        return {**self.state, "editable": self.guard.policy["editable"],
                "source_apply_supported": False, "git_commit_supported": False,
                "authority_requirement": "Host must deny agent writes to source, policy, control, verifier and check scratch."}

    def _candidate_patch(self):
        manifest, contents = Guard._scan(self.candidate, self.guard.policy, scratch=True)
        old_modes = {row["path"]: row["executable"] for row in self.snapshot["manifest"]}
        if any(row["path"] in old_modes and row["executable"] != old_modes[row["path"]] for row in manifest):
            raise GuardError("UNSUPPORTED_PATCH", "candidate mode changes unsupported")
        patch = exact_diff(self.originals, contents)
        if not patch:
            raise GuardError("NO_CANDIDATE_CHANGE", "nothing to verify; not a PASS")
        if len(patch.encode("utf-8")) > self.guard.policy["limits"]["max_patch_bytes"]:
            raise GuardError("INPUT_LIMIT", "candidate patch exceeds approved limit")
        changes = apply_patch(patch, self.originals)
        expected = {name: digest(self.originals[name]) if name in self.originals else None for name in changes}
        return patch, expected

    def verify(self):
        # Reopen protected state/policy on each operation; do not trust cached agent input.
        current = CandidateSession(self.control)
        patch, expected = current._candidate_patch()
        request = {"snapshot_id": current.state["snapshot_id"], "policy_id": current.state["policy_id"],
                   "patch_utf8": patch, "expected_files": expected}
        result = current.guard.verify(request)
        (self.control / "candidate.patch").write_bytes(patch.encode("utf-8"))
        (self.control / "verify-request.json").write_bytes(canonical(request))
        (self.control / "last-verification.json").write_bytes(canonical({"verification_id": result["verification_id"]}))
        return result

    def report(self):
        current = CandidateSession(self.control)
        request = load_json((self.control / "last-verification.json").read_bytes())
        # P1 report independently checks live source. If capture cannot be made,
        # retain historical checks with UNKNOWN applicability; never invent CURRENT.
        try:
            live = current.guard.snapshot({"project_root": current.snapshot["project_root"],
                "policy_id": current.state["policy_id"], "files": current.guard.policy["files"]})
            request["current_snapshot_id"] = live["snapshot_id"]
        except (GuardError, OSError):
            pass
        result = current.guard.report(request)
        try:
            patch, _ = current._candidate_patch()
            candidate_matches = digest(patch.encode("utf-8")) == result["patch_sha256"]
        except (GuardError, OSError, UnicodeError):
            candidate_matches = False
        # Separate from applicability to the original source: this evidence may
        # describe a previous candidate if the agent edited after verification.
        return result | {"candidate_matches_verified_patch": candidate_matches,
                         "source_apply_supported": False, "user_application_required": True}

    def tool_call(self, name: str, arguments: dict):
        """Optional app-server dynamic-tool callback, called only by trusted host."""
        if type(arguments) is not dict or arguments or name not in {row["name"] for row in TOOLS}:
            return {"success": False, "contentItems": [{"type": "inputText", "text": "INVALID_GUARD_TOOL_ARGUMENTS"}]}
        try:
            result = self.verify() if name == "guard_verify" else self.report()
            return {"success": True, "contentItems": [{"type": "inputText", "text": canonical(result).decode("utf-8")}]}
        except (GuardError, OSError, UnicodeError) as exc:
            reason = exc.code if isinstance(exc, GuardError) else "WORKFLOW_UNAVAILABLE"
            return {"success": False, "contentItems": [{"type": "inputText", "text": canonical(
                {"checks_status": "UNKNOWN", "applicability_status": "UNKNOWN", "reason": reason}).decode("utf-8")}]}
