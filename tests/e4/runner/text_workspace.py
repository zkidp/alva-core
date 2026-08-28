"""Fail-closed text workspace for the E4 text-facing arms.

The model-visible surface is deliberately narrower than the host workspace:
only an explicit, frozen set of existing ``src/**/*.alva`` files can be
listed, read, or changed.  All public operations return the same response
shape used by the ALVA agent protocol and never expose host paths.
"""

from __future__ import annotations

import os
import re
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable


@dataclass(frozen=True)
class _Failure(Exception):
    code: str
    safe_message: str


@dataclass(frozen=True)
class _Hunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    body: tuple[str, ...]


_HUNK = re.compile(
    r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: .*)?\n?$"
)


def _ok(result=None):
    return {"ok": True, "result": {} if result is None else result}


def _error(exc: _Failure):
    return {"ok": False, "error_code": exc.code, "message": exc.safe_message}


class TextWorkspace:
    """A pre-registered set of ALVA source files and optional transaction."""

    def __init__(
        self,
        workspace_root: str | Path,
        allowed_files: Iterable[str],
        *,
        require_session: bool,
    ) -> None:
        self._root = Path(workspace_root).resolve(strict=True)
        allowed = tuple(sorted({self._normalise_file(p) for p in allowed_files}))
        if not allowed:
            raise ValueError("allowed_files must not be empty")
        self._allowed = allowed
        self._allowed_set = frozenset(allowed)
        self._require_session = require_session
        self._snapshot: dict[str, bytes] | None = None
        for rel in self._allowed:
            path = self._validated_path(rel)
            if not path.is_file():
                raise ValueError(f"pre-registered file is not regular: {rel}")
            self._decode(path.read_bytes(), rel)

    @staticmethod
    def _normalise_file(raw: str) -> str:
        if not isinstance(raw, str) or not raw:
            raise ValueError("file path must be a non-empty string")
        value = raw.replace("\\", "/")
        path = PurePosixPath(value)
        if path.is_absolute() or ":" in path.parts[0]:
            raise ValueError("absolute file path is forbidden")
        if any(part in ("", ".", "..") for part in path.parts):
            raise ValueError("non-canonical file path is forbidden")
        if len(path.parts) < 2 or path.parts[0] != "src":
            raise ValueError("only src/ files are permitted")
        if path.suffix != ".alva":
            raise ValueError("only .alva files are permitted")
        return path.as_posix()

    @staticmethod
    def _normalise_directory(raw: str) -> str:
        if raw in ("", "."):
            return "."
        if not isinstance(raw, str):
            raise _Failure("E_PATH_NOT_ALLOWED", "path is not allowed")
        value = raw.replace("\\", "/").rstrip("/")
        path = PurePosixPath(value)
        if path.is_absolute() or not path.parts or ":" in path.parts[0]:
            raise _Failure("E_PATH_NOT_ALLOWED", "path is not allowed")
        if any(part in ("", ".", "..") for part in path.parts):
            raise _Failure("E_PATH_NOT_ALLOWED", "path is not allowed")
        if path.parts[0] != "src":
            raise _Failure("E_PATH_NOT_ALLOWED", "path is not allowed")
        return path.as_posix()

    @staticmethod
    def _decode(data: bytes, rel: str) -> str:
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"pre-registered file is not UTF-8: {rel}") from exc

    @staticmethod
    def _has_reparse_point(path: Path) -> bool:
        try:
            info = path.lstat()
        except OSError:
            return False
        attrs = getattr(info, "st_file_attributes", 0)
        marker = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        return path.is_symlink() or bool(attrs & marker)

    def _validated_path(self, rel: str) -> Path:
        if rel not in self._allowed_set:
            raise _Failure("E_PATH_NOT_ALLOWED", "path is not allowed")
        candidate = self._root.joinpath(*PurePosixPath(rel).parts)
        current = self._root
        for part in PurePosixPath(rel).parts:
            current = current / part
            if self._has_reparse_point(current):
                raise _Failure("E_PATH_NOT_ALLOWED", "path is not allowed")
        try:
            resolved = candidate.resolve(strict=True)
        except OSError as exc:
            raise _Failure("E_PATH_NOT_ALLOWED", "path is not allowed") from exc
        try:
            resolved.relative_to(self._root)
        except ValueError as exc:
            raise _Failure("E_PATH_NOT_ALLOWED", "path is not allowed") from exc
        return resolved

    def _ensure_write_authorised(self) -> None:
        if self._require_session and self._snapshot is None:
            raise _Failure("E_NO_PATCH_SESSION", "begin_patch_session is required")

    def _read_bytes(self, rel: str) -> bytes:
        try:
            return self._validated_path(rel).read_bytes()
        except _Failure:
            raise
        except OSError as exc:
            raise _Failure("E_IO", "file operation failed") from exc

    def _replace(self, source: str, destination: Path) -> None:
        os.replace(source, destination)

    def _stage(self, rel: str, data: bytes) -> tuple[str, Path]:
        path = self._validated_path(rel)
        try:
            fd, temp_path = tempfile.mkstemp(prefix=".e4-stage-", dir=path.parent)
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            return temp_path, path
        except OSError as exc:
            raise _Failure("E_IO", "file operation failed") from exc

    def _atomic_replace_many(self, changes: dict[str, bytes]) -> None:
        originals = {rel: self._read_bytes(rel) for rel in changes}
        staged: dict[str, tuple[str, Path]] = {}
        replaced: list[str] = []
        try:
            for rel, data in changes.items():
                staged[rel] = self._stage(rel, data)
            for rel in changes:
                temp_path, destination = staged[rel]
                self._replace(temp_path, destination)
                replaced.append(rel)
        except (OSError, _Failure) as exc:
            rollback_failed = False
            for rel in reversed(replaced):
                try:
                    temp_path, destination = self._stage(rel, originals[rel])
                    self._replace(temp_path, destination)
                except (OSError, _Failure):
                    rollback_failed = True
            code = "E_ATOMIC_ROLLBACK" if rollback_failed else "E_ATOMIC_WRITE"
            raise _Failure(code, "atomic file operation failed") from exc
        finally:
            for temp_path, _ in staged.values():
                try:
                    os.unlink(temp_path)
                except FileNotFoundError:
                    pass
                except OSError:
                    pass

    @staticmethod
    def _header_path(line: str, expected_prefix: str) -> str:
        value = line[4:].rstrip("\r\n").split("\t", 1)[0]
        if value == "/dev/null" or not value.startswith(expected_prefix):
            raise _Failure("E_PATCH_FORMAT", "patch format is not supported")
        return value[len(expected_prefix):]

    def _parse_patch(self, patch: str) -> dict[str, tuple[_Hunk, ...]]:
        if not isinstance(patch, str) or not patch:
            raise _Failure("E_PATCH_FORMAT", "patch format is not supported")
        if "\\ No newline at end of file" in patch or "GIT binary patch" in patch:
            raise _Failure("E_PATCH_FORMAT", "patch format is not supported")
        lines = patch.splitlines(keepends=True)
        result: dict[str, tuple[_Hunk, ...]] = {}
        index = 0
        while index < len(lines):
            if not lines[index].startswith("--- "):
                raise _Failure("E_PATCH_FORMAT", "patch format is not supported")
            old_rel = self._header_path(lines[index], "a/")
            index += 1
            if index >= len(lines) or not lines[index].startswith("+++ "):
                raise _Failure("E_PATCH_FORMAT", "patch format is not supported")
            new_rel = self._header_path(lines[index], "b/")
            index += 1
            try:
                old_rel = self._normalise_file(old_rel)
                new_rel = self._normalise_file(new_rel)
            except ValueError as exc:
                raise _Failure("E_PATH_NOT_ALLOWED", "path is not allowed") from exc
            if old_rel != new_rel or old_rel not in self._allowed_set or old_rel in result:
                raise _Failure("E_PATH_NOT_ALLOWED", "path is not allowed")
            hunks: list[_Hunk] = []
            prior_end = -1
            while index < len(lines) and not lines[index].startswith("--- "):
                match = _HUNK.match(lines[index])
                if match is None:
                    raise _Failure("E_PATCH_FORMAT", "patch format is not supported")
                old_start = int(match.group(1))
                old_count = int(match.group(2) or 1)
                new_start = int(match.group(3))
                new_count = int(match.group(4) or 1)
                index += 1
                body: list[str] = []
                while index < len(lines):
                    if lines[index].startswith("@@ ") or lines[index].startswith("--- "):
                        break
                    line = lines[index]
                    if not line.startswith((" ", "+", "-")) or not line.endswith(("\n", "\r")):
                        raise _Failure("E_PATCH_FORMAT", "patch format is not supported")
                    body.append(line)
                    index += 1
                consumed = sum(line[0] in " -" for line in body)
                produced = sum(line[0] in " +" for line in body)
                if consumed != old_count or produced != new_count:
                    raise _Failure("E_PATCH_FORMAT", "patch line counts do not match")
                start_index = old_start - 1 if old_count else old_start
                if start_index < 0 or start_index < prior_end:
                    raise _Failure("E_PATCH_FORMAT", "patch hunks overlap")
                prior_end = start_index + old_count
                hunks.append(_Hunk(old_start, old_count, new_start, new_count, tuple(body)))
            if not hunks:
                raise _Failure("E_PATCH_FORMAT", "patch has no hunks")
            result[old_rel] = tuple(hunks)
        return result

    @staticmethod
    def _apply_hunks(original: str, hunks: tuple[_Hunk, ...]) -> str:
        source = original.splitlines(keepends=True)
        eol = "\r\n" if any(line.endswith("\r\n") for line in source) else "\n"
        output: list[str] = []
        cursor = 0
        new_cursor = 0
        for hunk in hunks:
            start = hunk.old_start - 1 if hunk.old_count else hunk.old_start
            expected_new = hunk.new_start - 1 if hunk.new_count else hunk.new_start
            if start < cursor or start > len(source) or expected_new != new_cursor + (start - cursor):
                raise _Failure("E_PATCH_CONTEXT", "patch does not match current content")
            output.extend(source[cursor:start])
            new_cursor += start - cursor
            cursor = start
            for line in hunk.body:
                marker, payload = line[0], line[1:]
                if marker in (" ", "-"):
                    source_text = source[cursor].rstrip("\r\n") if cursor < len(source) else None
                    payload_text = payload.rstrip("\r\n")
                    if cursor >= len(source) or source_text != payload_text:
                        raise _Failure("E_PATCH_CONTEXT", "patch does not match current content")
                    if marker == " ":
                        output.append(source[cursor])
                        new_cursor += 1
                    cursor += 1
                else:
                    output.append(payload.rstrip("\r\n") + eol)
                    new_cursor += 1
        output.extend(source[cursor:])
        return "".join(output)

    def list_files(self, path: str = ".") -> dict:
        try:
            directory = self._normalise_directory(path)
            prefix = "" if directory == "." else directory + "/"
            files = [rel for rel in self._allowed if rel.startswith(prefix)]
            return _ok({"files": files})
        except _Failure as exc:
            return _error(exc)

    def read_file(self, path: str) -> dict:
        try:
            rel = self._normalise_file(path)
            content = self._decode(self._read_bytes(rel), rel)
            return _ok({"path": rel, "content": content})
        except ValueError:
            return _error(_Failure("E_PATH_NOT_ALLOWED", "path is not allowed"))
        except _Failure as exc:
            return _error(exc)

    def write_file(self, path: str, content: str) -> dict:
        try:
            self._ensure_write_authorised()
            rel = self._normalise_file(path)
            if not isinstance(content, str):
                raise _Failure("E_INVALID_UTF8", "content must be valid UTF-8 text")
            try:
                data = content.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise _Failure("E_INVALID_UTF8", "content must be valid UTF-8 text") from exc
            self._atomic_replace_many({rel: data})
            return _ok({"path": rel, "bytes_written": len(data)})
        except ValueError:
            return _error(_Failure("E_PATH_NOT_ALLOWED", "path is not allowed"))
        except _Failure as exc:
            return _error(exc)

    def apply_patch(self, diff: str) -> dict:
        try:
            self._ensure_write_authorised()
            parsed = self._parse_patch(diff)
            changes: dict[str, bytes] = {}
            for rel, hunks in parsed.items():
                original = self._decode(self._read_bytes(rel), rel)
                changes[rel] = self._apply_hunks(original, hunks).encode("utf-8")
            self._atomic_replace_many(changes)
            return _ok({"files_changed": sorted(changes)})
        except ValueError:
            return _error(_Failure("E_PATH_NOT_ALLOWED", "path is not allowed"))
        except _Failure as exc:
            return _error(exc)

    def begin_patch_session(self) -> dict:
        try:
            if self._snapshot is not None:
                raise _Failure("E_PATCH_SESSION_ACTIVE", "patch session is already active")
            self._snapshot = {rel: self._read_bytes(rel) for rel in self._allowed}
            return _ok({"files_snapshotted": len(self._snapshot)})
        except _Failure as exc:
            return _error(exc)

    def commit_patch(self) -> dict:
        if self._snapshot is None:
            return _error(_Failure("E_NO_PATCH_SESSION", "no patch session is active"))
        self._snapshot = None
        return _ok({"committed": True})

    def discard_patch(self) -> dict:
        if self._snapshot is None:
            return _error(_Failure("E_NO_PATCH_SESSION", "no patch session is active"))
        snapshot = dict(self._snapshot)
        try:
            self._atomic_replace_many(snapshot)
            self._snapshot = None
            return _ok({"discarded": True})
        except _Failure as exc:
            return _error(exc)

    def replace_from_host(self, changes: dict[str, bytes]) -> None:
        """Replace allowlisted files for a harness-owned AIR projection.

        This is intentionally not exposed by :func:`dispatch`.  It exists so
        HYBRID can materialise an already checked authoritative AIR commit
        back into the same frozen source paths before ``commit_patch``.
        """
        self._ensure_write_authorised()
        normalised: dict[str, bytes] = {}
        for raw, data in changes.items():
            try:
                rel = self._normalise_file(raw)
            except ValueError as exc:
                raise _Failure("E_PATH_NOT_ALLOWED", "path is not allowed") from exc
            if rel not in self._allowed_set or not isinstance(data, bytes):
                raise _Failure("E_PATH_NOT_ALLOWED", "path is not allowed")
            self._decode(data, rel)
            normalised[rel] = data
        if set(normalised) != set(self._allowed):
            raise _Failure("E_PROJECTION_MISMATCH", "AIR projection does not match frozen files")
        self._atomic_replace_many(normalised)


def dispatch(workspace: TextWorkspace, tool: str, arguments: dict) -> dict:
    """Dispatch only the E4 text-workspace tools with strict arguments."""
    functions: dict[str, tuple[Callable, frozenset[str]]] = {
        "list_files": (workspace.list_files, frozenset({"path"})),
        "read_file": (workspace.read_file, frozenset({"path"})),
        "write_file": (workspace.write_file, frozenset({"path", "content"})),
        "apply_patch": (workspace.apply_patch, frozenset({"diff"})),
        "begin_patch_session": (workspace.begin_patch_session, frozenset()),
        "commit_patch": (workspace.commit_patch, frozenset()),
        "discard_patch": (workspace.discard_patch, frozenset()),
    }
    entry = functions.get(tool)
    if entry is None:
        return _error(_Failure("E_UNKNOWN_TOOL", "tool is not available"))
    function, accepted = entry
    if not isinstance(arguments, dict) or not set(arguments).issubset(accepted):
        return _error(_Failure("E_ARGUMENT_BINDING", "tool arguments are invalid"))
    try:
        return function(**arguments)
    except TypeError:
        return _error(_Failure("E_ARGUMENT_BINDING", "tool arguments are invalid"))
