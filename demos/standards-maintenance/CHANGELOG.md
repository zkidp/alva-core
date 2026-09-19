# SM-001 development record

This is a retrospective summary of actual commands/results, not a live transcript,
hidden reasoning trace, blinded experiment or independent evaluator report.

## Baseline and test-first checkpoint

- Started repository inspection at 2026-09-19 23:12:39 UTC. Created independent
  `codex/standards-maintenance-demo` worktree at required base
  `77f37cefdee53e24651acabff2a990fbaa5d96c2`; did not reset or switch main.
- Strict SSH check of the user-designated Linux target stopped at an unknown
  ED25519 host key. No host-key bypass, credential probing or other host scan.
  This target has **not** been accepted; GitHub-hosted Linux is distinct.
- Read the existing component boundaries/history, then three candidate records.
  Selected explicit fragment support based on the standard's real schema use,
  not performance-reference weakness. Wrote REQUIREMENT and literal acceptance.
- Ran `reproduce.py --before BASE_CHECKOUT --baseline-only` against clean base
  sources, with a new compiler target and external local-library application.
  The actual release request for `#/$defs/name` returned exit 1, empty stdout,
  `Error: "json.patch: mode must be pointer or patch"`. All 44 expected baseline
  dispositions, 108 upstream enabled / 26 local cases and 33 Windows Core unit
  tests passed. Four upstream records remained disabled. Complete local result
  was retained in temporary directory `sm-l28g5bou`.
- Requirements/tests were committed before implementation as
  `8f1b65640de691731d2df69269d4088c19583b08`.

## Implementation and debugging

- Added ALVA `parse_fragment`, `resolve_fragment` and explicit native mode.
  All URI grammar, percent decoding and Pointer dispatch are ALVA source.
- Core change is limited to `alva.std.string.from_utf8_octets(vec i64)` and
  generic Rust glue: range-check octets, validate UTF-8. Existing `url-decode`
  is lossy and was deliberately not used. This is a new small stdlib API;
  no compiler type rules, AIR/AEP, remote dependency, numeric or mutator logic
  was altered. No new Cargo dependency or lockfile change.
- Initial `scripts/check_parens.py` rejected one missing closing parenthesis
  in `hex_digit`. Corrected it before project check/build. No source semantics
  or acceptance expectations were changed in response.
- `cargo build --locked`, component and stdlib `project check` succeeded.
  `project build tests/stdlib/string/alva.toml --test` and the generated crate's
  `cargo test --release --locked` each passed 22 tests, including five new
  generic conversion regressions.
- First after implementation run used the retained provenance-recorded before
  release binary and a **fresh**, offline-built after compiler/application.
  The working tree was correctly recorded as dirty at the test-first commit,
  not mislabeled as a clean implementation commit. All 44 dispositions passed
  on each arm; the after positive now returned `{"type":"string"}`, exit 0.
  Old 108 enabled + 26 local cases passed on both. New Core unit tests passed.
- A second application outside Core directly imported the same library and
  called `resolve_fragment`. It checked/built from another cwd, explicitly built
  release, and returned `{"minimum":9007199254740993.0}`. The existing caller
  accepted exact success bytes and rejected malformed-percent failure. No vendor
  copy or preparation script was used. Result retained as `sm-4phv8oxu`.
- `tests/local_dependencies/run_tests.py` passed on local Windows, including
  relocation, editable rebuild and existing AIR exclusions. Existing
  `tests/release_json_component/e2e_test.py` passed actual debug/release contract,
  overflow, numeric and caller checks. Expected overflow fixtures exiting 101
  are distinct from Pointer rejection acceptance, which requires exit 1.
- Whole `cargo fmt --check` still reports old `air.rs`/`aep.rs` formatting;
  strict Clippy still reports two AIR argument-count warnings and one old
  `main.rs` needless borrow. Modified `codegen.rs` formatting passes; Clippy
  passes when only those two existing lint classes are excluded. No broad
  baseline cleanup was performed.

## Accounting and reproducibility

- A complete local two-source offline run at clean implementation commit
  `09cedc00bf62e8024f77728e017fd0984d5d434d` used new before/after build trees
  (`sm-61yxuu0u`). Both checkout states were recorded clean at capture, with
  identical generated application lock hashes. All requirement, JSON regression,
  Core unit and independent-consumer checks passed (190.103 seconds elapsed,
  189.909 recorded subprocess wait). No executable from an earlier target was used.
- Delivery audit removed unnecessary Rust/Git prerequisites from binary-only
  mode, recorded harness/consumer input hashes, and rejected Python optimized
  mode, which would disable assertions. Four harness tests cover abnormal exits,
  exact types/numbers, malformed output, timeout and missing-program classification.
  These harness tests are not extra standards-conformance samples.
- Binary-only reproduction was then actually run with PATH empty and absolute
  Python/component paths (`sm-iy6bp0z3`); it passed in 8.337 seconds (8.236
  recorded subprocess wait). It correctly reports source consumer/Core units as
  not run instead of borrowing those claims from the source-mode run.

Raw per-command inputs, outputs, exit status, duration, source/lock hashes and
artifact hashes are retained by each runner under its own RESULTS.json. These
are program/test logs, not provider dialogues. The first baseline runner took
95.365 seconds (95.275 subprocess wait); the first mixed-provenance after run
took 125.245 seconds (125.079 subprocess wait), including repeated old acceptance.
These are specific run durations, **not total development labor or latency
benchmarks**. Additional local tests and CI runs are reported separately.

All implementation/debug attempts above remain part of the development case;
an initial syntax error is not hidden by a later pass. Complete per-action agent
timing, token/monetary usage and human active-time instrumentation were not
available, and are not invented. Session elapsed time is recorded separately
from measured subprocess waits. No tool-call count is used as a statistical
sample or a labor proxy.

Final clean-commit / cross-platform evidence is listed in RESULTS.json. Existing
historical experiment outputs, old Paper 1 and performance data remain unchanged.
No model/provider experiment, external outreach, PR, release, merge or deployment.
