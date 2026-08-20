# ALVA implementation agent guide

This repository is the authoritative implementation source for ALVA. Keep it
usable as a standalone public project.

## Repository map

- `alva/`: compiler, runtime-facing toolchain, AIR/AEP implementation, and Rust
  crate sources.
- `examples/`: public validation projects.
- `tests/`: conformance, storage, compatibility, and adversarial tests.
- `docs/`: stable public architecture, language, and agent-interface
  documentation when those directories are introduced.
- `scripts/`: maintained developer and release utilities.

## Repository boundary

Keep this repository self-contained and suitable for public use.

Do not commit credentials, private datasets, raw agent transcripts, local
experiment artifacts, generated build outputs, or machine-specific
configuration.

Public examples and tests must be reproducible from files contained in this
repository.

## Before committing

Run the checks relevant to the change. The public CI baseline is:

```bash
cd alva
cargo fmt --check
cargo clippy -- -D warnings
cargo test
cargo build
```

For repository-level changes, also run the affected scripts under `tests/` and
verify examples or target builds touched by the change. Do not commit generated
`out/`, `target/`, temporary build trees, Git bundles, or credentials.
