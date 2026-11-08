# Minimal maintenance engineering baseline and review split

9 November 2026. This is an engineering handoff, not a new study protocol or a
merge authorization. No model/provider/token-counter call is made. Existing
frozen inputs/results and the paper remain unchanged. Codex assisted this work;
deterministic testing is not model-free authorship or an agent effectiveness test.

## Exact checkout versus canonical main

This work starts from `cc27893935e6a0206e7510be197dd78ea7989238`
(`codex/host-context-v4`). The remote canonical main observed at inspection is
`cd73ae8c653953289ee758ce24e4821f1b4c5108`. They are not interchangeable releases.
The paper branch ends at `b7a8cf86094c8e85a2f22025508088579cdf9476`, independently
of subsequent maintenance engineering. P0–P38/RDR/paper PRs are not assumed merged.

Minimum *demonstrated* existing entry: the cost-optimized MaintenanceHost, with
operator-owned input paths, complete scope policy, compiler/SDK, evaluator and
requirement/regression tests. It is opt-in, Linux-only for candidate execution.
The current checkout also contains experimental compact context and historical
experiments; their presence is not a recommendation to enable them.

| Surface | Entry | Role / status |
| --- | --- | --- |
| Native, 20 tools | `alva mcp` / `--profile native` | Existing low-level semantic API; agent owns explicit transaction choreography |
| Maintenance, 9 tools | `alva mcp --profile maintenance` | Opt-in function-body editor with occurrence-copy; still explicit transactions |
| Host, 3 actions | `python -m integrations.codex.maintenance_host --config ...` | Recommended engineering starting point; read/prepare/publish, actual Guard and isolated draft tests |
| Compact context, 5 tools | `python -m integrations.codex.maintenance_context --config ...` | Experimental; V4 not promoted as default after tail regression |
| Bounded dependencies, 5 tools | `python -m integrations.codex.bounded_target_context --config ...` | This read-only prototype; same tools/mutations as compact entry, not a validated economy treatment |

No plugin installation, default tool surface, Core operation or trusted policy
is changed by this handoff. Three-action Host stability is relative to the
tested bounded components, not a production support/compatibility guarantee.

## Proposed dependency-ordered PR extraction (not performed)

Do not merge/cherry-pick the complete research chain into main. Do not rewrite
the original branch history. Create review branches only with explicit future
authorization, retaining origin commits and a path-level extraction record.
The following are engineering review units, not extra scientific gates.

1. **Shared-node-safe body editing and exact snapshot reads.** Source:
   `0edae8ec2ebcba8e2b340fb329e82eed6730027c`. Paths: affected `alva/src/` body
   editor, AST/check/project/gateway/MCP wiring, body-edit Rust tests,
   `tests/mcp/maintenance_profile_test.py`, `maintenance_mm02_test.py`, and user
   interface docs. Explicitly review the exact-revision inspect correction:
   this is a real existing-read behavior fix, not just adding nine tool names.
   Keep legacy profile schema and existing rejection regressions.
2. **Trusted protected Host and isolated evaluator.** Source:
   `e0bbfe44f4cf8f88c791758687bf401580efef72`. Depends on 1 and existing Guard,
   OS sandbox and transport prerequisites. Paths: maintenance_host/evaluator,
   private graph export/direct-context inspections, Guard adaptation and
   production docs/tests. The common return checker correction is a separately
   reviewable sub-change: it moved checking from editor-only into source/AIR,
   using existing inference. Preserve source/AIR equivalence tests. Include
   profile-aware Skill changes with their synchronized plugin copies only when
   that dependency lands; no default installer rewiring.
3. **Cost transport optimization.** Source:
   `53539ec4b0471f53b8732cecf066dc84b78cb680`. Depends on 2. Batch complete scope
   inspection, AIR digest rechecks and compact responses; retain strict
   before/after scope-equivalence and receipt tests. Do not import frozen
   experimental runtimes just to obtain the engineering code. Model token
   savings cannot be inferred from RPC-byte reductions.
4. **Common Result code-generation repair.** Source:
   `ed825b380edf1f5ebd5942bae80a16fc5324a53c`, but extract only the codegen fix
   and its independent source/AIR execution regression. The original commit
   mixes this with V4 qualification/tasks; do not cherry-pick it whole. Review
   parameter/lexical-let shadowing/match-tail cases independently of optional
   context delivery. It depends on the current checker/AST behavior, not a
   claim of complete Result typing soundness.
5. **Optional context work**, only after the stable pipeline: generic public
   reference/source readers and the present dependency projection. Do not make
   compact V4 the default or import a paid study as an acceptance requirement.

Main predates many of these prerequisites. Resolve actual ancestry against main
before extraction; preserve Git history where possible rather than squash
unreviewed research into a release. Existing P0–P2 and Native/Guard/sandbox PR
dependencies need explicit review/merge planning, not assumed presence. No new
full-history audit is requested here.

**Keep separate:** `benchmarks/maintenance_interface_comparison`,
`compact_maintenance`, `compact_deepseek`, `host_v3_acceptance`, `context_v4`,
their raw archive manifests/freezes, and paper/RDR directories remain historical
research evidence. Their original results, stops, caveats and consumed freezes
are neither cleanup targets nor code-migration test inputs. Existing engineering
tests that import witness modules should be replaced by a small standalone
consumer fixture in a future extraction—not erased from the historical branch.

## Small standalone consumer and failure contract

Use [bounded-target-context.md](bounded-target-context.md) for the actual
no-model consumer check and optional stdio entry. The new fixture uses a generic
record/enum/helper program, not MM/W02 task answers. Real Linux evaluation
compiles authoritative draft AIR and executes independently supplied assertions
before a proposal can be published. Windows runs real inspections/lifecycle
with an explicitly labelled receipt stub; it does not claim sandboxed behavior.

The trusted operator must supply complete allowed function inventory and tests.
Missing policy coverage remains unverified. Candidate code must stay inside the
existing Linux evaluator; no host-permission fallback. Source files remain
unchanged projections after Native publication: callers must read AIR authority
or explicitly materialize source through the existing supported mechanism.
Do not use a source diff alone to identify the published Native candidate.

Prepare rejection permits repair under normal Host rules. A failed new prepare
invalidates old proposals. Publish is single-use; stale source/base or changed
test identity must reject, and uncertain commit outcomes must not be retried.
These rules are unchanged. Context UNKNOWN/TOO_BROAD is not a grant to publish
or evidence of task failure. Full tests and exact candidate evidence remain
mandatory through the original Host.

## What is and is not ready

Engineering expressibility, actual scoped publication and some model task
completions are demonstrated. Cost V3 improves its preceding Host configuration,
but its matched-text screen did not pass. V4's median improvement against full
context coexists with H01's adverse tail; it is not default-ready. The present
prototype only demonstrates dependency facts and boundaries. It does not
establish fewer reads, tokens, latency, higher correctness or industrial use.
No next model run, paper revision, release or merge is automatically authorized.
