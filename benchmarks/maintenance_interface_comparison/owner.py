"""New-run owner adapter: coherent /proc inside the owned PID namespace.

Reuse the unchanged P36 pidfd/tombstone cleanup mechanism. Its outer unshare
must also mount a private procfs so nested bubblewrap sees its own process IDs.
No host /proc mount is changed, and no historical source is rewritten.
"""
from pathlib import Path
import runpy
import subprocess

if __name__ == "__main__":
    original = subprocess.Popen
    def launch(argv, *args, **kwargs):
        if isinstance(argv, list) and argv[:2] == ["unshare", "-Ur"] and "--pid" in argv:
            # The original owner first reports/pins the host PID using host
            # procfs. Mount private procfs ONLY after that handshake, as the
            # service command exec, preserving the pinned PID/start identity.
            index = argv.index("--")
            argv = argv[:index + 1] + ["unshare", "--mount", "--mount-proc", "--"] + argv[index + 1:]
        return original(argv, *args, **kwargs)
    subprocess.Popen = launch
    target = Path(__file__).resolve().parents[1] / "p36_mm02_native_model/startup_owner.py"
    runpy.run_path(str(target), run_name="__main__")
