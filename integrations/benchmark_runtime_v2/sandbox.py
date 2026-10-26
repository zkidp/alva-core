"""Linux namespace backend for prospective untrusted candidate checks/builds.

No Windows/unsandboxed fallback. Callers are trusted hosts, not model tools.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

from .freeze import relative


class Unsupported(RuntimeError):
    pass


@dataclass(frozen=True)
class SDK:
    """Host-approved public runtime only, never an entire checkout/home/CARGO_HOME."""
    alva: Path
    rust_toolchain: Path
    registry: Path


class LinuxSandbox:
    def __init__(self, sdk: SDK | None = None, wall_seconds: float = 120,
                 output_limit: int = 131072):
        if sys.platform != "linux":
            raise Unsupported("UNSUPPORTED_PLATFORM: no native Windows/macOS execution backend; no fallback")
        self.bwrap = shutil.which("bwrap")
        if not self.bwrap:
            raise Unsupported("BWRAP_UNAVAILABLE: no fallback")
        self.prlimit = shutil.which("prlimit")
        if not self.prlimit:
            raise Unsupported("PRLIMIT_UNAVAILABLE: no fallback")
        if wall_seconds <= 0 or output_limit <= 0:
            raise ValueError("Positive limits required")
        self.sdk, self.wall_seconds, self.output_limit = sdk, wall_seconds, output_limit
        self.launch_env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "LANG": "C"}
        if sdk:
            if not sdk.alva.is_file() or not (sdk.rust_toolchain / "bin/rustc").is_file() or not sdk.registry.is_dir():
                raise Unsupported("SDK_UNAVAILABLE")
        # A real namespace creation probe, not a configuration-only assertion.
        probe = subprocess.run(self._base() + ["--", "/usr/bin/true"], stdin=subprocess.DEVNULL,
                               capture_output=True, timeout=15, env=self.launch_env)
        if probe.returncode:
            raise Unsupported("NAMESPACE_SETUP_FAILED: " + probe.stderr.decode(errors="replace")[:500])

    def _base(self) -> list[str]:
        args = [self.bwrap, "--unshare-all", "--die-with-parent", "--new-session", "--cap-drop", "ALL",
                "--ro-bind", "/usr/bin", "/usr/bin", "--ro-bind", "/usr/lib", "/usr/lib",
                "--symlink", "usr/bin", "/bin", "--symlink", "usr/lib", "/lib"]
        for name in ("/usr/lib64", "/usr/include", "/usr/libexec"):
            if Path(name).exists():
                args += ["--ro-bind", name, name]
        if Path("/usr/lib64").exists():
            args += ["--symlink", "usr/lib64", "/lib64"]
        # Debian compiler aliases point through /etc/alternatives. Recreate
        # only public executable links; never bind the host /etc tree.
        for alias in ("cc", "c++"):
            path = Path("/usr/bin") / alias
            if path.is_file() and str(path.resolve()).startswith("/usr/bin/"):
                args += ["--symlink", str(path.resolve()), "/etc/alternatives/" + alias]
        args += ["--proc", "/proc", "--remount-ro", "/proc", "--dev", "/dev",
                 "--tmpfs", "/tmp", "--clearenv", "--setenv", "PATH", "/sdk/toolchain/bin:/usr/bin:/bin",
                 "--setenv", "HOME", "/tmp", "--setenv", "TMPDIR", "/tmp",
                 "--setenv", "CARGO_HOME", "/work/cargo", "--setenv", "CARGO_TARGET_DIR", "/work/target",
                 "--setenv", "CARGO_NET_OFFLINE", "true", "--setenv", "PYTHONDONTWRITEBYTECODE", "1"]
        return args

    def run(self, files: dict[str, bytes], argv: list[str], stdin: bytes = b"") -> dict:
        if not argv or not argv[0].startswith("/"):
            raise ValueError("Explicit sandbox executable required")
        if len(stdin) > 1024**2:
            raise ValueError("Stdin limit")
        if sum(map(len, files.values())) > 16 * 1024**2:
            raise ValueError("Input limit")
        for name, data in files.items():
            relative(name)
            if not isinstance(data, bytes):
                raise ValueError("Exact bytes required")
        with tempfile.TemporaryDirectory(prefix="alva-isolated-v2-") as name:
            root = Path(name)
            inputs, work = root / "input", root / "work"
            inputs.mkdir(); work.mkdir()
            project = work / "project"
            project.mkdir()
            for relative_name, data in files.items():
                for base in (inputs, project):
                    target = base / relative_name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
            args = self._base() + ["--ro-bind", str(inputs), "/input", "--bind", str(work), "/work"]
            if self.sdk:
                # Copy only public package registry material into disposable storage.
                # Never mount .cargo credentials/config, user home or another slot.
                cargo = work / "cargo"
                cargo.mkdir()
                if any(p.is_symlink() for p in self.sdk.registry.rglob("*")):
                    raise Unsupported("Registry symlinks unsupported; do not follow into host files")
                shutil.copytree(self.sdk.registry, cargo / "registry", symlinks=False)
                args += ["--ro-bind", str(self.sdk.alva.resolve()), "/sdk/alva",
                         "--ro-bind", str(self.sdk.rust_toolchain.resolve()), "/sdk/toolchain"]
            args += ["--chdir", "/work/project", "--remount-ro", "/", "--", *argv]
            started = time.monotonic()
            limited = [self.prlimit, "--cpu=90:90", "--as=4294967296:4294967296",
                       "--fsize=268435456:268435456", "--nofile=256:256", "--nproc=128:128", "--", *args]
            p = subprocess.Popen(limited, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 start_new_session=True, close_fds=True, env=self.launch_env)
            exceeded = threading.Event()
            streams = {}

            def read(stream, label):
                retained = bytearray(); total = 0; digest = hashlib.sha256()
                while chunk := stream.read(4096):
                    total += len(chunk); digest.update(chunk)
                    retained.extend(chunk[:max(0, self.output_limit - len(retained))])
                    if total > self.output_limit:
                        exceeded.set()
                streams[label] = {"text": retained.decode("utf-8", errors="replace"), "bytes_read": total,
                                  "sha256_read": digest.hexdigest(), "truncated": total > len(retained)}

            readers = [threading.Thread(target=read, args=(p.stdout, "stdout")),
                       threading.Thread(target=read, args=(p.stderr, "stderr"))]
            for reader in readers: reader.start()
            # Bounded stdin is ordinary input data, never a host reference file.
            def feed():
                try: p.stdin.write(stdin); p.stdin.close()
                except BrokenPipeError: pass
            feeder = threading.Thread(target=feed); feeder.start()
            reason = None
            try:
                while p.poll() is None:
                    if exceeded.is_set(): reason = "OUTPUT_LIMIT"; break
                    if time.monotonic() - started > self.wall_seconds: reason = "WALL_LIMIT"; break
                    time.sleep(.01)
            finally:
                # Also clear descendants after ordinary completion; no host retry.
                try: os.killpg(p.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                p.wait(timeout=10)
                feeder.join(timeout=5)
                for reader in readers: reader.join(timeout=5)
                if feeder.is_alive() or any(r.is_alive() for r in readers):
                    raise Unsupported("CLEANUP_UNCONFIRMED: refuse usable result")
            if exceeded.is_set():
                reason = "OUTPUT_LIMIT"
            return {"schema": "alva-execution/v2", "backend": "linux-bubblewrap-namespaces",
                    "status": "LIMIT" if reason else "EXECUTED", "exit": p.returncode, "limit": reason,
                    "elapsed_seconds": round(time.monotonic() - started, 3), **streams,
                    "writes": ["/work", "/tmp"], "network": "unshared network namespace",
                    "candidate_oracle": "not provided by execution backend"}
