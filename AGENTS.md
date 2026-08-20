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

The root design drafts and evidence backlog are historical documents. Do not
extend them with new hypotheses. Move stable implemented facts into `docs/`;
put unpublished proposals and research planning in the private lab repository.

## Repository boundary

Do not add manuscripts, reviewer notes, raw research sessions, held-out data,
author provenance, credentials, or duplicate evaluation datasets. Evaluation
packages must pin this repository by commit SHA instead of copying the compiler
into another active repository.

Do not promote a semantic capability merely because it is convenient for one
experiment. Follow the project's evidence-gate process and keep experimental
work outside this repository until its implementation is accepted.

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
