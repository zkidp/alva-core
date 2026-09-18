#!/usr/bin/env python3
"""End-to-end local-library dependency acceptance and rejection tests."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXE_SUFFIX = ".exe" if os.name == "nt" else ""


def run(command: list[str], *, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=180,
    )
    if check and completed.returncode != 0:
        raise AssertionError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


def write(path: Path, text: str, *, newline: str = "\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.replace("\n", newline), encoding="utf-8", newline="")


def library_module(
    name: str,
    output: str = "value",
    *,
    function: str = "value",
    export: bool = True,
) -> str:
    export_line = f"  (export {function})\n" if export else ""
    return (
        "(module\n"
        f'  (name "{name}")\n'
        '  (version "0.1.0")\n'
        f"{export_line}"
        f"  (fn {function}\n"
        "    (params)\n"
        "    (returns (prim string))\n"
        "    (pure)\n"
        f'    (body (string "{output}"))))\n'
    )


def app_module(library: str, function: str = "value") -> str:
    return (
        "(module\n"
        '  (name "app.main")\n'
        '  (version "0.1.0")\n'
        '  (dep "alva.std.io" "0.1.0")\n'
        f'  (dep "{library}" "0.1.0")\n'
        "  (cap io)\n"
        "  (export main)\n"
        "  (fn main\n"
        "    (params)\n"
        "    (returns (result (prim nil) (prim string)))\n"
        "    (eff io)\n"
        f"    (body (try (call alva.std.io.write_stdout (call {library}.{function}))\n"
        "      (catch e (raise (ref e)))))))\n"
    )


def app_manifest(dependencies: str, modules: str = '"app.main" = "src/main.alva"') -> str:
    return (
        "[project]\nname = \"fixture_app\"\n\n"
        f"[modules]\n{modules}\n\n"
        f"[dependencies]\n{dependencies}\n"
    )


def lib_manifest(name: str, modules: str, dependencies: str = "") -> str:
    text = f'[library]\nname = "{name}"\n\n[modules]\n{modules}\n'
    if dependencies:
        text += f"\n[dependencies]\n{dependencies}\n"
    return text


def check_project(alva: Path, manifest: Path, cwd: Path) -> subprocess.CompletedProcess[str]:
    return run([str(alva), "project", "check", str(manifest)], cwd=cwd)


def build_project(alva: Path, manifest: Path, out_dir: Path, cwd: Path) -> Path:
    run(
        [str(alva), "project", "build", str(manifest), "--out-dir", str(out_dir)],
        cwd=cwd,
    )
    crate = out_dir / "fixture_app"
    cargo_toml = (crate / "Cargo.toml").read_text(encoding="utf-8")
    assert 'features = ["arbitrary_precision"]' in cargo_toml
    assert "[profile.release]\noverflow-checks = true" in cargo_toml
    run(["cargo", "build", "--manifest-path", str(crate / "Cargo.toml"), "--release"], cwd=cwd)
    return crate / "target" / "release" / f"fixture_app{EXE_SUFFIX}"


def expect_failure(alva: Path, manifest: Path, cwd: Path, *needles: str) -> None:
    completed = run(
        [str(alva), "project", "check", str(manifest)],
        cwd=cwd,
        check=False,
    )
    assert completed.returncode != 0, f"expected failure for {manifest}"
    detail = completed.stdout + completed.stderr
    for needle in needles:
        assert needle.lower() in detail.lower(), f"missing {needle!r} in:\n{detail}"
    assert "panicked at" not in detail.lower(), detail


def create_hot_fixture(root: Path, value: str, *, crlf: bool = False) -> tuple[Path, Path]:
    library = root / "library"
    application = root / "application"
    write(
        library / "alva.lib.toml",
        lib_manifest("sample", '"sample.value" = "src/value.alva"'),
    )
    write(
        library / "src" / "value.alva",
        library_module("sample.value", value),
        newline="\r\n" if crlf else "\n",
    )
    write(application / "alva.toml", app_manifest('sample = "../library/alva.lib.toml"'))
    write(application / "src" / "main.alva", app_module("sample.value"))
    return application / "alva.toml", library / "src" / "value.alva"


def create_diamond_fixture(root: Path) -> Path:
    common = root / "common"
    left = root / "left"
    right = root / "right"
    app = root / "application"
    write(common / "alva.lib.toml", lib_manifest("common", '"common.value" = "src/value.alva"'))
    write(common / "src" / "value.alva", library_module("common.value"))
    for name, directory in (("left", left), ("right", right)):
        write(
            directory / "alva.lib.toml",
            lib_manifest(
                name,
                f'"{name}.value" = "src/value.alva"',
                'common = "../common/alva.lib.toml"',
            ),
        )
        write(
            directory / "src" / "value.alva",
            (
                "(module\n"
                f'  (name "{name}.value")\n'
                '  (version "0.1.0")\n'
                '  (dep "common.value" "0.1.0")\n'
                f"  (export {name})\n"
                f"  (fn {name} (params) (returns (prim string)) (pure)\n"
                "    (body (call common.value.value))))\n"
            ),
        )
    write(
        app / "alva.toml",
        app_manifest('left = "../left/alva.lib.toml"\nright = "../right/alva.lib.toml"'),
    )
    write(
        app / "src" / "main.alva",
        (
            "(module\n"
            '  (name "app.main")\n'
            '  (version "0.1.0")\n'
            '  (dep "left.value" "0.1.0")\n'
            '  (dep "right.value" "0.1.0")\n'
            "  (export joined)\n"
            "  (fn joined (params) (returns (prim string)) (pure)\n"
            "    (body (call concat (call left.value.left) (call right.value.right)))))\n"
        ),
    )
    return app / "alva.toml"


def rejection_tests(alva: Path, root: Path, cwd: Path) -> None:
    cases = root / "reject"

    missing_lib = cases / "missing-library"
    write(missing_lib / "alva.toml", app_manifest('missing = "../absent/alva.lib.toml"'))
    write(missing_lib / "src" / "main.alva", app_module("missing.value"))
    expect_failure(alva, missing_lib / "alva.toml", cwd, "dependency 'missing'", "cannot resolve")

    missing_module = cases / "missing-module"
    write(missing_module / "alva.toml", app_manifest('broken = "library/alva.lib.toml"'))
    write(missing_module / "src" / "main.alva", app_module("broken.value"))
    write(missing_module / "library" / "alva.lib.toml", lib_manifest("broken", '"broken.value" = "src/nope.alva"'))
    expect_failure(alva, missing_module / "alva.toml", cwd, "broken.value", "nope.alva")

    wrong_type = cases / "wrong-type"
    write(wrong_type / "alva.toml", app_manifest('wrong = "library/alva.lib.toml"'))
    write(wrong_type / "src" / "main.alva", app_module("wrong.value"))
    write(wrong_type / "library" / "alva.lib.toml", '[project]\nname = "wrong"\n\n[modules]\n"wrong.value" = "value.alva"\n')
    expect_failure(alva, wrong_type / "alva.toml", cwd, "application manifest", "expected [library]")

    bad_field = cases / "bad-field"
    write(bad_field / "alva.toml", '[project]\nname = "bad"\n\n[modules]\n"app.main" = ["src/main.alva"]\n')
    expect_failure(alva, bad_field / "alva.toml", cwd, "invalid toml", "expected a string")

    duplicate = cases / "duplicate"
    write(duplicate / "alva.toml", '[project]\nname = "one"\nname = "two"\n\n[modules]\n"app.main" = "src/main.alva"\n')
    expect_failure(alva, duplicate / "alva.toml", cwd, "invalid toml", "duplicate")

    remote = cases / "remote"
    write(remote / "alva.toml", app_manifest('remote = "https://example.invalid/lib.toml"'))
    write(remote / "src" / "main.alva", app_module("remote.value"))
    expect_failure(alva, remote / "alva.toml", cwd, "only local filesystem")

    mismatch = cases / "mismatch"
    write(mismatch / "alva.toml", app_manifest('sample = "library/alva.lib.toml"'))
    write(mismatch / "src" / "main.alva", app_module("sample.value"))
    write(mismatch / "library" / "alva.lib.toml", lib_manifest("sample", '"sample.value" = "value.alva"'))
    write(mismatch / "library" / "value.alva", library_module("other.value"))
    expect_failure(alva, mismatch / "alva.toml", cwd, "sample.value", "declares module 'other.value'")

    cycle = cases / "cycle"
    write(cycle / "alva.toml", app_manifest('a = "a/alva.lib.toml"'))
    write(cycle / "src" / "main.alva", app_module("a.value"))
    for name, other in (("a", "b"), ("b", "a")):
        write(
            cycle / name / "alva.lib.toml",
            lib_manifest(name, f'"{name}.value" = "value.alva"', f'{other} = "../{other}/alva.lib.toml"'),
        )
        write(cycle / name / "value.alva", library_module(f"{name}.value"))
    expect_failure(alva, cycle / "alva.toml", cwd, "cyclic library dependency", "a", "b")

    conflict = cases / "module-conflict"
    write(conflict / "alva.toml", app_manifest('one = "one/alva.lib.toml"\ntwo = "two/alva.lib.toml"'))
    write(conflict / "src" / "main.alva", app_module("dupe.value"))
    for name in ("one", "two"):
        write(conflict / name / "alva.lib.toml", lib_manifest(name, '"dupe.value" = "value.alva"'))
        write(conflict / name / "value.alva", library_module("dupe.value"))
    expect_failure(alva, conflict / "alva.toml", cwd, "module name conflict", "one", "two")

    std = cases / "std"
    write(std / "alva.toml", app_manifest('bad = "library/alva.lib.toml"'))
    write(std / "src" / "main.alva", app_module("alva.std.fake"))
    write(std / "library" / "alva.lib.toml", lib_manifest("bad", '"alva.std.fake" = "fake.alva"'))
    write(std / "library" / "fake.alva", library_module("alva.std.fake"))
    expect_failure(alva, std / "alva.toml", cwd, "compiler-managed", "alva.std.fake")

    filename = cases / "filename"
    write(filename / "alva.toml", app_manifest('names = "library/alva.lib.toml"'))
    write(filename / "src" / "main.alva", app_module("a.b"))
    write(filename / "library" / "alva.lib.toml", lib_manifest("names", '"a.b" = "a.alva"\n"a_b" = "b.alva"'))
    write(filename / "library" / "a.alva", library_module("a.b"))
    write(filename / "library" / "b.alva", library_module("a_b"))
    expect_failure(alva, filename / "alva.toml", cwd, "generated rust filename conflict", "a_b.rs")

    library_main = cases / "library-main"
    write(library_main / "alva.toml", app_manifest('bad = "library/alva.lib.toml"'))
    write(library_main / "src" / "main.alva", app_module("bad.value"))
    write(library_main / "library" / "alva.lib.toml", lib_manifest("bad", '"bad.value" = "value.alva"'))
    write(library_main / "library" / "value.alva", library_module("bad.value") + "\n")
    source = (library_main / "library" / "value.alva").read_text(encoding="utf-8").replace("(fn value", "(fn main")
    write(library_main / "library" / "value.alva", source)
    expect_failure(alva, library_main / "alva.toml", cwd, "local libraries cannot define fn main")

    ambiguous = cases / "ambiguous"
    write(
        ambiguous / "alva.toml",
        app_manifest('sample = "library/alva.lib.toml"', '"app.one" = "src/one.alva"\n"app.two" = "src/two.alva"'),
    )
    write(ambiguous / "src" / "one.alva", app_module("sample.value").replace('"app.main"', '"app.one"'))
    write(ambiguous / "src" / "two.alva", app_module("sample.value").replace('"app.main"', '"app.two"'))
    write(ambiguous / "library" / "alva.lib.toml", lib_manifest("sample", '"sample.value" = "value.alva"'))
    write(ambiguous / "library" / "value.alva", library_module("sample.value"))
    expect_failure(alva, ambiguous / "alva.toml", cwd, "ambiguous application entry point", "app.one", "app.two")

    private = cases / "private"
    write(private / "alva.toml", app_manifest('private = "library/alva.lib.toml"'))
    write(private / "src" / "main.alva", app_module("private.value", "secret"))
    write(private / "library" / "alva.lib.toml", lib_manifest("private", '"private.value" = "value.alva"'))
    write(
        private / "library" / "value.alva",
        library_module("private.value", "secret", function="secret", export=False),
    )
    expect_failure(alva, private / "alva.toml", cwd, "must be declared", "private.value.secret")

    air = cases / "air"
    manifest, _ = create_hot_fixture(air, "value")
    write(air / "application" / "alva-air" / "current", "1\ninvalid\n")
    expect_failure(alva, manifest, cwd, "authoritative air", "local library")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--alva",
        type=Path,
        default=ROOT / "alva" / "target" / "debug" / f"alva{EXE_SUFFIX}",
    )
    args = parser.parse_args()
    alva = args.alva.resolve()
    assert alva.exists(), f"compiler not found: {alva}"

    with tempfile.TemporaryDirectory(prefix="alva local dependencies ") as temp_text:
        temp = Path(temp_text)
        outside_cwd = temp / "unrelated cwd"
        outside_cwd.mkdir()

        diamond = create_diamond_fixture(temp / "diamond root")
        result = check_project(alva, diamond, outside_cwd)
        assert "4 modules checked" in result.stdout, result.stdout

        movable = temp / "movable root"
        manifest, _ = create_hot_fixture(movable, "before", crlf=True)
        check_project(alva, manifest, outside_cwd)
        moved = temp / "moved root with spaces"
        movable.rename(moved)
        moved_manifest = moved / "application" / "alva.toml"
        moved_binary = build_project(alva, moved_manifest, moved / "build output", outside_cwd)
        completed = run([str(moved_binary)], cwd=outside_cwd)
        assert completed.stdout == "before", completed.stdout

        hot = temp / "hot update root"
        hot_manifest, hot_source = create_hot_fixture(hot, "before")
        hot_output = temp / "stable build output"
        first = build_project(alva, hot_manifest, hot_output, outside_cwd)
        assert run([str(first)], cwd=outside_cwd).stdout == "before"
        write(hot_source, library_module("sample.value", "after"))
        second = build_project(alva, hot_manifest, hot_output, outside_cwd)
        assert second == first
        assert run([str(second)], cwd=outside_cwd).stdout == "after"

        rejection_tests(alva, temp, outside_cwd)

        json_manifest = ROOT / "examples" / "json_patch_consumer" / "alva.toml"
        check_project(alva, json_manifest, outside_cwd)
        json_out = temp / "json patch build"
        run(
            [
                str(alva),
                "project",
                "build",
                str(json_manifest),
                "--out-dir",
                str(json_out),
            ],
            cwd=outside_cwd,
        )
        json_crate = json_out / "json_patch_consumer"
        generated_manifest = (json_crate / "Cargo.toml").read_text(encoding="utf-8")
        assert 'features = ["arbitrary_precision"]' in generated_manifest
        assert "[profile.release]\noverflow-checks = true" in generated_manifest
        run(
            ["cargo", "build", "--manifest-path", str(json_crate / "Cargo.toml"), "--release"],
            cwd=outside_cwd,
        )
        json_binary = json_crate / "target" / "release" / f"json_patch_consumer{EXE_SUFFIX}"
        request = json.dumps(
            {
                "doc": {"name": "old"},
                "patch": [{"op": "replace", "path": "/name", "value": "new"}],
            },
            separators=(",", ":"),
        )
        completed = subprocess.run(
            [str(json_binary)],
            cwd=outside_cwd,
            input=request,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
        assert completed.returncode == 0, completed.stderr
        assert json.loads(completed.stdout) == {"name": "new"}, completed.stdout

    print('JSON PATCH OUTPUT: {"name":"new"}')
    print("LOCAL LIBRARY DEPENDENCY TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
