# Diagnostics and recovery

## Read the structured envelope first

For every `alva agent` response, inspect fields in this order:

1. `ok`
2. `error_code`
3. `result`
4. `diagnostics`
5. `message`

Use `message` as supporting detail, not as the primary machine contract when a
structured field supplies the same information. A failed staged operation is
atomic; do not assume it partially applied.

## Common recovery paths

- `E_AEP_AMBIGUOUS_ENTITY`: inspect `result.candidates`; retry
  `resolve_entity` with an exact candidate plus `kind` or `module`.
- `E_AEP_ENTITY_NOT_FOUND`, operand-not-found, or stale-revision errors:
  re-resolve the named entity and re-inspect its current body. Never silently
  refresh a revision by choosing the nearest-looking candidate.
- `E_AEP_UNKNOWN_TOOL`: use candidates in `result`, then call
  `describe_operation` on the intended canonical operation. A hidden
  experimental operation is unavailable, not permission to enable its gate.
- `E_AEP_BAD_REQUEST` or an invalid friendly position: call
  `describe_operation` and use its required arguments or
  `expected_positions` recovery data.
- Construction incomplete/type mismatch: inspect `result.missing`,
  `result.expected`, `result.actual`, and candidate bindings; re-run
  `describe_construction` before retrying.
- `E_AEP_CONFLICT`: another process changed authority after this transaction
  began. Abort, begin a new transaction, resolve again, and re-evaluate the
  change against the new project revision.

Do not retry an identical failed mutation without new information.

## Checker failures

`check_transaction` keeps the transaction staged when validation fails. Use
the returned envelope and checker detail to inspect the implicated semantic
entities, repair through described operations, and check again. Abort if a safe
semantic repair is not available.

For committed authority or source-only diagnostics, run:

```text
alva project check /path/to/alva.toml --json
alva check /path/to/module.alva --json
```

The project command consumes AIR when `alva-air/current` exists. JSON-mode
failures contain a `diagnostics` array with stable codes and structured fields
such as function, expected, and actual. Fix the represented semantic cause;
do not suppress diagnostics or edit generated output.

## Stop conditions

Abort and report the blocker when:

- authority is corrupt or cannot be verified;
- the requested semantic operation is absent from registry discovery;
- only an experimental gated operation could perform the change and the user
  did not request enabling it;
- repeated resolution produces genuine ambiguity that user intent cannot
  distinguish;
- validation cannot pass without expanding the requested change.
