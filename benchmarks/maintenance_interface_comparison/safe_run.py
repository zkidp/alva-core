"""Future entry only; explicitly refuses MIC-01's obsolete pre-fix freeze."""
import argparse
import json
from pathlib import Path
import sys
import shutil
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks.maintenance_interface_comparison import pilot, provider_gate
from integrations.benchmark_runtime_v2.freeze import sha

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--connection", required=True, type=Path)
    p.add_argument("--codex-binary", type=Path)
    args = p.parse_args()
    frozen = json.loads((pilot.HERE / "FREEZE.json").read_text())
    name = Path(provider_gate.__file__).relative_to(ROOT).as_posix()
    if frozen["runtime_files"].get(name) != sha(Path(provider_gate.__file__).read_bytes()):
        raise SystemExit("NO_GENERATION: requires a separately authorized new freeze including provider_gate.py; MIC-01 is not reopened")
    if not args.codex_binary or sha(args.codex_binary.resolve().read_bytes()) != frozen["codex_binary_sha256"]:
        raise SystemExit("NO_GENERATION: explicitly pinned CLI binary required")
    binary = args.codex_binary.resolve()
    original_which, original_host = shutil.which, pilot.host
    def which(command, *extra, **kwargs):
        return str(binary) if command == "codex" else original_which(command, *extra, **kwargs)
    def stamped_host(slot):
        before = sha(binary.read_bytes())
        if before != frozen["codex_binary_sha256"]:
            raise RuntimeError("PINNED_CLI_CHANGED_BEFORE_SLOT")
        h, c, thread = original_host(slot)
        if Path(h.process.args[0]).resolve() != binary:
            h.close()
            raise RuntimeError("UNEXPECTED_CLI_EXECUTABLE")
        stamp = {"binary_sha256_before": before, "explicit_executable_used": True}
        pilot.save(slot.path / "cli-identity.json", stamp)
        close = h.close
        def checked_close():
            close()
            stamp["binary_sha256_after"] = sha(binary.read_bytes())
            stamp["matches"] = stamp["binary_sha256_after"] == before
            pilot.save(slot.path / "cli-identity.json", stamp)
            if not stamp["matches"]:
                raise RuntimeError("PINNED_CLI_CHANGED_DURING_SLOT")
        h.close = checked_close
        return h, c, thread
    with patch.object(pilot.old, "drive", provider_gate.guarded_drive(pilot.old.drive)), \
         patch.object(shutil, "which", which), patch.object(pilot, "host", stamped_host):
        pilot.run(args)
