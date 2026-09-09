#!/usr/bin/env python3
"""WF-01 public-behavior acceptance; black-box subprocesses, no engine imports.

Every invocation is a restart. Assertions use reports and durable outputs, not
the implementation's hash formula or source shape. --legacy-exe optionally
supplies a real pre-WF-01 binary for compatibility acceptance.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile


def invoke(exe, root, expected=None, crash=None):
    env = dict(os.environ, ALVA_BUILD_ROOT=str(root))
    env.pop("ALVA_FAILPOINT", None)
    if crash:
        env["ALVA_FAILPOINT"] = crash
    p = subprocess.run([exe], env=env, text=True, capture_output=True, timeout=30)
    if crash:
        assert p.returncode == 17, (p.returncode, p.stdout, p.stderr)
    elif expected is not None:
        assert p.returncode == 0, (p.returncode, p.stdout, p.stderr)
        observed = dict(line.split() for line in p.stdout.splitlines() if line.strip())
        assert observed == expected, (observed, expected)
    return p


def graph(root):
    for directory in ("manifest", "src", "config"):
        (root / directory).mkdir(parents=True, exist_ok=True)
    for name, deps in {"core": "", "util": "core", "app": "util", "tool": "util", "e": ""}.items():
        (root / "manifest" / name).write_text(deps)
        (root / "src" / name).write_text(name + "-source")


def config(root, name, value):
    (root / "config" / name).write_bytes(value)


def outputs(root):
    return {p.name: p.read_bytes() for p in (root / "out").iterdir()}


def expected(*built):
    return {n: "BUILT" if n in built else "CACHED" for n in ("core", "util", "app", "tool", "e")}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", required=True)
    parser.add_argument("--legacy-exe")
    args = parser.parse_args()
    passed = []
    with tempfile.TemporaryDirectory(prefix="wf01-config-") as tmp:
        root = Path(tmp)
        graph(root)
        invoke(args.exe, root, expected("core", "util", "app", "tool", "e"))
        initial = outputs(root)
        invoke(args.exe, root, expected())
        config(root, "util", b"default")
        invoke(args.exe, root, expected())
        assert outputs(root) == initial
        passed.append("C1 default/explicit-default/restart cache")

        config(root, "util", b"release")
        invoke(args.exe, root, expected("util", "app", "tool"))
        release = outputs(root)
        assert all(release[n] != initial[n] for n in ("util", "app", "tool"))
        assert all(release[n] == initial[n] for n in ("core", "e"))
        invoke(args.exe, root, expected())
        passed.append("C2 middle config reverse-closure/output identity/restart")

        config(root, "app", b"leaf")
        invoke(args.exe, root, expected("app"))
        config(root, "e", b"unrelated")
        invoke(args.exe, root, expected("e"))
        config(root, "core", b"root")
        invoke(args.exe, root, expected("core", "util", "app", "tool"))
        passed.append("C3 leaf/unrelated/root config isolation")

        for value in (b"", b"\n", b"a\nb=c\r\n", "优化|debug".encode()):
            before = outputs(root)
            config(root, "util", value)
            invoke(args.exe, root, expected("util", "app", "tool"))
            assert outputs(root)["util"] != before["util"]
            invoke(args.exe, root, expected())
        (root / "config" / "util").unlink()
        invoke(args.exe, root, expected("util", "app", "tool"))
        invoke(args.exe, root, expected())
        passed.append("C4 exact config bytes and deletion-to-default")

        # Before promote, old output AND metadata must remain byte-identical.
        before = outputs(root)
        state = (root / "state" / "util").read_bytes()
        config(root, "util", b"crash-new")
        invoke(args.exe, root, crash="wf-build-before-promote")
        assert outputs(root) == before
        assert (root / "state" / "util").read_bytes() == state
        invoke(args.exe, root, expected("util", "app", "tool"))
        invoke(args.exe, root, expected())
        passed.append("C5 config crash before promote/retry")

        # Output has changed but metadata is old: reverting config must not
        # treat that mismatching output as an old valid cache entry.
        before = outputs(root)
        state = (root / "state" / "util").read_bytes()
        config(root, "util", b"interrupted")
        invoke(args.exe, root, crash="wf-build-after-promote")
        assert outputs(root)["util"] != before["util"]
        assert (root / "state" / "util").read_bytes() == state
        config(root, "util", b"crash-new")
        invoke(args.exe, root, expected("util"))
        assert outputs(root) == before
        invoke(args.exe, root, expected())
        passed.append("C6 post-promote crash/reverted config coherence")

        config(root, "util", b"next")
        invoke(args.exe, root, crash="wf-build-after-promote")
        invoke(args.exe, root, expected("util", "app", "tool"))
        invoke(args.exe, root, expected())
        passed.append("C7 post-promote crash/new config recovery")

        # Explicit public v2 fields are manipulated only to exercise recovery
        # from unsupported or incomplete durable metadata.
        path = root / "state" / "util"
        for mode in ("legacy", "unknown", "missing-config", "failed"):
            text = path.read_text()
            if mode == "legacy":
                text = "\n".join(x for x in text.splitlines() if not x.startswith(("format=", "config_hash="))) + "\n"
            elif mode == "unknown":
                text = text.replace("format=2", "format=999")
            elif mode == "missing-config":
                text = "\n".join(x for x in text.splitlines() if not x.startswith("config_hash=")) + "\n"
            else:
                text = text.replace("state=CACHED", "state=FAILED")
            path.write_text(text)
            invoke(args.exe, root, expected("util"))
            invoke(args.exe, root, expected())
        passed.append("C8 legacy/unknown/incomplete/failed metadata invalidation")

        (root / "manifest" / "util").write_text("core,e")
        invoke(args.exe, root, expected("util", "app", "tool"))
        (root / "manifest" / "util").write_text("core")
        invoke(args.exe, root, expected("util", "app", "tool"))
        (root / "manifest" / "core").write_text("app")
        p = invoke(args.exe, root)
        assert p.returncode != 0 and "cycle" in p.stdout + p.stderr
        (root / "manifest" / "core").write_text("")
        invoke(args.exe, root, expected())
        passed.append("C9 live dependency add/remove/cycle after restart")

        (root / "out" / "util").write_text("incomplete")
        invoke(args.exe, root, expected("util"))
        (root / "out" / "util").unlink()
        invoke(args.exe, root, expected("util"))
        passed.append("C10 missing/corrupt output cannot hit")

        (root / "config" / "util").unlink()
        (root / "config" / "util").mkdir()
        p = invoke(args.exe, root)
        assert p.returncode != 0, "configuration read errors must not default"
        passed.append("C11 config read failure is not default")

    if args.legacy_exe:
        with tempfile.TemporaryDirectory(prefix="wf01-legacy-") as tmp:
            root = Path(tmp)
            graph(root)
            invoke(args.legacy_exe, root, expected("core", "util", "app", "tool", "e"))
            invoke(args.legacy_exe, root, expected())
            invoke(args.exe, root, expected("core", "util", "app", "tool", "e"))
            invoke(args.exe, root, expected())
        passed.append("C12 real legacy binary state upgrade/restart")
    for case in passed:
        print("PASS", case)
    print(f"WF-01: {len(passed)} scenario groups PASS")


if __name__ == "__main__":
    main()
