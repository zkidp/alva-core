# P32 — fresh Native MM01 end-to-end maintenance

**CLOSED_COMPLETE / COMPLETED_CORRECT_MAINTENANCE.** Exactly one fresh S
slot was executed; no retry, replacement, extra slot or historical rescue.
This is single-case developmental feasibility, not an effectiveness estimate.

## Before execution

Base: `c9aecd0bfbbc6b7444d50bf85ca1558ae969d3db` (P31).
Freeze commit, pushed before the single model turn:
`997d26ceb63cba463d1cba659795c1c6b507c53b`.
Research/implementation branch: `codex/p32-native-mm01-maintenance`.

The exact P30 MM01 public input, original source-only bundle, 20 Native MCP
schemas, official Skill/references, generic language document, dynamic study
workbench and independent evaluator are reused unchanged. The task is to leave
negative-size metadata unchanged while retaining increment-by-one for
nonnegative sizes and preserving key/etag, constructor, accessor and app behavior.
No engineering witness, old model response/patch, other slot or hidden evaluator
source was delivered to the new model. Input and executing bytes are bound in
FREEZE.json; no post-execution changes to that freeze or runtime.

Actual SDK: ALVA Linux ELF SHA256
`29e5abd692206876a3929112e471cb99ce457d478dcd81c50cb006aa3b958257`;
Codex CLI `0.163.0-alpha.11.2`, executable SHA256
`c81ed464e5e7cafd09a5fa26af390c480bed8e9fab2a87a54b285fbd56e7122a`.
The freeze also binds the Python/bwrap runtime, Rust sysroot and registry.
Trusted Windows AppServer orchestration uses Ubuntu-26.04 WSL; candidate MCP,
AIR and generated-code compilation/execution stay in P22/P23 Linux OS isolation.
Windows/macOS native candidate execution remains unsupported.

Zero-model preflight used the existing P31 standalone synthetic Responses
fixture: **actual model-tool approval path PASS**, legal commit reaches native
MCP, invalid/closed IDs and invalid transactions reject, fresh AIR/build/behavior
PASS, default-policy negative control denies, unauthorized tools remain absent
and Host writes are denied. This is synthetic transport validation, not model
performance. The actual P32 Host then parsed and validated the P31 scoped
configuration, exact 20 schemas and destructive annotation, discovered Skill,
began/inspected/aborted an unchanged MM01 transaction, and independently confirmed
baseline check/build/regression PASS with new-task expected FAIL.

Only `alva.commit_transaction` gets `approval_mode="approve"`. Server default
remains `auto`; global/thread approval remains `never`; Host is read-only;
shell/web/apps/plugins/image/delegation tools are disabled. No Core, AEP, MCP,
Skill, user installation or canonical main change occurred.

## Observed single-slot path

Model: **gpt-5.6-sol / low**, one new ephemeral session and isolated project.
The actual parsed policy was checked again before turn/start.

| Stage | Actual evidence |
|---|---|
| Discovery | begin, resolve, inspect project/body, applicable operations, four describe-operation calls |
| Construction | create literal, binary and if through existing Native MCP |
| Target attachment | native dispatch 13: replace_expression; same-transaction read-only observer confirms changed target body |
| Preview/check | preview succeeds; native dispatch 15 check returns `problems: []`, no error |
| Commit delivery | one AppServer model-tool commit, native dispatch 16; matching AppServer ID and MCP `_meta.callId`; no direct Host commit |
| Authority publication | generation 1; project revision changes; `alva-air/current` and `alva-air/gen-1.air` created |
| Fresh process | committed revision matches new MCP authority read; only touch_size body differs among four observed functions |
| Independent evaluation | ordinary project check/build PASS; task tests 2/2 PASS; regression tests 2/2 PASS; scope PASS |
| Terminal | completed naturally, explicit finish, no interrupt and no infrastructure HOLD |

All **16** Native MCP calls succeeded without an AppServer or native operation
error. The model additionally issued study check, test and finish: **19 model
tool calls** total. Five trusted observer body reads are counted separately,
not Agent discoveries or model feedback. Raw source projection is byte-identical
to the original; committed AIR is authoritative. Scope evidence combines
protected manifest preservation, independent non-target requirements and the
unchanged constructor/accessor/app body hashes, not equality to a reference patch.

Commit and fresh-process authority revision:
`db9e4a7e50adc031d2a7e79930a02173b01d6c44fa7e5182a43f288846d2a252`.
Original revision:
`c55248b6f4e36aa61a0c84cdbdb2d5c64f6827497e7d747cd7ae437090de9863`.

## Resources and interpretation

Active-turn observation: **35.872 seconds**. Reported cumulative usage:

- input: **273563**; cached input: **251904** (not subtracted);
- output: **1448**, including **229** reasoning-output tokens;
- total: **275011**.

No 80-tool / 480-second / 600000-reported-token observation limit was reached.
The token threshold is not a provider hard cap, unique context size or dollar
cost. Provider request count and dollar cost are unavailable and remain null.
There was no interruption, so interrupt acknowledgement false means not
requested, not an unconfirmed stop. This slot is not resource-censored.

This is evidence that the real model completed this particular maintenance
task end to end using the existing Native interface under corrected Host commit
authorization. Staged/check/commit success was **not** substituted for independent
behavioral correctness. It does not prove general reliability, semantic-tool
superiority, or a causal gain versus text/Bridge. P30-T is not pooled with this
fresh S slot; P30-S remains NO_COMMITTED_CANDIDATE / HOST_AUTHORIZATION_BLOCKER,
with its staged candidate behavior NOT_INDEPENDENTLY_EVALUATED. P31 remains a
zero-model engineering result. No historical evidence was updated.

Stale/conflict, recovery, overflow-policy changes, arbitrary external effects
and source-projection/authority multi-artifact atomicity were not tested here.
No further model tasks or limit tests are authorized by this result.

## Evidence and reproduction

Controlled raw archive:
`.local/p32-native-mm01/execution-01/RAW.zip` (45032 bytes, 10 entries), SHA256
`6b1f8bac0074ae82eb3234f42ee4d4a5f185d442b1e6ea1bb18939115fba4ab1`.
It retains actual thread/turn requests, policy, observable tool/usage/terminal
events, same-session observations, source/AIR bytes, native RPC and independent
evaluator outputs. No raw Agent transcript/candidate log is committed to Git.
Credentials were not read, copied, printed, hashed or archived.

Public derived evidence: RESULTS.json, ANALYSIS.json, VALIDATION.json and
ARCHIVE.json. ANALYSIS records operation stages and final source/AIR hashes,
not private transcripts. `analyze.py` verifies the archive hash, reproduces the
published result, checks exact input/runtime binding and matches final AIR to
the native commit revision, without running a model or executing a candidate.

```text
python -m unittest benchmarks.p32_native_mm01.test_pilot -v
python benchmarks/p32_native_mm01/ci_exact_runtime.py
python tests/integrations/test_native_commit_authorization.py -v
python benchmarks/p32_native_mm01/analyze.py <controlled-P32-RAW.zip>
```

Local: four P32 tests PASS, exact-byte consumer PASS, seven P31 policy/protocol
tests PASS; real approval and P32 baseline preflight PASS. CI executes portable
provenance tests on Linux/Windows plus existing relevant repository workflows;
it does not claim to rerun the model or proprietary desktop AppServer probe.

All P30/P31 frozen records and implementation files are unchanged. No merge or
main update. **STOP for independent reviewer; no additional experiment.**
