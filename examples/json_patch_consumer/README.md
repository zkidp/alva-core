# Independent JSON Patch consumption

These checks demonstrate two current integration paths without copying the complete component example or substituting another patch implementation.

## Native release binary

`test_native.py` creates a clean temporary consumer directory containing only the supplied Linux binary, the caller, documentation, and non-sensitive request files. It runs from a different working directory and checks patch success, Pointer success, expected rejection, exact large numbers, timeout handling, nonzero exit, and invalid/truncated response handling.

```bash
python3 examples/json_patch_consumer/test_native.py --binary /path/to/json_patch_component
```

The successful transformations come from the ALVA executable. Small synthetic executables are used only to verify that the Python caller rejects timeout and malformed-output conditions which a correct ALVA binary must not produce.

## ALVA module reuse

The current toolchain has no package registry or versioned local-dependency declaration. `prepare_module_consumer.py` therefore verifies platform-independent LF-normalized hashes, writes only those two reusable modules into a clean project's `vendor/` directory, writes an explicit `alva.toml`, and leaves the consumer-owned `consumer.main` separate.

```bash
python3 examples/json_patch_consumer/prepare_module_consumer.py --output /tmp/alva-module-consumer
alva/target/debug/alva project build /tmp/alva-module-consumer/alva.toml --out-dir /tmp/alva-module-build
cargo build --manifest-path /tmp/alva-module-build/json_patch_consumer/Cargo.toml --release
```

This is a hash-bound source-vendoring path, not a package-manager claim. The component API remains `0.1.0`, JSON-string Pointer only, root removal unsupported, input bounded to 1 MiB by the native component adapter, and JSON-number equality bounded as documented by the component.
