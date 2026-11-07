# Compact DeepSeek diagnostic: NO_EXPLORATORY_FAVORABLE_SIGNAL

8 November 2026. All 16 registered fresh model sessions completed as scheduled,
with no infrastructure hold, slot replacement, extra user turn, operator repair
or replay. This is the independently registered DeepSeek variant, not a rescore
or continuation of the GPT study. Requested/reported model: deepseek-flash,
catalogue name DeepSeek-V4.1-Flash, thinking enabled, low effort.

## Results

| Endpoint | Text | Compact Native |
| --- | ---: | ---: |
| Correct authorized completions | 6 / 8 | 7 / 8 |
| Ordinary token-observation interruptions | 2 | 1 |
| Cumulative reported total tokens, all eight slots | 1,837,434 | 1,765,717 |
| Input, including cached input | 1,784,807 | 1,724,035 |
| Cached input (subset of input) | 1,682,432 | 1,625,856 |
| Output, including reasoning | 52,627 | 41,682 |
| Reasoning output (subset of output) | 30,968 | 26,027 |
| Submitted HTTP chat-completion attempts | 127 | 129 |
| Total-token median, six both-success pairs | 93,740.5 | 144,671.5 |
| Model tool-call median, six both-success pairs | 14.5 | 18.5 |
| Active seconds median, all eight slots | 31.02 | 37.71 |
| Setup seconds median | 2.19 | 2.69 |
| Finalization seconds median | 6.42 | 6.49 |

The prespecified endpoint is **median per-pair N/T reported-token ratio**,
which is **1.50955** across six both-success pairs. Native used about 51% more
reported tokens by this statistic, rather than the required 25% reduction
(ratio <=0.75). It meets the non-lower completion-count condition and minimum
four-pair condition, but fails the token screen. The ratio of arm medians is a
different statistic and does not replace the registered endpoint.

Across the whole batch Native used about 3.9% fewer reported tokens and completed
one additional task. This is a descriptive cost/completion observation worth
retaining, not an alternate passing criterion selected after results. Text's
two expensive XML failures consume 1,231,389 tokens; Native's single failure
consumes 621,505. Both the all-outcome and survivor-conditioned views matter.
Reported totals include cached input and are not dollar costs. Upstream
generation-request counts and dollar costs remain null; 256 submitted HTTP
attempts are directly observed. Input-token-count API calls = 0.

| Known task | Text correct / 2 | Native correct / 2 |
| --- | ---: | ---: |
| MM01 record maintenance | 2 | 2 |
| MM02 original shared prefix parser | 2 | 2 |
| MM04 graph/error completeness | 2 | 2 |
| MM07 XML escaping | 0 | 1 |

MM07 r2 supplies the one discordant completion: Native passes, Text does not.
MM07 r1 fails in both conditions. This single author-familiar task and two
repetitions cannot establish a general reliability advantage. The six successful
paired token ratios are 1.9114, 1.1077, 3.3102, 0.7521, 2.1925 and 0.9540.
Native is lower in two, higher in four. No cross-provider inference from the
historical GPT ratio of 2.93 to this ratio of 1.51 is valid: model, task subset,
transport and workbench changed.

## Actual completion and failure evidence

All seven successful Native sessions have an actual AIR commit, fresh-process
authority matching the receipt, changed authorized target, unchanged protected
body/metadata structure, and independently executed task/regression PASS. All
six successful Text candidates meet the same final structural and behavioral
policy on source authority. Tests bind to exact final snapshot digests.

The P34 collector is used for baseline/final scope evidence in both arms, as
registered. There is **no asymmetric live P34 commit interception** in this
disposable comparison. Do not call these seven Guard-mediated production commits
or substitute them for P36's older success conditions.

The three failures are ordinary observation-limit outcomes, not provider faults:

- Text MM07 r2: 628,552 tokens; final source fails checking. Scope structure is
  readable and authorized, but independent task/regression checks fail.
- Text MM07 r1: 602,837 tokens; final source fails checking and its final
  declaration snapshot cannot be verified. This is not a successful candidate.
