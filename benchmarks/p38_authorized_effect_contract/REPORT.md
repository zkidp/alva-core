# P38: Authorized Effect Contract deterministic study

Disposition: **NO_OBSERVED_INCREMENTAL_VALUE** relative to the strong source
diff-plus-tests baseline. Four registered counterexamples executed; model
generation calls = 0; input-token API calls = 0. No formal model slots exist.

The sequence is auditable in Git: prior-art review and case/contract
registration at `4fe0edceae8721f808e750c2dca266417d92ee98`, followed by
implementation and primary execution at
`3bb65c0f2abd9ab915d87dcabefe907927a3091a`. The registration is never changed
after comparison. The independent scoring oracle is not a mechanism input.

## Findings

Actual P34 allows the structurally authorized C1 candidate; fresh AIR
independently reproduces its protected caller regression. All test-aware
comparators reject it. All four mechanisms permit C2's explicitly authorized
downstream change. Actual Guard rejects C3's shared-parent structural
propagation without dispatching a Native commit. A/D retain UNKNOWN on C4's
absent required proof; ordinary testing and P34 do not enforce that extra rule.

A and D match the registered oracle on 4/4 decisions; B on 3/4; C on 2/4
under the stronger contract. No legitimate case is falsely rejected. These
counts compare declared policies, not statistical reliability. D supplies
no additional decision over strong A and adds no semantic proof.

Three actual Guard commits and four quarantine observation commits occur.
All committed states have fresh-process identity checks. Guarded C1 is the
one actual publication violating a confirmed stronger behavioral invariant;
C4 is separately proof-insufficient. A/B/D are offline decision simulations,
so their publication counts are null. No production AEC gate was installed.

## Deliverables and reproduction

- PRIOR-ART-MATRIX.md distinguishes established tools/theory, different
  assumptions, possible gaps and unverified claims, including pinned
  CodeStruct implementation paths and the AIR authority difference.
- AEC-V0-CONTRACT.md specifies trusted intent, actual structural roots,
  potential dependencies, observed behavior, evidence strength and decisions.
- REGISTRATION.md, COUNTEREXAMPLES.json, oracle.json and fixtures register
  selection, exact original/candidate bytes, expected policy and metrics.
- study.py runs the complete candidate-local batch using unchanged P22/P23,
  public 20-tool Native MCP, actual P34 and isolated independent evaluation.
- mechanisms.py implements bounded source scope, actual structure, direct
  call impact and policy decisions without loading expected verdicts.
- BASELINE-COMPARISON.json / BASELINE-ANALYSIS.md report same-candidate
  outcomes, real publication evidence, timing and baseline limitations.
- NOVELTY-DECISION.md answers all four research questions and recommends
  narrowing the hypothesis.
- validate_evidence.py / VALIDATION.json check retained raw evidence;
  ARCHIVES.json records CI archive identities and retention limits.

Linux, with the unchanged public SDK and public Cargo registry:

```sh
python -m unittest benchmarks.p38_authorized_effect_contract.test_study -v
python benchmarks/p38_authorized_effect_contract/study.py \
  --alva alva/target/debug/alva --toolchain "$(rustc --print sysroot)" \
  --registry "$HOME/.cargo/registry" --output out/p38-wave
python benchmarks/p38_authorized_effect_contract/validate_evidence.py out/p38-wave
```

The new CI runs controls on Windows/Linux and the isolated batch on Linux.
It runs cargo fmt, clippy with warnings denied, test and build on unchanged
Core. Primary CI completed 3/3 jobs. Final exact-HEAD CI is recorded in the PR
Git report. No P20–P37 historical experiment is rerun. Raw engineering calls
and logs stay in ignored local files / CI artifacts, not the public source.

## Controls, limitations and Git boundary

Canonical base: `0f9713848bf052161ca74e84fe7b17955daa61f6`.
Branch: `codex/p38-authorized-effect-contract`.
PR base: `codex/p37-prospective-maintenance-qualification`.
The PR description records full final HEAD, parent, exact compare/changed
files, final CI, origin equality and clean worktree without a self-referential
commit hash embedded in this file.

Only this P38 directory and its new workflow are added. Core/AEP/MCP, P34
Guard, official Skill, P36 startup cleanup and every P20–P37 frozen artifact
remain byte-identical to the canonical base. P37 remains four registered /
four QUALIFIED_MATCHED, from two correlated component sources, zero models
and no formal Text/Native model outcome. No historical conclusion is rescored.

The first wave has no execution failures. The initial local syntax typo was
caught by py_compile before any study execution. A later actual-Git-diff /
metadata-binding / timing conformance improvement is disclosed in
BASELINE-ANALYSIS.md; it changes no registered rule or scientific outcome.
All executed waves and any later failures remain retained in CI artifacts.

Limitations: synthetic arithmetic cases, one closed module per case, finite
samples, no checked proof, trusted collector, no adversarial concurrency or
I/O, narrow source parser, and D's decision simulation instead of a live
publication gate. The strong source baseline shares the policy combiner with
D; this explicitly demonstrates composition parity rather than independent
algorithm competition. Incremental end-to-end runtime overhead is not isolated
and remains null. No global novelty, universal safety, model ability or
cross-language implementation claim is supported.

Create the independent PR, then STOP for review. Do not merge, change Core,
run a model or start P39.
