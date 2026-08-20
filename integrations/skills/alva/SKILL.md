---
name: alva
description: Inspect, edit, check, and build ALVA language projects through the installed `alva` CLI and its transactional semantic agent interface. Use for work on ALVA programs; do not use for maintaining the ALVA compiler implementation itself.
---

# ALVA semantic workflow

Use ALVA's semantic control plane as the primary interface to an ALVA project.
Do not begin by reading the whole repository, inferring its complete source
layout, or applying a large text patch to `.alva` files.

## Required path

1. Run `alva doctor`. A missing Rust/Cargo toolchain blocks native `build` and
   `run`, but does not block semantic inspection, editing, or checking with the
   prebuilt ALVA binary.
2. Locate the relevant `alva.toml` and determine authority. If
   `alva-air/current` exists beside it, AIR is authoritative. Otherwise the
   first successful semantic commit creates AIR authority from the source
   projection; surface that transition before mutating.
3. Start one persistent `alva agent` process and send JSON-lines requests.
   Begin with `begin_transaction` using the manifest path.
4. Resolve the target with `resolve_entity`; use `kind` and `module` to resolve
   ambiguity instead of guessing.
5. Inspect only the semantic neighborhood needed for the task with
   `inspect_project`, `inspect_module`, `inspect_function`, `inspect_body`, or
   `inspect_entity`. Use standalone `alva view dependencies|callers` when an AIR
   file and those relationships are relevant.
6. Call `applicable_operations` on the resolved named entity. Before mutation,
   call `describe_operation`; for typed construction also call
   `describe_construction`. Treat these executable discovery responses as the
   source of truth, not a remembered operation schema.
7. Apply the smallest staged semantic mutation. Use returned entity and
   revision IDs; never edit raw `.air` bytes or invent slot names.
8. Review `preview_semantic_diff`, then run `check_transaction`.
9. On failure, use `error_code`, `result`, `diagnostics`, and only then
   `message` to make a targeted repair. Re-resolve stale entities and re-run
   discovery rather than silently substituting an ID.
10. Call `commit_transaction` only after the staged check passes. Otherwise
    call `abort_transaction`. Afterward run
    `alva project check <alva.toml> --json` and any task-relevant build or
    tests. An ALVA transaction commit is not a Git commit; inspect repository
    changes and create a Git commit only when the user requested one.

Read [references/workflow.md](references/workflow.md) before performing a
semantic edit. Read [references/diagnostics.md](references/diagnostics.md) when
any CLI or transaction operation fails. Read
[references/examples.md](references/examples.md) for a concrete hello-message
edit or when request/response shape is unclear.

## Boundaries

- Keep one transaction in one persistent `alva agent` process; revisions are
  session state and may become stale after mutation.
- Do not enable experimental capability gates unless the user explicitly asks.
- Do not treat `.alva` text as authoritative after graph authority exists.
- If the registry exposes no operation capable of the requested change, report
  the missing semantic operation. Do not fabricate a tool or silently fall
  back to broad source rewriting.
- Do not copy non-public research material or internal project history into an
  ALVA project or its public artifacts.