- Native MM07 r1: 621,505 tokens; no AIR commit, final authority unchanged,
  original regression PASS and new task TEST_FAIL. Twenty-four body replacement
  attempts include fourteen semantic rejections, eight parse rejections, one
  invariant rejection and one accepted changed staging revision. That staging
  is not an independently verified or published success. It was discarded on
  close; no operator connected, tested, committed or rescued it afterwards.

The token threshold is an observation boundary, not a hard provider cap;
overshoot is retained. No session was replaced or extended. API responses report
one model ID and one system fingerprint throughout; that is not proof of
immutable provider weights.

## What the remaining cost suggests

The post-run DIAGNOSIS.json is descriptive and changes no screen. In the same
six both-success pairs, Text receives ten provider function schemas (4,281
serialized JSON UTF-8 bytes); Native receives eight shared study functions plus
nine Native functions, seventeen in total (7,978 bytes). Nine Native tools does
not mean only nine functions in the complete provider prompt.

Native's median is 18.5 tool observations / 13 HTTP requests, versus Text's
14.5 / 10.5. Six Native successes involve six begin, preview, transaction-check
and commit calls each: 24 transaction-workflow calls. There are also six
function reads and six body replacements. Text uses eight source edit calls
over the matched set. Documentation calls are similar (Native 25, Text 24).
This supports reducing exposed workflow/schema burden before buying more
trials. It does not allocate provider tokens exactly to those components.

Native admission errors and source compiler failures are not the same metric:
the mutation rejects invalid staged bodies atomically, whereas Text can retain
invalid source between checks. The new body editor also checks declared return
compatibility, omitted by legacy project checking. This is a real bundle
difference, not evidence of an irreplaceable AIR property or of superiority over
an equally equipped source/AST editor. Both arms use identical final assertions.

Host Guard inspection RPCs are not individually retained by the reused
collector; total backend call count is unavailable. Full model-dispatch Native
wire receipts, structural snapshots and evaluation receipts are retained.
Setup/finalization timing is reported so trusted processing is not described
as free. Fine-grained CPU/memory costs and category-specific provider tokens
remain unmeasured.

## Registration, validation and boundary

Design/runtime commit before generation:
`ca111b863f5190668c7ba0ee376cfb0d6853dea5`.
Execution freeze commit before generation:
`210897cc72132795a81f366c9e300f9dd4be1f93`.
Freeze file SHA256:
`f0951cb294b052f180c6637f7609bd0edd88fdcf6a0c3859697b4def7dee7afa`.
Eight real T/N no-model preflight routes pass before freezing. Initial preparation
faults are disclosed in ATTEMPTS.md; no formal model slot was used for them.

VALIDATION.json checks all sixteen original records, reconstructed exact request
payload hashes, raw usage accumulation, cache inclusion, actual publications,
scope, independent receipt binding and cleanup. It is a separate post-run check
path, not an independent human-authored oracle. All 166 frozen Python source
files and full SDK trees remain unchanged. Ephemeral transport keys were revoked
and removed after all owned-process cleanup acknowledgments.

ARCHIVES.json binds controlled local raw model, exact runtime-byte and preparation
archives. Raw transcripts/reasoning, API keys, account data and machine connection
configuration are not published. The executable CLI/AppServer from the old GPT
study is not involved. Candidate execution remains Linux-isolated; Python runtime
tests run on Windows/Linux CI without model calls.

Analysis/diagnosis, evidence validation and safe_entry additions made after the
batch are explicitly post-run. They do not alter the frozen runner, original
records or endpoint. The frozen runner reserved only its output directory;
safe_entry adds an exclusive per-freeze reservation and refuses this consumed
freeze, preventing accidental alternate-directory replay. It is not retroactively
claimed to have guarded the completed run.

The evidence supports a narrow completion observation and identifies continuing
Native overhead. It does not establish the registered efficiency advantage,
general product superiority, statistical significance, ALVA language superiority,
or an advantage over CodeStruct. Next work should simplify Host-managed editing
workflow and profile-aware guidance, then preregister any new comparison. No
additional model trial or Core/Skill change is performed in this closeout.
