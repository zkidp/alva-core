# BUILD_OBSERVATIONS - M3 Incremental Build Graph

Status: **M3 frozen (B1-B11 all green)**. This file records language/toolchain
observations made during implementation.

## Result summary

`project check` PASS / `build --test` (2 topo tests) PASS / B1-B11 PASS:

| Case | Result |
|---|---|
| B1 single package first build | BUILT |
| B2 rebuild without change | CACHED |
| B3 A->B->C | topo order, all BUILT |
| B4 change leaf C | only C BUILT |
| B5 change root A | A,B,C all BUILT |
| B6 fan-out change core | reverse closure (util/api/app) all BUILT |
| B7 unrelated E | only E BUILT, rest CACHED |
| B8 cycle | rejected before build, no artifacts |
| B9 restart | metadata retained, CACHED |
| B10 crash (after staged) | no fake valid cache, rebuild after restart |
| B11 change middle node util | core/e CACHED, util/app/tool BUILT; order deterministic; core output unchanged |

## Observation 1: GAP-009 - nested fold accumulator shadowing (real codegen bug)

- Symptom: a nested fold (inner fold replaces list elements) whose body
  references the outer fold accumulator generated Rust where the inner fold's
  `let mut acc` shadowed the outer accumulator; source references to the outer
  accumulator then resolved to the inner (empty) accumulator -> **silently
  wrong result** (built list empty -> report panic).
- Root cause: codegen mapped every fold accumulator to the same Rust name
  `acc`; nested folds shadow each other.
- Fix (generic, no nested-fold special case): codegen introduces unique
  generated names (`__iN` / `__accN` / `__eN`) for fold index/acc, loop acc,
  and try-catch variables, so distinct source bindings never map to the same
  Rust identifier.
- Regression: `tests/codegen/xfoldnest` (nested fold whose body references the
  outer acc; correct result `[0,0,2,2]`, buggy result `[0,1,2,3]`).
- The M3 workaround (extracting `replace_package` to avoid nesting) has been
  removed; the natural nested-fold form is restored and B1-B11 pass.

## Observation 2: manifest CRLF/newline robustness

- Symptom: manifest files with `\r\n` made `deps_from_string` parse the line
  break into a dependency name (`["\r\n"]`) -> node never ready -> empty topo
  order.
- Workaround: take the first line (before `\n` / before `\r`) before parsing.
- Observation: file-format robustness (line endings/encoding) is a real
  workflow friction; a `trim`/`lines` primitive would be more direct.

## Observation 3: record-wide propagation (second independent instance)

- `Package` has 7 fields; new record construction sites ~10 places
  (`load_manifests`, `build_one` x2, `record_dep_outputs`, `parse_package`,
  tests x2, etc.).
- Together with the earlier workflow priority workload (~18 construction
  sites), this supports "record update / partial update" as a v0.8 backlog
  candidate.

## Observation 4: graph traversal repeats

- Cycle detection / topo / reverse dependency independently implemented (per
  constraint: do not reuse workflow code), again large amounts of `fold` +
  nested `if` + `vec_contains` (hand-written).
- `vec` has no `contains`/`any`/`filter`; hand-written `vec_contains` now
  appears a second time.
- Collection abstraction evidence extends from workflow to build.

## Observation 5: `string <` did not block again

- Deterministic same-level ordering was solved with `sort` (built-in
  lexicographic order); no redesign needed. `name`/`id` comparison still lacks
  `<`, but this workload was not blocked.

## Observation 6: result typing (compiler baseline natural regression)

- The whole workload uses `result` return values extensively (including a
  `result`-typed fold accumulator in find_package/replace_package) and did
  **not** re-trigger result inference/codegen errors - the rebuilt baseline's
  signature-table fix held up under a third workload.

## Observation 7: change-impact / reverse dependency

- `reverse_dependents` + topo propagation implements "change X -> reverse
  closure rebuild" (B6/B7), structurally the same concept as "changed entity
  -> callers/serializers/matches" for agent edits.
- If generalized, this is workload-side evidence for a future
  `inspect_change_impact` operation.

## Observation 8: crash-safe authoritative state reused across domains

- staged temp -> fsync -> FAILPOINT -> rename -> fsync_dir pattern appears a
  third time (store / workflow / build); B10 verifies partial builds are not
  treated as valid cache.
- "The same transactional thinking supports workflow recovery and build cache
  correctness" is now a cross-workload engineering story.

## Summary

M3 independently reproduces several workflow signals (record field
propagation, hand-written graph traversal, crash-safe pattern) and newly
exposes one real codegen bug (GAP-009 nested fold acc shadowing). B11 closes
the "change middle node -> upstream cached + self and downstream rebuilt"
matrix gap. M3 incremental semantics are now frozen:
manifest/model, DAG, cycle, deterministic order, content hash, cache
hit/miss, reverse invalidation (leaf/root/middle/unrelated), persistence and
restart, crash safety, check/build/tests/B1-B11 all green -> **M3 freeze, no
package manager**.

When the three workloads' LANGUAGE_GAPS are aligned, record update and
collection/graph abstraction each already have >= 2 independent instances and
can enter the v0.8 backlog discussion.
