# Semantic-edit workflow

## Preflight and authority

Run:

```text
alva doctor
```

Locate the nearest relevant `alva.toml` without recursively reading source
contents. Inspect the manifest and the existence of `alva-air/current` beside
it:

- present: AIR generations are authoritative; `.alva` files are projections;
- absent: `begin_transaction` imports the manifest's source modules, and the
  first `commit_transaction` creates `alva-air/current` plus a generation.

The second case is an authority transition, not an ordinary text-file update.
Mention it before mutation and expect new graph-store files in version-control
status. Never patch generation files directly.

## Prefer MCP when available

If the host exposes ALVA MCP tools, use them directly. Start with
`begin_transaction`, retain its explicit `transaction_id`, and include that
handle in every inspection, discovery, mutation, check, and finish call. Do not
substitute shell invocations for available semantic MCP tools.

The MCP server exposes the same AEP registry and AIR transaction implementation
as the CLI fallback. Treat each tool's advertised input schema as authoritative.
Always end a transaction with `commit_transaction` or `abort_transaction`.

## CLI fallback: keep one JSON-lines session

When MCP is not available, launch `alva agent` as a persistent child process
with writable stdin and readable stdout. Send exactly one JSON object per line
and read exactly one JSON response per request. Keep the process alive through
discovery, mutation, checking, and commit or abort.

Start with a request ID that makes transcripts easy to audit:

```json
{"request_id":"begin-1","tool":"begin_transaction","project":"/workspace/alva.toml"}
```

Every response is a JSON envelope. Confirm `ok` before consuming `result` and
retain the returned project revision. Do not require a hard-coded
`protocol_version`; use the version returned by the installed binary.

## Discover before changing

Resolve a named target explicitly:

```json
{"request_id":"resolve-1","tool":"resolve_entity","name":"main","kind":"function","module":"hello"}
```

If the result is ambiguous, choose only from the structured candidates and
retry with `kind` and/or `module`. Then inspect the narrowest useful view:

```json
{"request_id":"inspect-1","tool":"inspect_body","function":"hello.main"}
{"request_id":"ops-1","tool":"applicable_operations","entity":"hello.main"}
```

`applicable_operations` is for named entities. Expression revisions discovered
inside a body can be inspected with `inspect_entity`, but may not themselves be
resolvable as named entities.

Before using a returned operation, retrieve its executable schema:

```json
{"request_id":"describe-1","tool":"describe_operation","name":"change_field"}
```

For typed construction, also retrieve the kind-specific schema and candidate
bindings:

```json
{"request_id":"construct-schema-1","tool":"describe_construction","kind":"record_update","include_candidates":true}
```

Use the response's canonical name, required arguments, preconditions, effects,
and examples. Do not maintain a separate remembered list of operation
arguments.

## Stage, review, and finish

Apply the smallest mutation using the current revision IDs. After any mutation,
assume affected ancestor revisions may have changed. Re-resolve named entities
before a subsequent edit instead of recycling an old revision.

Review and check within the same process:

```json
{"request_id":"diff-1","tool":"preview_semantic_diff"}
{"request_id":"check-1","tool":"check_transaction"}
```

Commit only when the response to `check_transaction` has `ok: true`:

```json
{"request_id":"commit-1","tool":"commit_transaction"}
```

If the task is cancelled, the intended edit cannot be expressed through the
discovered interface, or validation cannot be repaired safely, end the staged
session without changing authority:

```json
{"request_id":"abort-1","tool":"abort_transaction"}
```

After a successful semantic commit, run:

```text
alva project check /workspace/alva.toml --json
```

Successful JSON-mode checking can produce no output; use its exit status. Run
`project build`, program tests, or `run` only when relevant and when `doctor`
showed the required Rust/Cargo toolchain. Finally inspect Git status. The AEP
commit writes authoritative program state; a Git commit remains a separate,
user-authorized repository action.
