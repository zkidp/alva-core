# P3: Codex × Guard exploratory pilot

Status at freeze: zero model turns. P0 #16, P1 #17 and P2 #18 remain OPEN and
stacked. Canonical main is `cd73ae8c653953289ee758ce24e4821f1b4c5108`.
This branch starts at verified P2 `7168a2346b9f3656e0f8d68fbee294d525a292a0`.
No merge is authorized. No ALVA, Guard, MCP or agent harness feature is added.

## Question and conditions

Does the existing optional Guard workflow add useful detection or evidence
binding beyond ordinary Codex + Git diff + the **same tests**, on these tasks?
This is a six-task exploratory convenience sample, not a statistical or
language-superiority study. Six task pairs, one fresh turn per condition, at
most twelve turns. No replacement, unilateral retry, outcome-based exclusion,
task redesign or extra run. All observed failures remain in the record.

- A: normal Codex editing, shell, Git status/diff and local Python tests.
- B: all those same tools, plus the existing P2 Skill and host-owned Guard
  snapshot/verify/report callbacks. The original project is never applied to.

Each starts from a disposable candidate with its own Git commit and identical
source/test bytes, same authorized editable files, same public task, explicit
model, reasoning, sandbox backend, shared observation budgets and independent
terminal evaluation. Both retain normal tests; A is not deliberately crippled.
B's additional tool schema, instructions, baseline rechecks, feedback and timing
are part of this **workflow bundle**, not isolated compactness or a new oracle.

## Public maintenance tasks

All six use genuine upstream commits and issue-derived requests. These are
**runnable upstream maintenance slices**, not entire repository benchmarks:
cachetools/more-itertools use their complete runtime Python package; boltons
uses its independently usable strutils/timeutils modules and package initializer.
BSD/MIT licenses are retained in each input. No reference fix is shown to agents.

