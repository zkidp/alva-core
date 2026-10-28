# MM01: two model slots closed; native commit blocked by Host policy

**Scientific disposition: `NATIVE_COMMIT_HOST_AUTHORIZATION_BLOCKER`.**
Both scheduled model turns executed once and reached natural `completed`
terminals, without retry, replacement, interruption or extra slot. However,
this is **not a clean paired utility comparison**: AppServer denied S's actual
commit request before the isolated native MCP received it. Do not interpret
the terminal-state task scores as evidence of Text superiority or Native
inability to construct/attach a correct change.

## Frozen execution and actual environment

P29 base: `8df4d24a55f1176a9fc8b9eaf5292c8b088ff5b4`.
Pre-generation freeze commit, pushed with a clean worktree:
`87ba3b82aaf26d9825fdf65f76e11d84b0d59639`.
`FREEZE.json` remains byte-identical to that commit. Order: MM01-T, MM01-S.
Two fresh AppServer sessions, two fresh Linux candidate namespaces; original
source bundle `6b2fbdf1d0b7929cc239a2db810a35549228a613d5a778f93e4ae3d0e39ac090`.

Model `gpt-5.6-sol / low`, authenticated Codex CLI
`0.163.0-alpha.11.2`; public SDK binary SHA256
`29e5abd692206876a3929112e471cb99ce457d478dcd81c50cb006aa3b958257`.
Trusted controller: Windows. Candidate MCP, text workbench, compilation and
generated tests: Ubuntu-26.04 WSL, existing Linux OS namespace backend,
bubblewrap 0.11.1, Python 3.14.4, approved Rust SDK. Exact SDK aggregate hashes
and actual runtime bytes are bound in the freeze. Native Windows/macOS
candidate execution is unsupported; no host-execution fallback was used.

Common resource observations: 80 model tools, 480 active-turn seconds,
600,000 cumulative reported tokens, 20-second interrupt confirmation grace.
These are observation/interruption limits, not a provider hard token cap.
Neither slot hit any of them. No input-count API was called. Provider request
count and dollar cost are unavailable; one AppServer turn is not one provider
generation request. Cached input remains included in the reported footprint.

## Independent terminal-state components

| Component | T — Text | S — Native + Skill |
|---|---|---|
| Effective final target change | Yes; only touch_size body changes | No; final authority unchanged |
| Connected staged target change | Source edit #6 | Yes; replace_expression #15 |
| Final task tests | PASS | FAIL on unchanged original program |
| Final non-target regressions | PASS | PASS on unchanged original program |
| Authorized scope | PASS | PASS for preserved final state |
| Final project check / build | PASS / PASS | PASS / PASS, original state |
| Native transaction check | N/A | `problems: []` at tool #18 |
| Commit | N/A | Attempt #19 denied by Host; zero native dispatches |
| Fresh-process authority reread | Source target changed, other bodies stable | Original target and other bodies stable |
| Handoff / final source | Explicit finish; evaluable changed source | Explicit finish after abort; no committed candidate |
| Observed slot disposition | COMPLETED_CORRECT_MAINTENANCE | NO_COMMITTED_CANDIDATE + HOST BLOCKER |

The final evaluator executes P29's exact two goal and two regression Rust tests
against generated native code in a separate namespace after candidate processes
close. It is not an AST/literal heuristic. S's final goal FAIL describes the
unchanged baseline, not a behaviorally tested and rejected staged candidate.
The uncommitted S program was **not independently evaluated**. A readonly body
hash, native check, or semantic diff is not a behavioral correctness proof.

Scope is determined by protected manifest, allowed source paths and public
non-target requirements, not equality to an engineering solution. T changes
only `src/model.alva` / `demo.model.touch_size`; constructor, accessor and app
body hashes are unchanged. S publishes no AIR and changes no final file.
Finite regressions do not prove preservation of all possible behavior.

## Observable operation paths

T: revision → three source/manifest reads → common language documentation →
one accepted exact edit → real Git diff → project check → independent test →
finish. Zero rejected edits or tool errors. First accepted edit is model tool
#6; usage bracketing is in `ANALYSIS.json` rather than an invented per-call cost.

