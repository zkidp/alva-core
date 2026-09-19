#!/usr/bin/env python3
"""End-to-end local-library dependency acceptance and rejection tests."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import shlex
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXE_SUFFIX = ".exe" if os.name == "nt" else ""


def run(command: list[str], *, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    print(f"cwd={cwd}\n$ {shlex.join(command)}", flush=True)
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=300,
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


def build_project(
    alva: Path, manifest: Path, out_dir: Path, cwd: Path, crate_name: str = "fixture_app"
) -> Path:
    check_project(alva, manifest, cwd)
    run(
        [str(alva), "project", "build", str(manifest), "--out-dir", str(out_dir)],
        cwd=cwd,
    )
    crate = out_dir / crate_name
    cargo_toml = (crate / "Cargo.toml").read_text(encoding="utf-8")
    assert 'features = ["arbitrary_precision"]' in cargo_toml
    assert "[profile.release]\noverflow-checks = true" in cargo_toml
    run(["cargo", "build", "--manifest-path", str(crate / "Cargo.toml"), "--release"], cwd=cwd)
    return crate / "target" / "release" / f"{crate_name}{EXE_SUFFIX}"


def expect_failure(alva: Path, manifest: Path, cwd: Path, *needles: str) -> None:
    output = manifest.parent / "must not generate"
    for command in ("check", "build"):
        completed = run(
            [str(alva), "project", command, str(manifest), "--out-dir", str(output)],
            cwd=cwd,
            check=False,
        )
        assert completed.returncode != 0, f"expected {command} failure for {manifest}"
        detail = completed.stdout + completed.stderr
        for needle in needles:
            assert needle.lower() in detail.lower(), f"missing {needle!r} in:\n{detail}"
        assert "panicked at" not in detail.lower(), detail
        assert not output.exists(), f"{command} generated output before rejecting {manifest}"


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
            "    (body (call concat (call left.value.left) (call right.value.right))))\n"
            '  (test diamond (body (== (call joined) (string "valuevalue")))))\n'
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

    # A user spelling can also collide with an injected std module or crate root.
    for name in ("alva_std_io", "main", "lib"):
        case = cases / f"reserved-{name}"
        write(case / "alva.toml", app_manifest('names = "library/alva.lib.toml"'))
        write(case / "src" / "main.alva", app_module(name))
        write(case / "library" / "alva.lib.toml", lib_manifest("names", f'"{name}" = "value.alva"'))
        write(case / "library" / "value.alva", library_module(name))
        expect_failure(alva, case / "alva.toml", cwd, "generated rust filename", name)

    app_conflict = cases / "app-conflict"
    write(app_conflict / "alva.toml", app_manifest('sample = "library/alva.lib.toml"'))
    write(app_conflict / "src" / "main.alva", app_module("app.main"))
    write(app_conflict / "library" / "alva.lib.toml", lib_manifest("sample", '"app.main" = "value.alva"'))
    write(app_conflict / "library" / "value.alva", library_module("app.main"))
    expect_failure(alva, app_conflict / "alva.toml", cwd, "module name conflict", "app.main")

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

    # External library bodies receive the same type/effect/capability checking.
    for label, content, needle in (
        ("type", library_module("checked.value").replace('(string "value")', '(+ (int 1) (bool true))'), "mismatch"),
        ("capability", library_module("checked.value").replace('(export value)', '(cap nonexistent)\n(export value)'), "capability"),
        ("effect", '''(module (name "checked.value") (version "0.1.0")
          (dep "alva.std.io" "0.1.0") (cap io) (export value)
          (fn value (params) (returns (prim string)) (pure)
            (body (block (call alva.std.io.write_stdout (string "x")) (string "x")))))''', "effect"),
    ):
        case = cases / f"library-{label}"
        write(case / "alva.toml", app_manifest('checked = "library/alva.lib.toml"'))
        write(case / "src" / "main.alva", library_module("app.main"))
        write(case / "library" / "alva.lib.toml", lib_manifest("checked", '"checked.value" = "value.alva"'))
        write(case / "library" / "value.alva", content)
        expect_failure(alva, case / "alva.toml", cwd, "alva.lib.toml", "checked.value", needle)

    air = cases / "air"
    manifest, _ = create_hot_fixture(air, "value")
    write(air / "application" / "alva-air" / "current", "1\ninvalid\n")
    expect_failure(alva, manifest, cwd, "authoritative air", "local library")

    for authoritative in (False, True):
        case = cases / f"edit-{authoritative}"
        edit_manifest, lib_source = create_hot_fixture(case, "value")
        before = lib_source.read_bytes()
        store = edit_manifest.parent / "alva-air"
        if authoritative:
            write(store / "current", "1\ninvalid\n")
        for command, request in (
            ("edit", {"op": "begin", "project": str(edit_manifest)}),
            ("agent", {"tool": "begin_transaction", "project": str(edit_manifest)}),
        ):
            result = subprocess.run(
                [str(alva), command], cwd=cwd, input=json.dumps(request) + "\n",
                text=True, encoding="utf-8", capture_output=True, timeout=10,
            )
            assert "local librar" in result.stdout, result.stdout + result.stderr
            assert '"ok":false' in result.stdout, result.stdout
        exported = run(
            [str(alva), "air", "export", str(edit_manifest), "--authoritative",
             "--out-dir", str(case / "no air export")], cwd=cwd, check=False,
        )
        assert exported.returncode != 0
        assert "local librar" in exported.stderr
        assert lib_source.read_bytes() == before
        assert not (case / "no air export").exists()
        if authoritative:
            assert (store / "current").read_text() == "1\ninvalid\n"
        else:
            assert not store.exists()


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
        run([str(alva), "project", "build", str(diamond), "--test", "--out-dir",
             str(temp / "diamond build")], cwd=outside_cwd)

        movable = temp / "movable root"
        manifest, _ = create_hot_fixture(movable, "before", crlf=True)
        first_movable = build_project(alva, manifest, movable / "build output", outside_cwd)
        assert run([str(first_movable)], cwd=outside_cwd).stdout == "before"
        moved = temp / "moved root with spaces"
        movable.rename(moved)
        moved_manifest = moved / "application" / "alva.toml"
        moved_binary = build_project(alva, moved_manifest, moved / "build output", outside_cwd)
        completed = run([str(moved_binary)], cwd=outside_cwd)
        assert completed.stdout == "before", completed.stdout

        hot = temp / "hot update root"
        hot_manifest, hot_source = create_hot_fixture(hot, "before")
        app_before = (hot_manifest.parent / "src" / "main.alva").read_bytes()
        hot_output = temp / "stable build output"
        first = build_project(alva, hot_manifest, hot_output, outside_cwd)
        assert run([str(first)], cwd=outside_cwd).stdout == "before"
        write(hot_source, library_module("sample.value", "after"))
        second = build_project(alva, hot_manifest, hot_output, outside_cwd)
        assert second == first
        assert run([str(second)], cwd=outside_cwd).stdout == "after"
        assert (hot_manifest.parent / "src" / "main.alva").read_bytes() == app_before
        print("EDITABLE SOURCE: before -> after; same application and output directory", flush=True)

        legacy = temp / "legacy entry order"
        legacy_manifest = write_legacy_entries(legacy)
        legacy_binary = build_project(alva, legacy_manifest, legacy / "generated", outside_cwd)
        assert run([str(legacy_binary)], cwd=outside_cwd).stdout == "last"

        rejection_tests(alva, temp, outside_cwd)

        isolated_json_acceptance(alva, temp, outside_cwd)

    print('JSON PATCH OUTPUT: {"name":"new"}')
    print("LOCAL LIBRARY DEPENDENCY TESTS PASSED")
    return 0


def write_legacy_entries(root: Path) -> Path:
    manifest = root / "alva.toml"
    write(manifest, '''[project]
name = "fixture_app"
[modules]
"z.first" = "first.alva"
"a.last" = "last.alva"
''')
    for name, value in (("z.first", "first"), ("a.last", "last")):
        text = app_module("unused.value").replace('"app.main"', f'"{name}"')
        text = text.replace('  (dep "unused.value" "0.1.0")\n', '')
        text = text.replace('(call unused.value.value)', f'(string "{value}")')
        write(root / f"{value}.alva", text)
    return manifest


def isolated_json_acceptance(alva: Path, temp: Path, cwd: Path) -> None:
    # Copy only the shared library and application sources into an isolated
    # acceptance fixture. No preparer or consumer-owned vendor directory is used.
    original_root = temp / "standalone JSON Patch"
    library = original_root / "library"
    application = original_root / "application"
    (library / "src").mkdir(parents=True)
    (application / "src").mkdir(parents=True)
    component = ROOT / "examples" / "json_patch_component"
    consumer = ROOT / "examples" / "json_patch_consumer"
    for name in ("pointer.alva", "patch.alva"):
        shutil.copyfile(component / "src" / name, library / "src" / name)
    shutil.copyfile(component / "alva.lib.toml", library / "alva.lib.toml")
    shutil.copyfile(consumer / "src" / "main.alva", application / "src" / "main.alva")
    write(application / "alva.toml", (consumer / "alva.toml").read_text(encoding="utf-8")
          .replace('../json_patch_component/alva.lib.toml', '../library/alva.lib.toml'))
    originals = {str(path.relative_to(original_root)): path.read_bytes()
                 for path in original_root.rglob('*') if path.is_file()}
    moved_root = temp / "relocated JSON Patch with spaces"
    for root in (original_root, moved_root):
        if root == moved_root:
            original_root.rename(moved_root)
        executable = build_project(
            alva, root / "application" / "alva.toml", root / "generated", cwd,
            crate_name="json_patch_consumer",
        )
        payloads = (
            ('{"doc":{"name":"old"},"patch":[{"op":"replace","path":"/name","value":"new"}]}', '{"name":"new"}'),
            ('{"doc":{"n":9007199254740993.0},"patch":[{"op":"test","path":"/n","value":9007199254740993}]}', '{"n":9007199254740993.0}'),
        )
        for payload, expected in payloads:
            completed = subprocess.run(
                [str(executable)], cwd=cwd, input=payload, text=True, encoding="utf-8",
                capture_output=True, timeout=10,
            )
            assert completed.returncode == 0, completed.stderr
            assert completed.stdout == expected, completed.stdout
            print(f"RUN {executable}\nINPUT: {payload}\nOUTPUT: {completed.stdout}", flush=True)
        for name, original in originals.items():
            assert (root / name).read_bytes() == original, f"source rewritten: {name}"
        assert not (root / "application" / "vendor").exists()
    print("ISOLATED JSON PATCH: check/build/release/run passed before and after relocation", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
