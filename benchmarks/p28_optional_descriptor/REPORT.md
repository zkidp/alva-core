# P28 — Optional Native Descriptor Discovery

Status: **CLOSED_COMPLETE**, exactly two fresh HE41 task turns, C1 then C0.

Classification:
`DESCRIPTOR_CALLS_REDUCED_NO_OBSERVED_STAGE_PROGRESS_BENEFIT`.

## Result

| Observable | C1 optional descriptor | C0 original rule |
|---|---:|---:|
| `describe_operation` calls | 1 | 3 |
| Model tool calls | 8 | 10 |
| First successful construction tool ordinal | none | 9 |
| Connected staged `bench.solve` change before interrupt | no | no |
| Model transaction checks / commits | 0 / 0 | 0 / 0 |
| Changed fresh authoritative target | no | no |
| Final disposition | NO_COMMITTED_CANDIDATE | NO_COMMITTED_CANDIDATE |
| Independent final check | PASS (unchanged stub) | PASS (unchanged stub) |
| Independent final behavior | TEST_FAIL (unchanged stub) | TEST_FAIL (unchanged stub) |
| Tool parameter/operation errors | 0 | 0 |
| Actual input tokens | 135,593 | 123,783 |
| Cached input tokens (not subtracted) | 113,408 | 104,064 |
| Output tokens | 1,010 | 997 |
| Reasoning output tokens (subset of output) | 358 | 355 |
| Actual total tokens | 136,603 | 124,780 |
| Excess above 120,000 observation threshold | 16,603 | 4,780 |
| Drive elapsed seconds | 18.788 | 22.709 |
| Trusted observer calls, separate from model calls | 1 | 3 |
| Observer read time, seconds | 0.000869222 | 0.001980628 |

Both stopped on the **token observation threshold**, not wall/tool limits.
Both `turn/interrupt` requests were acknowledged, both terminal states were
`interrupted`, and all final usage fields were retained. This transport does
not expose provider request counts or monetary charges; these stay null.
120,000 is not a provider hard cap or a unique-context-length claim.

C1 followed begin → inspect project → resolve → inspect body → applicable
operations → inspect entity twice → describe operation, then interruption.
C0 followed begin → inspect project → resolve → inspect body → applicable
operations → three describe operations → create reference → create binary.
The two constructed nodes were detached: both same-live-transaction body
observations equal the transaction's original `bench.solve` body hash.
Neither condition attempted target attachment, transaction check or commit.
Fresh-process authority re-reads agree with the initial state. The terminal
compiler/behavior results describe that unchanged stub, not a committed model
candidate and not an automatic repair.

The optional policy coincided with fewer descriptor calls in this single pair,
but **did not produce target connection or closure**. C1 consumed more actual
cumulative tokens than C0. This wave does not support the proposed stage-
progress mechanism. It does not show that descriptor information is useless,
that optional discovery generally helps/hurts, or that any language/semantic
mechanism is superior. No further experiment is launched.

## Frozen intervention and delivery

- Baseline: `8f2207a6533df87e3d2c707c8a04e3f0ce529345` (P27).
- Pre-generation freeze: `c79b8ebd3464075d45b0d3f0bb3cffa900cf6cca`.
  Commit/push and clean HEAD==origin were checked before the first turn/start.
- Exact task/stub, full Skill and all references, twenty native schemas,
  study surface, SDK, model `gpt-5.6-sol / low`, budget and controller are shared.
- Only C1's developer instructions append the exact P27 override: 519 UTF-8
  bytes, plus a two-byte newline separator. No compensating document removal.
- Actual thread/start instructions and observed initial user-message text
  match the freeze. Two distinct actual thread IDs and disposable sandbox
  workspaces were used. No retry, replacement or third slot occurred.
- Codex CLI: `0.163.0-alpha.11.2`. Approved Linux ALVA binary SHA256:
  `29e5abd692206876a3929112e471cb99ce457d478dcd81c50cb006aa3b958257`.
  Exact sysroot/registry/runtime aggregates are in `FREEZE.json`.
