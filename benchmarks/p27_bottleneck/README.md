# P27: archived execution bottleneck accounting

Read `docs/p26-execution-bottleneck-analysis.md`. This node executes no model,
candidate, compiler, or past study gate. Codex authored the analysis code and
interpretation; this is not a claim of model-free software development.

```text
python benchmarks/p27_bottleneck/audit.py <controlled-original-RAW.zip>
python -m unittest benchmarks.p27_bottleneck.test_audit -v
```

The script checks the exact authorized ZIP SHA before opening records, reads
the five public P26 sources as exact Git blobs at `fac3986...` (no checkout EOL
alternatives), verifies actual prompt/call/usage identities, and emits derived
stages, bounded diagnostic categories/hashes and accounting only. Never extract
or commit the raw ZIP or raw agent arguments/responses. Public call locators are
archive member plus zero-based event index; `linux_call_index` points to native
dispatch evidence. Operation ordinals are one-based and independent of transport
IDs. Dynamic CLI actions are the archived AppServer tool-result evidence, not
invented replacement requests. No hidden reasoning or agent self-reported success
is used as ground truth.

`STAGE-TRAJECTORIES.json` contains chronological model tools, MODEL_STOP, then
the separately recorded host final evaluation and overall stop. CHECK means an
observed check call; tool-envelope success is not compiler PASS. A late commit
does not establish that earlier attachment/check stages occurred. Source edits
mean changed UTF-8 bytes, not behavior correctness. Reference-return equality
uses actual content-addressed revision IDs. Repeated argument signatures are
not redundant-work claims; T checks are also keyed by actual source generation.

Usage bracket increments enclose all actions between observations, including
parallel groups and provider input/output. They must not be summed once per
tool or labeled individual tool charges. Missing before/after observations and
component token counts stay null. Canonical schema JSON bytes are a defined
analysis serialization, not unknown provider wire bytes. Cached counts are not
prices or unique context sizes.

The actual private ZIP was fully read locally after checksum verification.
CI tests synthetic edge cases and consistency of public derived data with P26;
CI does not possess the archive and must not claim a fresh raw-data audit.
Its unit logs are GitHub Actions Artifacts. Re-running this analyzer only reads
the archive; it never replays code or contacts providers. `NEXT-EXPERIMENT.json`
is a two-slot design only, not an execution freeze or execution authorization.
