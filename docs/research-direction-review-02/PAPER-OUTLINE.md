# Proposed case-study paper outline

Design/handoff only; not a finished manuscript or submission. Claims controlled
by [PAPER-CLAIM-EVIDENCE-MAP](PAPER-CLAIM-EVIDENCE-MAP.md).

## Section plan

1. **Introduction:** existing-code maintenance crosses operation, locality,
   authority and behavior boundaries. State the system/case-study contribution
   and negative evidence; no broad language-competition motivation.
2. **Background and closest alternatives:** CodeStruct/ACI, symbol/LST editing,
   graph rewrite locality, Git/CI/OCC. Explain why a persistent AIR differs,
   without assuming that difference is valuable for every task.
3. **System and trust boundaries:** source versus AIR authority; Registry versus
   twenty Native tools; private staging, check/commit, scoped Host approval,
   Linux sandbox, independent evaluator. Document supported fixed-body guard
   coverage and unsupported changes. Define “checked publication.”
4. **Study provenance and methods:** separate deterministic witnesses, archived
   analysis and actual model observations; identify model/runtime/resource
   freezes and finite oracles. No clean pooled treatment comparison is claimed.
5. **Locality case:** P33 original shared-parent counterexample, P34 guard deny,
   P35 existing-operation safe reconnection and P36 original-program model
   completion. Disclose all failures/controls, not only the safe route.
6. **Beyond the case:** P37 engineering-eligible tasks and correlated sources;
   P38 equal-evidence comparison, simulation boundary and negative result.
7. **Measurement limits:** RDR-02 E0/E1 agreement, unavailable intermediate
   observations/bridge IDs and standalone tested-revision receipt. Original
   outcomes remain intact. No new measurement advantage or prevalence estimate.
8. **Threats and implications:** custom-language familiarity, component selection,
   author/oracle dependence, finite tests, resource censoring, private archive
   access, trusted Host and OS assumptions. Explain why no mechanism expansion
   or paid rerun follows from these cases.
9. **Conclusion:** explicit state/control boundaries are useful engineering;
   effective agent maintenance and comparative utility are separate questions.

## Figure specifications (not new measurements)

| Figure | Inputs / encoding | Integrity constraint |
| --- | --- | --- |
| F1 architecture | Source parse → private AIR staging → check → Host scope gate → AIR generation/current; separate projection arrow and independent build/tests | Approval, scope and behavior are separate boxes. Source projection is not inside the atomic AIR commit. |
| F2 locality | Original P33 two-root/shared-parent paths, selected slot and actual changed roots; P35/P36 attachment at an existing unshared ancestor | Use recorded node/path hashes, no fabricated graph edges or implication of a new path-copy primitive. |
| F3 evidence lanes | U1–U4 categorical stages: not applicable, observed, rejected, unknown; distinguish model-tool request and Native dispatch | No success-rate bars, no continuous “progress score,” no claim equal stage names imply comparable experiments. |
| F4 safe composition | Side-by-side original risky shared-parent replacement and existing safe reconnection, using public engineering evidence | Do not expose a historical witness as a future model input or claim the drawing is a randomized intervention. |

## Table specifications

- **T1 assets/guarantees:** implemented feature, authority, enforced condition,
  independent test, unsupported claim. Use the existing RDR-01 inventory.
- **T2 case layers:** P33/P34/P35/P36 staging, check, Guard, actual commit, fresh
  read, target/regression/scope. Preserve denied cases' task incompletion.
- **T3 evidence types:** P32/P36 single model slots, P37 four engineering tasks/
  two components, P38 four synthetic cases, RDR-02 four heterogeneous evidence
  units. Do not sum them into a sample N.
- **T4 strong comparison:** original P38 A/B/C/D per-case verdicts, same tests,
  evidence-strength assumptions and simulation/actual-publication distinction.
- **T5 RDR-02:** E0/E1 same-input hashes, grounded classifications, explicit
  UNKNOWN links and missing evidence. Do not relabel it an Agent accuracy table.

## Submission readiness

Initially package as technical report/case study/workshop candidate. Reviewer
must assess whether system and case evidence support a coherent contribution
relative to existing work; no acceptance prediction. Required before any
submission: permitted stable artifact/access statement, exact claim audit,
venue-specific formatting/anonymity and independent review. Do not add model
experiments just to fill sections or treat missing raw receipts as an automatic
new instrumentation project. No paper, release, publication or next research
execution is authorized by this outline.
