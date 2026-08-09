# M3 - Incremental Build Graph (build system, not package manager)

## Positioning

The third real workload: **incremental build system**. It answers one question:

> Given a set of package/module nodes, dependency relations, and content
> hashes, can Alva correctly decide who needs a rebuild, who can be cached,
> and stay consistent after restart?

Explicitly out of scope: registry / network download / semver SAT solver /
lockfile ecosystem / package signing / remote cache / sandboxed builds.

## MVP capabilities (frozen)

1. **Manifest / package model**: `name`, `source_hash`, `deps[]`,
   `build_state`, `output_hash`, `prev_source_hash`
2. **Dependency DAG**: `core -> util/api -> app`
3. **Cycle rejection**: rejected before build
4. **Deterministic topological build order**: same graph, same order every run
5. **Content-based cache**: source hash unchanged + dep outputs unchanged
   -> CACHE HIT
6. **Incremental invalidation**: change B -> A cached, B/C/D rebuilt,
   unrelated nodes untouched
7. **Persistence + restart**: metadata persists; cache state known after
   restart
8. **Readable build report**: `core CACHED / util BUILT / ...`

## Test matrix (B1-B11, frozen, tests before implementation)

See `tests/build_cases.py` for the executable assertions.

## Design constraints

- **Do not reuse workflow DAG code**: cycle detection, topo order, reverse
  dependency, and invalidation are implemented independently inside this
  workload. Repetition itself is data - when two workloads naturally need the
  same abstraction, there is evidence to discuss a common one.
- Sources live on the filesystem (`src/<name>`), content hashed at build time;
  tests simulate "source change" by rewriting source files.
- Crash safety: output promoted via staged temp -> fsync -> rename ->
  fsync_dir. B10 verifies a partial build is never treated as a valid cache.

## Observation signals (recorded in BUILD_OBSERVATIONS.md)

1. Does record-wide propagation appear again (adding a Package field -> N
   construction sites)?
2. Does graph traversal again require large hand-written fold / nested if /
   vector scans?
3. Does `string <` again become a real blocker for deterministic ordering?
4. Result typing (natural regression test of the rebuilt compiler baseline).
5. Change-impact query (changed node -> reverse dependency closure).
6. Crash-safe authoritative state (staged -> validate -> atomic promote
   reuse).
