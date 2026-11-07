# MIC-01 exploratory comparison — INCONCLUSIVE_PROVIDER_LIMIT

7 November 2026. **No ALVA superiority established.** This is a new exploratory
study, not a re-score of the paper's frozen cases. It submitted 24 logical
turn requests on six known tasks, with gpt-5.6-sol / low and a requested single
turn per slot. Upstream provider generation request counts and dollar costs
are unavailable. No input-token-counting API was used.

The request list ended, but scientific completion did not: slot 22 encountered
usageLimitExceeded mid-turn; slots 23/24 also failed at quota with zero tools
and no usage report. These three are UNKNOWN for interface inference, not
ordinary wrong solutions. The original controller failed to stop new launches
after the first common fault, submitting two further scheduled requests.
This is a disclosed protocol deviation and an implementation defect. No slots
were replaced, no prompts changed, no additional turns or accounts used.

There is an additional executable-identity limitation: initial CLI hash
matched the freeze, but after the batch the resolver points to a different
hash with the same version string; its original cache path is gone. No per-slot
executable stamps were collected. Within-run change is UNKNOWN; it is neither
asserted to have happened nor ruled out. SDK and 145 Python runtime bytes
remain matched. Thus even quota-unaffected pairs are descriptive evidence,
not a fully certified causal comparison.

## Descriptive observations, not a completed advantage test

Twenty-one slots have ordinary outcomes: seventeen correct completions and four
token-threshold interruptions. Ten task/repetition pairs have both outcomes
unaffected by quota. On those exact same ten pairs:

| Endpoint | Text workbench T | Native MCP N |
| --- | ---: | ---: |
| Correct completions | 9 / 10 | 8 / 10 |
| Paired successes available for cost comparison | 8 | 8 |
| Median cumulative reported total tokens, both-success pairs | 157,012.5 | 459,289 |
| Median active-turn seconds, both-success pairs | 46.7975 | 82.253 |

Native's median reported total is about 2.93 times Text's in the eight
both-success pairs. This is not a dollar-cost ratio. Cached input is included
in total, and reasoning output is already part of output. Cost comparisons
exclude failures and are subject to survivor selection. Active-turn timing
includes model/tool waiting, excludes uninstrumented setup (null), and runs on
a shared host; no end-to-end latency or statistical effect claim follows.

| Known task | T correct / ordinary observations | N correct / ordinary observations | Quota rows T / N |
| --- | ---: | ---: | ---: |
| MM01 metadata preservation | 2 / 2 | 2 / 2 | 0 / 0 |
| MM02 original shared prefix parser | 2 / 2 | 1 / 2 | 0 / 0 |
| MM04 graph-order completeness | 2 / 2 | 2 / 2 | 0 / 0 |
| MM05 cache-state invariant | 2 / 2 | 2 / 2 | 0 / 0 |
| MM06 stable reverse-dependency deduplication | 1 / 1 | 1 / 1 | 1 / 1 |
| MM07 XML escaping | 0 / 2 | 0 / 1 | 0 / 1 |

Do not compare unpaired denominators as if all twelve repetitions per arm were
valid model trials. MM07 r1 and MM06 r2 do not provide usable complete pairs.
There is no valid full-batch application of the registered favorable-signal
screen. The observed ten pairs show neither a completion nor reported-token
advantage for Native; that is a bounded descriptive finding, not a general
negative theorem about structured tools or ALVA.

## Method and controls

Registration: `46783923a855be47853bd72143eeae926192c48d`; runtime freeze commit:
`9f1b2c06aec8540a004927f0333dc85c94e4e4c0`. Freeze SHA256:
`bbd95d7ce0bbf79f0ce6ae37e9f02662752938acbfb80df09f3433b61b7d0d2d`.
Both precede generation. See PROTOCOL.md for the fixed selection, counterbalanced
T/N order, two repetitions, primary completion condition and secondary measures.

Both arms receive identical original program bytes, task, full official Skill/
references and language documentation. T has exact text replacement AND a
complete-file editor, read/search/Git diff/check/test. N has actual twenty
Native MCP tools and the same source/doc/check/test workbench. Neither has
shell, witnesses, prior trajectories, evaluator source or hidden assertions.
Full official Skill in T is informational and overridden by its source-only
instruction; its Native-oriented content may still affect behavior. This is a
controlled tool-bundle comparison, not unrestricted Codex/Claude effectiveness.