| Task | Public source | Frozen upstream commit | Authorized source |
|---|---|---|---|
| CACHE-EXPIRY-ERROR | [cachetools #440](https://github.com/tkem/cachetools/issues/440) | `9976f1a8076631560f49c5b0dfda7e4d00ee0a4a` | cachetools/__init__.py |
| CACHE-EXPIRE-RESULT | [cachetools #323](https://github.com/tkem/cachetools/issues/323) | `51ec8b9fecab300c2708d64e4407abe95e29bad1` | cachetools/__init__.py |
| BOLTONS-EXPORTS | [boltons #355](https://github.com/mahmoud/boltons/issues/355) | `6cac49ce4eba506a3582e8089bcc347c6b2fa70f` | boltons/strutils.py |
| BOLTONS-NAIVE-EPOCH | [boltons #369](https://github.com/mahmoud/boltons/issues/369) | `6cac49ce4eba506a3582e8089bcc347c6b2fa70f` | boltons/timeutils.py |
| ITER-WEIGHTED-EMPTY | [more-itertools #1318](https://github.com/more-itertools/more-itertools/issues/1318) | `b21ec4ee8e139ebe297e2221980a694bebb69523` | more_itertools/more.py |
| ITER-ADJACENT-IDENTITY | [more-itertools #1319](https://github.com/more-itertools/more-itertools/issues/1319) | `b21ec4ee8e139ebe297e2221980a694bebb69523` | more_itertools/more.py |

Statements are in frozen `tasks.py` and each input's `TASK.json`. They specify
the acceptance contract rather than treating an ambiguous issue as an oracle.
For #323 we explicitly choose returned expired pairs, not a popitem redesign;
for #355 we retain existing real exports without inventing replacement APIs.
Some recent upstream reports disclose Codex assistance; that provenance is not
hidden or presented as production-originated demand. Public historical tasks
may be familiar to a pretrained model. No independent held-out claim is made.

Selection was based on runnable stdlib-only scope and public provenance before
any pilot generation, not on A/B outcomes. It is not randomized sampling and
does not cover arbitrary Python apps, dependency setup or large refactoring.

## Independent evaluation

The same public `test_pilot.py` is available to both arms. A focused regression
group protects unchanged behavior; a task group executes multiple concrete edge
cases. All six baselines must pass regression and fail the task group for the
documented behavior, not infrastructure. These are focused checks, **not full
upstream test suites or complete behavioral specifications**.

At termination a trusted host constructs a fresh tree from original frozen
inputs, copies only authorized candidate source files, and runs the unchanged
frozen evaluator. Modified tests/metadata do not become evaluation authority:
they are separately recorded as scope violations. Completion requires task and
regression PASS plus no scope violation; agent messages do not count as truth.
Final diffs, file manifests, evaluator outputs/hashes and local tool records are
retained. A's ordinary tests may detect exactly the same functional defect as
Guard; such a detection is not scored as ALVA-specific value.

## Exact freeze and execution

`pilots/codex_guard/EXECUTION-FREEZE.json` binds actual input files, licenses,
evaluator, statements, schedule, runner, P1/P2 implementations/Skill, Python and
Codex executable identities, policy bytes, prompts and real initialized candidate
Git commits. It is not a list of placeholders. All 12 source/candidate trees,
approved policy files, `thread-start-input.json` and `turn-start-input.json`
exist in host-local `.local/p3-execution` before generation. Their exact hashes
are public; machine-specific policy paths and local archives are not committed.
Only the fresh transport thread ID is added at execution. Byte attributes
prevent checkout newline conversion from rewriting public frozen inputs.

The freeze is committed and pushed before the batch starts. One sequential
batch reads the frozen inputs. Per-task arm order alternates A/B, B/A across
the six listed tasks. Each uses fresh workspace/thread; previous trajectories,
patches and reference fixes are not provided. Shell read access is not a strong
cross-session confidentiality barrier; agents are explicitly instructed not to
inspect other runs. No claim of adversarial blinding is made.

Frozen configuration: `gpt-5.6-sol` / OpenAI, low reasoning, one fresh Codex turn,
480-second observation deadline, 40 tool-item observation threshold shared by
normal commands/edits and Guard tools, up to 8 Guard callbacks within that total,
120,000 host-reported-token interruption threshold, concurrency 1. This uses
Codex's existing agent loop, not a new harness/provider adapter. Notification
interruption is not a hard pre-request token admission or hard per-command cap:
an in-flight action/request and cleanup can outlast an observation threshold.
Actual overshoot is retained, not rebilled or hidden. No extra turn or retry is
issued by this driver. Provider-internal behavior remains Codex-owned.

Model/provider identity is checked on thread creation. Ordinary task FAIL or
budget stop closes that slot and continues the frozen batch. A new reproducible
common host defect, unexpected approval or loss of source authority stops the
affected batch and preserves completed/started positions, without replacement.
Exclusive STARTED markers prevent silent reexecution.

## Trust, metrics and interpretation rules

Only these reviewed public, trusted-local fixtures are executed. Candidate-only
Codex sandbox writes and denied policy/source writes are mechanically probed.
The P1 test executor remains trusted-local, not a malicious-code sandbox. No
production data, credentials, deployment, native AIR, or semantic transaction
claim is involved. Policy approval is a host action; the model cannot supply
policy fields or expand its editable set.

For every task/arm retain task completion, focused regression failure, scope
violations, source integrity, Guard adoption/checks/applicability/candidate match,
elapsed time, tool items and available Codex token-accounting events. Unknown
usage stays null; cached input is included, never subtracted. Tokens are
host-reported, not an independent invoice. Dollar cost is unavailable for the
subscription host and remains null, not zero. Report each pair before totals.

A potential false rejection requires independent task+regression PASS, valid
scope, unchanged original source/current candidate, yet unusable Guard evidence.
Inspect its actual recorded reason; STALE caused by changed source or evidence
about an older candidate is not automatically a false rejection. No Guard call
means adoption absent, not evidence of Guard ineffectiveness. A mismatch between
Guard and terminal evaluation is a flagged discrepancy, not presumed superiority.

Separate zero-model cases compare stale source, post-verification candidate
change and protected-file changes. Ordinary Git can detect changes if its diff
or hashes are inspected; we do not pretend those capabilities are unique to
Guard. Guard's automatic policy/evidence linkage is distinct from test power.
These cases are not counted as agent-correctness wins.

Outputs are descriptive counts and per-task observations, no p-values,
statistical victory, causal attribution to one submechanism, or general agent
correctness improvement claim. Preserve mixed/negative evidence and stop after
this batch. Do not reopen E5/SS, calibrate difficulty or add a new treatment.

## Reproduce

Public frozen inputs run without network or a Codex login:

```text
python -m unittest discover -s tests/python_guard_pilot -v
```

Preparation was `python pilots/codex_guard/prepare.py`, using exact upstream
clones in ignored storage; it refuses existing freeze/runtime inputs rather than
regenerating them. `python pilots/codex_guard/run.py` is the **model-generating**
batch: it requires intact actual local runtime files, a clean pushed freeze and
no started slots. A new host must deliberately create a new preparation/freeze;
it cannot reuse the published run's policy hashes or results by changing paths.
CI validates frozen fixtures and deterministic scenarios only, never model runs.

Codex transport/usage reference: [official app-server documentation](https://learn.chatgpt.com/docs/app-server).