S: begin → resolve/project/body inspection → applicable operations → five
operation schemas → four node constructions → **connected replacement** →
body reread → semantic diff → transaction check → commit attempt → abort →
finish. All nineteen actually dispatched native calls returned non-error
envelopes. There was **one additional failed native call at the AppServer
boundary**. Thus `RESULTS.json.native_operation_errors = 0` counts the isolated
MCP side only; it does not mean zero Host errors. `ANALYSIS.json` and
`SCIENTIFIC-DISPOSITION.json` explicitly account for the withheld commit.

Six trusted readonly staged-body observations are counted separately, never
delivered to the model. Construction alone leaves the target hash unchanged;
replacement #15 changes its actual staged body. It is not merely a detached
node or `ok` label. No inference about hidden model reasoning is made.

## Concrete Host blocker and preflight limitation

S tool #19, `commit_transaction`, has a completed AppServer error:

```text
MCP tool call requires approval, but approval policy is never
```

Its duration is 0 ms, result is null, and no matching commit exists in the
isolated MCP dispatch ledger. The following abort is actually dispatched and
succeeds. This is an observed action-delivery/authorization failure, not a
transaction rejection, stale conflict, parameter error, missing AEP primitive,
behavior failure of a published change, or resource exhaustion.

**Our zero-model preflight exercised real initialize/discovery/begin/inspect/
abort, Text tools, isolated baseline check/build/tests and controller terminal
simulation, but did not exercise commit authorization through AppServer.**
It therefore did not establish end-to-end publication permission. Its original
PASS record is retained with this explicit coverage limitation, not rewritten.
The frozen runner's `CLOSED_COMPLETE` means two terminal records were collected;
it missed this pre-dispatch denial as an infrastructure flag. The additive
scientific disposition does not relabel it a successful treatment delivery.

No permission change, Host repair, rerun, direct-commit rescue or extra model
turn is performed here. A separately authorized future execution would need a
trusted, explicit isolated-MCP commit authorization check before generation;
that is a concrete missing integration test, not a new research gate or Core
feature. Both existing slots remain unchanged.

## Resources

| Reported quantity | T | S |
|---|---:|---:|
| Model tools (including withheld attempt) | 10 | 21 |
| Active-turn seconds | 27.501 | 63.677 |
| Input tokens | 127,100 | 341,252 |
| Cached input (subset, not deducted) | 105,216 | 315,264 |
| Output tokens | 924 | 2,035 |
| Reasoning output (subset) | 75 | 675 |
| Total reported tokens | 128,024 | 343,287 |
| Resource interruption | No | No |

These are cumulative reported charges, not unique context lengths, provider
prices or isolated per-tool costs. S additionally receives real schemas and
the complete official Skill/references, both via discovery and its first
prompt. T has common generic language documentation on request. The interfaces
and operational information differ; no information-equivalence claim is made.

## Evidence, boundaries and conclusion

Controlled raw archive SHA256:
`0ed04b131cf0d7fc2fe89d7d182fbfd589942e4bfca9d04e9ce5769bf7e52295`
(65,828 bytes, 15 entries). It contains original request/tool/terminal records,
final source/AIR snapshots and isolated evaluation outputs, not credentials.
It stays in ignored `.local/mm01-pilot/execution-01/RAW.zip`, not public Git.
`analyze.py` verifies its hash and member identities and recomputes the public
scores/actual input binding without provider calls or candidate execution.

Supported observation: this Text session completes MM01; this Native session
discovers operations, constructs and connects a target change and receives a
clean transaction check. Native publication and independent candidate behavior
remain untested because Host authorization blocks commit. No general usability,
correctness, safety superiority or causal package benefit follows from one pair.

Historical MM02 demonstrated that an anonymous parent revision may be shared
with an unrelated function: a transaction check/commit need not preserve every
non-target requirement. That risk remains relevant to semantic scope claims,
but no MM02 witness, answer, failure path or replacement procedure was included
in MM01 model inputs. MM01's final non-target hashes/regressions are reported;
the broader shared-parent issue is neither fixed nor generalized away.

This pair is conflict-free: stale-write acceptance, concurrent update loss and
recovery are NOT_EXERCISED, not observed zero failures. Private invalid Text
states are not published invalid integrations. No whole-source/AIR atomicity,
universal behavior preservation or external-side-effect rollback is claimed.
Core/AEP/MCP/Skill and P20–P29 frozen records are unchanged.

**STOP for independent review. No replacement slots, task change, next study
or automatic merge.**
