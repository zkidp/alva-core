# COMPILER_BASELINE - rebuildable compiler baseline for M3

> Purpose: avoid "there was a working compiler back then, but the commit is
> gone". This file records the original-baseline investigation and the
> rebuildable baseline that replaced it.

## 1. Original baseline `cd30061`: unrecoverable (recorded honestly)

The M3 workload (and the workflow M1/M2 workloads before it) originally used a
local compiler commit `cd30061` as baseline. Investigation:

| Search location | Result |
|---|---|
| local alva-lang repository history / reflog / fsck reachable+unreachable objects | no `cd30061` object |
| GitHub: alva-lang / alva-core / alva-research-private | no such commit |
| other local git repositories | no such object |
| Linux isolation host clone | no |
| full-disk compiler source copies (codegen.rs / main.rs search) | no copy containing the fixes |
| alva-core public snapshot | same as alva-lang main, no fix |

Conclusion: `cd30061` was a **local, never-pushed compiler modification** made
in a temporary worktree ("copied to an ASCII temp path" build); that temporary
copy is lost. Its content can only be reconstructed from the fix records in
the workflow development log (root cause + fix + regression names are all
recorded).

## 2. Rebuilt baseline (current authority, fully rebuildable)

The two fixes were rebuilt on top of the alva-lang base and committed:

```text
compiler source identity:  alva-lang e7a85b1 (main)
                           (baseline 223a6f3 + GAP-009 fix:
                            codegen unique variable names, nested
                            fold/loop/try no longer shadow)
rustc:                     1.97.1
cargo:                     1.97.1
target:                    x86_64-pc-windows-msvc (local default toolchain)
build command:             cd alva && cargo build
compiler binary SHA-256:   C7057FC08363C26AB838936DC77922F2A7A06B520291D399524A2FAE16B7D56A
                           (alva/target/debug/alva.exe)
private backup bundles:    alva-compiler-baseline-e7a85b1.bundle
                           alva-compiler-baseline-223a6f3.bundle
                           (private, never push to a public repository)
reachable refs:            alva-lang main (e7a85b1) and the workload branch
                           are both pushed to origin; both baseline commits
                           are directly fetchable.
```

Rebuilt content (matching what `cd30061` was recorded to fix):

1. **produces_result signature table**: `codegen()` receives a unified
   signature table (local fns + extern + directly dependency-exported external
   fns); `expr_returns_type()` infers return types by expression shape (call
   consults signatures / fold uses acc type annotation / ok, err, lookup,
   parse-int constructors known result / if, block, let recursion);
   `produces_result` = inferred type is `Result(..)`. `try` keeps its
   "already unwrapped" semantics. Regressions: `tests/codegen/xres`,
   `tests/codegen/xfold`.
2. **Cross-module enums**: checker `Expr::Variant`/`Expr::Match` query
   `external_types` with Record/Field same-name resolution; codegen applies
   `type_path()` for Variant/Match (e.g. `crate::xenum_a::Color::Red`).
   Regression: `tests/codegen/xenum`.

## 3. Verification checklist (rebuilt baseline)

```text
alva-lang:
  cargo test                    PASS
  cargo clippy -- -D warnings   PASS
  cargo fmt --check             PASS
  conformance suite             PASS (parser/typecheck/effects/contracts/
                                   modules/limits/golden/depth/air/manifest/
                                   project/codegen regressions)
  examples + WASM               PASS

workflow M2:
  project check PASS (6 modules)
  project build --test PASS (7 tests)

M3 buildsys (freeze):
  project check PASS (5 modules)
  project build --test PASS (2 topo tests)
  B1-B11 PASS (build_cases.py)

M3 buildsys (after workaround removal):
  project check PASS (5 modules)
  project build --test PASS (2 topo tests)
  B1-B11 PASS (natural nested fold restored; no replace_package extraction;
  GAP-009 fix verified)
```

## 4. M3 freeze commit

```text
repo:    alva-research-private (private)
branch:  codex/v08-build-system (local mirror v08-build-system-local)
commit:  959b485 "v0.8-dev: freeze M3 incremental build graph (B1-B11)"
```

## 5. Going forward

- Any new compiler change must be committed on top of this baseline and update
  this file's compiler source identity and binary SHA-256.
- New baselines must re-run workflow M2 regression + M3 B1-B11 full
  regression.
- `cd30061` itself is unrecoverable; references to it should be read as
  "the 223a6f3 rebuilt baseline".
