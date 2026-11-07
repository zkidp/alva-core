# Host V3 model cost acceptance: partial acceptance

8 November 2026. **V3 passes the predeclared cost screen against V2. It does
not pass the stricter screen against the matched Text proposal control.**
All three conditions succeed on all four tasks. The observed direction is
favorable to V3 in every task/contrast, but the Text comparison falls short of
the declared 25% median reduction requirement. Its disposition is retained;
the cutoff is not changed after observing results.

## Registered run and outcomes

Implementation base: `53539ec4b0471f53b8732cecf066dc84b78cb680`.
Protocol/runtime registration: `09971145cf007043cee9763687edeb218a1a18e2`.
Freeze commit `7b85c651df0de3d7656cc41726ab76c054b44c0f` precedes all model
generation. Freeze SHA256:
`db9983df71909f92eff850a89405c5fc02314e022c8a717f7f7e80d99902e785`.

The [protocol](PROTOCOL.md) fixes twelve fresh conversations: four original
tasks, one T/V2/V3 slot each, pair ordering balanced 2:2. Model is requested
and reported `deepseek-flash`, low reasoning effort, thinking enabled. All
12 slots are valid and independently correct; 54 completion HTTP attempts
return complete usage. No replacements, new user turns, operator repairs,
generation retries or post-result extra slots occur. Every model publishes
through the actual Guard and Native commit path. Independent task, regression,
scope, fresh AIR and cleanup checks pass in every slot, including original
MM02's shared graph and unchanged last-match delimiter regression.

T is the matched source-proposal Host described in the protocol. It submits
exact source edits; the trusted compiler/P34 checks the imported component and
attaches its target body to the same protected publication pipeline. It is
neither the historical ten-tool Text workbench nor a competitor reproduction.
V2/V3 share tool schemas and current compiler/SDK; V2 selects the earlier
serial/full-export/full-feedback configuration, V3 the optimized configuration.
All arms get the same initial source, public requirement, complete official
Skill and public reference access. Historical witnesses, evaluators and prior
model records are never supplied to the model.

| Task | T reported total | V2 reported total | V3 reported total | V3/V2 | V3/T |
| --- | ---: | ---: | ---: | ---: | ---: |
| MM01 | 31,399 | 36,822 | 30,760 | 0.8354 | 0.9796 |
| MM02 | 17,854 | 24,179 | 15,847 | 0.6554 | 0.8876 |
| MM04 | 34,781 | 24,222 | 23,892 | 0.9864 | 0.6869 |
| MM07 | 59,740 | 72,025 | 42,568 | 0.5910 | 0.7126 |

| Registered comparison | Both-success pairs | Median ratio | Observed median reduction | Required ratio | Disposition |
| --- | ---: | ---: | ---: | ---: | --- |
| V3 vs V2 | 4 | 0.74539 | **25.46%** | ≤0.90 | `EXPLORATORY_COST_ACCEPTANCE_PASS` |
| V3 vs T | 4 | 0.80007 | **19.99%** | ≤0.75 | `NO_EXPLORATORY_COST_ADVANTAGE` |

The second label denotes failure of the registered screen, not a claim that
the observed saving is zero. All success counts are 4/4, so no cheap failed
attempt is used to manufacture a cost reduction. With four paired observations
on known tasks, these are descriptive exploratory results, not significance or
generalization claims.

## Complete resource accounting

Values below sum all completion requests in each condition, including repair
and document-reading requests. Cached input stays inside reported total;
reasoning is a subset of output and is not added again.

| Condition | Success | HTTP completion attempts | Input | Cached input | Output | Reasoning output | Reported total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| T | 4/4 | 19 | 136,477 | 111,872 | 7,297 | 4,564 | 143,774 |
| V2 | 4/4 | 19 | 149,387 | 120,960 | 7,861 | 5,314 | 157,248 |
| V3 | 4/4 | 16 | 107,966 | 82,560 | 5,101 | 3,352 | 113,067 |

Aggregate total reduction is 28.10% vs V2 and 21.36% vs T; these aggregate
figures do not replace the preregistered paired-median screens. There are
12 model sessions, 54 submitted completion HTTP attempts and 414,089 reported
tokens overall. Upstream provider generation-request counts and attributable
dollar cost remain **null**. No token-count API calls were made. Cache pricing,
account attribution and provider-side work cannot be inferred from total tokens.

Active-time paired median V3/control ratios are 0.7630 vs V2 and 0.8147 vs T.
These timing observations are unreplicated and not acceptance criteria; one
task has V3 slightly slower than T. Setup and independent finalization times
are recorded separately. The public [results](RESULTS.json) include Host Native
calls/bytes/time, Guard reads, isolated evaluator commands and the additional
source-import/setup/final verification work, so Text's import costs are not
hidden. Backend counts are not model-tool counts or provider requests.

## What explains the remaining variation

The [tool diagnostics](DIAGNOSTICS.json) show V3 needed one preparation on each
task with zero rejected tool calls. V2 needed seven preparations total, with
three rejections; T needed six with two rejections. Document reads also differ
even though access and initial Skill bytes are equal. MM07 dominates absolute
resource use. Thus the observed saving belongs to the complete interface
configuration and this set of fresh model behaviors. It cannot all be attributed
to batch RPC transport or a particular graph representation.

The earlier deterministic byte/RPC acceptance remains a separate result.
These real-model observations now support a narrower cost statement:
**on this four-task pilot, V3 preserved success and reduced reported total
tokens relative to the preceding Host configuration.** They do not establish
universal ALVA cost superiority or a dollar saving, and the Text comparison
has not passed its declared screen. Historical unfavorable model experiments
remain unchanged rather than being overwritten by this study.

## Evidence validation and reproducibility

The read-only post-run [validator](../../scripts/validate_host_v3_acceptance.py)
reconstructs all 54 request hashes from exact initial public inputs, frozen
schemas and unmodified tool continuations (including private reasoning).
It checks usage totals/categories, raw backend receipt hashes, all twelve
Native commits, matching passing staged-test receipts, final scope/authority,
original source projections and cleanup. Four tamper controls reject changed
initial inputs, cached subtraction, tool arguments and backend receipts.
[Validation](VALIDATION.json) passes; all 183 frozen Python files remain
byte-identical. Post-run SDK executable/runtime checks and full toolchain/
registry tree rehashes also match the pre-run freeze; see the
[post-run identity audit](POSTRUN-IDENTITY.json).

Raw provider thoughts, messages, tool arguments and evaluator stdout remain
private. The [archive manifest](ARCHIVES.json) publishes their hashes and byte
counts without those contents. No API key, SSH password, host configuration
or machine path is included. Post-run validator, safe entry and safety tests
are add-only postprocessing; no frozen generation runtime is edited.

CI exercises only the no-model runtime contract, twelve deterministic real
routes and Text scope-refusal control. It does not replay paid generations.
This study is consumed: the supported
`python -m benchmarks.host_v3_acceptance.safe_entry` entry rejects replay before
reading credentials or contacting a provider. The original frozen runner is
retained as historical evidence, not an instruction to rerun this freeze.

## Next decision

Retain V3 as the lower-overhead Host path. Further cost work should target
reference retrieval and repair rounds, with profile-specific useful context
instead of redundant document loading. A subsequent acceptance should use
previously unseen maintenance tasks, larger components and equal public-source
access on demand; this run supplied full original source up front to every arm.
That will test bounded semantic context as a product behavior without hiding
information from the comparator. Keep trusted scope and independent tests fixed,
declare budgets/criteria before generation and do not retune on these four tasks
until a desired number appears. No further model slot is launched here.
