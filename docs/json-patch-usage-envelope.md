# JSON Pointer/Patch usage envelope

This document summarizes the tested component envelope. It does not claim complete RFC coverage, production deployment, independent human adoption, or an industrial latency target.

## Interface and conformance

The release executable accepts one UTF-8 JSON request on stdin, limited to 1 MiB, and writes one complete JSON result only on zero exit. Supported modes are JSON-string Pointer resolution, explicit URI-fragment Pointer resolution, and RFC 6902 `add`, `remove`, `replace`, `move`, `copy`, and `test`. Fragment resolution is an additive source-mode library API described in the [standards maintenance demonstration](../demos/standards-maintenance/README.md), not automatic dialect detection, a URL fetcher or schema validator. Existing Pointer/Patch paths stay JSON-string-only. Removing the whole root is rejected; decimal-value comparison is exact within the documented exponent bound and is not a general decimal type.

The pinned public corpus and local boundary/caller regressions must be rerun for every build. Expected specification rejection requires a classified JSON Pointer/Patch error, empty stdout, and no panic. Disabled upstream rows remain disabled rather than counted as passes.

## Runtime envelope

The engineering benchmark uses one process per request, Linux x86-64 release builds, prepared request bytes, a fixed Rust `json-patch` reference, three warmups, and thirty alternating observations. It reports raw samples and nearest-rank descriptive quantiles. It separately records first invocation and an OS-reported process maximum RSS. Driver limits—10 seconds, 512 MiB address space, and 16 MiB captured output—are external protections, not component guarantees.

Workloads are deterministic engineering constructions spanning approximately 1 KiB, 32 KiB, 256 KiB, and 960 KiB requests. They are not real user traces. Only cases with matching correctness and behavior enter direct ratios; number-semantics compatibility cases are reported separately.

The original D1 run is a historical result: on the authorized Ubuntu 22.04 x86-64 target, all 21 workloads completed with the expected disposition. ALVA p50 latency ranged from 2.09 to 33.88 ms and OS-reported process peak RSS from 2,288 to 12,752 KiB. The workload-level ALVA/Rust p50 ratio had descriptive median 1.87x and range 1.01–11.32x. D2 and D3, including the later owned-mutator optimization and its limits, are described in [`benchmarks/json_patch/HOTSPOT-ANALYSIS.md`](../benchmarks/json_patch/HOTSPOT-ANALYSIS.md). The raw D1/D2/D3 data remains unchanged. These workloads are limited engineering constructions and do not define an SLO or a general performance claim.

## Integration

The binary consumer requires only the release executable, `call_component.py`, interface documentation, and request files. Callers must reject timeout, nonzero exit, empty/invalid/truncated output, and unexpected response shape. The first version returns transformed JSON and never overwrites the input file.

Reusable ALVA modules can be referenced through editable local-library manifests. The clean consumer example points to the component's `alva.lib.toml`, keeps its own application adapter, and builds through normal project tooling without copying `json_patch.pointer` or `json_patch.patch`. See [`local-library-dependencies.md`](local-library-dependencies.md).

The first target-Linux vendored module-consumer attempt exposed one real integration defect: hashes based on platform-specific working-tree line endings rejected identical Git content. `CHANGE-001` changed that legacy preparer to bind LF-normalized source bytes. This remains historical internal integration evidence, not the current local-library workflow and not evidence of an external human user.

## Licensing and dependencies

The component repository is licensed under its root license. The fixed external corpus records its upstream repository and Apache-2.0 declaration in `tests/json_patch/UPSTREAM.json`. The Rust performance reference pins `json-patch` and `serde_json`; its generated `Cargo.lock` is the authoritative transitive dependency record.
