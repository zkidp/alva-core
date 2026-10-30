"""Post-run fix: Linux owner for one SSH launch, including pre-readiness failure.

No PID-list kills. A private cancellation endpoint owns pidfds for its exact
child and PID-namespace init. Init exit destroys even setsid/nested descendants.
"""
import argparse
import ctypes
import json
import os
from pathlib import Path
import re
import select
import shutil
import signal
import socket
import subprocess
import sys
import time
from contextlib import contextmanager


def write(path, value):
    temporary = path.with_name(path.name + ".tmp-" + str(os.getpid()))
    temporary.write_text(json.dumps(value))
    temporary.replace(path)


@contextmanager
def locked(state, instance, timeout=2):
    import fcntl
    if not re.fullmatch(r"[0-9a-f]{32}", instance):
        raise ValueError("Invalid startup instance")
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    if state.is_symlink():
        raise ValueError("Symlink startup state")
    with (state / "lock").open("a") as stream:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("STARTUP_OWNER_LOCK_TIMEOUT")
                time.sleep(.02)
        try:
            marker = state / "instance"
            if marker.exists() and marker.read_text() != instance:
                raise ValueError("Startup identity mismatch")
            marker.write_text(instance)
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def identity(pid):
    stat = Path("/proc", str(pid), "stat").read_text().rsplit(") ", 1)[1].split()
    return {"pid": pid, "start_ticks": stat[19],
            "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip()}


def exited(fd, seconds=0):
    return bool(select.select([fd], [], [], seconds)[0])


def child(report, gate, command):
    if os.getpid() != 1:
        raise RuntimeError("SERVICE_REQUIRES_OWN_PID_NAMESPACE")
    # /proc is the parent's procfs, giving a host PID for an atomic pidfd open.
    host_pid = int(os.readlink("/proc/self"))
    os.write(report, (json.dumps(identity(host_pid)) + "\n").encode())
    os.close(report)
    allowed = os.read(gate, 1) == b"G"
    os.close(gate)
    if not allowed:
        return 1
    os.execvpe(command[0], command, os.environ)


def cancel(state, instance, timeout=8):
    # A tombstone and spawn registration share a lock. Cancellation before SSH
    # ever starts prevents a delayed launcher from creating the service later.
    with locked(state, instance):
        (state / "cancelled").touch()
        record = json.loads((state / "state.json").read_text()) if (state / "state.json").exists() else None
        if record and record.get("finished"):
            return record
        if record is None:
            return {"instance": instance, "confirmed": True, "proof": "CANCELLED_BEFORE_SPAWN"}
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(timeout)
        client.connect(record["socket"])
        client.sendall(json.dumps({"instance": instance, "action": "cancel"}).encode() + b"\n")
        with client.makefile("rb") as reader:
            result = json.loads(reader.readline(16384))
    if result.get("instance") != instance or not result.get("finished"):
        raise RuntimeError("STARTUP_CLEANUP_IDENTITY_OR_TERMINAL_MISMATCH")
    return result


def serve(state, instance, command):
    process = None
    helper_fd = init_fd = None
    init = None
    gate_write = report_read = None
    released = False
    claimed = bound = False
    stop = []
    scratch = state / "scratch"
    address = "/tmp/alva-p36-owner-" + instance + ".sock"
    record = {"instance": instance, "socket": address, "finished": False}
    listener = socket.socket(socket.AF_UNIX)
    try:
        with locked(state, instance):
            if (state / "cancelled").exists():
                return 0
            if (state / "state.json").exists():
                raise RuntimeError("STARTUP_INSTANCE_ALREADY_USED")
            claimed = True
            listener.bind(address)
            bound = True
            os.chmod(address, 0o600)
            listener.listen(2)
            scratch.mkdir(mode=0o700)
            report_read, report_write = os.pipe()
            gate_read, gate_write = os.pipe()
            parent = os.getpid()
            def parent_death():
                if ctypes.CDLL(None).prctl(1, signal.SIGKILL) != 0 or os.getppid() != parent:
                    os._exit(125)
            env = dict(os.environ, TMPDIR=str(scratch.resolve()))
            try:
                process = subprocess.Popen(["unshare", "-Ur", "--pid", "--fork", "--kill-child=KILL",
                    sys.executable, str(Path(__file__).resolve()), "child", "--report", str(report_write),
                    "--gate", str(gate_read), "--", *command], stdin=subprocess.DEVNULL,
                    pass_fds=(report_write, gate_read), start_new_session=True, env=env,
                    preexec_fn=parent_death)
                helper_fd = os.pidfd_open(process.pid)
            finally:
                os.close(report_write)
                os.close(gate_read)
            record["supervisor"] = identity(os.getpid())
            record["helper"] = identity(process.pid)
            write(state / "state.json", record)
        # The service cannot execute before the exact init identity is pinned.
        if not select.select([report_read], [], [], 4)[0]:
            raise TimeoutError("NAMESPACE_INIT_HANDSHAKE_TIMEOUT")
        message = os.read(report_read, 4096)
        if not message:
            raise RuntimeError("NAMESPACE_EXIT_BEFORE_SERVICE_EXEC")
        init = json.loads(message)
        if identity(init["pid"]) != init:
            raise RuntimeError("NAMESPACE_INIT_IDENTITY_MISMATCH")
        init_fd = os.pidfd_open(init["pid"])
        if identity(init["pid"]) != init or exited(init_fd):
            raise RuntimeError("NAMESPACE_INIT_IDENTITY_CHANGED")
        record["namespace_init"] = init
        write(state / "state.json", record)
        os.write(gate_write, b"G")
        os.close(gate_write)
        gate_write = None
        released = True
        for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
            signal.signal(sig, lambda signum, frame: stop.append(signum))
        deadline = time.monotonic() + 690
        while not exited(helper_fd) and not stop and time.monotonic() < deadline:
            if select.select([listener], [], [], .1)[0]:
                connection, _ = listener.accept()
                with connection:
                    connection.settimeout(1)
                    with connection.makefile("rb") as reader:
                        request = json.loads(reader.readline(4096))
                    if request != {"instance": instance, "action": "cancel"}:
                        connection.sendall(b'{"error":"INSTANCE_MISMATCH"}\n')
                        continue
                    result = finish(state, record, process, helper_fd, init_fd, released, scratch)
                    connection.sendall(json.dumps(result).encode() + b"\n")
                    return 0 if result["confirmed"] else 1
        result = finish(state, record, process, helper_fd, init_fd, released, scratch)
        return (process.returncode or 0) if result["confirmed"] else 1
    except BaseException as exc:
        record["startup_error"] = type(exc).__name__ + ":" + str(exc)
        if process is not None:
            finish(state, record, process, helper_fd, init_fd, released, scratch)
        elif claimed:
            if scratch.exists():
                shutil.rmtree(scratch)
            record.update(finished=True, confirmed=True, proof="NO_CHILD_SPAWNED", scratch_removed=True)
            write(state / "state.json", record)
        raise
    finally:
        for fd in (gate_write, report_read, helper_fd, init_fd):
            if fd is not None:
                os.close(fd)
        listener.close()
        # Only unlink the endpoint bound by this owner, never a reused instance.
        if bound:
            Path(address).unlink(missing_ok=True)


def finish(state, record, process, helper_fd, init_fd, released, scratch):
    if record.get("finished"):
        return record
    errors = []
    def kill(fd):
        if fd is not None and not exited(fd):
            try:
                signal.pidfd_send_signal(fd, signal.SIGKILL)
            except ProcessLookupError:
                pass
    try:
        # Killing namespace init tears down all descendants, including children
        # that P22/P23 deliberately put into separate process groups/sessions.
        kill(init_fd)
        if init_fd is not None and not exited(init_fd, 4):
            raise TimeoutError("NAMESPACE_INIT_EXIT_UNCONFIRMED")
        kill(helper_fd)
        process.wait(timeout=2)
        if released and init_fd is None:
            raise RuntimeError("MISSING_NAMESPACE_INIT_PIDFD")
        if scratch.is_symlink() or scratch.resolve().parent != state.resolve():
            raise RuntimeError("UNSAFE_OWNED_SCRATCH_PATH")
        if scratch.exists():
            shutil.rmtree(scratch)
    except BaseException as exc:
        errors.append(type(exc).__name__ + ":" + str(exc))
    record.update(finished=True, confirmed=not errors, cleanup_errors=errors,
                  proof="PIDFD_NAMESPACE_INIT_EXIT_AND_HELPER_REAPED" if released else "PRE_EXEC_GATE_NOT_RELEASED",
                  scratch_removed=not scratch.exists(), helper_returncode=process.returncode)
    write(state / "state.json", record)
    return record


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("serve", "cancel", "child"))
    p.add_argument("--state", type=Path)
    p.add_argument("--instance")
    p.add_argument("--report", type=int)
    p.add_argument("--gate", type=int)
    a, remaining = p.parse_known_args()
    command = remaining[1:] if remaining[:1] == ["--"] else remaining
    if a.mode == "child":
        raise SystemExit(child(a.report, a.gate, command))
    if a.mode == "cancel":
        print(json.dumps(cancel(a.state, a.instance)))
    else:
        raise SystemExit(serve(a.state, a.instance, command))
