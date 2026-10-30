"""Post-run tests. No model, SDK execution, historical slot or SSH credentials."""
import io
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from benchmarks.p36_mm02_native_model import pilot


class Process:
    def __init__(self, early=False, stubborn=False):
        self.returncode = 7 if early else None
        self.stubborn = stubborn
        self.terminated = self.killed = False
        self.communications = 0
        self.stdin, self.stdout, self.stderr = (io.BytesIO() for _ in range(3))

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True

    def communicate(self, timeout):
        self.communications += 1
        if self.stubborn and not self.killed:
            raise subprocess.TimeoutExpired("fake-ssh", timeout)
        self.returncode = self.returncode if self.returncode is not None else -15
        return b"", b"service failed"


class FakeRemote:
    def __init__(self, ready=False, failure=False, probe_error=False):
        self.ready, self.failure, self.probe_error = ready, failure, probe_error
        self.cancelled = []

    def path(self, path):
        return str(path)

    def put(self, path):
        pass

    def get(self, path):
        pass

    def owned_service_argv(self, *args):
        return ["fake-ssh"]

    def run(self, args, timeout=None):
        if self.probe_error:
            raise OSError("injected readiness transport exception")
        return SimpleNamespace(returncode=0 if self.ready else 1, stderr="")

    def cleanup_owned(self, state, instance):
        self.cancelled.append(instance)
        if self.failure:
            raise OSError("injected remote termination failure")
        return {"instance": instance, "confirmed": True, "proof": "FAKE_TRANSPORT_ONLY"}


