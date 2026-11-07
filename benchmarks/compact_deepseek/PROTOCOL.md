# Compact DeepSeek diagnostic (independent provider registration)

8 November 2026. User explicitly supplied DeepSeek access and authorized model
testing. This is a new provider/transport variant; MIC-02's registered GPT
configuration and all previous artifacts stay unchanged. No token comparison
across different models/tokenizers will be interpreted as an interface effect.

Use official https://api.deepseek.com, requested/returned model deepseek-flash
(catalogue name DeepSeek-V4.1-Flash), thinking enabled, reasoning_effort low,
max_tokens 8192 per HTTP completion, non-streaming. Omit temperature and other
parameters ignored by thinking mode. The catalogue confirms low and tool support.
Preserve complete reasoning_content in tool continuations as required by the
official API. Raw reasoning/transcripts remain private; reports contain outcomes
and counts only. Model ID/fingerprints are recorded per response; an alias is
not proof of immutable provider weights.

This uses the same four familiar tasks, original bundles/assertions, sixteen-slot
counterbalanced schedule, documents, typed shared workbench, nine-tool compact
Native profile, final neutral P34 structural policy and independent tests as
MIC-02. Both sides see the same public information. Provider-facing Native
results retain isError and structuredContent once, removing duplicate MCP text
and transport metadata. Full backend receipts remain private. This is an
interface-bundle comparison, not an isolated method ablation or CodeStruct test.

One initial user message per fresh conversation, followed only by assistant
tool calls/tool replies. HTTP tool continuations are multiple provider requests,
not extra operator turns. No extra user prompt, slot replacement, retry, parallel
model slot, operator repair or result-dependent schedule change. Same limits:
80 model tool observations, 480 active seconds, 600000 cumulative reported tokens,
20 seconds cleanup grace, concurrency one. Observe between requests/tools;
overshoot is retained. At most 80 tools dispatch; a batched response can exceed
the observed call threshold. Serial dispatch stops at finish/limit. Length and
filter terminations do not count as normally completed candidates.

HTTP request timeout is 90 seconds or the remaining active budget, whichever is
shorter. If transport/deadline makes provider termination uncertain, retain
UNKNOWN and stop the entire schedule. The API has no trusted generation-cancel
acknowledgment; closing HTTP is not claimed to stop server work. No subsequent
model requests after a common provider/runtime, identity, isolation or cleanup
fault. Expected argument/tool errors may be repaired within the same budget.

Record submitted HTTP completion attempts separately from unknown upstream
generation-request counts; never infer one from the other. Sum provider-reported
total/input/output/cache categories across requests, include cached input in
total, and keep absent reasoning counts null. A missing reasoning subcategory
does not invalidate a reported-total cost comparison in this provider variant.
No fabricated zero, cached subtraction or reasoning double-count. Dollar cost
remains null because account balance differences cannot reliably be attributed
to a slot. No token-count API calls.

Setup/finalization timing is separate from active conversation time. Tool and
API calls, errors, commits, authority roots and exact tested snapshot receipts
are retained. Code/controller Python and ALVA/rustc executable bytes are checked
before and after each slot. Full SDK tree identities are frozen. There is no
Codex CLI/AppServer in this variant, so no CLI-equivalence claim. Existing
P22/P23 Linux isolation and P36 owned PID cleanup are reused, with the existing
shared-host nproc=512/procfs/short-socket adapters; candidate mounts never contain
the checkout, host evaluator, old traces or API credentials.

Eight real zero-model preflight routes (T/N for all four tasks) must pass:
original check/build/regression PASS and task TEST_FAIL; deterministic witness
task/regression/scope PASS; Native real commit and fresh authority; exact tools,
shared public docs and confirmed owner cleanup. Prior preflight technical faults
are retained, not model failures. FREEZE.json binds these receipts, exact code,
SDK, public inputs and schemas in a separate commit before generation. No model
generation is used for protocol/capability preflight; a provider incompatibility
on the first formal request stops the batch without a replacement.

Correct completion requires a normal stop or explicit study_finish, final task
and regression PASS, target changed, no unauthorized body/metadata change, exact
candidate-bound independent tests, and confirmed cleanup. Native additionally
requires an actual commit receipt matching fresh AIR. Failed observations remain
in the denominator; infrastructure rows are UNKNOWN, never wrong-task zeros.

Screen: all sixteen slots valid, at least four both-success pairs with complete
reported total/input/output/cache usage, N correct count >= T correct count, and
median per-pair N/T total-token ratio <=0.75. Otherwise report no favorable
signal, insufficient paired successes, or infrastructure inconclusive as
applicable. Report all outcomes/resources as well as survivor-conditioned costs.
This is a small author-informed diagnostic on known tasks, not independent
confirmation, statistical significance, or general product/language superiority.

Official references checked before generation:
- https://api-docs.deepseek.com/api/list-models/
- https://api-docs.deepseek.com/guides/thinking_mode/
- https://api-docs.deepseek.com/api/create-chat-completion/