- The [official AppServer protocol](https://learn.chatgpt.com/docs/app-server)
  was checked for developer instructions and interrupt/terminal handling;
  the already frozen P26 drive/controller implementation was reused unchanged.

## Observer and independent evaluation

The new wrapper runs in the trusted host, under the existing service's serial
lock and its own reentrant lock. After successful model begin/mutation it
performs `inspect_body` in the same real MCP process and transaction. It
does not create a transaction, check, mutate, repair, commit or produce an
agent action. Original native replies are forwarded unmodified. Observer
results are not model-visible and do not inflate model discovery counts.

The primary endpoint additionally requires the associated completed model
tool event to precede the first interrupt request's recorded event boundary.
This is conservative about late-delivered completion notifications; no host/
Linux clock comparison or post-interrupt credit is used. All expected observer
associations are present. Here the staged hashes never changed, so cutoff
ambiguity cannot turn either result into a positive.

All candidate MCP execution and independent compilation/behavior checks remain
inside the existing P22/P23 Linux OS boundary. Host-owned evaluator assertions
are in a separate evaluator namespace, not model-visible. Linux is the only
candidate backend; Windows only orchestrates WSL. Native Windows/macOS candidate
execution remains unsupported. No Core, AEP, MCP API or Skill was changed.

## Tests, byte reproducibility and evidence

- Eight new adapter/input/scoring tests pass locally; the eight affected P26
  controller regressions also passed without editing their implementation.
- Zero-model real Linux observer validation passed on a separate non-task
  string fixture: repeated reads preserve staged graph/revision/diff, source
  and authority; detached node exclusion; connected modification; no publish
  before commit; check/commit/fresh reload; isolated compile and behavior.
- Both real Codex AppServer preflights passed native schema/Skill discovery
  and begin/abort. The original stub's isolated check PASS / behavior FAIL was
  explicitly expected. A synthetic envelope through the real service relay
  verified observer associations and separate call accounting.
- Initial preparation failures were fixture-helper issues only, before any
  model generation: a helper parameter-name collision, and using string-only
  `change_field` on an integer literal. The final fixture uses a supported
  string change. No HE41 solution or P25 witness was used; no Core fix followed.
- Initial Linux CI correctly rejected a checkout/runtime hash mismatch in
  inherited `benchmarks/native_mcp_skill/proxy.py`: the approved Windows/WSL
  runtime used CRLF, while Git's blob uses LF. The freeze already includes the
  exact executable bytes and their SHA256. **Neither freeze nor scientific
  executor was changed.** A post-execution, CI-only consumer materializes the
  exact SHA-checked base64 runtime in a disposable tree before running the
  frozen tests on Linux/Windows. It does not accept multiple hashes, normalize
  bytes, ignore mismatches or overwrite checkout/history. Its unit test passed
  locally. The original CI failure is retained, not rerun as model evidence.
- The first freeze-commit Linux CI observer job independently passed its actual
  isolated purity/build/behavior test. Updated CI logs are Actions Artifacts;
  final-head statuses are linked on PR #28 rather than copied raw into Git.

`analyze.py` verifies the private archive hash before reading it and exactly
reproduces both public slot summaries, actual input binding and validation.
Run: `python benchmarks/p28_optional_descriptor/analyze.py <controlled RAW.zip>`.
Analysis makes zero provider/generation/input-count calls.

Raw archive SHA256:
`1b92ee8b09e3c85ee763d05899fce837961f342f07d95e1d508e3de0cc76534f`
(52,396 bytes, 14 entries). Raw transcripts, candidate/AIR files and machine-
local configs stay in ignored controlled storage, not Git. No credentials are
read, hashed or archived. `ARCHIVE.json` records only bounded metadata.

## Limits and stopping

One task selected after P26 and one observation per condition, fixed order,
full-document repeated-input burden, small extra C1 instruction and resource
censoring limit interpretation. Per-call usage rows are enclosing observable
intervals, not independently attributable token charges. No significance test,
general causal effect, correctness gain, automatic next study or merge.

P26/P27 and all earlier frozen records remain byte-unchanged. The P28 freeze
and executed runtime remain byte-unchanged after execution; only derived
results, this report and the explicit CI-only transport consumer were added.
All two authorized slots are closed. **STOP; await reviewer.**
