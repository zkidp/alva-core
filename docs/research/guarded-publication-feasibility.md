# After PR43: bounded publication baseline feasibility

## Scope and provenance

This follows the owner's requested competitive-position report and subsequent
choice to do deterministic verification because no non-author participant is
available. It is Codex-assisted development, with **zero provider generation
and input-token API calls**, not model-free authorship, agent effectiveness,
an independent human walkthrough, or a new novelty claim. The supplied report
is not copied into the public repository. Its suggested experiments are proposals,
not executed instructions.

Base: PR43 `3bddc89f476336170bfa158903d09766fcf91a98`; observed main:
`cd73ae8c653953289ee758ce24e4821f1b4c5108`. PR43 was OPEN, without independent
reviews, and all 14 checks SUCCESS at inspection on 2026-11-09. This branch
stacks on PR43, not on an assumed merged main. No merge is authorized here.

## Historical constraints remain in force

- [P38](../../benchmarks/p38_authorized_effect_contract/NOVELTY-DECISION.md)
  remains **NO_OBSERVED_INCREMENTAL_VALUE**: equivalent trusted source diff,
  tests and policy could make the same decisions. We do not rerun its cases,
  search for cases to reverse its conclusion, or rename its hypothesis.
- [RDR02](../../benchmarks/rdr02_treatment_realization/NOVELTY-DECISION.md)
  remains **INCONCLUSIVE_EVIDENCE_LIMITATION**, with zero E0/E1 disagreements.
  Recording exact versions is not an ALVA-exclusive measurement capability.
- PR43 demonstrates an author-scripted real consumer round trip, not external
  usability or model benefit. Existing closed model trials remain unchanged.

The narrower work here is executable baseline preparation: P38 simulated the
source policy decisions; this driver uses **actual Git object creation and
checked reference updates** on PR43's different public example. This fills an
operational comparison hole, not a claim that the old scientific question was
unanswered. It must not become another paid mechanism-tuning loop.

## What the comparison actually runs

Entry: `scripts/publication_baseline_feasibility.py`. One fixed, public,
author-created packing demo, two modules, same task and protected helper tests.
These are six scripted scenarios of **one fixture**, not six maintenance tasks,
six independent samples, or held-out effectiveness evidence.

**Text + Git + tests:** exact source candidates enter a disposable bare Git
repository. The trusted driver restricts edits to the example's predeclared body
byte region; manifest, other declarations and other files must stay unchanged.
This is an intentionally narrow byte allowance, not a general ALVA parser or
semantic baseline. Complete check/build/behavior tests run on bytes read back
from the candidate commit. Publication updates `refs/heads/published` using the
expected original commit, not a mutable candidate worktree. Subsequent readers
read the commit referenced by that ref. No remote service or protected GitHub
branch is actually provisioned. Trusted tests, authorization and publication
control are explicit pipeline components, not built-in Git semantics.

**ALVA:** the existing three-action Host is launched over real stdio, with its
unchanged Guard and Linux evaluator. The same tests and target-body permission
apply. Candidate AIR becomes authority only through the existing publish action.
The successful result is read from fresh authority, independently evaluated,
projected into a separate source project and evaluated again.

Candidate builds and behavior execution, plus source-only parse/check evaluation,
use existing Linux OS isolation. Native graph/body parsing and transactions use
the existing Host's trusted `AgentProcess` on the host; this is not a claim that
the entire three-action server runs inside the P23 sandbox. No isolation boundary
is newly strengthened here. The trusted Git driver only stores/reads fixture bytes
and updates its new local ref; it never runs candidate hooks, shell or code. Neither path mutates
the checkout containing this example. Output directories must be new.

| Scripted scenario | Expected controlled publication |
| --- | --- |
| Correct local repair | Both publish; final behavior passes |
| Malformed candidate | Neither publishes |
| Check-valid, behavior-wrong candidate | Neither publishes |
| Good preparation followed by failed new preparation | Old proposal cannot publish |
| Source bytes change after preparation | Neither publishes old preparation |
| Second checked publication advances authority first | Old publication rejects; concurrent state survives |

Concurrent injection is deterministic, not a stress test or proof of all races.
The Git side executes a genuine failing old-ref update. The ALVA side uses a
second real Host with the same checks to publish an alternate valid body before
the original Host attempts to publish. No Host publishes on the model's behalf;
there is no model in this driver.

A **separate unpaired coverage probe** gives Text a correct target change plus
a behavior-preserving unauthorized helper edit. Tests alone pass, while the
declared source byte allowance rejects it. The three-action ALVA input only
accepts one authorized body, so this complete source proposal is
NOT_REPRESENTABLE_BY_THREE_ACTION_INPUT. This is not counted as an observed
Native rejection or a matched candidate comparison. Shared-node graph mutation
is not retested here; P33-P35 remain the relevant historical evidence.

## Reproduction and output

Use the Linux prerequisites in the
[consumer Quickstart](../maintenance-consumer-quickstart.md). From a clean checkout:

```sh
cargo build --locked --manifest-path alva/Cargo.toml
python3 -m unittest tests.integrations.test_publication_baseline -v
python3 scripts/publication_baseline_feasibility.py \
  --alva "$PWD/alva/target/debug/alva" \
  --toolchain "$(rustc --print sysroot)" \
  --registry "${CARGO_HOME:-$HOME/.cargo}/registry" \
  --output "$PWD/.local/publication-01"
```

