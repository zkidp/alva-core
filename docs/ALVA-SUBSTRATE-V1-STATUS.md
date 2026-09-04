# ALVA Substrate V1 Status

## Outcome

The behavior-bearing substrate-v1 refactor is complete on
`codex/core-substrate-v1`. It reduces repeated agent-facing information and
transaction work while retaining full authoritative commit checks, stale-write
protection, and crash-safe generation semantics.

This is an infrastructure result. It does not claim that structured editing
improves task correctness, that static byte reductions equal provider-billed
token reductions, or that the refactor improves model quality without a
separate frozen evaluation.

## Closed work packages

1. Compact modern MCP discovery and responses, with a legacy compatibility
   fallback.
2. Bounded preparation, diagnostic, diff, and transaction observations.
3. Shared protocol validation and a transport-neutral transaction runtime.
4. Compound `stage_and_check` and checked transactional text input.
5. Canonical source-projection preview and CAS-guarded reconciliation.
6. Transaction graph-work instrumentation and affected-root rebuilding.
7. Mutation-local dirty tracking, guarded by an optional full-scan oracle.
8. Changed-module plus transitive-dependent checks for repeated transaction
   checks, guarded by an exact full-check oracle; commit remains full-project.
9. Authoritative-store recovery from orphan generations and atomic
   replace-existing behavior.

The detailed design and retained boundaries are in
`docs/ALVA-SUBSTRATE-REFACTOR.md`. Measurement records are in
`benchmarks/agent_io/WAVE-01.json` through `WAVE-12.json`.

## Final validation

Commit `6c83421a48c19e7b7942d0c308d30237239d3342` was validated in an isolated
`rust:1.89-bullseye` container with both correctness oracles enabled:

- `cargo fmt --check`: PASS
- strict Clippy over all targets/features with warnings denied: PASS
- Rust unit tests: 39 passed, 0 failed
- all-target/all-feature build: PASS
- MCP protocol and Codex/Claude plugin checks: PASS
- transaction-work and source-projection checks: PASS
- full repository conformance, including AIR/AEP, manifest, project linking,
  code generation, contracts, parser, type/effect, limits, and strict-negative
  checks: PASS

The resulting Linux debug binary SHA-256 was
`e0931db560ca35305af206d2d299e6f69a1312e423e97482a92edbb618491408`.

## Remaining non-blocking work

Two follow-ups remain outside the behavior-bearing v1 completion gate:

1. Continue splitting the large operation, graph, and store files only where
   the split produces a concrete ownership or isolated-testing benefit. File
   movement alone is not treated as a refactor success metric.
2. Exercise the `cfg(windows)` `MoveFileExW` replacement path in native Windows
   CI. Linux validation cannot compile or execute that platform-specific path.

Neither follow-up changes the Linux substrate-v1 completion result. Any later
performance or model-effect claim requires a separately frozen benchmark or
experiment.
