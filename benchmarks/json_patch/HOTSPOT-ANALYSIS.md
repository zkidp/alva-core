# JSON Patch hotspot analysis

This is an engineering profile of four preselected workloads on Ubuntu 22.04.5,
x86-64, Intel N100. It is not an industrial sample or a statistical performance
claim. D1 remains untouched; D2 and D3 use the repaired driver.

## Observations

- In D2, ALVA p50 ranged 1.477–33.857 ms and OS-reported peak RSS ranged
  2,292–12,688 KiB. The descriptive median workload-level ALVA/Rust p50 ratio
  was 1.91x (range 1.02–11.67x). All 21 workloads and every timed output passed.
- For the two 256 KiB array insertions and the 64-operation sequence, child CPU
  nearly equalled wall time. `strace -c -f` on the sequence recorded 119 calls
  and 0.522 ms of syscall time, versus about 34 ms end-to-end. The low-cost
  pointer control was about 1.5 ms. This locates the material difference inside
  user-space computation rather than blocked pipe I/O.
- `perf` was unavailable under `kernel.perf_event_paranoid=4`; no security
  setting was changed. Valgrind/heaptrack were absent. The remaining evidence is
  generated-release-source inspection plus the predeclared paired workload run.
- Generated Rust passed an already-owned `serde_json::Value` into each mutator,
  borrowed it, then cloned its full object or array before changing one member.
  The surrounding generated ALVA call already clones the public argument, so
  consuming the glue-local value removes one redundant container clone without
  introducing observable in-place mutation.

## Localized change and result

The one candidate changes the five generic JSON container mutators (`set`,
`array_set`, `array_insert`, `array_remove`, and `object_remove`) to consume the
value their extern already owns. It does not move JSON Patch semantics into
Rust and does not alter parsing, exact-number support, contracts, or overflow
checks. Regression tests reuse an original value after successful, repeated,
and rejected mutations.

In the three-way D3 rotation (unoptimized ALVA, optimized ALVA, fixed Rust), the
paired median optimized/unoptimized wall ratios were 0.966 for head insertion,
0.968 for tail insertion, 0.953 for the 64-operation sequence, and 0.991 for
the pointer control. Wins were respectively 27/30, 22/30, 30/30, and 16/30;
paired CPU ratios tracked wall ratios. Corresponding one-shot RSS observations
were 12,664→12,056, 12,632→11,944, 5,608→5,100, and 2,212→2,184 KiB. Across all
21 workloads, 16 p50s improved and five regressed; median p50 ratio was 0.988.
The largest regressions were on failure paths and remain visible in the raw
data. No claim is made that small differences generalize beyond these inputs.

## Remaining uncertainty

The profile does not measure exact allocation counts or copied bytes, and the
single RSS observation per workload is descriptive. Recursive generated code
still contains other clones, parsing/serialization remain combined with patch
execution, and process startup dominates the smallest case. The retained change
is justified narrowly by a provably redundant clone and repeatable paired signal,
not by a broad speedup claim.
