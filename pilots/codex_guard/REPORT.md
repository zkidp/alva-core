# P3 exploratory pilot: executed, but equal-budget comparison invalid

**Status: EXECUTED_12_WITH_COMMON_HOST_BUDGET_DEFECT.** No more model tasks
will run. The frozen batch driver is retained as evidence, **not a safe template
for another pilot**. Do not rerun it or regenerate its started slots.

## Essential incident disclosure

Post-closure accounting found that the frozen driver sent `turn/interrupt` with
`threadId` but omitted required `turnId`, and did not check the JSON-RPC error
response. A same-host, zero-generation reproduction returned:

```text
-32600: Invalid request: missing field `turnId`
```

The raw `TOKEN_OBSERVATION_LIMIT` field means the driver observed the threshold,
not that Codex was successfully interrupted. Ten turns subsequently emitted
natural `completed` notifications; two emitted no terminal notification before
the driver's grace period and host closure. Last reported tokens range from
126,523 to 381,091, against a 120,000 observation threshold. This is more than
the predeclared limitation of an in-flight request overshooting a valid
interruption: the interruption request itself was invalid.

This newly identified common host defect was discovered after all twelve
positions had run. No input, budget, result or frozen driver was rewritten;
no task was retried or replaced. See [incident](results/INCIDENT-01.json).
The record **cannot support a strict equal-budget treatment comparison or a
causal cost/utility estimate**. CI passing below validates reproduction and
disclosure, not the scientific validity of the failed budget controller.

## Engineering facts and executed observations

- Freeze `ace28282bd6780172d1d2ce753ab6b099636ac01` was committed/pushed before
  any pilot generation. Its JSON SHA256 remains
  `3cc95085554b92e649c7bd5730bc03d7e068f39ea68210e026701ed75306ccb4`.
- All 12 actual prepared input/policy/candidate positions passed no-model host
  access checks. P1/P2 code and historical frozen artifacts remain unchanged.
- Twelve fresh Codex turns were started sequentially using `gpt-5.6-sol`, low
  reasoning, OpenAI. There were no replacement turns or extra tasks. Provider
  request count is not available; a turn is not one provider request.
- The independent terminal evaluator ran real Python code in fresh host copies,
  with the original protected evaluator. Final source passed task and focused
  regression checks for A 6/6 and B 6/6. No scope violations, source writes or
  candidate Git commits were observed. This is **focused-check correctness**,
  not complete upstream conformance or an agent-claimed result.
- All six B tasks consumed Guard, with 8 verify and 9 report calls. Final Guard
  evidence was PASS/CURRENT and matched the current candidate in all six.
  Every observed Guard invocation returned PASS, so it did not catch a new
  functional error missed by the same tests in this sample.

## Per-task paired record (not a controlled effect estimate)

Every row's final task and regression checks passed in both arms.
Tokens include cached input; no cached tokens were subtracted.

| Task | A/B task completion | A tool items | B tool items (Guard calls) | A last-reported tokens | B last-reported tokens | A/B elapsed seconds |
|---|---:|---:|---:|---:|---:|---:|
| CACHE-EXPIRY-ERROR | PASS / PASS | 5 | 12 (4) | 133,540 | 243,483* | 47.708 / 60.329 |
| CACHE-EXPIRE-RESULT | PASS / PASS | 6 | 6 (2) | 157,116 | 126,523 | 41.891 / 29.094 |
| BOLTONS-EXPORTS | PASS / PASS | 9 | 10 (3) | 197,945* | 381,091 | 79.790 / 50.607 |
| BOLTONS-NAIVE-EPOCH | PASS / PASS | 9 | 9 (4) | 213,769 | 223,227 | 48.446 / 50.258 |
| ITER-WEIGHTED-EMPTY | PASS / PASS | 5 | 7 (2) | 143,249 | 154,758 | 44.315 / 47.826 |
| ITER-ADJACENT-IDENTITY | PASS / PASS | 8 | 11 (2) | 164,013 | 265,535 | 47.464 / 57.531 |

*No terminal notification observed; usage is the last available report, not a
guaranteed final invoice. That uncertainty is retained in every affected row.

Descriptive recorded totals: A 42 tool items, 1,009,632 last-reported tokens,
309.614 seconds; B 55 tool items, 1,394,617 last-reported tokens, 295.645 seconds.
These totals combine actual observed usage but include two potentially incomplete
usage records and invalid budget enforcement. **Do not interpret the differences
as Guard's causal token overhead or a speed improvement.** Dollar cost is null:
the subscription host provides no attributable per-task invoice. Missing cost
is not zero. Full input/cached/output accounting is in
[derived analysis](results/analysis.json); raw per-slot results are preserved.

## Extra detection and evidence binding

The same public assertions are available to A/B. Guard's successful reuse of
them is not extra behavioral knowledge, and all final candidates were at the
focused-check ceiling. No correctness gain or additional functional-defect
detection is demonstrated. There were no observed false rejections among these
six correct matching B candidates; this does not establish sensitivity or
false-rejection rates for failing, unsupported or stale candidates.

The separate [zero-model cases](DETERMINISTIC.json) show explicit source STALE,
candidate/evidence mismatch and protected-file rejection. Native Git/hashes can
also detect the respective changes, and the protected path was visible in
ordinary Git diff. Guard automates policy/evidence linkage; these cases do not
establish unique test power or count as agent-correctness wins.

## Supported and unsupported conclusions

Supported: existing P2 can be used by Codex on these real upstream-derived
Python maintenance slices and retain bound evidence without applying changes
to original source. Its deterministic evidence checks work in the tested
scenarios. Ordinary Codex/Git/tests also produced passing final code here.

Unsupported: statistically significant success, generalized agent-correctness
gain, a valid equal-budget performance/cost contrast, isolated causality from
Guard, voluntary default adoption, arbitrary Python safety or whole-project
correctness. Guard usage was explicitly requested in B. Small convenience
sampling, focused public checks, historical/public-task familiarity, shared
host configuration and trusted-local execution further limit interpretation.

Codex assisted development and analysis; “zero-model” describes deterministic
checks without task generation, not a claim of model-free development.

## Reproduction and stopping boundary

The final 12 native patches are published next to their result JSON. Zero-model
CI applies them to the frozen inputs and reruns the independent evaluator, plus
the original baseline and deterministic cases. Frozen fixture bytes remain exact
on Linux/Windows. Reused P1/P2 text uses platform checkout line endings; CI
reconstructs only LF/CRLF representations to match the frozen Windows execution
hash without altering any actual execution input. The initial Linux raw-byte
comparison failure is preserved in CI history and does not imply a different
executed treatment.

Raw app-server inputs, filtered tool records, final source and Guard/evaluator
evidence remain in the host-local archive. No credentials, raw reasoning or
provider transport were copied. [Archive manifest](results/archive-manifest.json)
binds the archive by SHA256; per-slot JSON also binds individual files. Public
patches are code artifacts, not raw agent transcripts.

Model execution is stopped. No repaired-budget rerun, replacement pilot, new
mechanism, replication or history rewrite is authorized by this closure. Any
future correction/re-study needs explicit new scope; this record is not rescued
by relabeling its resource limits after observing outcomes.
