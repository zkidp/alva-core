# P37 — Prospective maintenance task qualification

**Four registered candidates; four final QUALIFIED_MATCHED engineering results.**
Real model generation calls **0**; input-token API calls **0**. No formal slot,
P38, production integration or merge. These are Codex-authored deterministic
witnesses and tests, not Coding Agent outcomes or independent human ground truth.

## Prospective record and source coverage

Canonical base: `6d5eab29e801415be1054e02ef6cf2335a3c091b`.
Registration commit: `e800c8808beb6c333e61d23e84119a4bcb6ec747`, pushed before
any new witness ran. Registry, original bundles, public requirements, approved
docs, authorized scopes, selection protocol and trusted assertion source were
committed together. Exact registered bytes still verify against that commit.
No task, source input, scope or assertion was revised after seeing results.

| ID | Existing target | Registered maintenance | Distinct coverage |
|---|---|---|---|
| MM04 | build.model.topo_order | Reject cycles/unresolved dependencies rather than return successful partial order; retain stable valid DAG ordering | Graph/error completeness |
| MM05 | build.model.needs_build | Pending/failed states cannot reuse cache even when hashes match; retain source/dependency invalidation | Enum-state cache invariant and helper data flow |
| MM06 | build.model.reverse_dependents | Deduplicate matching package names in first matching occurrence order; preserve direct-only matching | Stable collection aggregation |
| MM07 | store.model.xml_error | XML-escape code/message text, preserving response metadata and ordinary helpers | Formatting/data-encoding invariant |

The source is existing Apache-2.0 repository code at the canonical base. The
registry records LICENSE blob/SHA, full module Git origin and source bytes.
Original source modules are retained **in full**, with their private functions,
types and tests. New explicit single-module manifests are the only input
adaptation: project `buildq` for build.model, `response` for store.model. This
does not validate either full application, filesystem or server integration.

MM04–MM06 share one identical build.model bundle with 21 functions; MM07 has
the three-function store.model bundle. Thus the pool spans four task types but
only **two correlated component sources**, not four independent projects.
Source-only bundle hashes:

```text
MM04/MM05/MM06: 7ee7e3de3deae009458187d963f8045dcb9656b25d3e2acb95e6c8539361e74e
MM07:          6b03233443ee91284d677d9e47b86e2791ce49580e1bd25fe78af6eafb77a6f2
```

The requirements are plausible maintenance requests over existing functionality,
not independently reported production defects. They avoid constant replacement,
MM01 record-increment variants and MM02 query-parser renaming. Existing MM03's
signature/call-arity limitation is neither repackaged nor retested. FFI-bearing
application modules were not selected as fixed-body Guard components; no
registered candidate was later dropped or replaced to improve the tally.

## Actual batch validation and retained first failures

Every candidate independently established baseline check/build/regression PASS
and a **runtime assertion** failure on the new target. The driver checks Rust's
executed-test failure output, not just a nonzero compiler status. Each Text
witness then passed target/regressions and complete declaration/body scope.

The first Native wave at `b1c8b3602014dacddaa2be986019f9b2bf8ce565` produced
four CANDIDATE_LOCAL_FAILURE results. They remain unchanged in
`waves/wave-01.json`, with full controlled raw evidence and hashes:

- MM04 supplied the wrong representation for an optional constructed-error
  expected_type constraint. It was rejected before the target connected.
- MM05/MM06 incorrectly qualified same-module helper calls, producing concrete
  E_CALL_002 check errors. Existing source calls these helpers unqualified.
- MM07 expected specialized concat nodes, while actual original nodes were
  generic calls. The attempted selection failed before a mutation connected.

These are failed **witness sequences**, not interface-impossibility proofs or
model failures. Exactly one corrected engineering batch used the same tasks
and frozen assertions at `b230ae7f01eaed2225a90a6dd900190f0df375f5`.
The correction removed MM04's optional witness constraint, used existing
unqualified helper names, and reconstructed MM07's affected call ancestors
through public create_call before reconnecting its existing function block.
No indexed-argument operation, new primitive or Core change was invented.

| Candidate | Baseline regression / target | Text goal / regression / scope | Native goal / regression / scope | Final disposition |
|---|---|---|---|---|
| MM04 | PASS / expected runtime FAIL | PASS / PASS / PASS | PASS / PASS / PASS | QUALIFIED_MATCHED |
| MM05 | PASS / expected runtime FAIL | PASS / PASS / PASS | PASS / PASS / PASS | QUALIFIED_MATCHED |
| MM06 | PASS / expected runtime FAIL | PASS / PASS / PASS | PASS / PASS / PASS | QUALIFIED_MATCHED |
| MM07 | PASS / expected runtime FAIL | PASS / PASS / PASS | PASS / PASS / PASS | QUALIFIED_MATCHED |

Final registered count **4**. Disposition counts: QUALIFIED_MATCHED **4**;
TEXT_ONLY_NATIVE_UNSUPPORTED **0**; NATIVE_ONLY_TEXT_UNSUPPORTED **0**;
CANDIDATE_LOCAL_FAILURE **0**; INCONCLUSIVE_WITH_BLOCKER **0**;
EXCLUDED_AT_REGISTRATION **0**. The four first-wave failures are retained as
attempt history, not erased and not counted as four extra candidate tasks.
No success percentage over these dependent engineering attempts is a model rate.

## Native capability, Guard and independent scope

All new candidate execution uses unchanged P22/P23 PersistentSandbox/LinuxSandbox
namespaces. Evaluators receive source/AIR snapshots in **separate** isolated
workspaces; hidden assertion source is never inserted into the Native workspace.
The source-only Text copy and original Native copy are separate. There is no
host-permission candidate execution or Windows fallback.

