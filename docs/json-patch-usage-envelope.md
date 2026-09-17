# JSON Pointer/Patch usage envelope

This document summarizes the tested component envelope. It does not claim complete RFC coverage, production deployment, independent human adoption, or an industrial latency target.

## Interface and conformance

The release executable accepts one UTF-8 JSON request on stdin, limited to 1 MiB, and writes one complete JSON result only on zero exit. Supported modes are JSON-string Pointer resolution and RFC 6902 `add`, `remove`, `replace`, `move`, `copy`, and `test`. URI fragments are unsupported; removing the whole root is rejected; decimal-value comparison is exact within the documented exponent bound and is not a general decimal type.

The pinned public corpus and local boundary/caller regressions must be rerun for every build. Expected specification rejection requires a classified JSON Pointer/Patch error, empty stdout, and no panic. Disabled upstream rows remain disabled rather than counted as passes.

## Runtime envelope

The engineering benchmark uses one process per request, Linux x86-64 release builds, prepared request bytes, a fixed Rust `json-patch` reference, three warmups, and thirty alternating observations. It reports raw samples and nearest-rank descriptive quantiles. It separately records first invocation and an OS-reported process maximum RSS. Driver limits—10 seconds, 512 MiB address space, and 16 MiB captured output—are external protections, not component guarantees.

Workloads are deterministic engineering constructions spanning approximately 1 KiB, 32 KiB, 256 KiB, and 960 KiB requests. They are not real user traces. Only cases with matching correctness and behavior enter direct ratios; number-semantics compatibility cases are reported separately.

On the authorized Ubuntu 22.04 x86-64 target, all 21 workloads completed with the expected disposition. ALVA p50 latency ranged from 2.09 to 33.88 ms and OS-reported process peak RSS from 2,288 to 12,752 KiB. The workload-level ALVA/Rust p50 ratio had descriptive median 1.87x and range 1.01–11.32x. These results are recorded with raw samples under `benchmarks/json_patch/results/`; they do not define an SLO. No optimization was made because no real latency target exists and the largest relative gap did not make the absolute run exceed 34 ms p50.

## Integration

The binary consumer requires only the release executable, `call_component.py`, interface documentation, and request files. Callers must reject timeout, nonzero exit, empty/invalid/truncated output, and unexpected response shape. The first version returns transformed JSON and never overwrites the input file.

Reusable ALVA modules currently require explicit hash-bound source vendoring because the toolchain has no package registry/local dependency declaration. The clean consumer example copies only `json_patch.pointer` and `json_patch.patch`, keeps its own application adapter, and builds through normal project tooling.

The first target-Linux module-consumer attempt exposed one real integration defect: hashes based on platform-specific working-tree line endings rejected identical Git content. `CHANGE-001` changed the preparer to bind LF-normalized source bytes. The repaired clean project passed check, release build, and execution. This is an internal integration acceptance, not evidence of an external human user.

## Licensing and dependencies

The component repository is licensed under its root license. The fixed external corpus records its upstream repository and Apache-2.0 declaration in `tests/json_patch/UPSTREAM.json`. The Rust performance reference pins `json-patch` and `serde_json`; its generated `Cargo.lock` is the authoritative transitive dependency record.
