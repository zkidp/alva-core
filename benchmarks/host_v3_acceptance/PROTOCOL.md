# Host V3 fresh model cost acceptance

Base `53539ec4b0471f53b8732cecf066dc84b78cb680`. This is a separately frozen
12-slot pilot, not replay of any consumed registration. The user authorized
continued real-model acceptance on 8 November 2026. Historical artifacts and
the production compiler/Host are unchanged by this study.

Four original tasks (MM01/MM02/MM04/MM07) each receive one fresh T, V2 and V3
conversation. The schedule balances every pair's ordering 2:2 across tasks.
No result-dependent schedule change, replacement, extra user turn, operator
repair or generation retry is allowed. Maximum 12 slots, concurrency one;
each gets 80 model-tool observations, 480 active seconds observation, 600,000
cumulative provider-reported tokens observation, and 20 seconds cleanup grace.
These are observation/interruption bounds, not provider token hard caps;
boundary overshoot is retained. HTTP requests are bounded to 90 seconds or
the remaining active budget, with no retry. An unknown provider termination,
identity/isolation or cleanup fault stops the entire schedule.

Use the existing authorized official DeepSeek API, requested/returned model
`deepseek-flash`, thinking enabled, effort low, max_tokens 8192 per completion,
non-streaming. Verify the current model catalogue before freezing. Preserve
all private `reasoning_content` in tool continuations as required by the
[official thinking-mode contract](https://api-docs.deepseek.com/guides/thinking_mode/).
No temperature or ignored sampling parameters are supplied. Model alias and
reported fingerprints are recorded without claiming immutable weights.

All three conditions receive exactly the same original source bytes, public
requirement, complete current official Skill and shared public reference access.
Four tools are exposed: read_target, prepare_change, publish_change, study_doc.
Schemas for V2/V3 are identical. Both use complete body proposals. V2 selects
the prior serial/full-AIR-export/full-receipt path on the same instrumented
compiler, stripping measurement-only counters from its model-visible result.
V3 selects the cost-optimized path and compact model feedback. Successful
publication ends every condition's conversation immediately. Otherwise a
normal final response or a fixed limit ends the slot. Raw thoughts, request
payloads and tool traces stay private and are never used as subsequent inputs.

T is a deliberately strong matched source-proposal control: it uses unique
exact old/new source edits, with the same view/proposal lifecycle and compact
feedback. Source import uses the real compiler; actual P34 compares its full
component snapshot to the original trusted baseline. Syntax/type/scope failures
do not apply text edits and invalidate old proposals. Valid tested drafts are
retained and explicitly acknowledged. The Host then attaches the imported
target body through the same Native editor/Guard/tests/publication path as V3.
Thus T is not the old ten-tool Text workbench, a different language, a raw-file
publication baseline or a competitor reproduction. This compares complete
interface configurations, not an isolated semantic representation effect.

Generated candidate code and check/build/test run only in the existing P22
Linux namespaces with the previously declared shared-UID nproc=512 adapter.
Trusted Core parsing/publication runs in a Host-owned child outside candidate
execution namespaces. No checkout, hidden evaluator, historical witness, trace,
API credential or private path is mounted into candidate execution. The API
key remains in the Windows controller; the Linux service never receives it.
Independent evaluators and historical engineering witnesses are absent from
model messages/tools. Public doc tools expose only the frozen approved docs.

Before generation: qualify all twelve routes with real deterministic edits,
actual Guard commit, fresh AIR, original regression/task tests and confirmed
cleanup; verify text scope refusal invalidates an older passing proposal.
Freeze exact local and Linux-export Python file maps, compiler/rustc executable
hashes, SDK tree hashes, source/task/doc bytes, schemas, provider metadata and
preflight. Separate maps explicitly bind platform/newline differences. Verify
runtime/executables before/after every slot. Reservation is exclusive for this
freeze; no replay. Final independent evaluation must test the actually published
AIR; original source projections must remain unchanged. A normal handoff,
task/regression/scope PASS, a real commit and matching fresh authority plus
confirmed cleanup are required for success.

Sum all provider-reported input, cached input, output, reasoning output and
total categories separately. Cached input remains in total; absent categories
stay null and reasoning is not added a second time. Submitted completion HTTP
attempts are counted separately from unknown upstream generation requests;
provider generation requests and attributable dollar costs stay null. No
token-count API calls. Report all failures, resource use and incomplete rows.

Two separately reported exploratory screens, fixed before generation:

- V3 vs V2: all 12 slots valid, at least three both-success complete-usage
  pairs, V3 correct count at least V2, median paired reported-total ratio ≤0.90.
- V3 vs T: same validity/pair/success conditions, median ratio ≤0.75.

If any condition fails, retain NO advantage or INCONCLUSIVE as appropriate;
do not replace failed pairs with total-token savings from cheap failures.
These are four known author-informed tasks with one observation per arm/task,
not statistical confirmation, general product advantage or competitor proof.
