"""Trusted SSH transport only; private endpoint/key live outside study archives."""
import argparse
import json
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


class Remote:
    def __init__(self, connection):
        self.connection = Path(connection).resolve()
        self.cfg = json.loads(self.connection.read_text())
        self.root = self.cfg["root"]
        self.options = ["-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes", "-o",
                        "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=10",
                        "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=2",
                        "-o", "UserKnownHostsFile=" + self.cfg["known_hosts"],
                        "-i", self.cfg["identity"]]

    def path(self, local):
        return self.root + "/" + Path(local).resolve().relative_to(ROOT).as_posix()

    def argv(self, args):
        return ["ssh", "-T", *self.options, "-p", str(self.cfg.get("port", 22)),
                self.cfg["destination"], shlex.join([str(a) for a in args])]

    def run(self, args, **kwargs):
        return subprocess.run(self.argv(args), capture_output=True, text=True,
                              encoding="utf-8", timeout=kwargs.pop("timeout", 180), **kwargs)

    def checked(self, args, **kwargs):
        result = self.run(args, **kwargs)
        if result.returncode:
            raise RuntimeError("SSH_REMOTE_FAILURE:" + result.stderr[-1500:])
        return result.stdout

    def owned_service_argv(self, state, instance, service, config):
        owner = self.root + "/benchmarks/p36_mm02_native_model/startup_owner.py"
        return self.argv(["python3", owner, "serve", "--state", state, "--instance", instance,
                          "--", "python3", service, "--role", "server", "--config", config])

    def cleanup_owned(self, state, instance):
        owner = self.root + "/benchmarks/p36_mm02_native_model/startup_owner.py"
        result = json.loads(self.checked(["python3", owner, "cancel", "--state", state,
                                          "--instance", instance], timeout=12))
        if result.get("instance") != instance or result.get("confirmed") is not True:
            raise RuntimeError("STARTUP_CLEANUP_UNCONFIRMED:" + json.dumps(result))
        return result

    def put(self, local):
        self.checked(["mkdir", "-p", str(Path(self.path(local)).parent).replace("\\", "/")])
        subprocess.run(["scp", "-q", *self.options, "-P", str(self.cfg.get("port", 22)),
                        str(Path(local).resolve()), self.cfg["destination"] + ":" + self.path(local)],
                       check=True, timeout=120)

    def get(self, local):
        Path(local).parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["scp", "-q", *self.options, "-P", str(self.cfg.get("port", 22)),
                        self.cfg["destination"] + ":" + self.path(local), str(Path(local).resolve())],
                       check=True, timeout=120)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--connection", type=Path, required=True)
    p.add_argument("--ready", required=True)
    a = p.parse_args()
    remote = Remote(a.connection)
    service = remote.root + "/benchmarks/p36_mm02_native_model/service.py"
    # Inherit only stdio transport. No credential bytes are read or serialized.
    raise SystemExit(subprocess.call(remote.argv(["python3", service, "--config", a.ready])))
