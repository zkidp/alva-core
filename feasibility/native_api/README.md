# Native Semantic Control: one API evolution feasibility result

**SUPPORTED for this one case**, not a coding-agent utility result.
The [case and perturbation](CASE.md) and [independent tests](behavior.rs) were
written before the execution. [RESULTS.json](RESULTS.json) contains actual
CLI AEP requests/responses, command exits/outputs, source hashes, binary hash,
and authoritative generation hashes. No Core, MCP, language, existing fixture,
Guard, historical research inputs or installed plugin was modified.

## What actually ran

Starting from the exact public two-module metadata fixture, evolve unary
`touch_size(m)` into `touch_size(m, delta)`, retaining the application behavior.
This adds variable signed adjustments, not merely a changed literal. These
are mechanically authored modifications, not model-generated task attempts.

| Observation | Actual Windows result |
|---|---|
| Baseline | Project check/build and executed unary behavior test PASS |
| Ordinary text path | Parameter-first edit produces E_CALL_003; body/caller repair, project check/build and independent tests PASS |
| Public discovery | applicable_operations for both functions, describe_operation for six used operations, describe_construction(field) succeed |
| Structured path | add_param; create_reference + replace_expression; create_literal + add_call_arg |
| Invalid intermediate state | check and attempted commit both reject E_CALL_003; complete authority file manifest remains unchanged |
| Repair in same transaction | Accepted; preview identifies both modules/functions; final check PASS |
| API commit | Generation 1 -> 2; semantic revision changes; a fresh session reads two parameters and delta reference |
| Independent generated-code tests | Application compatibility, four signed/zero vectors and metadata, repeated adjustment: all PASS, for both paths |
| Predeclared stale transaction | Checked competing rename commit rejects E_AEP_CONFLICT; full authority manifest stays unchanged; loser aborted |
| Source projection | Exact original .alva hashes unchanged throughout native path |

Execution: 60 deterministic AEP calls, 13 external commands, zero generation
and input-token API calls. Windows x64, Python 3.14.0, rustc/cargo 1.97.1;
toolchain binary SHA256
`c8f5e89a19c4a0cd81ecbadb7d837d2eec8bd5661a3686ebb8ca22036c003d61`.
It was built using `cargo build --offline --manifest-path alva/Cargo.toml`.
The script builds generated projects with ordinary `project build`, then runs
`cargo test` with host-owned Rust assertions appended **only to disposable
generated crates**. Assertions execute compiled code, not a source-literal
surrogate. RUSTFLAGS overrides are removed for these generated builds.

## Observable authority boundary

The first unmodified commit establishes original AIR authority. Both competing
sessions start from that base. The actual evolution changes authoritative
semantic revision from
`c55248b6f4e36aa61a0c84cdbdb2d5c64f6827497e7d747cd7ae437090de9863` to
`8a56d83a0c8f50b824c9d56a6fe0e1231abb4463398c925c74c878a5af686149`.
The failing commit and later stale commit publish no generation changes.
`project check/build` consume the committed AIR state even though source files
still show the old unary API. The source-only text path has no AIR store and
builds its changed source instead. Do not mix those authority models.

The added control relative to **ordinary writes plus checks** is a private,
repairable staged graph and a commit boundary that rechecks validity and rejects
an outdated base under the store lock. Text checking detects the same arity
error, and the final behavior is equally correct; a failing text check does not
itself prevent publishing the invalid working tree. Git/worktrees plus a trusted
checked compare-and-swap publisher could implement analogous controls. This case
does not establish a uniquely ALVA-only guarantee, fewer repairs, or agent gain.

No whole-source atomic materialization, external-effect rollback, general merge,
recovery success, crash/power-loss durability, arbitrary concurrent writers,
universal operation coverage, or task correctness beyond these vectors is tested.
The stale loser is aborted, not automatically repaired. Overflow is not studied.
This is an existing public fixture adaptation, not evidence of industrial demand.

## Reproduce exactly this case

From this repository, with Rust/Cargo and Python available:

```text
cargo build --locked --manifest-path alva/Cargo.toml
python feasibility/native_api/run.py alva/target/debug/alva --output out/native-api.json
```

On Windows use `alva/target/debug/alva.exe`. Root build fetches/caches dependencies;
generated builds use `CARGO_NET_OFFLINE=true`. The script uses disposable temporary
projects, never edits the repository fixture, never starts Codex/provider sessions,
and writes only the requested result file outside temporary state. Read that
file's classification: exit 0 may also mean an explicitly recorded UNSUPPORTED;
FAILED is nonzero. The scoped CI asserts the current case is SUPPORTED on
Linux/Windows and uploads its own evidence, rather than rewriting this local
Windows record. Until CI completes, local execution does not imply Linux PASS.

The CLI JSON-lines AEP path is used directly. This is not a new Codex-host
discovery test or a rerun of P0/P3. Public operation schemas and construction
discovery are recorded; there are no raw AIR patches. This node ends here for
review, without starting any further model experiment or another case.
