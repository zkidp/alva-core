"""Deliberately narrow unified-diff application with exact preimages."""

from __future__ import annotations

import re
from pathlib import PurePosixPath


class GuardError(ValueError):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code


def relative_path(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value or "\x00" in value:
        raise GuardError("PATH_OUTSIDE_ROOT", repr(value))
    path = PurePosixPath(value)
    if path.is_absolute() or any(x in {"", ".", ".."} for x in value.split("/")):
        raise GuardError("PATH_OUTSIDE_ROOT", value)
    # Reject Windows device paths and alternate path normalization on all hosts.
    for part in path.parts:
        if part.endswith((".", " ")) or part.split(".")[0].upper() in {
            "CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(10)), *(f"LPT{i}" for i in range(10))
        }:
            raise GuardError("UNSUPPORTED_PATH", value)
    return value


def header_path(line: str, prefix: str) -> str | None:
    value = line[4:].rstrip("\r\n")
    if value == "/dev/null":
        return None
    if not value.startswith(prefix):
        raise GuardError("UNSUPPORTED_PATCH", "require a/ and b/ paths without timestamps")
    return relative_path(value[len(prefix):])


def apply_patch(text: str, originals: dict[str, bytes]) -> dict[str, bytes | None]:
    """Return file replacements without writing anything; never search for context."""
    if not isinstance(text, str) or not text or "\x00" in text:
        raise GuardError("INVALID_PATCH", "nonempty UTF-8 unified diff required")
    lines = text.splitlines(keepends=True)
    i = 0
    changes: dict[str, bytes | None] = {}
    while i < len(lines):
        if lines[i].startswith("diff --git "):
            i += 1
            if i < len(lines) and re.fullmatch(r"index [0-9a-f]+\.\.[0-9a-f]+(?: 100(?:644|755))?\r?\n?", lines[i]):
                i += 1
        if i >= len(lines) or not lines[i].startswith("--- "):
            raise GuardError("UNSUPPORTED_PATCH", "expected file header; binary/mode/rename metadata unsupported")
        old = header_path(lines[i], "a/")
        i += 1
        if i >= len(lines) or not lines[i].startswith("+++ "):
            raise GuardError("INVALID_PATCH", "missing new file header")
        new = header_path(lines[i], "b/")
        i += 1
        name = old or new
        if name is None or (old is not None and new is not None and old != new):
            raise GuardError("UNSUPPORTED_PATCH", "renames and empty file identities unsupported")
        if name in changes:
            raise GuardError("INVALID_PATCH", "duplicate file patch")
        if old is None and name in originals or old is not None and name not in originals:
            raise GuardError("PREIMAGE_MISMATCH", name)
        before = originals.get(name, b"").decode("utf-8").splitlines(keepends=True)
        output: list[str] = []
        cursor = 0
        hunks = 0
        while i < len(lines) and lines[i].startswith("@@ "):
            match = re.fullmatch(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@[^\r\n]*\r?\n?", lines[i])
            if not match:
                raise GuardError("INVALID_PATCH", "malformed hunk header")
            old_start, old_count, new_start, new_count = match.groups()
            old_count = int(old_count) if old_count is not None else 1
            new_count = int(new_count) if new_count is not None else 1
            position = int(old_start) - (1 if old_count else 0)
            if position < cursor or position > len(before):
                raise GuardError("PREIMAGE_MISMATCH", "overlapping/out-of-range hunk")
            output.extend(before[cursor:position])
            if len(output) != int(new_start) - (1 if new_count else 0):
                raise GuardError("INVALID_PATCH", "new hunk position inconsistent")
            cursor = position
            i += 1
            entries: list[tuple[str, str]] = []
            consumed_old = consumed_new = 0
            while i < len(lines):
                line = lines[i]
                if line.rstrip("\r\n") == "\\ No newline at end of file":
                    if not entries or not entries[-1][1].endswith("\n"):
                        raise GuardError("INVALID_PATCH", "misplaced no-newline marker")
                    tag, content = entries[-1]
                    entries[-1] = (tag, content.removesuffix("\n").removesuffix("\r"))
                elif consumed_old == old_count and consumed_new == new_count:
                    break
                elif line and line[0] in " +-":
                    entries.append((line[0], line[1:]))
                    consumed_old += line[0] != "+"
                    consumed_new += line[0] != "-"
                    if consumed_old > old_count or consumed_new > new_count:
                        raise GuardError("INVALID_PATCH", "hunk count overflow")
                else:
                    raise GuardError("INVALID_PATCH", "invalid hunk line")
                i += 1
            if sum(tag != "+" for tag, _ in entries) != old_count or sum(tag != "-" for tag, _ in entries) != new_count:
                raise GuardError("INVALID_PATCH", "hunk count mismatch")
            for tag, content in entries:
                if tag != "+":
                    if cursor >= len(before) or before[cursor] != content:
                        raise GuardError("PREIMAGE_MISMATCH", f"{name}:{cursor + 1}: exact context required")
                    cursor += 1
                if tag != "-":
                    output.append(content)
            hunks += 1
        if not hunks:
            raise GuardError("INVALID_PATCH", "at least one hunk required")
        output.extend(before[cursor:])
        if new is None and output:
            raise GuardError("INVALID_PATCH", "deletion must remove all content")
        changes[name] = None if new is None else "".join(output).encode("utf-8")
    return changes
