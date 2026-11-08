# Public maintenance consumer walkthrough

This is a scripted author/Codex-assisted consumer walkthrough, not an external
user study or a model-effectiveness experiment. It reuses the unchanged
three-action maintenance MCP Host. No model or token-count API is called.
The public packing example is illustrative, not a production business claim.

## Supported environment and installation

Use Linux, Python 3.12+, Rust stable, Cargo's populated registry cache,
`bubblewrap`, and `prlimit` (util-linux). Windows/macOS candidate execution is
unsupported; there is no ordinary-host execution fallback. On Windows use a
supported Linux environment such as WSL and perform these steps inside Linux.
Clone this PR branch into a fresh directory and run from its root:

```sh
sudo apt-get install bubblewrap util-linux
cargo build --locked --manifest-path alva/Cargo.toml
python3 scripts/maintenance_consumer_walkthrough.py \
  --alva "$PWD/alva/target/debug/alva" \
  --toolchain "$(rustc --print sysroot)" \
  --registry "${CARGO_HOME:-$HOME/.cargo}/registry" \
  --output "$PWD/.local/packing-walkthrough-01"
```

The output directory must not exist. Namespace/SDK support is checked before
creating it. Unsupported environments fail rather than downgrade isolation.
This does not install or update a user's Codex plugin, or require Codex login.
It exercises the actual MCP stdio consumer boundary, not an AppServer model turn.

## Configuration and workflow

Only the manifest and two source modules from `examples/maintenance_packing`
are copied into `project/`. Operator-owned assertions and complete declaration
inventory are stored separately under `operator/host.json` and `checks.rs`.
The example permits only `model.packs_required` body changes. The caller and
`full_pack_units` helper are protected. Real deployments must have their trusted
operator approve the configuration; the script is not an authorization service.

The script launches the existing server using:

```sh
python3 -m integrations.codex.maintenance_host --config /absolute/operator/host.json
```

It exchanges real `initialize`, `tools/list`, and `tools/call` messages:

1. `read_target` returns READY and a revision-bound view.
2. A malformed body returns REJECTED.
3. A well-formed but incorrect body returns VALIDATION_FAILED: check/build PASS,
   behavior test FAIL. Neither preparation publishes authority.
4. Repairing the same draft returns PREPARED with all checks PASS.
5. `publish_change` returns PUBLISHED only after scope checking, validation and
   actual commit; a repeated proposal is REJECTED.
6. A new read and a new process independently confirm the published authority.
7. Isolated compilation/tests confirm task cases and protected helper behavior.

The arithmetic repair handles zero, exact multiples, remainders and i64 limits
without an overflowing `units + pack_size - 1` intermediate. Public operator
tests cover both target and caller. Passing these cases is not a proof for every
program/input. The sample is deliberately a repair exercise: baseline behavior
tests FAIL, while check/build PASS.

## Saving and using the result

`REPORT.json` records statuses and revision/hash bindings. Detailed stdio and
test outputs stay in the generated local directory, not Git. Preserve:

- `handoff-air/`: original sources plus the published `alva-air/current` and
  matching generation. Authority-aware project commands use this AIR state.
- `handoff-source/`: separately projected source-only project, independently
  checked, built and behavior-tested by the walkthrough.

Publication does **not** rewrite the original `.alva` files. Copying only their
unchanged bytes would lose the change. Projection uses existing
`alva air import <generation.air> --out-dir <fresh-directory>` inside isolation;
the sample maps generated module filenames back to its manifest paths.
Do not point projection at a real project without reviewing its output.
Do not use `air export --authoritative` to save published AIR: it parses sources.
There is no claim of an atomic write combining AIR publication and all sources.

## Actual walkthrough and limits

On 2026-11-09 the real run passed on Ubuntu 26.04/WSL, Python 3.14.4,
Rust 1.98.0, bubblewrap 0.11.1. Baseline check/build PASS and test FAIL;
published AIR and separately projected source both check/build/test PASS.
Original source bytes stayed unchanged. Tests include i64::MAX boundaries.
No Core, MCP operation, Guard or Skill implementation change was needed.

Usability limitations remain: configuration needs a trusted declaration inventory,
SDK and operator tests; compact failure feedback exposes check statuses, not a
detailed counterexample; source handoff is an explicit separate step. The scope
guard covers the configured structural boundary, not all behavioral effects.
This walkthrough neither resolves an independent review nor establishes cost,
general correctness or agent improvement. Runtime outputs are CI artifacts.
