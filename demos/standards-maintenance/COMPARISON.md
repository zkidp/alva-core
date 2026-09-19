# Next maintenance comparison — proposal only

**Question:** compare implementation stacks (ALVA library/toolchain versus a
reasonable conventional stack) on the cost of completing the same concrete
change and satisfying the same acceptance/regressions. Do not attribute a
stack-level result to language syntax, AIR/AEP, or one compiler mechanism.

SM-001 is excluded: it has been selected, implemented and debugged in this
development case. It is not unseen. Of the other examined records, #328 concerns
a schema format validator that neither ALVA's component nor its Rust performance
reference owns; #758's invalid-Pointer condition is already rejected by the
existing parser, while full anchor/URI resolution belongs to a schema resolver.
Neither is currently a fair unsolved, in-scope comparison task. No task is retained
merely to fill an evaluation list. No external reference repair was inspected;
public issue explanations and normative specifications were inspected.

The Rust `json-patch` performance reference cannot automatically serve as a
maintenance arm: its crate dependency, adapter and ALVA library own different
layers. Its existing README pins `json-patch` 4.2.0 and `serde_json` 1.0.151;
Patch execution is delegated to the former. Only that README/dependency metadata
was read after SM-001 selection, not the reference implementation or a repair.
For SM-001, ALVA owns the new decoder and needs a small stdlib conversion;
a conventional adapter could use existing ecosystem URI facilities. Whether a
specific pinned conventional stack already satisfies the whole new contract,
or exactly the same old contract, has **not** been established. Its work may be
smaller or zero; no equal-work starting point is claimed. Before selecting a
future task, map the behavior owner in each stack,
verify both starting versions satisfy identical old requirements, and explicitly
allow changes to the corresponding application/library/dependency layers.
Check the chosen conventional dependency's actual pinned capability. If it
already supports the change, record zero implementation required; do not remove
features or forbid normal dependencies to fabricate symmetric work. Toolchain
work required only on ALVA's side is real stack cost, not excluded setup.

There is therefore **no justified comparative execution ready now**. A future
bounded task search and conventional-stack capability check must yield concrete
sources and starting commits first. This does not block delivery of SM-001.

Before any future run the user must approve: task list and start versions; both
arms and allowed code; exact model ID/configuration; per-task and total elapsed,
request, token and monetary ceilings plus currency; participants if any; and
how human active time is recorded. All are presently **TBD**, not authorized by
this proposal. No model credentials were read or tested in this task.

Primary outcomes: new requirement correctness, old regressions, usable independent
consumer. Cost accounting must include failed attempts, build/test wait and agent
elapsed time, plus human active time only if actually recorded. Missing labor
data stays missing: neither tokens nor commit timestamps proxy for it. Few
related tasks support case-level reporting, not treating tool calls as independent
statistical samples. No submission deadline supplies authorization or a positive
result assumption. Controlled maintenance comparison: **not executed**.
