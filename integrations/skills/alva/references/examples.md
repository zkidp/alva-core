# Example: change a hello message semantically

Assume `/workspace/hello/alva.toml` declares module `hello` with function
`main`. Prefer the ALVA MCP server and include the `transaction_id` returned by
`begin_transaction` in every later tool call. The JSON below shows the
equivalent CLI fallback wire shape; keep those requests in one persistent
`alva agent` process.

## 1. Begin and discover

```json
{"request_id":"begin","tool":"begin_transaction","project":"/workspace/hello/alva.toml"}
{"request_id":"resolve-main","tool":"resolve_entity","name":"main","kind":"function","module":"hello"}
{"request_id":"ops-main","tool":"applicable_operations","entity":"hello.main"}
{"request_id":"body-main","tool":"inspect_body","function":"hello.main"}
```

The body view identifies the current string literal and its revision without
requiring the agent to read the complete source file. Save the exact literal
revision from this response as `<literal-revision>`.

Discover the mutation contract rather than assuming its parameters:

```json
{"request_id":"describe-change","tool":"describe_operation","name":"change_field"}
{"request_id":"inspect-literal","tool":"inspect_entity","entity":"<literal-revision>"}
```

Confirm that the inspected node is the intended string literal and that its
current `value` matches the message being changed.

## 2. Stage the semantic edit

Use the schema returned by `describe_operation`:

```json
{"request_id":"change-message","tool":"change_field","entity":"<literal-revision>","field":"value","value":"hello from ALVA"}
```

Do not edit `.alva`, a generation file, or a raw AIR slot. The mutation returns
the new node revision while keeping the change staged.

## 3. Review, validate, and commit

```json
{"request_id":"diff","tool":"preview_semantic_diff"}
{"request_id":"check","tool":"check_transaction"}
```

Confirm that the diff contains only the intended semantic change and that the
check response has `ok: true`. Then commit the ALVA transaction:

```json
{"request_id":"commit","tool":"commit_transaction"}
```

If either review or checking is unsatisfactory, send `abort_transaction`
instead.

## 4. Verify outside the session

```text
alva project check /workspace/hello/alva.toml --json
alva project build /workspace/hello/alva.toml
```

Run the build only when it is part of the task and Rust/Cargo are available.
Inspect Git status and confirm that the authoritative `alva-air` generation—not
an unrelated source or generated-output patch—contains the intended change.
