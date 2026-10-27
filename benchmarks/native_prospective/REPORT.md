# P26 prospective native MCP/Skill coding pilot — closed

Twelve new frozen slots completed once; no common HOLD, retries, replacements or extra slots.
This is a small developmental workflow-package comparison, not a superiority test.

## Per-task results (independent final scoring)

| Task | T: text | B: thin bridge | N: native + Skill |
|---|---|---|---|
| HE41 | COMPILE_FAIL | NO_COMMITTED_CANDIDATE | NO_COMMITTED_CANDIDATE |
| HE23 | COMPILE_FAIL | TEST_FAIL | NO_COMMITTED_CANDIDATE |
| HE42 | COMPILE_FAIL | NO_COMMITTED_CANDIDATE | NO_COMMITTED_CANDIDATE |
| HE3 | COMPILE_FAIL | NO_COMMITTED_CANDIDATE | NO_COMMITTED_CANDIDATE |

## Stages and costs

| Arm | Valid entity-resolution slots | Attachment slots | Commit slots | Changed target slots | API errors | Tools | Actual total tokens |
|---|---:|---:|---:|---:|---:|---:|---:|
| T | N/A | N/A | N/A | N/A | 0 | 129 | 498980 |
| B | 0 | 0 | 1 | 0 | 25 | 50 | 505812 |
| N | 4 | 0 | 0 | 0 | 0 | 46 | 518009 |

N received exact native schemas and complete official Skill/references in every slot.
It made successful discovery/schema calls without operation errors, unlike B's unknown-operation/entity/operand errors.
Three N slots performed discovery only; HE41 constructed two references but never attached or committed them.
There is therefore a bounded interface-discovery observation, **no demonstrated coding/commit/behavior utility**.
B/HE23 committed the unchanged stub: fresh-process target body hash did not change and independent behavior failed.
A successful commit must not be scored as a useful edit or task completion.
All four T final sources failed ordinary compilation. Recorded diagnostics include unknown `var`/`name` expression tags
T made 58 accepted source edits and 59 model-directed checks; AIR stage columns are not applicable to T.
and an invalid/empty `block`; these are observed constructions, not proof that ALVA cannot express the tasks.

All twelve turns were interrupted at frozen resource thresholds (eleven TOKEN, one TOOL); every interrupt was acknowledged
and terminal status recorded. Every actual token total exceeded the 120000 observation threshold; the overshoot is retained.
These are censored trajectories, not complete unconstrained solver attempts. Native schema/Skill input and repeated discovery
consume the same observation budget; their exact cost is included, not subtracted. No hard provider token cap is claimed.
Usage is present for every slot, including cached input without deduction. Provider request counts and dollar costs are unknown.

## Evidence and limits

FREEZE.json was committed/pushed before the first model turn; ANALYSIS.json crosschecks raw slot identity, schema bytes,
the authority current file, fresh-process body hashes and independent compilation/behavior. Raw transcripts, final sources/AIR,
Linux build/test output and configs remain only in controlled ignored local RAW.zip; ARCHIVE.json binds its exact bytes.
No P24/P21/P3 evidence was modified or pooled. The P25 closeout removed tracked local logs with an additive commit;
its existing PR CI automatically ran after that update. No P25 solution witness was manually rerun for pilot preparation.

N uses official workspace Skill discovery and explicit complete Skill text, plus per-process native MCP registration;
it does not update a user's installed plugin. The Skill's CLI-doctor instruction has no separate doctor tool here:
the isolated SDK was preverified by the host and model check/test callbacks use that exact SDK. This surface limitation
is not changed after seeing outcomes. N has added documentation/tool support; differences are not pure AEP semantic effects.
Public adapted HumanEval tasks may be training-contaminated; this is not an official benchmark score or independent task
generalization. Small samples, one run/condition and budget censoring preclude statistical or language-superiority claims.
The two P25 checker/anonymous-revision limitations remain; independent final evaluation, not `ok:true`, is decisive.

## Disposition

CLOSED_COMPLETE; no end-to-end utility signal established in this bounded wave.
Engineering integration is observable; coding effectiveness is not established. No automatic follow-up, rerun, merge or Core change.
STOP; independent reviewer decision required.
