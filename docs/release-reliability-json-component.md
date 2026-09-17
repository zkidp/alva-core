# Release reliability and minimal JSON component

This change makes ALVA-generated contracts and ordinary `i64` addition, subtraction, and multiplication fail consistently in supported debug and release native builds. Generated root manifests now contain:

```toml
[profile.release]
overflow-checks = true
```

Function preconditions, postconditions, function invariants, and loop invariants are emitted with `assert!`, so release optimization does not remove them. This is deliberately limited to ALVA contract generation; compiler-internal assertions were not rewritten. It does not introduce a contract-disable switch, decimal arithmetic, checked casts, checked FFI, or a comprehensive floating-point safety model.

Before the fix, the committed minimal single-file precondition fixture exited `101` in debug and `0` in release, and its generated manifest had no release profile. After the fix, the precondition, postcondition, and invariant fixtures exit nonzero in both profiles. Runtime-input overflow cases for `i64` add/subtract/multiply also exit nonzero in both profiles. On the tested Windows Rust toolchain the observed panic exit was `101`; that is Rust's observed process status here, not an ALVA-specific contract or overflow error code.

`alva.std.io` adds two narrow effectful operations: a UTF-8 stdin read with a fixed 1 MiB limit, and a checked stdout write plus flush. The Rust glue performs only process I/O. The example's JSON parsing, required-field/type/range validation, exact `i64` calculation, contracts, and response construction are ALVA code using `alva.std.json`; integers are never routed through `f64`.

The component and caller live in [`examples/json_component`](../examples/json_component/README.md). The reproducible end-to-end test is `python tests/release_json_component/e2e_test.py`. It generates and directly runs debug and release binaries, removes `RUSTFLAGS`, `CARGO_ENCODED_RUSTFLAGS`, and `CARGO_PROFILE_RELEASE_OVERFLOW_CHECKS` from its child environment, verifies the generated profile table, and records exact toolchain and exit results. The execution host also had no repository or user Cargo config file, so the reported run did not depend on a hidden profile override. It covers normal JSON, contracts, runtime overflow, `i64` boundaries, `2^53 + 1`, invalid JSON/UTF-8, missing and wrong-typed fields, invalid operations, out-of-range integers, oversized input, empty stdout on calculation/contract failure, and caller rejection of nonzero/truncated results.

Verified in this development worktree on Windows only (`x86_64-pc-windows-msvc`) with `rustc 1.97.1 (8bab26f4f 2026-07-14)`, `cargo 1.97.1 (c980f4866 2026-06-30)`, and Python 3.14.0. Linux, macOS, WASM/WASI, broken-pipe behavior, signal delivery, and OS-level write atomicity were not verified. The design does not claim rollback of arbitrary external side effects.
