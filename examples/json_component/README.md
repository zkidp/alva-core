# Minimal JSON component

This is a native, one-request-per-process interface and runtime regression example. It is not an inventory-allocation application or a deployment template.

Build the compiler, generate the multi-module crate, and build both profiles:

```powershell
cd alva
cargo build
target/debug/alva.exe project build ../examples/json_component/alva.toml --out-dir target/json-component
cargo build --manifest-path target/json-component/json_component/Cargo.toml --release
```

Call the release artifact (the executable name is `json_component.exe` on Windows and `json_component` elsewhere):

```powershell
'{"op":"sum","values":[1,2,3]}' | target/json-component/json_component/target/release/json_component.exe
python ../examples/json_component/call_component.py target/json-component/json_component/target/release/json_component.exe 1 2 3
```

The component accepts at most 1 MiB of valid UTF-8 on stdin. Requests are JSON objects. `sum` accepts an integer `values` array (at most 100,000 entries); `add`, `subtract`, and `multiply` accept integer `left` and `right` fields. Integers must fit in `i64`. A successful process writes exactly one complete JSON document such as `{"result":6}` and exits zero. Expected parse/validation errors use the existing `Result` path and stderr. Contract failures and arithmetic overflow retain Rust's existing panic path. Callers must wait for termination and reject nonzero exit, timeout, signal termination, empty output, invalid/truncated JSON, or an unexpected response shape.

The checked stdout write and flush happen only after parsing, validation, calculation, and contracts complete. This does not make stdout an OS-level transactional write, and it does not roll back arbitrary external side effects.

## Real-use confirmation template

- Actual user:
- Current workflow:
- Input and data authorization:
- Output purpose:
- Fallback process after failure:
