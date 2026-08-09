# Incremental Build System (M3 workload)

A third real workload written in Alva: an incremental build system that decides,
for a set of package/module nodes with dependency edges and content hashes, who
needs a rebuild, who can be cached, and stays consistent across restarts.

This is a build system, not a package manager. It deliberately does not include
registry, network download, semver solving, signing, remote cache, or sandboxed
build farms.

## What it implements

- manifest / package model (`name`, `source_hash`, `deps[]`, `build_state`,
  `output_hash`, `prev_source_hash`, `dep_outputs`)
- dependency DAG (`core -> util/api -> app`), cycle rejection before build
- deterministic topological build order
- content-based cache: source hash unchanged + dependency outputs unchanged
  -> CACHE HIT
- incremental invalidation: change B -> A cached, B/C/D rebuilt, unrelated
  nodes untouched
- persistence + restart: metadata survives, cache state known after restart
- crash-safe promote: staged temp -> fsync -> rename -> fsync_dir; a partial
  build is never promoted to a valid cache entry
- readable build report (`core CACHED / util BUILT / ...`)

## Build and run

```bash
alva project check alva.toml
alva project build alva.toml --test --out-dir <out>
```

Then drive the acceptance scenarios with the built binary:

```bash
python tests/build_cases.py --exe <out>/buildsys/target/debug/buildsys.exe
```

`build_cases.py` covers B1-B11:

| Test | Scenario | Expected |
|---|---|---|
| B1 | single package first build | built |
| B2 | rebuild without change | cache hit |
| B3 | A -> B -> C first build | A,B,C in topo order |
| B4 | change leaf C | only C rebuilds |
| B5 | change root A | A,B,C all rebuild |
| B6 | fan-out dependency | reverse dependents rebuild |
| B7 | unrelated package | unaffected / cached |
| B8 | cycle | rejected before build |
| B9 | restart | cache metadata retained |
| B10 | crash during build | no fake valid cache; rebuild after restart |
| B11 | change middle node util (core->util->app, util->tool) | core/e CACHED, util/app/tool BUILT; order deterministic; core output unchanged |

The graph-scenario tests write manifests and sources under `ALVA_BUILD_ROOT`,
then drive scenario runs and assert the build report.
