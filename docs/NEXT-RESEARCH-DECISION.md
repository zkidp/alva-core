# P3 closeout and next research decision

Checked 2026-10-27. This is a decision from existing public code and frozen
evidence, not a new experiment. No model generation or input-count API calls,
historical gate reruns, implementation changes, or PR merges were performed.
Codex assisted this document; this is not model-free authorship.

## Engineering baseline and deterministic merge plan

Canonical `main`: `cd73ae8c653953289ee758ce24e4821f1b4c5108`.
All four PRs are OPEN and unmerged at this inspection; their displayed checks
pass. This records checks already run, not another acceptance audit.

| PR | Head | Current base | Role |
|---|---|---|---|
| [16](https://github.com/zkidp/alva-core/pull/16) | `b9bbaaa72cbfa3345683efa2b9f7ccbe272145d5` | `main` | P0 native integration acceptance/design |
| [17](https://github.com/zkidp/alva-core/pull/17) | `a83e94956c459e87bd489dd7a4efd4e43d6adf84` | `codex/codex-integration-p0-guard-design` | P1 Guard |
| [18](https://github.com/zkidp/alva-core/pull/18) | `7168a2346b9f3656e0f8d68fbee294d525a292a0` | `codex/python-guard-mvp` | P2 optional Codex workflow |
| [19](https://github.com/zkidp/alva-core/pull/19) | `d1691c4ab345fc25d605132c02b1fa1b5831c5d4` | `codex/python-guard-codex-integration` | P3 evidence, before this closeout document |

`merge-base(main, P0) == main`, `merge-base(P0, P1) == P0`, and
`merge-base(P1, P2) == P1`. Main/P2 left-right counts are 0/9:
P0 adds two commits, P1 four, P2 three. GitHub permits merge commits.
There is currently no independent main-side work to reconcile.

Owner-authorized sequence (a plan only; no merge/retarget performed):

1. Merge #16 into main using **Create a merge commit**, not squash/rebase.
2. Retarget #17 to main. Confirm its merge-base retains the exact P0 head and
   its effective diff contains only P1 changes, not P0 again. Let the relevant
   checks for the retargeted PR finish; then merge #17 with a merge commit.
3. Retarget #18 to main. Confirm the exact P1 head is an ancestor of main and
   its effective diff contains only P2 changes. After its relevant checks,
   merge #18 with a merge commit.
4. Retain dependent branches until children have been retargeted. Do not
   cherry-pick the stack, rewrite it, or squash parents and then merge unchanged
   children. If heads/main advance, inspect the actual new diff/conflicts rather
   than applying this recorded plan blindly.

Treat #19 separately: after P2 integration its base may be retargeted to main
for evidence-only review, preserving ancestry. It is not a dependency for shipping
P0/P1/P2 and must not be bundled as a successful equal-budget experiment.
The historical driver is explicitly not a reusable execution template.

## Established facts, and what they do not establish

**Python Guard / Evidence Control.** P1/P2 implement byte/path/policy-bound
snapshot, isolated exact patch verification, equivalent baseline/candidate
checks, and separate checks/applicability statuses. Original source is not an
apply target. Trusted policy ownership and host-enforced candidate write roots
are preconditions, not guarantees supplied by a policy hash alone.

[P3](../pilots/codex_guard/REPORT.md) executed exactly twelve fresh turns, with
no replacements. Independent final focused task/regression checks passed for
A 6/6 and B 6/6; all six B candidates consumed Guard and finished with matching
PASS/CURRENT evidence. This demonstrates operation on these maintenance slices,
not reliable autonomous discovery or a correctness gain. Every observed Guard
verification passed: no extra functional defect missed by the same tests was
detected. There were no observed false rejections among those correct candidates;
the sample does not establish a false-rejection rate.

The existing [deterministic cases](../pilots/codex_guard/DETERMINISTIC.json)
separately demonstrate source STALE, candidate/evidence mismatch and protected
file rejection, even where candidate tests pass. **Increment over bare test
exit codes:** explicit, automated linkage of results to approved inputs, patch,
policy and current applicability. **Overlap:** Git diff plus recomputed hashes
and a scope checker can detect those changes too. The evidence does not show
that an equivalently instrumented Git/tests workflow cannot do this, or that
Guard adds behavioral knowledge. Guard remains trusted-local, not a hostile-code
sandbox, semantic transaction system, or automatic source publisher.

P3's equal-budget contract is invalid. See
[P3-INCIDENT-01](../pilots/codex_guard/results/INCIDENT-01.json): the interrupt
request omitted `turnId` and its error was not handled. Preserve all twelve
slots, inputs and driver bytes. A **future separately authorized executor** must
use the active thread/turn IDs, handle RPC errors, confirm termination and retain
incomplete accounting explicitly; a threshold flag is not cancellation success.
No repair is made here. Observed token/time differences cannot establish causal
overhead, efficiency, or a controlled utility effect.

**ALVA native Semantic Control.** The current AEP/AIR implementation and
[P0 acceptance](codex-integration-p0.md) demonstrate the real Codex plugin/MCP
path: discovery, structured staged mutation, diff, check, commit, abort and
independent build checks. `alva/src/main.rs` checks the staged graph again at
commit and supplies its base hash to `air::write_authoritative`; MCP delegates
to that native interface. This is a program-state control boundary, unlike
Python Guard's read-only patch evidence. It is not a demonstrated agent benefit.
AIR authority and source projection are distinct; first semantic commit can
change authority. Do not claim atomic publication of all projected source files.

Missing evidence includes supported-operation coverage for useful maintenance,
legitimate repair paths through intermediate invalid states, end-to-end behavioral
closure, and whether discovery/transaction burden offsets any reduction in unsafe
actions. A check-valid graph or successful commit does not prove task intent.
P3 is Python evidence and cannot answer these native ALVA questions. No private
research material or closed historical hypotheses are imported or reopened here.

## Two falsifiable hypotheses and decisions

| Direction | One falsifiable key hypothesis | Recommendation |
|---|---|---|
| Python Guard / Evidence Control | Against a declared ordinary Codex/Git/tests workflow, Guard reduces **undetected use of stale, mismatched or out-of-scope check evidence**, without unacceptable false blocking, when both have the same tests and permissions. | **Retain optional engineering capability; defer another agent-effect study.** Existing evidence establishes linkage, not improved decisions or uniquely stronger detection. |
| Native Semantic Control | For a useful maintenance change already expressible through public AEP operations, structured checked staging prevents publication of an invalid/stale program state while preserving a legal path to the correct behavior that an equally checked source workflow can also attempt. | **Continue only bounded operation/task feasibility first; defer paid comparison and language expansion.** P0 proves connectivity, not coverage or utility. |

The Guard hypothesis is weakened or falsified if an explicitly matched native
hash/scope workflow catches the same events with comparable burden and no worse
false blocking, or if agents already avoid evidence misuse. Do not manufacture
such events and count them as ordinary task-correctness wins.

The native hypothesis fails for the chosen scope if the public operations cannot
express the intended edit/repair, publish invalid/stale state, or offer no safety
increment over the matched source path. Even successful deterministic safety
witnesses would not establish improved agent task completion.

## Minimum next scope (proposal, not execution authorization)

Prioritize engineering baseline integration by the owner, not another broad
agent pilot. For Guard, the remaining question is evidence consumption and
decision correctness, not adding more check formats: specify the ordinary
Git/tests comparator and an explicit hash/scope comparator before deciding
whether another model study is worth doing. Reuse the three P3 deterministic
cases as requirements; do not rerun passed gates or P3 slots.

For native ALVA, the smallest useful next node is one publicly specified,
non-W02 cross-module API evolution case, with an independent behavioral test
and a predeclared stale-base perturbation. Use only existing operations. Record
one executable structured path and one ordinary source/check path with the same
public facts, including the authority/materialization boundary. If unsupported,
report the gap and stop rather than implement a language feature to save the
hypothesis. This would be deterministic feasibility, **not** an agent experiment;
only a later explicit decision could authorize fresh matched model tasks.

No next node is started here. In particular, do not repair/reuse the frozen P3
driver, add P3 slots, or transfer another run's candidate as an agent hint.

## Unsupported promotion and paper conclusions

No agent-correctness gain, statistical superiority, causal cost reduction,
generalization across projects/models/languages, arbitrary Python semantic
safety, uniquely stronger tests, atomic source application, or automatic update
of installed integrations is established. P3 is engineering/observational
evidence with a disclosed invalid budget controller, not a successful controlled
experiment. No existing paper or frozen conclusion is changed by this decision.

Basis: the linked P0/P3 records, [P1 implementation](python-guard-implementation.md),
[P2 host evidence](python-guard-codex-evidence.md), the native
[workflow](../integrations/skills/alva/references/workflow.md), and read-only
inspection of `alva/src/main.rs`, `alva/src/aep.rs`, and `alva/src/mcp.rs`.