`INPUTS.json` binds actual fixture/test/driver hashes, scenario order and expected
publication before the run. It is not a model execution freeze. `RESULTS.json`
contains per-scenario statuses, exact checked snapshots, Git OIDs, authority and
handoff results. Git commands, real stdio and evaluator outputs stay in the local
output tree/Actions artifacts; they are not committed. A partial failure retains
the completed prefix and exception, rather than replacing a run. Windows unit
tests exercise real Git; Windows/macOS candidate execution remains unsupported.

Do not compare the driver's combined elapsed times as interaction economy. It
performs different trusted inspection and handoff work per representation, has
no Agent, and does not measure setup or human burden. Native authority and source
projection are separate operations. Git commits/reference updates likewise do
not provide atomic deployment or rollback of arbitrary external effects.

## Competitive comparison: evidence, not a substitute third arm

Primary sources checked on 2026-11-09:

- [CodeStruct](https://github.com/amazon-science/CodeStruct/tree/d89efa473754f455d38ab47b4dc938cfc8334a0d):
  structured code actions and published benchmark results. This node does not
  reproduce those results, install its Agent stack, or establish an ALVA frontend.
- [Serena language support](https://oraios.github.io/serena/01-about/020_programming-languages.html)
  and repository HEAD `ede329aaf0c824bea75455a2926f01420d7aa620`: mainstream
  symbol tooling is relevant competition; ALVA is not listed as an out-of-box
  language on the inspected support page. This does not prove adaptation is
  impossible. An ALVA-capable third arm has **not been established**.
- [OpenRewrite recipes](https://docs.openrewrite.org/concepts-and-explanations/recipes):
  composable semantic transformations overlap with editing, not evidence of a
  matched ALVA experiment.
- [Git update-ref](https://git-scm.com/docs/git-update-ref): old-object checking
  already provides a conventional stale-publication primitive. Our driver uses
  it rather than claiming stale rejection is unique to AIR.

Consequently no fake "Serena-style" or "CodeStruct-style" arm is implemented.
The report's three-system proposal cannot yet be run as a fair same-language
off-the-shelf comparison. Migrating tasks to Python or inventing an ALVA adapter
would change the question and is not done here. No broad language-count,
performance or global novelty claim is adopted from the report.

## Decision and next necessary work

### Actual deterministic result

The full run on 2026-11-09 passed on Ubuntu 26.04/WSL, Python 3.14.4,
Rust 1.98.0, Git 2.53.0 and bubblewrap 0.11.1:

| Scenario | Text final publication | ALVA final publication |
| --- | --- | --- |
| Correct | PUBLISHED | PUBLISHED |
| Malformed | REJECTED | REJECTED |
| Behavior wrong | REJECTED | REJECTED |
| Failed reprepare | REJECTED | REJECTED |
| Source changed | REJECTED: SOURCE_BASE_CHANGED | REJECTED: SOURCE_CHANGED_READ_TARGET |
| Authority changed | REJECTED: old-ref update failed | PUBLISH_REJECTED: E_AEP_CONFLICT |

Both concurrent winners were preserved and independently passed tests. Only
the correct primary candidate published; rejection does not complete the task:
without a concurrent winner, the original behavior remains task-failing. The
unpaired protected-helper edit check/build/tests all passed, but its source scope
was rejected. No Native full-source rejection is claimed for that probe.

The first development run completed all six pairs but failed the last unpaired
probe due to an extra closing parenthesis in this new driver. It is retained
locally, not reclassified as an ALVA failure. After the one-character correction,
the entire driver passed in a new output directory. No historical freeze or
model slot was changed or repeated. Results SHA256:

- Incomplete development result:
  `d8e14409c7619d9c64dc9358a907c593f0aab91825b1711718853976834d00a4`.
- Complete local result:
  `c71901963a877eae0f00b63e7ab86fdb66c3c005ce41eb5eb95723195068bf9c`.
- Complete-run driver:
  `ea0333c9aaef978e7f0061079cef067e6cd1c1ec46e0e62df941c9aa42092cc2`.
- Exact source input snapshot:
  `bfbe99a515f5ba8b2302a09f122a5b84c4a7a2b824f7f56ab27acd2b2a5340ce`.

Windows and Linux each passed four real Git unit tests. These unit tests label
their evaluator stub explicitly; only the Linux integration driver uses actual
compiler/build/behavior checks. New CI reruns that full driver and saves its own
runtime evidence as artifacts; local hashes above do not imply identical timing,
random proposal IDs, result hashes or toolchain bytes across machines.

### Bounded conclusion

The six scenarios agree. The supported statement is operational overlap in
this example: an explicit strong source/Git/test pipeline can bind checked bytes
and reject stale publication too. It does not prove systems equivalent, establish
user value, or invalidate ALVA's engineering reliability. A larger experiment is
not justified merely by repeating these same decisions.

Keep the three-action Host as an opt-in engineering prototype. Do not expand
AIR operators, obligations, navigation or language features. Do not tune these
fixture cases to make ALVA win. The next unavailable input is a genuine
non-author walkthrough, using the accompanying
[participant packet](maintenance-non-author-walkthrough.md). Its status is
NOT_EXECUTED, not PASS. The owner explicitly reports no participant yet.

Only after real setup/recovery/handoff observations identify a task with a
plausible trade-off should a separate model comparison be proposed. It must:
use fresh maintenance tasks, the same public checks/scope/acceptance on both
sides, normal source tools with candidate branches and trusted publication
checks, exact candidate-bound evidence, and separate task completion from bad
publication. Fix actual model/provider limits and cost measurement before any
generation. Publish ordinary failures; no favorable task screening. A third
semantic competitor requires a genuinely supported shared language, not a new
parser presented as an existing product. No model execution is authorized or
started by this preparation.
