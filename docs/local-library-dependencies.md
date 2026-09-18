# Local library dependencies

ALVA applications can reuse editable local source libraries during normal
`project check` and `project build` operations. This is a path-dependency
feature, not a package registry or an immutable version lock.

An application declares its own modules and a path to each library manifest:

```toml
[project]
name = "json_patch_consumer"

[modules]
"consumer.main" = "src/main.alva"

[dependencies]
json_patch = "../json_patch_component/alva.lib.toml"
```

The library has a separate `alva.lib.toml`:

```toml
[library]
name = "json_patch"

[modules]
"json_patch.pointer" = "src/pointer.alva"
"json_patch.patch" = "src/patch.alva"
```

Dependency paths are relative to the manifest that declares them. Module paths
are relative to their own application or library manifest. ALVA does not search
parent directories, global locations, URLs, Git repositories, or version
ranges. The dependency key must match `[library].name`; it does not rename ALVA
modules.

Libraries may declare their own `[dependencies]`. A canonical manifest path is
loaded once, so a diamond dependency shares one library. Cycles report the
manifest chain. Different sources may not declare the same ALVA module name,
map to the same generated Rust filename, or replace compiler-managed
`alva.std.*` modules.

Normal module rules remain in force. Source `(module (name ...))` declarations
must match manifest keys, `(dep ...)` declarations still select imported
modules, and only exported functions and types are visible. In a project with
local libraries, `main` must be unique among application modules and libraries
may not define `main`.

Path dependencies are editable. Every new check or build reads the current
library files; changing a library source changes the next generated crate. ALVA
does not copy, rewrite, normalize line endings in, or content-lock those files.
This feature trusts explicitly selected local source and does not provide a
sandbox or supply-chain security boundary.

Authoritative AIR projects cannot currently be combined with local library
dependencies. ALVA reports this combination as unsupported instead of falling
back to source or importing library sources into writable AIR state. AEP and MCP
editing of local libraries is likewise outside this version.

From the repository root, the JSON Patch consumer can be reproduced with:

```bash
alva/target/debug/alva project check examples/json_patch_consumer/alva.toml
alva/target/debug/alva project build examples/json_patch_consumer/alva.toml --out-dir /tmp/alva-local-build
cargo build --manifest-path /tmp/alva-local-build/json_patch_consumer/Cargo.toml --release
printf '%s' '{"doc":{"name":"old"},"patch":[{"op":"replace","path":"/name","value":"new"}]}' \
  | /tmp/alva-local-build/json_patch_consumer/target/release/json_patch_consumer
```
