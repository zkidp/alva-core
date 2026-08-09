#!/usr/bin/env python3
"""M3 incremental-build acceptance cases (B1..B11).

Graphs are described as {name: (deps_list, source_content)}. Manifests and
source files are written under ALVA_BUILD_ROOT, then workflow-like scenario
runs drive the build and the report is asserted.

Run:
  python tests/build_cases.py --exe <path-to-buildsys.exe>
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile


def write_graph(root, graph):
    manifest = os.path.join(root, "manifest")
    src = os.path.join(root, "src")
    os.makedirs(manifest, exist_ok=True)
    os.makedirs(src, exist_ok=True)
    for name, (deps, content) in graph.items():
        with open(os.path.join(manifest, name), "w", encoding="utf-8") as fh:
            fh.write(",".join(deps))
        with open(os.path.join(src, name), "w", encoding="utf-8") as fh:
            fh.write(content)


def run(exe, root, extra=None):
    env = dict(os.environ)
    env["ALVA_BUILD_ROOT"] = root
    if extra:
        env.update(extra)
    p = subprocess.run(
        [exe],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    report = {}
    for line in p.stdout.splitlines():
        if " " in line:
            k, _, v = line.partition(" ")
            report[k.strip()] = v.strip()
    return p, report


def expect_report(report, wanted, ctx):
    assert report == wanted, f"{ctx}: expected {wanted!r}, got {report!r}"
    print(f"{ctx} PASS: {report}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", required=True)
    ap.add_argument("--root", default=None)
    args = ap.parse_args()

    root = args.root or os.path.join(tempfile.gettempdir(), "alva-build-root")

    def reset():
        shutil.rmtree(root, ignore_errors=True)

    # B1 + B2: single package, first build then cache hit
    reset()
    write_graph(root, {"p": ([], "v1")})
    p, r = run(args.exe, root)
    assert p.returncode == 0, f"B1: rc={p.returncode}\n{p.stdout}\n{p.stderr}"
    expect_report(r, {"p": "BUILT"}, "B1")
    _, r = run(args.exe, root)
    expect_report(r, {"p": "CACHED"}, "B2")

    # B3: A->B->C first build, all built
    reset()
    write_graph(root, {"a": ([], "a1"), "b": (["a"], "b1"), "c": (["b"], "c1")})
    p, r = run(args.exe, root)
    assert p.returncode == 0, f"B3: rc={p.returncode}"
    assert list(r.keys()) == ["a", "b", "c"], f"B3: order {list(r.keys())}"
    expect_report(r, {"a": "BUILT", "b": "BUILT", "c": "BUILT"}, "B3")

    # B4: change leaf C -> only C rebuilds
    write_graph(root, {"a": ([], "a1"), "b": (["a"], "b1"), "c": (["b"], "c2")})
    _, r = run(args.exe, root)
    expect_report(r, {"a": "CACHED", "b": "CACHED", "c": "BUILT"}, "B4")

    # B5: change root A -> A,B,C all rebuild
    write_graph(root, {"a": ([], "a2"), "b": (["a"], "b1"), "c": (["b"], "c2")})
    _, r = run(args.exe, root)
    expect_report(r, {"a": "BUILT", "b": "BUILT", "c": "BUILT"}, "B5")

    # B6: fan-out core->util, core->api, util->app; change core -> reverse closure
    reset()
    graph6 = {
        "core": ([], "c1"),
        "util": (["core"], "u1"),
        "api": (["core"], "a1"),
        "app": (["util"], "p1"),
    }
    write_graph(root, graph6)
    p, r = run(args.exe, root)
    assert p.returncode == 0, f"B6 initial: rc={p.returncode}"
    graph6["core"] = (["core"][:0], "c2")
    write_graph(root, graph6)
    _, r = run(args.exe, root)
    expect_report(
        r, {"core": "BUILT", "util": "BUILT", "api": "BUILT", "app": "BUILT"}, "B6"
    )

    # B7: unrelated package E, change E -> only E rebuilds
    graph7 = {
        "core": ([], "c1"),
        "util": (["core"], "u1"),
        "api": (["core"], "a1"),
        "app": (["util"], "p1"),
        "e": ([], "e1"),
    }
    write_graph(root, graph7)
    _, r = run(args.exe, root)
    graph7["e"] = ([], "e2")
    write_graph(root, graph7)
    _, r = run(args.exe, root)
    expect_report(
        r,
        {"core": "CACHED", "util": "CACHED", "api": "CACHED", "app": "CACHED", "e": "BUILT"},
        "B7",
    )

    # B8: cycle rejected before build
    reset()
    write_graph(root, {"a": (["b"], "a1"), "b": (["a"], "b1")})
    p, r = run(args.exe, root)
    assert p.returncode != 0, f"B8: cycle must fail, rc={p.returncode}"
    assert "cycle detected in build graph" in p.stderr + p.stdout, (
        f"B8: expected cycle message, got {p.stdout!r} {p.stderr!r}"
    )
    out_dir = os.path.join(root, "out")
    assert not os.path.exists(out_dir) or not os.listdir(out_dir), (
        "B8: nothing may be built"
    )
    print("B8 PASS: cycle rejected before execution")

    # B9: restart preserves cache metadata (fresh process, no changes)
    reset()
    write_graph(root, {"p": ([], "v1")})
    p, r = run(args.exe, root)
    assert p.returncode == 0
    expect_report(r, {"p": "BUILT"}, "B9 seed")
    _, r = run(args.exe, root)
    expect_report(r, {"p": "CACHED"}, "B9 restart")

    # B10: crash after staged output, before promote -> no fake valid cache
    reset()
    write_graph(root, {"p": ([], "v1")})
    p, r = run(args.exe, root, {"ALVA_FAILPOINT": "wf-build-before-promote"})
    assert p.returncode == 17, f"B10 crash: rc={p.returncode}"
    out_path = os.path.join(root, "out", "p")
    assert not os.path.exists(out_path), "B10: staged output must not be promoted"
    _, r = run(args.exe, root)
    expect_report(r, {"p": "BUILT"}, "B10 recovery (no fake cache)")
    assert os.path.exists(out_path), "B10: output promoted after clean rebuild"
    print("B10 crash PASS: staged output not promoted, rebuild after restart")

    # B11: modify middle node util -> upstream CACHED, util + reverse closure rebuilt
    # Graph: core -> util -> app, util -> tool, plus unrelated e.
    # After touching util's source:
    #   core CACHED (source + dep outputs unchanged)
    #   util BUILT  (source changed)
    #   app  BUILT  (dep util output changed)
    #   tool BUILT  (dep util output changed)
    #   e    CACHED (unrelated)
    reset()
    graph11 = {
        "core": ([], "c1"),
        "util": (["core"], "u1"),
        "app": (["util"], "a1"),
        "tool": (["util"], "t1"),
        "e": ([], "e1"),
    }
    write_graph(root, graph11)
    p, r = run(args.exe, root)
    assert p.returncode == 0, f"B11 initial: rc={p.returncode}"
    assert list(r.keys()) == ["core", "e", "util", "app", "tool"], (
        f"B11: deterministic topo order {list(r.keys())}"
    )
    expect_report(
        r,
        {"core": "BUILT", "e": "BUILT", "util": "BUILT", "app": "BUILT", "tool": "BUILT"},
        "B11 initial",
    )
    core_out_before = open(os.path.join(root, "out", "core"), encoding="utf-8").read()
    e_out_before = open(os.path.join(root, "out", "e"), encoding="utf-8").read()

    graph11["util"] = (["core"], "u2")
    write_graph(root, graph11)
    _, r = run(args.exe, root)
    assert list(r.keys()) == ["core", "e", "util", "app", "tool"], (
        f"B11: order stable after invalidation {list(r.keys())}"
    )
    expect_report(
        r,
        {"core": "CACHED", "e": "CACHED", "util": "BUILT", "app": "BUILT", "tool": "BUILT"},
        "B11 after util change",
    )
    core_out_after = open(os.path.join(root, "out", "core"), encoding="utf-8").read()
    e_out_after = open(os.path.join(root, "out", "e"), encoding="utf-8").read()
    assert core_out_before == core_out_after, (
        "B11: core output hash must be unchanged (content-addressed cache)"
    )
    assert e_out_before == e_out_after, "B11: unrelated node output must be unchanged"
    print("B11 PASS: middle-node invalidation (core/e CACHED, util/app/tool BUILT)")

    print("\nALL BUILD CASES (B1-B11) PASSED")


if __name__ == "__main__":
    main()
