# JSON component runtime envelope

This directory measures the existing one-request-per-process ALVA JSON component against a fixed Rust reference CLI. It is an engineering runtime baseline, not a statistical superiority study or an industrial workload sample.

The reference is pinned to `json-patch = 4.2.0` and `serde_json = 1.0.151` with `arbitrary_precision`. It uses `json_patch::patch`, selected before timing because that API restores the in-memory document after an operation failure; `patch_unsafe` may leave it partially modified. Both CLIs still expose the same all-or-error process boundary.

`generate_workloads.py` deterministically creates at most 24 engineering workloads before timing. `benchmark.py` checks both implementations first, excludes compatibility mismatches from direct ratios, records first invocation separately, then uses three warmups and thirty alternating measurements. Reported p50/p90/p95 are nearest-rank descriptive quantiles; thirty observations do not establish a production P99.

The Linux driver applies a 10-second wall timeout and a 512 MiB address-space limit to each child. Planned outputs are below 16 MiB and are rejected if they exceed that capture bound. These are driver limits, not built-in component guarantees. `/usr/bin/time -v` supplies a separate OS-reported maximum resident-set measurement.

Run after supplying release executables:

```bash
python3 benchmarks/json_patch/generate_workloads.py --output target/json-patch-workloads
python3 benchmarks/json_patch/benchmark.py \
  --workloads target/json-patch-workloads \
  --alva /path/to/json_patch_component \
  --reference /path/to/json-patch-reference-cli \
  --output target/json-patch-benchmark.json
```