Limits are identical: 80 model tools, 480 active seconds, 600,000 cumulative
reported-token observation threshold, 20 seconds interrupt grace, concurrency
one, no slot replacement. These are observation limits, not provider hard caps.
Fine-grained Native construction can consume more tool calls than one complete
source replacement; the result must not be generalized to every possible
semantic interface. No task-aware shortcuts were added after outcomes.

The real P34 collector captures complete initial/final structural snapshots
for BOTH arms; no extra live Guard prevention is credited to N. Both use the
same final body/metadata policy. Native success requires an actual AIR commit
and fresh authority; unconnected/staged-only work earns no success. Source
bytes are T's authority. Independent evaluation consumes exact final source/AIR
in new Linux namespaces and records its tested snapshot digest explicitly.

All seventeen successful completions were independently checked against the
retained actual commit/fresh authority/test receipt and scope conjunction.
All twenty-four retained outcome records and owner cleanup acknowledgments
were checked. “Independent” here means a separate execution/checking path,
not human-independent oracle authorship. Original assertions are unchanged.

No-model preflight establishes regression PASS and target TEST_FAIL for all
six originals, actual full-file editing, Native schemas, and actual T/N
AppServer/SSH dispatch. Startup repairs and failed attempts are retained:
per-UID nproc=128 was below unrelated host threads; the new profile uses 512.
The new owner adapter fixes nested procfs and short IPC handling. Existing
P22/P23/P36 source files stay unchanged. See ATTEMPTS.md and PREFLIGHT.json.

## What blocks an advantage claim

1. The full comparison is incomplete due to provider quota and the post-fault
   stop defect. Quota-affected rows cannot be labeled ordinary task failures.
2. Per-slot CLI binary identity was not recorded; equal version strings alone
   do not close that gap. Do not assert a wrong-binary incident without evidence.
3. Six historically selected, author-familiar tasks, three correlated component
   sources, two repetitions each, one model/effort. No fresh independent task
   distribution or statistical reliability estimate.
4. A controlled source workbench is not every strong mainstream agent setup.
   Both use ALVA, so no Python/TypeScript language superiority is tested.
5. Finite tests, Codex-assisted oracle/implementation/analysis and controlled
   raw access limit external validation. Host trust and Linux-only candidate
   execution remain assumptions. Setup/dollar costs are null.

The raw archives remain controlled local files, not public transcripts. Public
summaries/hashes are in RESULTS.json, VALIDATION.json and ARCHIVES.json.
Exact Python byte restoration, including recorded checkout line endings, is
provided by restore_runtime.py. ALVA inputs are never normalized. The original
CLI hash is recorded, but its original executable is not currently accessible.

## Post-run repairs and next decision

provider_gate.py classifies failed service/runtime terminals as common faults;
the wrapper lets terminal cleanup complete and blocks the next launch. Its
regression tests use the observed usageLimitExceeded shape and unknown failed
terminals. safe_run.py also requires an explicitly pinned executable and records
before/after identities per slot. It deliberately refuses the old freeze,
so no additional model request was made to test the repair. These files were
added AFTER the experiment and cannot improve its validity retroactively.

Recommendation: do not expand the task pool or spend another model budget merely
to finish a favorable result. The existing paper can receive a transparent
exploratory limitations addendum; it cannot become an efficacy paper from this
batch. Preserve its historical P32/P36, P38 and RDR-02 conclusions.

If product development continues, first address the observed interaction cost:
Native successful slots commonly need 28–37 model tools where successful Text
slots use 11–15. Profile generic construction/discovery/schema overhead and
improve task-independent ergonomics, with equal source-baseline access. This
is a proposed engineering direction, NOT a causal diagnosis proven by an
ablation. Do not add MM-specific recipes or claim that batching will create
superiority. Some declaration-local replacement may require additional Core
support; feasibility must be checked rather than assumed.

Only a separately reviewed, fresh-task and repaired-harness design could test
an improved interface. No new model run, quota purchase/account switch, Core
change, paper rewrite, merge or follow-on experiment happens automatically.