class Startup(unittest.TestCase):
    def create(self, root, remote, process):
        args = SimpleNamespace(connection="unused", alva="sdk", toolchain="rust", registry="registry")
        frozen = {"task": {"bundle": {}}, "policy": {}, "docs": {}}
        with patch.object(pilot, "Remote", return_value=remote), patch.object(pilot.subprocess, "Popen", return_value=process), \
             patch.object(pilot.Slot, "READY_SECONDS", .002):
            return pilot.Slot(root, {"id": "test", "arm": "N"}, frozen, args)

    def test_normal_start_and_close(self):
        with tempfile.TemporaryDirectory() as d:
            remote, process = FakeRemote(ready=True), Process()
            slot = self.create(Path(d), remote, process)
            self.assertEqual(remote.cancelled, [])
            with patch.object(pilot.mm.Slot, "close") as graceful:
                slot.close()
            graceful.assert_called_once()
            self.assertTrue(process.communications)
            self.assertEqual(len(remote.cancelled), 1)

    def test_timeout_reclaims_ssh_after_precise_remote_cancel(self):
        with tempfile.TemporaryDirectory() as d:
            remote, process = FakeRemote(), Process(stubborn=True)
            with self.assertRaisesRegex(pilot.old.InfrastructureError, "SERVICE_READY_TIMEOUT") as caught:
                self.create(Path(d), remote, process)
            cleanup = caught.exception.startup_cleanup
            self.assertEqual(cleanup["status"], "STARTUP_CLEANUP_CONFIRMED")
            self.assertTrue(cleanup["local_ssh_reaped"])
            self.assertTrue(process.terminated and process.killed)
            self.assertTrue(process.stdout.closed and process.stderr.closed)
            self.assertEqual(len(remote.cancelled), 1)

    def test_early_exit_keeps_specific_reason_and_reaps(self):
        with tempfile.TemporaryDirectory() as d:
            process = Process(early=True)
            with self.assertRaisesRegex(pilot.old.InfrastructureError, "SERVICE_EXIT_BEFORE_READY:7:service failed") as caught:
                self.create(Path(d), FakeRemote(), process)
            self.assertEqual(caught.exception.startup_cleanup["status"], "STARTUP_CLEANUP_CONFIRMED")
            self.assertGreaterEqual(process.communications, 1)

    def test_cleanup_failure_preserves_timeout_and_fail_closed_record(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(pilot.old.InfrastructureError, "SERVICE_READY_TIMEOUT") as caught:
                self.create(Path(d), FakeRemote(failure=True), Process())
            cleanup = caught.exception.startup_cleanup
            self.assertEqual(cleanup["status"], "STARTUP_CLEANUP_UNCONFIRMED")
            self.assertIn("remote termination failure", str(cleanup["errors"]))
            record = json.loads((Path(d) / "test/startup-failure.json").read_text())
            self.assertIn("SERVICE_READY_TIMEOUT", record["startup_error"])
            self.assertEqual(record["cleanup"], cleanup)

    def test_probe_exception_and_record_write_failure_do_not_mask_original(self):
        with tempfile.TemporaryDirectory() as d:
            real_save = pilot.save
            def save(path, value):
                if path.name == "startup-failure.json":
                    raise OSError("injected record failure")
                real_save(path, value)
            with patch.object(pilot, "save", side_effect=save):
                with self.assertRaisesRegex(OSError, "readiness transport exception") as caught:
                    self.create(Path(d), FakeRemote(probe_error=True), Process())
            self.assertIn("record_error", caught.exception.startup_cleanup)


@unittest.skipUnless(sys.platform == "linux", "Real Linux process/namespace simulation only; not SSH proof")
class LinuxOwnership(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        probe = subprocess.run(["unshare", "-Ur", "--pid", "--fork", "--kill-child=KILL", "true"], capture_output=True)
        if probe.returncode:
            raise unittest.SkipTest("Linux namespace simulation unavailable: " + probe.stderr.decode())

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="p36-startup-test-")
        self.root = Path(self.temp.name)
        self.processes = []

    def tearDown(self):
        for process in self.processes:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)
        self.temp.cleanup()

    def launch(self, command):
        instance = uuid.uuid4().hex
        state = self.root / instance
        owner = Path(__file__).with_name("startup_owner.py")
        process = subprocess.Popen([sys.executable, str(owner), "serve", "--state", str(state), "--instance", instance,
                                    "--", *command], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.processes.append(process)
        return process, state, instance

    def wait_for(self, predicate):
        end = time.monotonic() + 8
        while not predicate():
            self.assertLess(time.monotonic(), end, "bounded simulated service startup")
            time.sleep(.02)

    def test_no_readiness_kills_namespace_and_setsid_child_only(self):
        from benchmarks.p36_mm02_native_model.startup_owner import cancel
        unrelated = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(60)"], start_new_session=True,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.processes.append(unrelated)
        marker = self.root / "child-pid"
        child_code = "import os,pathlib,time;pathlib.Path(" + repr(str(marker)) + ").write_text(os.readlink('/proc/self'));time.sleep(60)"
        code = "import subprocess,sys,time;subprocess.Popen([sys.executable,'-c'," + repr(child_code) + "],start_new_session=True);time.sleep(60)"
        process, state, instance = self.launch([sys.executable, "-c", code])
        self.wait_for(marker.exists)
        child_fd = os.pidfd_open(int(marker.read_text()))
        try:
            with self.assertRaises(ValueError):
                cancel(state, uuid.uuid4().hex)
            self.assertIsNone(process.poll())
            result = cancel(state, instance)
            self.assertTrue(result["confirmed"], result)
            process.communicate(timeout=5)
            self.assertTrue(select.select([child_fd], [], [], 2)[0], "setsid descendant actually exited")
            self.assertFalse((state / "scratch").exists())
            self.assertIsNone(unrelated.poll(), "other task must stay alive")
            self.assertTrue(cancel(state, instance)["confirmed"], "idempotent exact-instance cleanup")
        finally:
            os.close(child_fd)

    def test_exit_before_ready_reaps_owned_namespace(self):
        from benchmarks.p36_mm02_native_model.startup_owner import cancel
        process, state, instance = self.launch([sys.executable, "-c", "raise SystemExit(7)"])
        process.communicate(timeout=8)
        result = cancel(state, instance)
        self.assertTrue(result["confirmed"], result)
        self.assertFalse((state / "scratch").exists())

    def test_cancel_before_identity_prevents_delayed_spawn(self):
        from benchmarks.p36_mm02_native_model.startup_owner import cancel
        instance = uuid.uuid4().hex
        state = self.root / instance
        self.assertEqual(cancel(state, instance)["proof"], "CANCELLED_BEFORE_SPAWN")
        marker = self.root / "must-not-spawn"
        owner = Path(__file__).with_name("startup_owner.py")
        result = subprocess.run([sys.executable, str(owner), "serve", "--state", str(state), "--instance", instance,
                                 "--", "touch", str(marker)], capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
