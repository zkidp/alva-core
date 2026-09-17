# JSON component runtime envelope

This directory measures the existing one-request-per-process ALVA JSON component against a fixed Rust reference CLI. It is an engineering runtime baseline, not a statistical superiority study or an industrial workload sample.

The reference is pinned to `json-patch = 4.2.0` and `serde_json = 1.0.151` with `arbitrary_precision`. It uses `json_patch::patch`, selected before timing because that API restores the in-memory document after an operation failure; `patch_unsafe` may leave it partially modified. Both CLIs still expose the same all-or-error process boundary.

`generate_workloads.py` deterministically creates at most 24 engineering workloads before timing. `benchmark.py` checks each implementation first, excludes compatibility mismatches from direct ratios, records a `pre_warmup_observation` after that correctness call, then uses three warmups and thirty cyclically rotated measurements. It validates disposition and exact output after every measured process exits, outside the timed interval. Reported p50/p90/p95 are nearest-rank descriptive quantiles; thirty observations do not establish a production P99.

The Linux driver applies one 10-second monotonic deadline and a 512 MiB address-space limit to each task process. It sends stdin and drains stdout/stderr concurrently. Stdout and stderr each retain at most 16 MiB (32 MiB combined); crossing either bound terminates that task process group. A separate two-second cleanup allowance is recorded apart from compute time. Process creation itself cannot be interrupted reliably from inside Python, so this is not a hard-real-time or hostile-code sandbox guarantee. `/usr/bin/time -v` runs through the same bounded path and reports the measured executable's OS maximum resident set.

Run after supplying release executables:

```bash
python3 benchmarks/json_patch/generate_workloads.py --output target/json-patch-workloads
python3 benchmarks/json_patch/benchmark.py \
  --workloads target/json-patch-workloads \
  --alva /path/to/json_patch_component \
  --reference /path/to/json-patch-reference-cli \
  --output target/json-patch-benchmark.json
```
