"""Prospective host resource profile; original P22/P23 sources stay unchanged."""
from pathlib import Path
from integrations.benchmark_runtime_v2.sandbox import LinuxSandbox

PROFILE = {"nproc_rlimit": 512, "scope": "per-real-UID, not per-candidate process count",
           "cpu_seconds": 90, "address_space_bytes": 4294967296,
           "reason": "shared execution UID already has >128 unrelated threads"}
_installed = False


def install():
    global _installed
    if _installed:
        return
    original = LinuxSandbox.__init__
    wrapper = Path(__file__).with_name("prlimit_profile.py").resolve()
    wrapper.chmod(0o755)
    def initialized(self, *args, **kwargs):
        original(self, *args, **kwargs)
        self.prlimit = str(wrapper)
    LinuxSandbox.__init__ = initialized
    _installed = True
