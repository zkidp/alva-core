#!/usr/bin/env python3
"""Build and execute real generated debug/release artifacts for this change."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ALVA_DIR = ROOT / "alva"
EXAMPLE = ROOT / "examples" / "json_component"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
EXE_SUFFIX = ".exe" if os.name == "nt" else ""


def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    if kwargs.get("check") and completed.returncode != 0:
        sys.stderr.write(completed.stdout.decode("utf-8", errors="replace"))
        sys.stderr.write(completed.stderr.decode("utf-8", errors="replace"))
        completed.check_returncode()
    return completed


def invoke(executable: Path, payload: bytes) -> subprocess.CompletedProcess[bytes]:
    return run([str(executable)], input=payload, timeout=10, check=False)


def require_failure(completed: subprocess.CompletedProcess[bytes], label: str) -> None:
    assert completed.returncode != 0, f"{label}: expected nonzero exit"
    assert completed.stdout == b"", f"{label}: failure leaked stdout: {completed.stdout!r}"
    assert completed.stderr, f"{label}: expected stderr detail"


def request(**values: Any) -> bytes:
    return json.dumps(values, separators=(",", ":")).encode("utf-8")


def load_caller() -> Any:
    source = EXAMPLE / "call_component.py"
    spec = importlib.util.spec_from_file_location("alva_json_component_caller", source)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    compiler = ALVA_DIR / "target" / "debug" / f"alva{EXE_SUFFIX}"
    run(["cargo", "build"], cwd=ALVA_DIR, check=True)
    assert compiler.exists()

    clean_env = os.environ.copy()
    clean_env.pop("RUSTFLAGS", None)
    clean_env.pop("CARGO_ENCODED_RUSTFLAGS", None)
    clean_env.pop("CARGO_PROFILE_RELEASE_OVERFLOW_CHECKS", None)

    report: dict[str, Any] = {
        "platform": sys.platform,
        "python": sys.version.split()[0],
        "rustc": run(["rustc", "--version"], check=True).stdout.decode().strip(),
        "cargo": run(["cargo", "--version"], check=True).stdout.decode().strip(),
        "build_arguments": {
            "debug": "cargo build",
            "release": "cargo build --release",
        },
        "environment_overrides_removed": [
            "RUSTFLAGS",
            "CARGO_ENCODED_RUSTFLAGS",
            "CARGO_PROFILE_RELEASE_OVERFLOW_CHECKS",
        ],
    }

    with tempfile.TemporaryDirectory(prefix="alva-release-json-") as temp_text:
        temp = Path(temp_text)
        clean_env["CARGO_TARGET_DIR"] = str(temp / "cargo-target")

        contract_results: dict[str, dict[str, int]] = {}
        for fixture in sorted(FIXTURES.glob("single_file_*_failure.alva")):
            out_dir = temp / "single-file"
            run(
                [str(compiler), "build", str(fixture), "--out-dir", str(out_dir)],
                cwd=ALVA_DIR,
                env=clean_env,
                check=True,
            )
            crate = out_dir / fixture.stem
            manifest = (crate / "Cargo.toml").read_text(encoding="utf-8")
            assert "[profile.release]\noverflow-checks = true\n" in manifest
            generated = (crate / "src" / "main.rs").read_text(encoding="utf-8")
            assert "debug_assert!" not in generated
            assert "assert!(" in generated

            run(
                [
                    str(compiler),
                    "build",
                    str(fixture),
                    "--release",
                    "--out-dir",
                    str(out_dir),
                ],
                cwd=ALVA_DIR,
                env=clean_env,
                check=True,
            )
            name = fixture.stem
            profile_results: dict[str, int] = {}
            for profile in ("debug", "release"):
                executable = temp / "cargo-target" / profile / f"{name}{EXE_SUFFIX}"
                completed = invoke(executable, b"")
                require_failure(completed, f"{name}/{profile}")
                profile_results[profile] = completed.returncode
            contract_results[name] = profile_results

        generated_root = temp / "json-generated"
        run(
            [
                str(compiler),
                "project",
                "build",
                str(EXAMPLE / "alva.toml"),
                "--out-dir",
                str(generated_root),
            ],
            cwd=ALVA_DIR,
            env=clean_env,
            check=True,
        )
        crate = generated_root / "json_component"
        manifest = (crate / "Cargo.toml").read_text(encoding="utf-8")
        assert "[profile.release]\noverflow-checks = true\n" in manifest
        run(
            ["cargo", "build", "--manifest-path", str(crate / "Cargo.toml"), "--release"],
            env=clean_env,
            check=True,
        )

        component_results: dict[str, Any] = {}
        for profile in ("debug", "release"):
            executable = temp / "cargo-target" / profile / f"json_component{EXE_SUFFIX}"
            cases = {
                "sum": (request(op="sum", values=[1, 2, 3]), {"result": 6}),
                "i64_max": (request(op="sum", values=[9223372036854775807]), {"result": 9223372036854775807}),
                "i64_min": (request(op="sum", values=[-9223372036854775808]), {"result": -9223372036854775808}),
                "above_2_pow_53": (request(op="sum", values=[9007199254740993]), {"result": 9007199254740993}),
            }
            for label, (payload, expected) in cases.items():
                completed = invoke(executable, payload)
                assert completed.returncode == 0, (label, completed.stderr)
                assert json.loads(completed.stdout) == expected
                assert completed.stdout == json.dumps(expected, separators=(",", ":")).encode()
                assert completed.stderr == b""

            expected_errors = {
                "invalid_json": b"not-json",
                "invalid_utf8": b"\xff",
                "missing_field": request(op="sum"),
                "wrong_type": request(op="sum", values="not-an-array"),
                "invalid_operation": request(op="divide", left=6, right=3),
                "range_error": b'{"op":"sum","values":[9223372036854775808]}',
                "oversized": b" " * (1048576 + 1),
            }
            for label, payload in expected_errors.items():
                require_failure(invoke(executable, payload), f"{profile}/{label}")

            overflow_inputs = {
                "add_overflow": request(op="add", left=9223372036854775807, right=1),
                "subtract_overflow": request(op="subtract", left=-9223372036854775808, right=1),
                "multiply_overflow": request(op="multiply", left=9223372036854775807, right=2),
            }
            overflow_statuses: dict[str, int] = {}
            for label, payload in overflow_inputs.items():
                completed = invoke(executable, payload)
                require_failure(completed, f"{profile}/{label}")
                overflow_statuses[label] = completed.returncode

            component_results[profile] = {"overflow_exit_statuses": overflow_statuses}

        caller = load_caller()
        release_executable = temp / "cargo-target" / "release" / f"json_component{EXE_SUFFIX}"
        assert caller.call_component(release_executable, {"op": "sum", "values": [4, 5]}) == 9
        try:
            caller.call_component(
                release_executable,
                {"op": "add", "left": 9223372036854775807, "right": 1},
            )
            raise AssertionError("caller accepted a failed process")
        except RuntimeError:
            pass
        try:
            caller.validate_completed(
                subprocess.CompletedProcess(["synthetic"], 0, b'{"result":', b"")
            )
            raise AssertionError("caller accepted truncated JSON")
        except RuntimeError:
            pass

        report["contract_failure_exit_statuses"] = contract_results
        report["component"] = component_results
        report["caller_rejected_nonzero_and_truncated"] = True
        report["generated_binary_pattern"] = str(
            temp / "cargo-target" / "<debug|release>" / f"json_component{EXE_SUFFIX}"
        )

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
