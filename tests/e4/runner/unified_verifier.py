"""One arm-blind final verification entry point for all E4 arms."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_e3_core():
    path = Path(__file__).resolve().parents[2] / "e3" / "runner" / "runner_core.py"
    spec = importlib.util.spec_from_file_location("e3_runner_core_for_e4_verify", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("E3 verifier bridge is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_final(runtime, alva, workspace, checkspec, baseline=None):
    """Prepare authoritative AIR, then call the same hidden verifier.

    Arm identity is deliberately absent from this function's verifier call.
    """
    ready = runtime.prepare_final_verifier()
    if not ready.get("ok"):
        return {"ok": False, "reason": "FINAL_STATE_NOT_READY",
                "prepare": ready, "output": ""}
    passed, output = _load_e3_core().run_verifier_arm_blind(
        str(alva), str(workspace), checkspec, baseline)
    return {"ok": bool(passed), "reason": "PASS" if passed else "FAIL",
            "output": output}

