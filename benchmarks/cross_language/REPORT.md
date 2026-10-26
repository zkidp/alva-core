# Cross-language coding pilot: closed, descriptive only

Twelve predeclared fresh model tasks were executed exactly once, with no
replacement, retry turn or additional task. **Python 4/4; ALVA Text 1/4;
ALVA AEP 0/4.** These are results of this small adapted-task workflow, not
language superiority or an official benchmark score. No follow-up run is started.

## Frozen methods and evidence

Base: verified PR #20 `7ca5f44e8c4b01d24c416cef838c429f79046345`, stacked above
P0-P2. Main remains `cd73ae8c653953289ee758ce24e4821f1b4c5108`; no PR was merged.
Freeze commit `8b31682c322a47ccd4fb3855198d541fd51a2085` was pushed **before**
the first task. [FREEZE.json](FREEZE.json) binds actual twelve input files,
templates, reference/vector code, tool surface, controller/runtime, binary,
configuration and seeded random order. Its bound files remain unchanged.

[Selection](SELECTION.md) fixed four different operation features before any
model outcome. Public HumanEval IDs 3, 23, 41, 42 come from
[OpenAI's MIT-licensed source](https://github.com/openai/human-eval/tree/b9453e8f1865df0a0057a1383767caa400acfbcf).
[Provenance](PROVENANCE.json) and [license](HUMANEVAL-LICENSE.txt) retain attribution.
Natural-language requirements were adapted to bounded i64/list inputs and
ASCII string length, with `solve` as the common entry point. This is not
MultiPL-E's official translation or scoring pipeline. [Qualification](QUALIFICATION.json)
proved all four domains executable in all arms: initial compiling stubs fail
task tests, independently implemented references pass. The
[preparation log](PREPARATION.md) retains unsupported vector-fold construction
and naming/type affordance limitations; no Core feature was added or task replaced.

Model: `gpt-5.6-sol`, OpenAI, low reasoning, Codex CLI
`0.163.0-alpha.11.2`, Windows/Python 3.14. Actual thread identities matched the
same configured model/provider in all twelve slots; no rerouting was observed.
The service alias does not attest an undisclosed immutable weight snapshot.
One Codex turn is not one provider request. Provider generation-request count
and attributable dollar cost are unavailable and remain null.

Each task received the same demand and equivalent default-return stub. A/B
could read/edit/check/test through a common host-owned bridge; C could read
and use public CLI AEP operations/staging/check/commit but not edit source.
All tests use the same frozen typed vectors. Python executes the candidate;
ALVA check/build generates real Rust and host-owned assertions execute it.
No agent PASS claim, source-literal oracle, cross-session patch or reference
answer is used as ground truth. References and evaluator implementation are
outside the allowed model tool surface. All candidates were disposable and
no canonical application/source was edited.

**Tool delivery limit:** C used a thin JSON request bridge to the real AEP
process, not individually advertised MCP operation schemas or the installed
native ALVA Skill. Its prompt named broad steps and only a few operations;
the model had to discover names/arguments. B received its stub but no language
manual/primer. Those are material onboarding conditions, not an estimate of
all possible Codex/ALVA integrations. Existing Codex transport was reused;
P3's driver was not. No shell/network/delegation items were observed.

## Per-task results: keep the two comparisons separate

| Adapted HumanEval task | Feature | A Python | B ALVA Text | C ALVA AEP |
|---|---|---|---|---|
| 41 | Collision-count arithmetic | PASS | COMPILE_FAIL | NO_COMMITTED_CANDIDATE |
| 23 | ASCII string length | PASS | PASS | NO_COMMITTED_CANDIDATE |
| 42 | Ordered integer-list increment | PASS | COMPILE_FAIL | NO_COMMITTED_CANDIDATE |
| 3 | Negative running-prefix balance | PASS | COMPILE_FAIL | NO_COMMITTED_CANDIDATE |

**Python vs ALVA Text:** Python passed four tasks, with one accepted edit and
one model-directed test per task. Text passed ASCII length and failed parsing
on the other three. Final diagnostics included unknown `var`/`binary` expression
tags and an invalid call form. Text made 17 accepted source edits in total,
with repeated checks before observation-budget interruption. This is observed
construction/repair behavior under this onboarding and budget, not intrinsic
language causality or a conclusion about arbitrary Python/ALVA programs.

**ALVA Text vs ALVA AEP:** no AEP candidate reached a successful commit (indeed,
no commit request was made). All four opened native transactions. Trace records
show repeated guessed operation names (`discovery`, `discover`, `list_tools`),
missing/wrong argument fields, and some successful inspection/schema calls.
One empty create_call request created a detached call node; it was neither
attached to solve nor committed. This is not four behaviorally wrong committed
programs, nor evidence that AEP cannot express the tasks: qualification already
executed supported witnesses. Terminal tests on the still-original source stubs
fail; no post-commit semantic-control benefit was exercised by these model runs.
The end-to-end bridge workflow showed **no incremental completion signal**;
effects conditional on successful staging/commit remain unevaluated.

Oracle limitation disclosed at closure: the frozen Python comparator checks
top-level return type plus value equality, not recursive list-element types
(Python equates bool/int leaves). A read-only audit of the already captured
final outputs confirms exact recursive types/values for every A vector, so no
observed score changes. The evaluator/tests were not repaired or rerun to obtain
this result; broader type-confusion sensitivity is not established.

[ANALYSIS.json](ANALYSIS.json) reports every task/arm, first mutation callback
ordinal, edit counts, AEP operation outcomes/rejections, checks/tests and
termination. Callback ordinals are not provider generation ordinals. Filtered
tool arguments/results and native AEP traces are preserved in the local archive,
not inferred from final status or hidden reasoning. No psychological intent is
assigned to the model. Published `.alva` files for C are explicitly unchanged
source projections, not an invented committed final program.

## Resource and stop accounting

| Condition | Last-reported total tokens | Study callbacks | Observed active-turn seconds |
|---|---:|---:|---:|
| A | 220,786 | 20 | 51.504 |
| B | 524,350 | 44 | 146.417 |
| C | 515,449 | 84 | 102.785 |

Input/cached/output breakdowns are retained per slot; cached input is **not
subtracted**. Host-reported totals are not invoices. The active-loop clock
includes tool work but not all process/thread setup or terminal host evaluation.
Rust build/check overhead differs from Python and is not normalized away.

Each slot had a 480-second observation deadline, 80-callback ceiling and
120,000 total-token observation threshold. These are not hard provider token
or wall caps. All four A turns completed naturally; all eight B/C turns reached
the token threshold and were interrupted. Last totals for those eight range
124,544-133,447: in-flight/notification overshoot was predeclared, not hidden.
All eight interrupt RPCs were acknowledged and all twelve terminal notifications
confirmed. Missing usage would remain null/incomplete; none was missing here.
Host terminal confirmation does not establish provider-invoice completeness.
No wall/tool ceiling was the terminal cause. Budget censoring limits interpretation
of the failed repair/discovery trajectories; there is no claim an extra turn
would have succeeded. Observed costs are not statistically estimated causal effects.

[PREFLIGHT.json](PREFLIGHT.json) records zero-generation simulated ID binding,
RPC-error, terminal, duplicate and missing-usage checks, plus actual no-generation
host identity/error handling. [VALIDATION.json](VALIDATION.json) reports twelve
closed positions, intact frozen files, no common-infrastructure HOLD, and zero
replacement slots. All twelve published final-code dispositions were reproduced
locally by [replay.py](replay.py), without generation. CI separately replays them
on Linux/Windows; read the PR checks for the actual platform conclusions.

## Reproduce and stop

```text
cargo build --locked --manifest-path alva/Cargo.toml
python -m unittest discover -s benchmarks/cross_language -p test_controller.py -v
python benchmarks/cross_language/replay.py alva/target/debug/alva
```

Use `.exe` on Windows. The script runs saved final code with frozen tests, not
another model task. [RESULTS.json](RESULTS.json) contains terminal scoring and
[ARCHIVE.json](ARCHIVE.json) binds local filtered input/tool/output/authority
evidence by SHA256. Raw reasoning, credentials, user environment values and
private provider transport were not archived. The original private runtime is
retained; the exclusive execution ledger refuses another batch start.

This convenience sample consists of very public, small tasks with strong
pretraining-contamination/familiarity risk, restricted domains and finite tests.
There is one run per cell, no inferential statistics, no official benchmark
score and no general language-superiority claim. It demonstrates this model's
observed behavior in the frozen workflows, not ALVA's theoretical capability
or a controlled estimate of semantics after adoption. No tests, task inputs,
Core implementation or historical P0-P3 freeze was rewritten after outcomes.
Codex assisted adaptation/development; this is not model-free development.

The authorized pilot is closed. No rerun, replacement, automatic replication,
task addition, onboarding optimization, language change or merge follows.
