# JSON Pointer and JSON Patch component

This native, one-request-per-process CLI implements JSON Pointer resolution and JSON Patch application in ALVA. The reusable logic lives in `json_patch.pointer` and `json_patch.patch`; Rust glue supplies generic JSON container operations and bounded process I/O, not patch semantics.

Build a Linux release artifact:

```bash
cd alva
cargo build
target/debug/alva project build ../examples/json_patch_component/alva.toml --out-dir target/json-patch-component
cargo build --manifest-path target/json-patch-component/json_patch_component/Cargo.toml --release
```

The executable is `alva/target/json-patch-component/json_patch_component/target/release/json_patch_component`. It reads at most 1 MiB of UTF-8 from stdin and emits exactly one complete JSON document only after the whole request succeeds.

Resolve a pointer:

```bash
printf '%s' '{"mode":"pointer","doc":{"a/b":{"m~n":7}},"pointer":"/a~1b/m~0n"}' | ./json_patch_component
```

Apply a patch:

```bash
printf '%s' '{"mode":"patch","doc":{"items":[1,2]},"patch":[{"op":"add","path":"/items/1","value":9}]}' | ./json_patch_component
```

`call_component.py` shows a fail-closed subprocess caller that waits for termination and rejects nonzero exit, timeout, empty output, and malformed/truncated JSON.

## Supported range

- RFC 6901 JSON-string pointer syntax, including the distinct empty pointer and `/`, array indices, and `~1` then `~0` decoding.
- RFC 6902 `add`, `remove`, `replace`, `move`, `copy`, and `test`, applied sequentially with failure propagation.
- Exact JSON-number equality based on decimal value, including integers above 2^53; comparisons do not pass through `f64`. The base-10 exponent must fit in `i64`; larger exponents are rejected as unsupported rather than rounded.
- A failed request writes no result document to stdout. Errors go to stderr and the process exits nonzero.

This component accepts the JSON representation only, not URI-fragment pointers. It is an interface/runtime component, not a deployment or an authorization layer. It does not overwrite files, provide OS-level transactional output, or roll back external side effects. Callers remain responsible for timeouts, process status, response validation, and application-specific authorization.

Run the pinned external and local conformance tests with:

```bash
python3 tests/json_patch/run_tests.py
```

The external corpus is pinned in `tests/json_patch/UPSTREAM.json`. Disabled upstream records remain counted and are not silently treated as passes.
