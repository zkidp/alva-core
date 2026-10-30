# Same-candidate baseline comparison

Primary wave: [41117034325](https://github.com/zkidp/alva-core/actions/runs/41117034325),
code `3bb65c0f2abd9ab915d87dcabefe907927a3091a`. Registration:
`4fe0edceae8721f808e750c2dca266417d92ee98`. Four of four cases executed.
The machine-readable record is BASELINE-COMPARISON.json. Every Text candidate
has the same inspected function bodies as the actual staged Native candidate;
all recorded Text/Native sample observations agree.

| Case / fixed policy oracle | A: strong source diff + tests | B: structural scope + ordinary tests | C: actual P34 | D: AEC |
| --- | --- | --- | --- | --- |
| C1 protected caller regression: REJECT | REJECT | REJECT | ALLOW | REJECT |
| C2 permitted caller change: ALLOW | ALLOW | ALLOW | ALLOW | ALLOW |
| C3 unauthorized shared propagation: REJECT | REJECT | REJECT | REJECT | REJECT |
| C4 proof absent: UNKNOWN | UNKNOWN | ALLOW | ALLOW | UNKNOWN |

| Metric (4 cases, descriptive only) | A | B | C | D |
| --- | --- | --- | --- | --- |
| Exact policy-oracle decisions | 4 | 3 | 2 | 4 |
| Confirmed-invalid candidates allowed | 0 | 0 | 1 | 0 |
| Legitimate case falsely rejected | 0 | 0 | 0 | 0 |
| UNKNOWN | 1 | 0 | 0 | 1 |
| Proof-insufficient candidate allowed | 0 | 1 | 1 | 0 |
| Actual guarded publications | n/a | n/a | 3 | n/a |
| Actual publications violating confirmed stronger intent | n/a | n/a | 1 | n/a |

A/B/D are policy decision simulations. Their zero invalid allows must not be
reported as zero observed unauthorized *publications* by deployed gates. C
actually dispatches three Native commits; C3 dispatches zero, retains the
baseline authority and passes fresh baseline evaluation. Four additional
unguarded quarantine commits exist solely to obtain candidate observations;
they are not behavior-authorized final publications. All experiments are
disposable synthetic research programs.

## Case evidence and interpretation

- **C1:** Only `aec.c1.adjust` changes structurally, from `x+1` to `x+2`.
  `exposed`'s body stays identical but its call to `adjust` changes its return
  at input 0 from 1 to 2, contrary to the protected required value 1. Actual
  P34 returns SCOPE_ALLOWED, Native commits, AIR publishes, and a fresh process
  agrees with staging. Independent evaluation of that authority is TEST_FAIL.
  This is P34's defined scope, not a bypass or faulty Guard. A and B detect
  the same assertion failure as D with the same tests.
- **C2:** The same arithmetic edit now explicitly permits `exposed` to change.
  At 0 both target and caller return 2; protected `stable(0)` stays 100. Caller
  reachability and actual changed observations do not cause D to reject.
  Actual Guard commit, fresh AIR and independent tests all pass.
- **C3:** New `left` and `right` functions initially share their anonymous
  body block. Replacing its step with literal 2 changes both real body roots.
  Only `left` is structurally authorized. Guard returns SCOPE_VIOLATION,
  makes no underlying commit dispatch, publishes no AIR, and a fresh process
  sees unchanged baseline roots. Quarantine proves the candidate itself is
  executable; Text explicitly edits both functions to give the same candidate.
  The sample expectations describe the candidate outputs, not permission to
  edit `right`. Its unauthorized body change alone requires REJECT.
- **C4:** `adjust` changes from `x+0` to `x`; protected caller samples agree.
  The policy requires a checked proof of universal equivalence. No proof
  checker/artifact exists in this experiment, so A/D return UNKNOWN. This
  deliberately simple rewrite is not evidence of a difficult or impossible
  equivalence problem. B/C do not implement evidence-strength gating; adding
  that ordinary policy rule to B would make it agree with A/D. C commits and
  fresh independent tests pass, which is insufficient for the stronger policy.

For C1/C2/C4, direct-call closure includes the target and `exposed`; unchanged
`stable` is absent. C3 has no call edges; its actual two-root structural
change is distinct from dependency propagation. Shared primitive/ref nodes
exist in other cases without creating a violation. All actual roots, metadata,
preview_semantic_diff, check_transaction, Guard records, fresh revisions and
observations are in the JSON; full public-tool calls are retained in archives.

## Evidence parity and limitations

All baselines get every registered sample, invariant, trusted authorization
and evidence-strength requirement. A uses exact public source bytes and a
body-region source checker independent of AIR. It receives the same check,
build and behavior coverage. D does not get a hidden oracle. A and D share a
small policy truth function intentionally: this tests whether extra AIR and
dependency evidence adds decisions beyond that strong composition, not whether
one can hand-code a worse source policy. The independent oracle is loaded only
after all mechanism decisions.

B includes structural scope and all ordinary tests; its difference on C4 is
the absence of proof-strength enforcement, not an intrinsic defect of
structural editing. C's real implementation consumes structural evidence only;
test evidence is available to the study but adding a behavioral gate would
change the baseline mechanism. No existing key test was withheld from A/B.

The source checker supports only these frozen, comment-free, one-line-body
fixtures and returns UNKNOWN for unsupported parsing. D's direct-call analysis
likewise supports a closed, single-module subset. Neither is a production
analyzer. No dynamic calls, I/O, concurrency, adversarial collector or broad
maintenance distribution is covered. Outcomes do not establish statistical
reliability, semantic soundness or model ability.

## Runtime cost

Primary complete acquisition/evaluation times: C1 8.317 s, C2 7.223 s,
C3 7.196 s, C4 7.214 s (29.950 s total), excluding SDK build/setup. Each
includes separate source/AIR inspection, two Native candidate replays and
four isolated check/build/test evaluations. Decision-combiner times are below
0.004 ms in this run and too small for a speed claim. C's commit measurement
includes Guard inspection, transport and possible publication; it is not a
pure Guard CPU measurement. Incremental end-to-end D-versus-A overhead is null:
evidence acquisition is shared and was not randomized or separately allocated.

The first wave emitted a Python unified source diff, while authorization used
the complete source comparison. A subsequent conformance improvement captures
an actual `git diff --no-index`, verifies complete Text/Native metadata as well
as roots, and times source/structural/impact analyses separately. It does not
change registered cases, policies, tests or verdict logic. The primary wave is
retained, not replaced; subsequent CI artifacts provide those additional
measurements. No favorable runtime or architecture claim follows from them.
