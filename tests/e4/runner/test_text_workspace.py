from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from text_workspace import TextWorkspace, dispatch


class TextWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        # Keep test scratch inside the writable checkout.  The desktop
        # sandbox intentionally denies writes to the user's global TEMP.
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.root = Path(self.temp.name)
        (self.root / "src/pkg").mkdir(parents=True)
        (self.root / "src/pkg/a.alva").write_bytes(b"one\ntwo\n")
        (self.root / "src/pkg/b.alva").write_bytes(b"red\nblue\n")
        (self.root / "alva.toml").write_bytes(b"private")
        self.allowed = ("src/pkg/a.alva", "src/pkg/b.alva")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def workspace(self, require_session: bool = False) -> TextWorkspace:
        return TextWorkspace(self.root, self.allowed, require_session=require_session)

    def test_list_and_read_expose_only_allowlist(self) -> None:
        ws = self.workspace()
        self.assertEqual(ws.list_files()["result"]["files"], list(self.allowed))
        self.assertEqual(ws.list_files("src/pkg")["result"]["files"], list(self.allowed))
        self.assertEqual(ws.read_file("src/pkg/a.alva")["result"]["content"], "one\ntwo\n")
        self.assertFalse(ws.read_file("alva.toml")["ok"])

    def test_rejects_absolute_traversal_and_unregistered_paths(self) -> None:
        ws = self.workspace()
        for path in ("../x.alva", "src/../x.alva", str(self.root / "src/pkg/a.alva"),
                     "src/pkg/new.alva", "src/pkg/a.txt"):
            result = ws.read_file(path)
            self.assertEqual(result["error_code"], "E_PATH_NOT_ALLOWED", path)
            self.assertNotIn(str(self.root), result["message"])

    def test_text_arm_write_and_utf8_validation(self) -> None:
        ws = self.workspace()
        result = ws.write_file("src/pkg/a.alva", "更新\n")
        self.assertTrue(result["ok"])
        self.assertEqual((self.root / "src/pkg/a.alva").read_text(encoding="utf-8"), "更新\n")
        self.assertEqual(ws.write_file("src/pkg/a.alva", "\ud800")["error_code"], "E_INVALID_UTF8")

    def test_session_is_required_for_control_plane_arms(self) -> None:
        ws = self.workspace(require_session=True)
        self.assertEqual(ws.write_file("src/pkg/a.alva", "x\n")["error_code"], "E_NO_PATCH_SESSION")
        self.assertTrue(ws.begin_patch_session()["ok"])
        self.assertEqual(ws.begin_patch_session()["error_code"], "E_PATCH_SESSION_ACTIVE")
        self.assertTrue(ws.write_file("src/pkg/a.alva", "changed\n")["ok"])
        self.assertTrue(ws.commit_patch()["ok"])
        self.assertEqual(ws.write_file("src/pkg/a.alva", "x\n")["error_code"], "E_NO_PATCH_SESSION")

    def test_discard_restores_all_files(self) -> None:
        ws = self.workspace(require_session=True)
        ws.begin_patch_session()
        ws.write_file("src/pkg/a.alva", "changed-a\n")
        ws.write_file("src/pkg/b.alva", "changed-b\n")
        self.assertTrue(ws.discard_patch()["ok"])
        self.assertEqual((self.root / "src/pkg/a.alva").read_text(), "one\ntwo\n")
        self.assertEqual((self.root / "src/pkg/b.alva").read_text(), "red\nblue\n")

    def test_single_and_multi_file_patch(self) -> None:
        ws = self.workspace()
        diff = (
            "--- a/src/pkg/a.alva\n+++ b/src/pkg/a.alva\n"
            "@@ -1,2 +1,2 @@\n one\n-two\n+three\n"
            "--- a/src/pkg/b.alva\n+++ b/src/pkg/b.alva\n"
            "@@ -1,2 +1,2 @@\n-red\n+green\n blue\n"
        )
        result = ws.apply_patch(diff)
        self.assertTrue(result["ok"], result)
        self.assertEqual((self.root / "src/pkg/a.alva").read_text(), "one\nthree\n")
        self.assertEqual((self.root / "src/pkg/b.alva").read_text(), "green\nblue\n")

    def test_patch_preserves_crlf_style(self) -> None:
        (self.root / "src/pkg/a.alva").write_bytes(b"one\r\ntwo\r\n")
        ws = self.workspace()
        diff = "--- a/src/pkg/a.alva\n+++ b/src/pkg/a.alva\n@@ -2 +2 @@\n-two\n+three\n"
        self.assertTrue(ws.apply_patch(diff)["ok"])
        self.assertEqual((self.root / "src/pkg/a.alva").read_bytes(), b"one\r\nthree\r\n")

    def test_patch_context_mismatch_is_atomic(self) -> None:
        ws = self.workspace()
        before_a = (self.root / "src/pkg/a.alva").read_bytes()
        before_b = (self.root / "src/pkg/b.alva").read_bytes()
        diff = (
            "--- a/src/pkg/a.alva\n+++ b/src/pkg/a.alva\n"
            "@@ -1 +1 @@\n-one\n+changed\n"
            "--- a/src/pkg/b.alva\n+++ b/src/pkg/b.alva\n"
            "@@ -1 +1 @@\n-wrong\n+changed\n"
        )
        self.assertEqual(ws.apply_patch(diff)["error_code"], "E_PATCH_CONTEXT")
        self.assertEqual((self.root / "src/pkg/a.alva").read_bytes(), before_a)
        self.assertEqual((self.root / "src/pkg/b.alva").read_bytes(), before_b)

    def test_second_replace_failure_rolls_back_first(self) -> None:
        ws = self.workspace()
        original_replace = ws._replace
        calls = 0

        def fail_second(source, destination):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected")
            return original_replace(source, destination)

        diff = (
            "--- a/src/pkg/a.alva\n+++ b/src/pkg/a.alva\n@@ -1 +1 @@\n-one\n+A\n"
            "--- a/src/pkg/b.alva\n+++ b/src/pkg/b.alva\n@@ -1 +1 @@\n-red\n+B\n"
        )
        with mock.patch.object(ws, "_replace", side_effect=fail_second):
            result = ws.apply_patch(diff)
        self.assertEqual(result["error_code"], "E_ATOMIC_WRITE")
        self.assertEqual((self.root / "src/pkg/a.alva").read_text(), "one\ntwo\n")
        self.assertEqual((self.root / "src/pkg/b.alva").read_text(), "red\nblue\n")

    def test_rejects_unsupported_and_overlapping_patches(self) -> None:
        ws = self.workspace()
        bad = (
            "--- a/src/pkg/a.alva\n+++ b/src/pkg/a.alva\n"
            "@@ -1 +1 @@\n-one\n+x\n@@ -1 +1 @@\n-one\n+y\n"
        )
        self.assertEqual(ws.apply_patch(bad)["error_code"], "E_PATCH_FORMAT")
        create = "--- /dev/null\n+++ b/src/pkg/a.alva\n@@ -0,0 +1 @@\n+x\n"
        self.assertEqual(ws.apply_patch(create)["error_code"], "E_PATCH_FORMAT")

    def test_symlink_escape_is_rejected_when_supported(self) -> None:
        outside = self.root / "outside.alva"
        outside.write_text("secret\n")
        link = self.root / "src/pkg/link.alva"
        try:
            os.symlink(outside, link)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        with self.assertRaises(Exception):
            TextWorkspace(self.root, ["src/pkg/link.alva"], require_session=False)

    def test_dispatch_rejects_unknown_or_extra_arguments(self) -> None:
        ws = self.workspace()
        self.assertEqual(dispatch(ws, "unknown", {})["error_code"], "E_UNKNOWN_TOOL")
        result = dispatch(ws, "read_file", {"path": "src/pkg/a.alva", "extra": 1})
        self.assertEqual(result["error_code"], "E_ARGUMENT_BINDING")


if __name__ == "__main__":
    unittest.main()
