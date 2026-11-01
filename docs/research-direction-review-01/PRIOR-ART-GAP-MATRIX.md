# Competitive gap review

Primary source IDs and access depth are in [SOURCES](SOURCES.md). “Candidate
gap” is a question still requiring a discriminating test, not an absence claim.
No row asserts global novelty. CodeStruct was inspected in depth; other systems
were reviewed at the stated source/document/paper level, not reproduced.

| Closest work | Mature / established method | Different assumptions and possible gap | Consequence for ALVA |
| --- | --- | --- | --- |
| [CodeStruct (CS/P1)](ALVA-VS-CODESTRUCT.md) | Named AST actions and actual coding-agent evaluation | Persistent AIR publication differs; whether that identity improves any end result is unproved | Broad structured-action performance novelty collides. Compare actual surfaces and documents, not names. |
| [SWE-agent / ACI (P2)](https://arxiv.org/abs/2405.15793) | Navigation/edit/feedback interface design influences agent work | AEP construction/attachment stages differ from source edits; diagnostic/interface friction is not new | A needs a narrower maintenance-specific intervention than “better tools.” |
| [Serena (SE)](https://github.com/oraios/serena/blob/ede329aaf0c824bea75455a2926f01420d7aa620/src/serena/tools/symbol_tools.py#L352) | Language-server symbol retrieval and body replacement with diagnostics | Native authoritative revision versus source-symbol addressing; no complete backend transaction audit here | Do not claim semantic tools or MCP symbol editing are ALVA-first. |
| [OpenRewrite / Moderne (P3)](https://docs.openrewrite.org/concepts-and-explanations/lossless-semantic-trees) | Typed, format-preserving source transformations; visitor/recipe composition | General recipe ecosystem versus fine-grained Agent composition; complete publication semantics UNKNOWN | Established strong transformation baseline; “ASTs lack semantics” is untenable. |
| [ast-grep (P4)](https://ast-grep.github.io/guide/rewrite-code.html) | Structural pattern rewrite on mainstream source | Pattern match/rewrite need not mean typed/global behavior preservation | Useful conventional locality baseline, not universal semantic proof. |
| [ChangeGuard (P5)](https://arxiv.org/abs/2410.16092) | Differential behavior testing for code changes; inconclusive outcomes | Learned execution assumptions differ from registered finite ALVA tests; intent authorization is a distinct policy | Executing before/after code and returning uncertainty is not an AEC invention. |
| [Progent (P6)](https://arxiv.org/abs/2504.11703v3) | Deterministic privilege checks over tool calls and controlled policy update | Permission for a call differs from permission for its resulting program behavior | Existing enforcement must be reused/compared, not rebranded an effect theorem. |
| [AgentBound (P7)](https://arxiv.org/abs/2510.21236v3) | MCP resource/execution access control | Program-functional effect policy is a different object; full artifact not executed | Sandbox plus tool allowlist is infrastructure, not functional correctness. |
| [Slicing (P8)](https://www.cs.kent.edu/~jmaletic/cs63901/readings/Weiser84.pdf) / [Chianti (P9)](https://prolangs.cs.vt.edu/refs/docs/oopsla04.pdf) | Dependence-directed program/test impact analysis | Soundness, precision and incomplete dependency coverage require declared assumptions | P38's closed direct-call reachability is much weaker; no sound general impact engine. |
| [Effect systems (P10)](https://doi.org/10.1145/73560.73564) | Established research area; specific primary full text unavailable here | Detailed comparison UNVERIFIED, not inferred from paper title | No claim that ALVA has a new effect calculus or that prior work lacks required effects. |
| [Design by contract (P11)](https://files.ifi.uzh.ch/rerg/amadeus/teaching/courses/ase_fs10/Meyer1992.pdf) | Explicit pre/post/invariant obligations | Trusted change intent and adequate specifications remain human/host responsibilities | Additional specification/check strength must not be counted as architecture-only benefit. |
| [Equivalence (P12)](https://www.cl.cam.ac.uk/~amp12/papers/opespe/opespe-lncs.pdf) / [noninterference (P13)](https://www.cs.purdue.edu/homes/ninghui/readings/AccessControl/goguen_meseguer_82.pdf) | Formal relations between executions/observations | Declaration-root equality is neither relation; finite samples leave unknown behaviors | P34 scope and P38 tests cannot be promoted to general protected-behavior proof. |
| [LTK transactional refactoring (P14)](https://www.eclipse.org/articles/Article-LTK/ltk.html) | Conditions, coordinated changes, validation and undo | Exact crash/publication semantics vary; not completely verified in this review | Batch/abort/undo alone does not establish ALVA originality. |
| [OCC (P15)](https://www.eecs.harvard.edu/~htk/publication/1981-tods-kung-robinson.pdf) | Validate candidate against concurrent state before publication | ALVA graph identity is domain-specific; generic conflict rejection is mature | C must beat correctly implemented OCC, not an unprotected writer. |
| [Git CAS / CI (P16)](https://git-scm.com/docs/git-update-ref) | Immutable object identity, expected-old ref update, coordinated ref transactions; required checks via branch policy | Must bind check, candidate, environment and target ref; CAS alone does not validate behavior | Strong source baseline can express the tested P38 decisions and version binding. |
| [PCC (P17)](https://people.eecs.berkeley.edu/~necula/pcc.html) | Consumer checks producer-supplied proof against safety policy | Evidence logs are not proofs. Full proof-carrying-change literature coverage UNKNOWN | “Proof-carrying” is prohibited for current AEC. |
| [Term graph rewriting (P18)](https://pure.york.ac.uk/portal/en/publications/term-graph-rewriting/) | Shared-subexpression representation and graph-rewrite semantics are longstanding | Agent selecting node vs occurrence can produce practical errors; full chapter algorithms not audited | P33 is a concrete implementation case, not discovery that DAG sharing exists. B needs novel empirical question, not generic path-copy. |
| [Verified Tool Calls (P19)](https://arxiv.org/abs/2608.02645) | Postcondition checks, idempotency and verify-before-retry under ambiguous failure | Coding-target attachment/publication lineage is more specific; not yet shown absent there | Broad tool-result semantics/recovery claims collide. Do not restart that line under another acronym. |
| [Callability / AFT (P20)](https://arxiv.org/abs/2608.23628v2) | Operational state and controlled fixed-backend interface intervention | Coding-specific connected-state evidence may matter; novelty remains uncertain without full artifact comparison | D must exceed ordinary lifecycle trace reconciliation or be a replication/case study. |
| [FixedBench (P21)](https://arxiv.org/abs/2605.07769) | No-change-needed coding tasks / action calibration | A no-op commit with an unsatisfied requirement is a different case, not intrinsically a failure | Never define “nonempty patch” as task success or all no-ops as bad. |
| [tau-bench (P22)](https://arxiv.org/abs/2406.12045) / [agent process evaluation (P23)](https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-evaluators/agent-evaluators) | State-grounded completion and call/argument/process metrics already exist | Mapping a permitted coding treatment to actually connected/published target and evaluator revision is a narrower measurement candidate | The four-layer distinction alone is not a new evaluation theory. |

## Coverage of the eight requested failure classes

| Question | Existing answer / collision | Remaining ALVA evidence and uncertainty |
| --- | --- | --- |
| Intent versus actual edit location | Selectors, AST differencing, typed recipes, trusted diff scope | P33/P34 quantify one actual mismatch and block it. General intent inference not solved or authorized. |
| DAG-sharing propagation | Term/graph rewrite theory and explicit occurrence/path selection | P33 identifies actual map mutation/rebuild, P35/P36 show safe composition; arbitrary-DAG locality still UNKNOWN. |
| Allowed tool but unauthorized program effect | Privilege control solves invocation, tests/contracts constrain outputs | P38 C1 separates these but strong source tests detect it too. No observed new capability. |
| Checked version not published version | Git CAS, CI candidate checks, OCC | AIR also supplies identity. No controlled ALVA-over-Git advantage demonstrated. |
| Available but unusable semantics | ACI, CodeStruct, Serena; interface/operation usability | P24 unavailable surface vs P26 discovery vs P32 completion are distinct actual observations. |
| Structured operations cost more / fail | Existing interface studies and ALVA censored developmental observations | Cannot infer composition caused failure from cumulative token stops or cross-task comparisons. |
| Impact soundness / false positives / UNKNOWN | Slicing, impact analysis, static analysis; finite dynamic testing | P38 collector covers only admitted closed fixtures. Heterogeneous effects must remain unknown, not ranked into certainty. |
| Multiple writers and validation consistency | OCC, transactions, CAS/check binding | Native stale rejection is not recovery success. No new multi-agent experiment or blanket serialization claim. |

## Novelty disposition

No production mechanism is presently justified by a demonstrated comparative
gap. The least costly remaining question is **whether coding-treatment
realization is mismeasured by existing call-level evidence, even after a strong
state-aware baseline is used**. That hypothesis is HYPOTHESIZED, with serious
collision from P19/P20/P22/P23. It should first face a no-new-model measurement
test, not a new effect ledger, language, recovery wrapper, or task calibration.
If the strong baseline is sufficient, publish bounded lessons or stop; do not
weaken it until an advantage appears.