Actual tools/list returned the same twenty public Native tools. Witnesses used
only admitted reference/literal/binary/call/if construction, construct_expression
field/err, and replace_expression reconnection. Internal AEP/Core mutation,
raw AIR editing, new MCP tools and Host rescue mutation were not used.
The driver is direct deterministic MCP engineering, not an AppServer model
approval-route experiment. P31 scoped approval implementation remains unchanged;
its historical experiments are not reopened.

Actual unchanged P34 Guard mediated every candidate commit under the registered
complete module inventory and authorized target-only function set. On the final
wave: **four SCOPE_ALLOWED decisions, four underlying commits**, each generation
1, no unauthorized function-body change. Check returned problems=[] and previews
identified only the authorized function for each candidate. Original sources
and manifests remained byte-identical after Native publication.

The public result retains before/staged/fresh body roots, actual Guard decisions,
commit generation/revision, Native dispatch counts and independent check/build.
Fresh Native processes read the committed AIR and match both commit revision
and staged body roots. Final authoritative project revisions:

```text
MM04 c7f82469587e996f0d6e52ba865fa3733b5db4ef8259bcf834428bbb25d16154
MM05 997899976163806d6b934cbc8fc57413e9a891d45d93015db96a13461866609e
MM06 13e3ad58266782fa57ead53d4f75cbf4ffb49c60eeda824e0dd4f6667741c1d8
MM07 9fc9ca263287ffc215e18110d82e33d2e34171e712dd59fca1e8d667c5cc32b9
```

Text scope is separately recomputed from complete original/changed declaration
snapshots, checking module/type/test roots and function metadata plus authorized
body changes; it is not judged by equality to a Native gold patch. The publisher
recomputes both sides' scope from actual evidence and reconciles Guard snapshot
digests, actual Native commit responses and fresh-process inspection calls.
Type checking, Guard allow, detached construction or commit success alone is
never a qualification result. Scope does not prove absence of all downstream
behavioral effects; regression vectors are finite.

## Future inputs and eligibility

`public/<ID>/task.json` contains the requirement and public authorization facts.
`TASK-BUNDLES.json` contains exact original sources; APPROVED-DOCS.json binds the
original approved language and current full official Skill/references.
`inputs.model_inputs` constructs only those public task/source/docs through an
explicit allowlist. T receives language docs; S additionally receives full
official Skill/references and, in any future separately frozen Host, its actual
tool schemas. These are different interfaces/information packages, not claimed
information-equivalent.

Registry hypotheses/policies, assertions.py, witnesses.py, raw calls, attachment
revisions, qualification traces and other task histories are excluded from future
model inputs and mounts. This is an explicit data construction boundary, not a
claim that public Git filenames alone provide access control. A future executor
must actually enforce the allowlist/isolation and obtain new authorization.

All four are engineering-qualified **candidates for future model eligibility**,
not approved/executed formal slots. No budget, model schedule or P38 execution
is created. No independent human review is claimed; the tests are independently
executed behavioral oracles authored by Codex before witness implementation,
so correlated author/specification error remains possible.

## Evidence, reproduction and CI

Registration and every final criterion remain anchored to the prospective
commit. Both full raw archives were downloaded from their Actions artifacts,
ZIP integrity checked and each candidate's canonical record hash recomputed.
`publish.py` produces derived result/history/validation only. No raw transcript,
candidate AIR or generated code is committed. SHA256:

```text
wave-01 RAW.zip (504256 bytes): b4696b76fb2b24c4bff93366e318dbe8faa8edee55443dfdc49f62573fb677c9
wave-02 RAW.zip (939884 bytes): 9d297f89f39719fcf5c4f08d1bd6b6d86f3e0157556352c0165485657ca986a6
```

[Wave 01 CI](https://github.com/zkidp/alva-core/actions/runs/41111842859) and
[wave 02 CI](https://github.com/zkidp/alva-core/actions/runs/41112699596) pass;
CI success means the qualification procedure completed, **not that first-wave
candidate failures were converted to PASS**. Actions artifacts preserve each
run's raw evidence; ARCHIVES.json and ENGINEERING-ATTEMPTS.json bind IDs/digests.
Later CI runs repeat the fixed wave-02 code as zero-model regression validation,
not adaptive new witnesses or candidate selection. Final-HEAD CI is reported in
the PR description. Public Rust fmt/Clippy/tests/build and Linux/Windows input/
provenance tests run alongside the isolated batch. Historical model experiments
and P34/P35 engineering suites are not rerun by the P37 workflow.

```text
python -m unittest benchmarks.p37_maintenance_qualification.test_qualification -v
# Supported Linux, unchanged trusted SDK, new output directory:
python benchmarks/p37_maintenance_qualification/qualification.py --alva <ELF> --toolchain <Rust-sysroot> --registry <public-registry> --output out/p37-new
# Controlled local wave artifacts; verification/publication does not execute candidates:
python benchmarks/p37_maintenance_qualification/publish.py .local/p37-qualification/wave-01 .local/p37-qualification/wave-02
```

All changes are additive P37 files and its new CI workflow. P20–P36 freezes,
results/archives, P36 scientific outcome and post-run startup fix, Core/AEP/MCP,
official Skill and production plugin defaults are unchanged. No existing fixture
is rewritten. The PR records final HEAD/parent, exact changed paths, comparison,
origin equality and clean worktree.

Supported conclusion: a pre-registered four-task pool over two original public
components has deterministic Text and existing-Native engineering paths with
finite independent behavior and current Guard-compatible scope validation.
No real model result, Native-over-Text reliability advantage, universal semantic
correctness, broad project generalization or selection-bias-free benchmark is
established. STOP after independent PR creation; no merge or P38.
