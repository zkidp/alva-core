# ALVA Substrate Refactor

## Objective

ALVA will optimize for the amount of information an agent must read, rediscover,
and repeat while preserving typed authority, validation, stale-write protection,
and atomic commit. Increasing the number of semantic mutation tools is not a
goal by itself.

The initial scope is the ALVA language and toolchain. General-purpose language
frontends are explicitly outside this refactor.

## Immutable evidence boundary

The refactor begins from public `main` and does not rewrite E3, E4, or E5
branches, artifacts, runners, outcomes, or frozen evidence. Product changes on
experimental branches must be reviewed and ported independently; experimental
commits are not merged wholesale into the public product line.

## Execution order

1. Freeze compatibility and measurement baselines.
2. Add adversarial reproductions, then fix confirmed safety and protocol bugs.
3. Measure agent-facing instruction, schema, observation, diagnostic, action,
   and repeated wire content.
4. Remove duplicated responses and unnecessary eager schema guidance while
   retaining a legacy fallback.
5. Add bounded/delta observations, stable diagnostic IDs, and transaction-local
   short handles.
6. Add compound prepare/stage/check calls and a first-class transactional text
   patch path.
7. Separate protocol, operations, transaction, graph, store, project, and
   diagnostic service boundaries without changing behavior.
8. Instrument and incrementally rebuild affected AIR subgraphs and indexes.
9. Unify stale-reference and crash/concurrency semantics.
10. Admit only operations with positive delivery, negative specificity,
    atomic-failure, propagation, and scale evidence.

## First-wave gates

- Standard JSON Unicode and escape behavior is shared by CLI/AEP and MCP.
- Manifest modules cannot escape the project root lexically or through links.
- Rejected mutations leave no authoritative or projected partial write.
- Advertised closed schemas reject unknown fields at the server boundary.
- A reproducible, model-free MCP byte census reports tool-list and response
  duplication cost before optimization.
- Windows missing-linker behavior is reported as an environment prerequisite;
  Linux/WSL remains the executable validation environment for this wave.

## Implemented agent-I/O primitives

- Modern MCP returns a short text summary plus complete `structuredContent`;
  legacy MCP retains the full JSON text fallback.
- Modern tool discovery uses `compact-v1`, a stable surface hash, and a cache
  TTL rather than eagerly repeating examples and schema descriptions.
- `prepare_edit` combines entity resolution, compact entity context,
  applicability, and one caller-selected operation schema. The selected-only
  design is intentional: returning every applicable schema reduced round trips
  but did not reduce information volume.
- AEP parsing, compatibility normalization, registry argument validation, and
  response envelopes now have a dedicated protocol module.
- Agent transaction state and `begin/check/diff/commit/abort` lifecycle now
  have one transport-neutral runtime owner.
- Stdio parsing now delegates each decoded request to a reusable operation
  execution entry point. `stage_and_check` uses that entry point to stage one
  registered mutation and return its result, a bounded semantic diff, and a
  bounded structured check result in one call. Failed checks leave the staged
  transaction available for repair; commit always checks again.
- MCP rejects lifecycle, inspection, recursive, gated, and non-exposed nested
  operations before forwarding `stage_and_check`, so the compound tool cannot
  bypass the curated MCP capability surface.
- `stage_text_patch` provides a narrow text-input bridge for manifest-declared
  `.alva` modules. It uses content-SHA CAS, exact-match replacement, full
  project parse/check, path confinement, and commit-time source revalidation.
  It never writes source files: successful commit stores the checked program as
  authoritative AIR. MCP exposes it only as a nested `stage_and_check`
  mutation, avoiding a second unconstrained filesystem-edit surface.
- Text patching currently refuses source-less projects, source/AIR divergence,
  and text-after-semantic mixed mode.
- Projection reconciliation is explicit and two-step. A read-only preview first
  renders every manifest module with the existing canonical AIR serializer and
  requires the complete source set to parse, check, and reproduce the exact AIR
  semantic revision. A separate materialization operation may then replace one
  declared source under source-SHA, projection-SHA, and AIR-revision CAS while
  holding the authoritative-store lock. It refuses uncommitted semantic state
  and reports whether all source modules have converged. This projection write
  is intentionally not described as atomic with the earlier AIR commit.

## Planned service boundaries

```text
CLI / MCP / integrations
        |
protocol: decode, schema, version, compact wire forms
        |
operations: registry, discovery, native operation execution
        |
transaction: session, stale policy, check, commit, abort
        |
graph: AIR model, revisions, indexes, validation, diff
        |
store: generations, CAS, locking, recovery

language: parse, AST, check, codegen
project: manifest, loading, confinement
diagnostics: stable IDs, plain/structured serializers, repair plans
```

File splitting is an enabling task, not a success metric. Each boundary must
reduce duplicated logic, permit isolated testing, or unlock measurement and
incremental execution.

## Compound-operation placement decision

`stage_and_check` and the later transactional text-patch operation belong in a
transport-neutral execution service, not in the MCP gateway. The gateway is a
wire adapter and transaction-ID owner; composing mutations there would make
MCP behavior differ from direct AEP behavior and would create a second source
of transaction semantics.

The enabling sequence is therefore:

1. Extract AEP JSON decoding, compatibility normalization, registry argument
   validation, rendering, and response envelopes from the CLI entry point.
2. Extract the stateful operation dispatcher and transaction lifecycle behind
   one execution-service interface used by direct AEP and MCP.
3. Implement `stage_and_check` in that service as one mutation plus a bounded
   diff/check observation. Commit continues to re-run authoritative checks.
4. Add transactional text patching through the same service, path policy,
   stale-write rules, check path, and atomic commit boundary.

The first extraction is intentionally behavior-preserving. Its value is the
single protocol boundary it creates; no token or correctness improvement is
claimed from moving code between files.

## Non-goals for the first wave

- no AIR storage-format change;
- no grammar or effect-system redesign;
- no effect inference or polymorphism;
- no automatic propagation mutation;
- no general TEXT-versus-HYBRID model tournament;
- no claim that static byte counts equal provider-billed tokens.
