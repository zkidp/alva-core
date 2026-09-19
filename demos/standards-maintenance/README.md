# Standards-based ALVA maintenance demonstration

ALVA is a typed, S-expression source language and toolchain that generates Rust
crates. This engineering case extends its existing JSON Pointer/Patch library
with **explicit URI-fragment Pointer resolution**. It does not compare languages
or agents, and it does not demonstrate industrial adoption or semantic editing.

## Why this change?

JSON Schema uses URI-fragment Pointers to identify parts of an already loaded
schema. The previous ALVA component deliberately accepted only JSON-string
Pointers. [REQUIREMENT.md](REQUIREMENT.md) defines the new scope and public
standards; [CANDIDATES.md](CANDIDATES.md) records the bounded search and historical
issue context. The old rejection is not mislabeled as a bug.

## Prepare and reproduce

Use Git, Python 3.10+, Cargo/Rust stable and a native linker. No Python packages
or model credentials are needed. On Windows, use a working MSVC C++ toolchain
or Rust's GNU toolchain with MinGW on PATH. PowerShell may need
`$env:RUSTUP_TOOLCHAIN='stable-x86_64-pc-windows-gnu'` for the latter.

Obtain two explicit local checkouts, without resetting any existing workspace:

```sh
git worktree add --detach ../alva-before 77f37cefdee53e24651acabff2a990fbaa5d96c2
# alva-after is an existing checkout of codex/standards-maintenance-demo.
python alva-after/demos/standards-maintenance/reproduce.py --before alva-before --after alva-after
```

Paths are relative to your current directory; absolute paths work too. The
runner creates and retains its own uniquely named directory under the system
temporary directory, **outside both Core checkouts**. `--work-parent DIR` chooses
an existing parent instead. It prints the exact `RESULTS.json` and artifact
locations. It does not reset, overwrite, or clean user sources, fetch Git refs,
run downloaded scripts, or contact any model/provider. Build failures exit nonzero.

First Cargo builds may fetch packages from crates.io and need network access.
Compiler dependencies use the checked-in `alva/Cargo.lock`; each generated
application obtains a Cargo lock during its debug build and uses `--locked`
for release. Generated lock contents/hash are captured in the result. This is
not a new remote ALVA dependency feature. Dependencies are not silently replaced
by a new hand-selected version. Toolchain versions are logged, and binaries are
hashed, but identical hashes on different machines are not promised.

To require cached dependencies, append `--offline`. A missing cache fails; the
script does not fall back online. Only environments explicitly reported as
offline-tested in RESULTS.json establish that result, not this option alone.

The script performs, for each checkout:

1. Build its compiler in a fresh target directory with locked dependencies.
2. Create a separate application adapter referring directly to that checkout's
   `alva.lib.toml`, without copying any reusable library module.
3. From an unrelated cwd, `project check`, `project build`, explicit Cargo
   `--release --locked`, then execute the release binary for every test.
4. Run the same new acceptance plus unchanged upstream/local JSON regressions,
   including the existing exact-number and type-sensitive Python comparator.
5. Run Core unit tests. On the new checkout, build another independent ALVA
   consumer that calls the public library API and uses the fail-closed caller.

The runner does not by itself rerun every Core conformance suite. Full project,
stdlib, local-library, release contract/overflow and native-caller runs are
separately recorded in RESULTS.json and the existing acceptance CI workflow.
No performance benchmark is part of reproduction.

For already built **component release binaries**, not compiler binaries:

```sh
python alva-after/demos/standards-maintenance/reproduce.py --before-binary /path/to/old-component --after-binary /path/to/new-component
```

Binary-only mode checks behavior and old JSON regressions, but explicitly reports
source/library-consumer and Core unit tests as not run. The caller supplying the
binaries owns their provenance; hashes are recorded, not treated as proof of origin.
`--baseline-only --before PATH` records the old result without expecting a repair.

## What to expect

The old component rejects `mode: fragment` with exit 1, no stdout and
`json.patch: mode must be pointer or patch`. The new component resolves
`{"mode":"fragment","doc":{"$defs":{"name":{"type":"string"}}},"pointer":"#/$defs/name"}`
to `{"type":"string"}`. Invalid fragments fail with classified errors. Both
versions preserve the old Pointer/Patch tests. Four upstream disabled records
remain disabled, not passed. The independent new consumer preserves the number
`9007199254740993.0` in its successful output.

`pointer` mode and Patch `path`/`from` still accept JSON-string syntax only;
there `%20` means literal percent-two-zero. The new `fragment` mode requires `#`,
decodes one percent layer as strict UTF-8, and then parses Pointer tokens.
No automatic dialect detection, root removal, full URL fetch, `$anchor`
resolution, JSON Schema validation, or universal media-type interpretation is
provided. The adapter retains a 1 MiB input limit and one request per process.
Callers must wait for exit, apply a timeout and validate JSON and its expected
shape before adopting it. A stdout write is not an OS transaction.

## Evidence and limitations

| Supported by this package's evidence | Not supported |
| --- | --- |
| One standards-defined feature and a traceable Codex development case | Industrial adoption or external-user endorsement |
| Recorded release execution and source-library consumption where marked PASS | Reduced human work or ALVA superiority over mature languages |
| Logged command durations, versions, outputs and artifact hashes | AEP/AIR maintenance effectiveness or general agent correctness gains |

Tests newly authored here were written by the same Codex agent that selected
and implemented the task, based on public specifications; they are not blinded
or independent human tests. The task is now a development case, never an unseen
evaluation task. No existing paper, frozen experiment or historical interpretation
is changed. See [CHANGELOG.md](CHANGELOG.md), [RESULTS.json](RESULTS.json),
[DEMO.md](DEMO.md), and the one-page [COMPARISON.md](COMPARISON.md).
