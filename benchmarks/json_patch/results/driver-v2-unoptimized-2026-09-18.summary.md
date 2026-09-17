# Target Linux runtime summary

Host: `Linux-5.15.0-186-generic-x86_64-with-glibc2.35` / `x86_64`.

All 21 engineering workloads completed with their expected disposition. Each p50/p95 uses 30 sequential observations after 3 warmups; quantiles use nearest rank.

Across workload-level p50 ratios, ALVA/Rust had descriptive median `1.91x`, range `1.02–11.67x`. This is not a pooled speedup estimate. ALVA workload p50 ranged `1.48–33.86 ms`; OS-reported process peak RSS ranged `2292–12688 KiB`.

| workload | bytes | ALVA p50 ms | Rust p50 ms | ratio | ALVA/Rust RSS KiB |
|---|---:|---:|---:|---:|---:|
| pointer-object-1k | 1024 | 1.477 | 1.443 | 1.02 | 2292/2212 |
| pointer-object-32k | 32768 | 1.680 | 1.497 | 1.12 | 2488/2428 |
| pointer-object-256k | 262144 | 8.347 | 5.647 | 1.48 | 4380/2732 |
| pointer-object-near1m | 983040 | 9.750 | 4.728 | 2.06 | 10856/4964 |
| wide-object-replace-32k | 32768 | 9.051 | 3.409 | 2.66 | 3920/2592 |
| wide-object-replace-256k | 262144 | 8.521 | 4.091 | 2.08 | 6180/3412 |
| array-head-insert-32k | 32768 | 8.344 | 4.380 | 1.91 | 3616/2596 |
| array-tail-insert-32k | 32768 | 8.697 | 4.545 | 1.91 | 3628/2616 |
| array-head-insert-256k | 262144 | 24.895 | 4.295 | 5.80 | 12576/4264 |
| array-tail-insert-256k | 262144 | 25.499 | 4.277 | 5.96 | 12688/4180 |
| deep-replace-32k | 32768 | 2.095 | 1.642 | 1.28 | 2764/2412 |
| deep-replace-256k | 262144 | 5.523 | 3.600 | 1.53 | 5112/3232 |
| copy-subtree-32k | 32768 | 2.094 | 1.653 | 1.27 | 2732/2444 |
| copy-subtree-256k | 262144 | 5.990 | 3.241 | 1.85 | 5088/3236 |
| recursive-test-32k | 32768 | 11.186 | 2.867 | 3.90 | 3304/2592 |
| recursive-test-256k | 262144 | 12.960 | 4.352 | 2.98 | 5560/3492 |
| operation-sequence-16-32k | 32768 | 9.007 | 4.560 | 1.98 | 2656/2352 |
| operation-sequence-64-256k | 262144 | 33.857 | 2.900 | 11.67 | 5788/3316 |
| first-operation-failure-32k | 32768 | 2.079 | 1.930 | 1.08 | 2556/2320 |
| late-operation-failure-32k | 32768 | 9.059 | 5.187 | 1.75 | 2648/2448 |
| move-object-32k | 32768 | 2.042 | 1.814 | 1.13 | 2504/2396 |

Compatibility cases are excluded from direct timing ratios. `1` versus `1.0` succeeds in ALVA and is rejected by the fixed Rust reference; the distinct above-2^53 decimals are rejected by both.

No workload hit the external timeout, address-space, output-capture, panic, or process-failure boundary. These constructed inputs therefore demonstrate the measured envelope only; they do not establish a production SLO or memory-leak claim.
