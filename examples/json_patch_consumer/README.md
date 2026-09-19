# Independent JSON Patch consumption

This application consumes the adjacent JSON Patch library directly through its
manifest. The reusable `json_patch.pointer` and `json_patch.patch` sources stay
in `../json_patch_component`; the consumer has no `vendor/` copy and does not
run a preparation step.

```bash
alva project check examples/json_patch_consumer/alva.toml
alva project build examples/json_patch_consumer/alva.toml --out-dir /tmp/alva-module-build
cargo build --manifest-path /tmp/alva-module-build/json_patch_consumer/Cargo.toml --release
printf '%s' '{"doc":{"name":"old"},"patch":[{"op":"replace","path":"/name","value":"new"}]}' \
  | /tmp/alva-module-build/json_patch_consumer/target/release/json_patch_consumer
```

The expected output is `{"name":"new"}`. The dependency path is resolved from
this manifest's directory, so the check does not depend on the shell's current
directory.

`prepare_module_consumer.py` remains only as a legacy source-vendoring example.
It is not part of normal local-library use. `test_native.py` separately tests
the prebuilt native component boundary and is unchanged.

The component API remains `0.1.0`; this Patch application continues to use
JSON-string paths only. A separate additive `resolve_fragment` API and explicit
native `fragment` mode are demonstrated in
[`demos/standards-maintenance`](../../demos/standards-maintenance/README.md).
Root removal is unsupported, input is bounded to 1 MiB by the native component
adapter, and JSON-number equality is bounded as documented by the component.
