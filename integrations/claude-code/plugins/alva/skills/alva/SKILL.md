---
name: alva
description: Inspect, edit, check, and build ALVA language projects through the ALVA MCP server or installed CLI transactional semantic interface. Use for work on ALVA programs; do not use for maintaining the ALVA compiler implementation itself.
---

# ALVA semantic workflow

Use ALVA's semantic control plane as the primary interface to an ALVA project.
Do not begin by reading the whole repository, inferring its complete source
layout, or applying a large text patch to `.alva` files.

## Select the exposed profile first

Use the tools actually advertised by the Host. The following profile routes
take precedence over the general transaction path and reference examples.
Never call a tool that is absent from the advertised profile.

- **Maintenance Host** (`read_target`, `prepare_change`, `publish_change`):
  call `read_target` with the authorized qualified function name. Use its
  declaration, current body and direct context to prepare a `(body ...)`
  fragment. Call `prepare_change` with its `view_id`; the Host owns revisions,
  transactions, authorization and isolated draft tests. Inspect the returned
  diff and require `PREPARED`, passing checks and `can_publish` before calling
  `publish_change` with that proposal's ID. A prepared draft is not published.
  On a body rejection, revise using the same view; on expiry or conflict,
  read the target again. Proposals are single-use. Report
  `PUBLISHED_UNVERIFIED` or an unknown publication outcome honestly; do not
  retry publication or claim success. Do not bypass this route with raw Native
  commits, source writes or private AEP operations.
- **Maintenance Native** (`read_function`, `replace_function_body` with the
  transaction tools): begin a transaction, read the qualified function, retain
  its body revision and replace only its body. Preview, check and commit or
  abort with the returned transaction ID. Use only this profile's advertised
  operations; it does not include the general discovery/construction tools.
  Run the trusted task tests and verify fresh AIR after publication.
- **General Native / CLI**: use the required path below. This remains the
  default plugin profile; installing the Skill does not enable the Host.

Direct context is a bounded neighborhood, not a complete effect or dependency
proof. Use compiler feedback to repair missing or invalid references. Keep
authorization and the task's regression requirements unchanged.

## General Native / CLI required path

1. Run `alva doctor`. A missing Rust/Cargo toolchain blocks native `build` and
   `run`, but does not block semantic inspection, editing, or checking with the
   prebuilt ALVA binary.
2. Locate the relevant `alva.toml` and determine authority. If
   `alva-air/current` exists beside it, AIR is authoritative. Otherwise the
   first successful semantic commit creates AIR authority from the source
   projection; surface that transition before mutating.
3. Prefer the ALVA MCP tools when the host exposes them. Otherwise start one
   persistent `alva agent` process and use the CLI JSON-lines fallback. Begin
   with `begin_transaction` using the manifest path. With MCP, retain the
   returned `transaction_id` and pass it to every later ALVA tool call.
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

- In transaction profiles, keep one explicit transaction from begin through commit or abort. With MCP,
  pass its `transaction_id` on every call; with the CLI fallback, keep one
  persistent `alva agent` process. Revisions may become stale after mutation.
- Do not enable experimental capability gates unless the user explicitly asks.
- Do not treat `.alva` text as authoritative after graph authority exists.
- If the registry exposes no operation capable of the requested change, report
  the missing semantic operation. Do not fabricate a tool or silently fall
  back to broad source rewriting.
- Do not copy non-public research material or internal project history into an
  ALVA project or its public artifacts.
