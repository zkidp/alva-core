"""Manual, zero-model SSH integration probe; uses only pre-existing login auth.

prepare on a control SSH session; service via owner on a second SSH session;
verify on the control session after an injected no-readiness deadline. No SDK.
"""
import argparse
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time

from startup_owner import cancel, identity


def pin(expected):
    assert identity(expected["pid"]) == expected
    fd = os.pidfd_open(expected["pid"])
    assert identity(expected["pid"]) == expected
    return fd


def wait_for(path):
    end = time.monotonic() + 8
    while not path.exists():
        if time.monotonic() >= end:
            raise TimeoutError("probe service startup")
        time.sleep(.05)


def main(mode, root, instance):
    owner = Path(__file__).with_name("startup_owner.py")
    state = root / "owner"
    if mode == "prepare":
        root.mkdir(parents=True, exist_ok=False)
        process = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(600)"],
            start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        (root / "unrelated.json").write_text(json.dumps(identity(process.pid)))
        print("PROBE_PREPARED")
    elif mode == "service":
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "descendant", str(root), instance],
                                  start_new_session=True)
        (root / "init.json").write_text(json.dumps(identity(int(os.readlink("/proc/self")))))
        (Path(os.environ["TMPDIR"]) / "owned-sandbox-marker").write_text("owned test data")
        # Deliberately no readiness file, exactly the reviewed startup failure.
        time.sleep(600)
    elif mode == "descendant":
        (root / "child.json").write_text(json.dumps(identity(int(os.readlink("/proc/self")))))
        time.sleep(600)
    else:
        wait_for(root / "child.json")
        wait_for(root / "init.json")
        assert not (root / "ready.json").exists()
        # Inject a short startup observation deadline; this is not a model run.
        time.sleep(.3)
        init_fd = pin(json.loads((root / "init.json").read_text()))
        child_fd = pin(json.loads((root / "child.json").read_text()))
        unrelated_fd = pin(json.loads((root / "unrelated.json").read_text()))
        try:
            result = subprocess.run([sys.executable, str(owner), "cancel", "--state", str(state),
                "--instance", instance], capture_output=True, text=True, timeout=12)
            assert result.returncode == 0, result.stderr
            record = json.loads(result.stdout)
            assert record["instance"] == instance and record["confirmed"]
            assert select.select([init_fd], [], [], 2)[0]
            assert select.select([child_fd], [], [], 2)[0]
            assert not select.select([unrelated_fd], [], [], 0)[0]
            assert not (state / "scratch").exists()
            evidence = {"source_commit": "617330dc4cb873ec573d3cb5b8a25d2b87f6bc52",
                "startup_error_injected": "SERVICE_READY_TIMEOUT", "readiness_never_created": True,
                "remote_service_init_exited": True, "remote_setsid_descendant_exited": True,
                "other_task_alive_after_cleanup": True, "owned_scratch_removed": True,
                "owner_ack": record, "model_generation_calls": 0}
            (root / "evidence.json").write_text(json.dumps(evidence, indent=2))
            print(json.dumps(evidence))
        finally:
            # Only our own unrelated-control process is removed after proving
            # the service cleanup did not touch it; never target other jobs.
            signal.pidfd_send_signal(unrelated_fd, signal.SIGKILL)
            assert select.select([unrelated_fd], [], [], 2)[0]
            for fd in (init_fd, child_fd, unrelated_fd):
                os.close(fd)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("prepare", "service", "descendant", "verify"))
    p.add_argument("root", type=Path)
    p.add_argument("instance")
    a = p.parse_args()
    main(a.mode, a.root, a.instance)
