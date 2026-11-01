# RDR-02 — read-only evidence comparison and publication handoff

Primary disposition: **INCONCLUSIVE_EVIDENCE_LIMITATION**.
Observed comparison: **BASELINE_PARITY on accessible propositions; 0 actual
E0/E1 disagreements**. No incremental measurement capability is established.
This is not a new Agent task experiment or a historical rescore.

## Frozen scope and execution

Approved base `5cc33a531e465d97ded33a0749db6451468a54b8`; branch
`codex/rdr02-treatment-realization-comparison`, PR base
`codex/alva-research-direction-review-01`. Protocol/input registration was
committed/pushed at `67a91cb` before archive-content classification. Full hashes
and public paths are in INPUT-MANIFEST.json. Source blobs load from current HEAD
with pinned hashes, not from an old registration object. New single-root/shallow
checkout support is tested. Private archives are supplied by explicit arguments.

Three original ZIPs are present locally and verified against their unchanged
historical manifests:

| Unit | Original archive SHA256 | Access |
| --- | --- | --- |
| U1 | Public coverage source hashes in manifest | Actual public MCP call/descriptor records; no private archive required |
| U2 | b37b499ec63388824efde38c395c221a71ae04d1367b1ad8555309c3888c6dd2 | 236273 bytes; verified |
| U3 | 0ed04b131cf0d7fc2fe89d7d182fbfd589942e4bfca9d04e9ce5769bf7e52295 | 65828 bytes; verified |
| U4 | 6b1f8bac0074ae82eb3234f42ee4d4a5f185d442b1e6ea1bb18939115fba4ab1 | 45032 bytes; verified |

The extractor selects tool/RPC records, target observers, before/final authority,
file hashes and evaluator exits. Model private reasoning and historical score/
disposition labels are not features; no original transcript is copied to Git.
Config/reference test bodies are not exported. Both evaluators receive the same
hashed projection and all relevant state/authority/test evidence available to it.
E0/E1 are separately implemented, not aliases to one final classifier.

## Per-unit findings

| Unit | E0 and E1 classification | Grounded relationship / limitation |
| --- | --- | --- |
| U1 P24 | CAPABILITY_COVERAGE_GAP | Actual Registry descriptions succeed, needed Native calls return E_MCP_UNKNOWN_TOOL. Not a model task. |
| U2 P26 HE23-B | PUBLISHED_WITHOUT_TARGET_CHANGE | Constructor returns a revision; commit generation 1; project/target identities remain equal; actual final tests fail. No per-operation target observation or bridge backend callId. |
| U3 P30 MM01-S | CONNECTED_NOT_PUBLISHED | Changed staged body linked to replace call; commit denied by host approval before Native dispatch; authority unchanged. Staged behavior NOT_INDEPENDENTLY_EVALUATED. |
| U4 P32 MM01-S | PUBLISHED_TESTS_PASS_IDENTITY_RECEIPT_UNAVAILABLE | Target changes; actual Native commit and stored/fresh authority agree; final check/build/goal/regression exits pass. Independent evaluation has no standalone revision echo. |

For U2 the project identity before/final is
`b8f29ca0471100074c45541f01503902d82c3a270ae875250056188693c99159`;
target body inspection hash remains
`94e7eb3eeed9c8cbf46331ea6442147d29137dd44ddac832990850c193fbadde`.
This is not a “no-op is always wrong” rule: task failure comes from executed
tests, not from empty diff. An unobserved intermediate body is not invented.

U3 changed staging but did not publish. Its unchanged authoritative final task
failure must not be assigned to the uncommitted candidate. U4 commit/final
authority is `db9e4a7e50adc031d2a7e79930a02173b01d6c44fa7e5182a43f288846d2a252`.
P32's historical COMPLETED_CORRECT_MAINTENANCE remains unchanged. The new UNKNOWN
is about self-contained identity receipt strength, not evidence of wrong-version
testing, a revision of its historical grade, or a demand for more model calls.

Exact calls/IDs and record hashes are in OBSERVATIONS.json; comparisons reference
those same facts. DISAGREEMENTS.md explains partial-chain versus full-chain
agreement. Four selected heterogeneous units are not an effectiveness sample.
P24 never enters a model denominator; P32 is not a general Native success rate.

## Independent validation and portability

validate.py does **not import/call E0/E1**. It independently rechecks source
hashes, record pointers, constructor/attachment/publication relationships,
missingness and evaluator exits, then checks the derived classifications.
Raw mode reopens all three original archives; public CI validates the portable
derived certificate and public source pointers only, explicitly reporting
private pointers it cannot reopen. Public CI is not raw-archive validation.

Local verification: Windows, Python 3.14.0, eight unit tests PASS. Raw validation
reopened all three original ZIPs and checked 238 source pointers with zero
private pointers left unopened. The committed VALIDATION.json records that raw
run. Linux/Windows portable CI separately checks the public certificate without
claiming access to the private originals.

An independent Linux checkout under WSL Ubuntu 26.04 / Python 3.14.4 also passed
all eight tests and public-certificate verification (60 public pointers checked,
178 private pointers explicitly not reopened). Failed clone-setup commands are
recorded in ATTEMPTS.md; they produced no comparison results.

```text
python -m unittest benchmarks.rdr02_treatment_realization.test_analysis -v
python benchmarks/rdr02_treatment_realization/validate.py
# Full local verification; use your authorized original archives:
python benchmarks/rdr02_treatment_realization/validate.py --u2 P26-RAW.zip --u3 P30-RAW.zip --u4 P32-RAW.zip
# Read-only batch; stdout contains JSON artifacts, no source mutation:
python benchmarks/rdr02_treatment_realization/analyze.py --u2 P26-RAW.zip --u3 P30-RAW.zip --u4 P32-RAW.zip
```

Without archives the analyzer returns unavailable/UNKNOWN for U2–U4 rather than
silently filling them from historical labels. A public certificate can be
checked/reclassified but cannot prove its private-source origin afresh. A
consumer needs the original ZIPs for that stronger check. Source/ZIP hashes are
integrity identities, not signatures defending against a compromised Host.

Attempt 01 and its parser defect are retained in Git and ATTEMPTS.md. Repair
corrected Registry versus Native exposure without changing any registered rule
or input. Tests cover missing/corrupt evidence, ordinary argument versus coverage
errors, label poisoning, fairness/result tampering, P24 denominator, P30 unknown
staged behavior, U4 missing identity receipt and independent checkout. No new
research cases or executions were introduced by these parser controls.

## Publication decision and boundaries

There is no basis to develop a D measurement mechanism or run new models.
Incomplete full-chain identity evidence prevents claiming a definitive four-unit
incremental-value falsification, but gives E1 no advantage. Keep the stronger
uncertainty explicit. No archive reconstruction, new task or extra audit is
proposed to manufacture a favorable answer.

The separate documents in docs/research-direction-review-02 provide the requested
systems/case-study publication handoff, not a submitted manuscript. They retain
P33 sharing risk, P34 scope boundaries, P35 engineering composition, P36 one
real-model case, P37 4/4 correlated engineering pool and P38's negative result.
No superiority, global novelty, broad benchmark defect or statistical claim.

Only RDR-02 analysis/docs and its minimal pure-analysis CI are new. Core, Skill,
RDR-01 and P20–P38 artifacts remain byte-identical. No compiler/candidate/model
was executed by this node. Codex authored/assisted analysis and writing; this is
not independent human adjudication. Model generation calls = **0**; input-token
API calls = **0**; next model experiment = **NOT_AUTHORIZED**. Final Git/CI and
exact changed-file report belongs to the PR description. STOP for Reviewer.
