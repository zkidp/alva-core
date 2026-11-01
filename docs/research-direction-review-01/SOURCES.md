# RDR-01 sources and audit boundary

Review date: **2026-11-02** (Australia/Brisbane). This is a bounded,
Codex-assisted source review, not an independent human review, systematic
literature review, replication, or priority search. No competitor code is copied
into ALVA. No study-model generation or input-token API was called.

## ALVA revision and public evidence

All ALVA source references below mean the exact approved base
[`60902939732f03f5653d6b2ce320ed7ca25b4c17`](https://github.com/zkidp/alva-core/tree/60902939732f03f5653d6b2ce320ed7ca25b4c17).
Relative links in this directory point to those unchanged files in this PR.
Sources were read, not executed again. Original reports' execution/verification
claims remain attributable to their recorded runs; this review is not a fresh
audit of their private raw archives.

| ID | Actual source read | Evidence boundary |
| --- | --- | --- |
| L1 | [ast.rs](../../alva/src/ast.rs), [s_expr.rs](../../alva/src/s_expr.rs), [check.rs](../../alva/src/check.rs), [project.rs](../../alva/src/project.rs), [codegen.rs](../../alva/src/codegen.rs) | Source inspection of parser/types, checking entry points, AIR loading and Rust generation; not a proof of checker soundness. |
| L2 | [air.rs](../../alva/src/air.rs), especially AirNode/AirGraph, add, rebuild_revisions, stage, replace_slot, check, write_authoritative | Actual persistence/mutation/publication implementation, not just architectural descriptions. |
| L3 | [aep.rs](../../alva/src/aep.rs), [main.rs](../../alva/src/main.rs), [mcp.rs](../../alva/src/mcp.rs) | Registry, executable Gateway, twenty-tool Native surface, session/check/commit dispatch. |
| L4 | [P31 helper](../../integrations/codex/native_commit_authorization.py), [P34 guard](../../integrations/codex/precommit_scope_guard.py), [P34 report](../research/p34-host-owned-scope-guard.md) | Scoped approval and actual precommit mediation are different boundaries. |
| L5 | [P32](../../benchmarks/p32_native_mm01/REPORT.md), [P33](../research/p33-shared-node-mutation-scope.md), [P35](../research/p35-occurrence-scope-feasibility.md), [P36](../../benchmarks/p36_mm02_native_model/REPORT.md) | Two separate S-only model observations, deterministic sharing/reconnection evidence; not a paired effectiveness sample. |
| L6 | [P37 report](../../benchmarks/p37_maintenance_qualification/REPORT.md), [registry](../../benchmarks/p37_maintenance_qualification/CANDIDATE-REGISTRY.json), [qualification](../../benchmarks/p37_maintenance_qualification/QUALIFICATION-RESULTS.json) | Four registered/matched engineering cases, two correlated component sources, zero model outcomes. |
| L7 | [P38 report](../../benchmarks/p38_authorized_effect_contract/REPORT.md), [mechanisms](../../benchmarks/p38_authorized_effect_contract/mechanisms.py), [study](../../benchmarks/p38_authorized_effect_contract/study.py), [comparison](../../benchmarks/p38_authorized_effect_contract/BASELINE-COMPARISON.json), [decision](../../benchmarks/p38_authorized_effect_contract/NOVELTY-DECISION.md) | Four synthetic cases; A/B/D offline simulations, C actual P34 publication. |
| L8 | [P20–P28 synthesis](../research/p20-p28-evidence-synthesis.md), [P26 results](../../benchmarks/native_prospective/RESULTS.json), [P27 stages](../../benchmarks/p27_bottleneck/STAGE-TRAJECTORIES.json), [P28 report](../../benchmarks/p28_optional_descriptor/REPORT.md), [P30 disposition](../../benchmarks/mm01_pilot/SCIENTIFIC-DISPOSITION.json) | Historical public records, not new execution or rescoring. |
| L9 | [Skill](../../integrations/skills/alva/SKILL.md), [Codex packaging](../../integrations/codex/README.md), [Claude packaging](../../integrations/claude-code/README.md), [persistent sandbox](../../integrations/benchmark_runtime_v2/persistent.py), [OS isolation](../../integrations/benchmark_runtime_v2/sandbox.py) | Documentation/source and prior integration records; no new installation or host/model test. |
| L10 | [Python Guard](../../integrations/python_guard/guard.py), [implementation contract](../python-guard-implementation.md) | Existing transferable source-evidence engineering; not proof of Agent utility. |

**E5/SS access:** neither their complete corrected evidence nor scoring
dispositions is published in this Core tree. The neighboring research repository
is private. No private report, transcript, dataset or unpublished statistic is
copied here. E5/SS are acknowledged as historical context with
**UNKNOWN / NOT_REVALIDATED_HERE** quantitative conclusions. User-supplied
historical summaries are not treated as validated public evidence. In particular,
this review cannot reaffirm SS behavioral scores or E5 significance claims.
The public P24/P26/P30/P32 records already suffice to demonstrate the four-layer
measurement distinction without relying on inaccessible history. No CLOSED gate
is reopened; missing access lowers the claim, not the execution boundary.

## Competitor implementation sources

**CS**: CodeStruct clone inspected at exact current commit
[`d89efa473754f455d38ab47b4dc938cfc8334a0d`](https://github.com/amazon-science/CodeStruct/tree/d89efa473754f455d38ab47b4dc938cfc8334a0d).
Read the actual implementations, config, README, LICENSE and paper source;
did not install dependencies, execute tools, or rerun published models.

- [CS-read](https://github.com/amazon-science/CodeStruct/blob/d89efa473754f455d38ab47b4dc938cfc8334a0d/SWE-agent/tools/ast_read/bin/readCode): extract_signatures, fuzzy_search_signatures, format_signatures_compact.
- [CS-edit](https://github.com/amazon-science/CodeStruct/blob/d89efa473754f455d38ab47b4dc938cfc8334a0d/SWE-agent/tools/ast_edit/bin/editCode#L291): find_exact_node/find_all_nodes, execute_operation at 420, Python syntax gate at 598, StringOperations at 618.
- [CS-write](https://github.com/amazon-science/CodeStruct/blob/d89efa473754f455d38ab47b4dc938cfc8334a0d/SWE-agent/tools/ast_edit/lib/file_operations.py#L136): write_file_safe.
- [CS-MCP](https://github.com/amazon-science/CodeStruct/blob/d89efa473754f455d38ab47b4dc938cfc8334a0d/SWE-agent/tools/ast_edit/lib/codewrite_server.py#L30): CodeWriteRequest and write_code subprocess wrapper.
- [CS-config](https://github.com/amazon-science/CodeStruct/blob/d89efa473754f455d38ab47b4dc938cfc8334a0d/SWE-agent/tools/ast_edit/config.yaml): advertised operations and explicit preference for ordinary string editing on small edits.
- [CS-license](https://github.com/amazon-science/CodeStruct/blob/d89efa473754f455d38ab47b4dc938cfc8334a0d/LICENSE): CC-BY-NC-4.0; [NOTICE](https://github.com/amazon-science/CodeStruct/blob/d89efa473754f455d38ab47b4dc938cfc8334a0d/NOTICE) lists third-party attribution.
- **SE**: Serena source at
  [`ede329aaf0c824bea75455a2926f01420d7aa620`](https://github.com/oraios/serena/blob/ede329aaf0c824bea75455a2926f01420d7aa620/src/serena/tools/symbol_tools.py#L352), ReplaceSymbolBodyTool and neighboring symbol tools. Actual GitHub source fetched, not executed. Wider backend transaction guarantees are not audited.

## Papers / official documentation actually fetched

| ID | Primary reference | What was checked; limits |
| --- | --- | --- |
| P1 | [CodeStruct, ACL 2026, pp.13290–13306](https://aclanthology.org/2026.acl-long.607/), [PDF](https://aclanthology.org/2026.acl-long.607.pdf) | PDF text and local paper source; structured interface and published multi-model evaluations. No reproduction and no direct effect-size comparison to ALVA. |
| P2 | [SWE-agent / ACI](https://arxiv.org/abs/2405.15793) | Author abstract and public artifact framing; interface design/performance is prior art. |
| P3 | [OpenRewrite LST](https://docs.openrewrite.org/concepts-and-explanations/lossless-semantic-trees), [visitors](https://docs.openrewrite.org/concepts-and-explanations/visitors) | Type-attributed, format-preserving representation and transformations; not all Moderne recipes/backends tested. |
| P4 | [ast-grep rewrite](https://ast-grep.github.io/guide/rewrite-code.html) | Structural matching/replacement; no universal semantic preservation inferred. |
| P5 | [ChangeGuard](https://arxiv.org/abs/2410.16092), [publisher full text](https://doi.org/10.1145/3715760) | Differential execution and inconclusive outcomes; not a trusted-intent publication proof. |
| P6 | [Progent v3](https://arxiv.org/abs/2504.11703v3) | Symbolic tool privilege policy; narrowing/approved expansion. Do not rely on older abstract for current scope. |
| P7 | [AgentBound v3](https://arxiv.org/abs/2510.21236v3) | MCP execution/resource permission policy; not task-functional correctness. |
| P8 | [Weiser 1984](https://www.cs.kent.edu/~jmaletic/cs63901/readings/Weiser84.pdf) | Data/control-flow slicing criterion; P38 reverse-call reachability is weaker. |
| P9 | [Chianti](https://prolangs.cs.vt.edu/refs/docs/oopsla04.pdf) | Change/test impact analysis; potential impact is not forbidden actual behavior. |
| P10 | [Lucassen/Gifford, Polymorphic Effect Systems](https://doi.org/10.1145/73560.73564) | Full text retrieval failed (publisher redirect). Detailed comparison UNVERIFIED; no theorem or algorithm attributed from memory. |
| P11 | [Meyer, Applying Design by Contract](https://files.ifi.uzh.ch/rerg/amadeus/teaching/courses/ase_fs10/Meyer1992.pdf) | Preconditions/postconditions/invariants; not change-authorization novelty. |
| P12 | [Pitts, Operational Semantics and Program Equivalence](https://www.cl.cam.ac.uk/~amp12/papers/opespe/opespe-lncs.pdf) | Contextual equivalence framework; finite test success is not that property. |
| P13 | [Goguen/Meseguer 1982](https://www.cs.purdue.edu/homes/ninghui/readings/AccessControl/goguen_meseguer_82.pdf) | Policy/model distinction and noninterference; no equivalence with P34 body scope claimed. |
| P14 | [Eclipse LTK](https://www.eclipse.org/articles/Article-LTK/ltk.html) | Refactoring conditions, changes, validation and undo; specific crash guarantees unverified. |
| P15 | [Kung/Robinson 1981](https://www.eecs.harvard.edu/~htk/publication/1981-tods-kung-robinson.pdf) | Original OCC paper accessible via author site; earlier CMU URL failed. |
| P16 | [Git update-ref](https://git-scm.com/docs/git-update-ref), [protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches) | Expected-old-object validation, ref transactions, required checks; not validation of this repository's actual branch protection configuration. |
| P17 | [Necula PCC](https://people.eecs.berkeley.edu/~necula/pcc.html) | Author overview of consumer-checked proofs; proof-carrying-change implementations not fully surveyed. |
| P18 | [Plump, Term Graph Rewriting, 1999](https://pure.york.ac.uk/portal/en/publications/term-graph-rewriting/) | Author institution abstract/bibliography, pp.3–61; full chapter not reviewed. Detailed locality algorithm comparison UNVERIFIED. |
| P19 | [Verified Tool Calls](https://arxiv.org/abs/2608.02645) | Author abstract: postconditions/retry/idempotency under non-atomic failure. Full artifact not reproduced. |
| P20 | [Callability Is Not Operability](https://arxiv.org/abs/2608.23628v2) | Author abstract: operational state, lifecycle/recovery, fixed-backend interface interventions. Detailed coding-domain coverage unverified. |
| P21 | [FixedBench](https://arxiv.org/abs/2605.07769) | Author abstract: coding tasks requiring no code change; abstention is already a research topic. |
| P22 | [tau-bench](https://arxiv.org/abs/2406.12045) | Final database-state evaluation; final-state grounding is not new. |
| P23 | [Microsoft agent evaluators](https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-evaluators/agent-evaluators) | Official process/outcome metrics; documentation, not a comparative trial. |
| P24 | [OpenAI plugin server policy](https://developers.openai.com/plugins/build/plugins) | Official per-server/tool configuration; ALVA P31 behavior is established by its pinned historical runtime, not by extrapolating current docs. |

Sources are limited by retrieval depth. Absence of a feature in inspected paths
does not establish its absence from an ecosystem, publication novelty, or inability
to compose existing tools. No numeric external performance claims are needed for
the decision. Access failures above do not block the other comparisons.
