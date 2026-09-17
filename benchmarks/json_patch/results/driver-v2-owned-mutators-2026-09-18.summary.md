# Target Linux runtime summary

Host: `Linux-5.15.0-186-generic-x86_64-with-glibc2.35` / `x86_64`.

All 21 engineering workloads completed with their expected disposition. Each p50/p95 uses 30 sequential observations after 3 warmups; quantiles use nearest rank.

Across workload-level p50 ratios, ALVA/Rust had descriptive median `1.77x`, range `1.03–10.76x`. This is not a pooled speedup estimate. ALVA workload p50 ranged `1.51–32.17 ms`; OS-reported process peak RSS ranged `2184–12056 KiB`.

| workload | bytes | ALVA p50 ms | unoptimized p50 ms | Rust p50 ms | ALVA/Rust ratio | opt/unopt ratio | RSS opt/unopt/Rust KiB |
|---|---:|---:|---:|---:|---:|---:|---:|
| pointer-object-1k | 1024 | 1.506 | 1.506798 | 1.462 | 1.03 | 0.9994604452620723 | 2184/2212/2292 |
| pointer-object-32k | 32768 | 2.998 | 3.013015 | 2.746 | 1.09 | 0.9950109773764817 | 2520/2480/2404 |
| pointer-object-256k | 262144 | 9.155 | 8.84595 | 5.976 | 1.53 | 1.0349069348119762 | 4408/4396/2732 |
| pointer-object-near1m | 983040 | 7.957 | 8.017766 | 3.631 | 2.19 | 0.9924371701543797 | 10724/10784/4860 |
| wide-object-replace-32k | 32768 | 9.306 | 9.365253 | 3.593 | 2.59 | 0.9936548430672402 | 3800/3960/2616 |
| wide-object-replace-256k | 262144 | 8.539 | 8.574204 | 4.014 | 2.13 | 0.9958627063223595 | 5952/6352/3468 |
| array-head-insert-32k | 32768 | 7.591 | 7.94831 | 3.963 | 1.92 | 0.955007542483874 | 3304/3516/2584 |
| array-tail-insert-32k | 32768 | 9.372 | 9.252753 | 4.433 | 2.11 | 1.0128369362069862 | 3416/3644/2632 |
| array-head-insert-256k | 262144 | 24.102 | 24.934291 | 4.358 | 5.53 | 0.9666199853045752 | 12056/12664/4248 |
| array-tail-insert-256k | 262144 | 24.816 | 25.625394 | 4.353 | 5.70 | 0.9684099686428236 | 11944/12632/4240 |
| deep-replace-32k | 32768 | 3.864 | 3.827011 | 3.090 | 1.25 | 1.0097005208503451 | 2832/2812/2424 |
| deep-replace-256k | 262144 | 4.783 | 4.906041 | 3.211 | 1.49 | 0.9748273607986562 | 4852/5112/3364 |
| copy-subtree-32k | 32768 | 2.567 | 2.59876 | 2.145 | 1.20 | 0.9876310240268436 | 2760/2688/2444 |
| copy-subtree-256k | 262144 | 5.883 | 5.980849 | 3.318 | 1.77 | 0.9836337616950369 | 5268/5256/3368 |
| recursive-test-32k | 32768 | 7.645 | 7.952054 | 2.475 | 3.09 | 0.9614175155249197 | 3300/3312/2704 |
| recursive-test-256k | 262144 | 9.652 | 9.92568 | 3.430 | 2.81 | 0.9724126709706539 | 5364/5336/3380 |
| operation-sequence-16-32k | 32768 | 3.781 | 3.923088 | 2.185 | 1.73 | 0.9637469258910327 | 2716/2752/2448 |
| operation-sequence-64-256k | 262144 | 32.167 | 33.733317 | 2.989 | 10.76 | 0.953580017049613 | 5100/5608/3276 |
| first-operation-failure-32k | 32768 | 2.183 | 2.110781 | 1.906 | 1.15 | 1.0340523247082478 | 2548/2504/2476 |
| late-operation-failure-32k | 32768 | 8.640 | 8.155106 | 5.206 | 1.66 | 1.0594094055920302 | 2536/2648/2492 |
| move-object-32k | 32768 | 2.785 | 2.933327 | 2.530 | 1.10 | 0.9495402319618644 | 2580/2496/2448 |

Compatibility cases are excluded from direct timing ratios. `1` versus `1.0` succeeds in ALVA and is rejected by the fixed Rust reference; the distinct above-2^53 decimals are rejected by both.

No workload hit the external timeout, address-space, output-capture, panic, or process-failure boundary. These constructed inputs therefore demonstrate the measured envelope only; they do not establish a production SLO or memory-leak claim.
