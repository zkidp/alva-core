# Target Linux runtime summary

Host: `Linux-5.15.0-186-generic-x86_64-with-glibc2.35` / `x86_64`.

All 21 engineering workloads completed with their expected disposition. Each p50/p95 uses 30 sequential observations after 3 warmups; quantiles use nearest rank.

Across workload-level p50 ratios, ALVA/Rust had descriptive median `1.87x`, range `1.01–11.32x`. This is not a pooled speedup estimate. ALVA workload p50 ranged `2.09–33.88 ms`; OS-reported process peak RSS ranged `2288–12752 KiB`.

| workload | bytes | ALVA p50 ms | Rust p50 ms | ratio | ALVA/Rust RSS KiB |
|---|---:|---:|---:|---:|---:|
| pointer-object-1k | 1024 | 3.461 | 3.433 | 1.01 | 2288/2320 |
| pointer-object-32k | 32768 | 5.975 | 5.452 | 1.10 | 2492/2272 |
| pointer-object-256k | 262144 | 9.911 | 6.922 | 1.43 | 4364/2828 |
| pointer-object-near1m | 983040 | 8.871 | 4.281 | 2.07 | 10692/4968 |
| wide-object-replace-32k | 32768 | 10.759 | 4.823 | 2.23 | 4008/2672 |
| wide-object-replace-256k | 262144 | 7.760 | 3.670 | 2.11 | 6332/3496 |
| array-head-insert-32k | 32768 | 10.256 | 4.981 | 2.06 | 3684/2476 |
| array-tail-insert-32k | 32768 | 9.530 | 4.327 | 2.20 | 3536/2612 |
| array-head-insert-256k | 262144 | 25.042 | 4.362 | 5.74 | 12752/4292 |
| array-tail-insert-256k | 262144 | 25.517 | 4.313 | 5.92 | 12736/4180 |
| deep-replace-32k | 32768 | 7.279 | 5.752 | 1.27 | 2816/2356 |
| deep-replace-256k | 262144 | 10.955 | 7.199 | 1.52 | 5232/3356 |
| copy-subtree-32k | 32768 | 5.053 | 4.089 | 1.24 | 2728/2416 |
| copy-subtree-256k | 262144 | 12.886 | 6.882 | 1.87 | 5292/3412 |
| recursive-test-32k | 32768 | 11.336 | 2.712 | 4.18 | 3332/2492 |
| recursive-test-256k | 262144 | 11.716 | 3.370 | 3.48 | 5528/3452 |
| operation-sequence-16-32k | 32768 | 9.162 | 5.128 | 1.79 | 2772/2368 |
| operation-sequence-64-256k | 262144 | 33.879 | 2.994 | 11.32 | 5772/3476 |
| first-operation-failure-32k | 32768 | 2.093 | 1.937 | 1.08 | 2588/2292 |
| late-operation-failure-32k | 32768 | 10.036 | 6.003 | 1.67 | 2752/2416 |
| move-object-32k | 32768 | 4.438 | 3.672 | 1.21 | 2592/2452 |

Compatibility cases are excluded from direct timing ratios. `1` versus `1.0` succeeds in ALVA and is rejected by the fixed Rust reference; the distinct above-2^53 decimals are rejected by both.

No workload hit the external timeout, address-space, output-capture, panic, or process-failure boundary. These constructed inputs therefore demonstrate the measured envelope only; they do not establish a production SLO or memory-leak claim.
