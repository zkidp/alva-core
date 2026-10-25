# Optional Codex + Python Guard candidate workflow

P2 is stacked on the P1 Guard, not a change to the ALVA-native plugin. Python
source stays authoritative. Nothing here applies a patch to source or commits
Git. This is engineering integration, not evidence of improved agent correctness.

## Trust and installation

Use Python 3.12+ and the checked-out repository. No extra Python dependencies.
The native ALVA compiler, MCP server and Skill are not needed by this consumer.

The **user or trusted host** writes and approves a complete P1 policy outside
the project and outside every agent-writable root. Review the exact `files`,
`editable`, interpreter, check argv, exclusions, scratch outputs, resource limits,
and `trusted_project`. Obtain the SHA256 identity from these reviewed bytes;
do not accept an identity or replacement policy chosen by the candidate agent.
See [P1 implementation](python-guard-implementation.md) for the policy schema.

**A separate directory is not an access-control boundary.** Run Codex with an
OS-enforced candidate-only writable root, approvals disabled, no network and no
implicit writable TEMP roots. Policy, source, control/evidence, verifier/Skill
code and check scratch must be outside agent write authority. Do not launch this
workflow with full filesystem access or approvals that can expand the roots.
The example checks real denied writes before doing any model work and refuses
an unsupported configuration. There is no automatic fallback to full access.

P1's check backend remains `trusted-local`, **not a sandbox**. Approving
`trusted_project` includes trusting execution of the candidate and authorized
check code. Shell isolation of the coding agent does not make malicious code
safe when a trusted checker later executes it. Untrusted projects/candidates
require an external execution sandbox and are not supported by this adapter;
keep `trusted_project=false` and obtain UNKNOWN without running checks. This
adapter does not grant itself trust, install dependencies, or supply a new
secure execution backend. Tests may have external effects that Guard cannot
roll back. Only use the public toy example or appropriately trusted projects.

## Standalone consumer CLI

Run these commands from a **trusted host terminal**, not an agent shell. Use
absolute paths. `<CLI>` means the clone's `scripts/python_guard_candidate.py`.
Policy, check-scratch, control and candidate must be separate paths; control and
candidate must not already exist. The project may have dirty files: actual
bytes, not Git HEAD, are the base.

```text
python <CLI> prepare --policy <approved-policy.json> --approved-policy-id sha256:<reviewed-hash> --control <new-host-control> --candidate <new-candidate>
```

This captures the source snapshot with the real P1 Guard, materializes its exact
bytes in the candidate and records the approved policy/snapshot identities in
protected host state. It does not edit source or execute project checks. Review
the returned `editable` paths. Give Codex **only the candidate** as its writable
workspace; do not add the source, policy, control or tool installation as writable.

The independently optional Skill is
`integrations/skills/python-guard/SKILL.md`. A trusted host can pass its absolute
path as a Codex app-server `skill` input, or a user may explicitly install that
folder in their Codex skills directory. The repository never updates the user's
installed plugins/skills automatically. Installing this Skill does not change
the native `alva` Skill or enable Guard for unrelated tasks.

After ordinary candidate edits, the trusted host runs:

```text
python <CLI> verify --control <host-control>
python <CLI> report --control <host-control>
```

The host computes a deterministic full-file unified diff (including CRLF and
no-final-newline handling), round-trips it through the existing P1 parser, and
supplies exact preimage hashes. It rejects undeclared files, mode changes and
protected-file edits; it does not silently drop a changed file. P1 re-materializes
fresh baseline and candidate check trees and runs its original verification.
Generated caches may be ignored only at policy-declared scratch paths. No edit
produces `NO_CANDIDATE_CHANGE`, not a synthetic passing check.

`candidate.patch`, `verify-request.json`, and content-addressed P1 evidence remain
in host control storage. There is no apply command. Review the exact patch and
limitations, then decide whether to apply using your own tools. Recheck the base
immediately before a later application; evidence does not make that write atomic.

## Host callbacks, without another agent harness

An app-server consumer may register the optional `TOOLS` from
`integrations.python_guard_codex` on `thread/start` and route the existing
`item/tool/call` callbacks to the bound `session.tool_call(name, arguments)`.
Both tools take `{}`; neither accepts paths, policy, trust, limits or commands.
`guard_verify` and `guard_report` are host callbacks, not MCP additions. Use the
same sandbox policy for command probes and the model turn. The example reuses
the existing app-server test client; Codex still owns model execution, editing,
continuation and normal tool handling.

The Skill requests verification after meaningful edits, inspects feedback and
requests a report before handoff. Without these callbacks it asks the trusted
host to use the CLI; it must not elevate itself to run the host operations.

## Status and failure handling

Keep `checks_status` (PASS / FAIL / UNKNOWN) separate from
`applicability_status` (CURRENT / STALE / UNKNOWN). A successful callback means
the operation returned, not that checks passed. A failed syntax/test check
remains FAIL. Missing evidence/dependencies, unsupported execution or timeout
remain UNKNOWN; changed source is STALE. Existing baseline failures remain
visible. Tool errors have UNKNOWN statuses and a reason, never a green result.

`report` also returns `candidate_matches_verified_patch`: false means the
working candidate no longer matches the evidence, even if the historical checks
are PASS and the original source is CURRENT. Verify the new candidate before
using that evidence. CLI returns 0 only for PASS/CURRENT with a matching candidate,
1 for failed checks, and 2 for other non-usable results. Report never reruns checks.

## Reproduce engineering checks (Linux / Windows)

From the clone, with Python and Codex on PATH:

```text
python -m unittest discover -s tests/python_guard -p test_candidate_workflow.py -v
python examples/python_guard_codex/demo.py
```

The default demo creates a separate public consumer project, installs the
optional Skill only in a disposable Codex home, discovers it via real Codex
`skills/list`, probes actual denied writes, and edits the candidate through real
`command/exec`. It then runs real Guard verify/report. Its `+ 0` edit deliberately
does **not** implement the requested input validation: expected checks FAIL /
applicability CURRENT is a passing engineering test, not a task success.
No model turn or credential is required for this mode.

CI pins official Codex 0.164.0 on Linux/Windows and installs Linux `bubblewrap`.
The standalone example disables unrelated plugins, leaving the separate Guard
Skill and host callbacks available without background marketplace cloning.
The local Windows demonstration
used 0.163.0-alpha.11.2. The example explicitly selects the legacy `unelevated`
Windows backend for this bounded fixture; it neither changes global config nor
installs elevated sandbox accounts. Source, policy, control and tool directories
are still required to pass actual denied-write probes. Unsupported platforms or
restricted CI environments fail explicitly, rather than bypassing isolation.
Windows candidate storage uses a normally created `.local/` directory, avoiding
the restrictive parent permissions Python `TemporaryDirectory` can create for
the restricted-token child. Policy/control still must be outside writable roots.

## Opt-in model demonstration, separate from CI

The following command **does use the user's authenticated Codex model**. Review
the toy public task and policy in `examples/python_guard_codex/` first. It sends
only that consumer task and candidate, not any private research material.

```text
python examples/python_guard_codex/demo.py --model-demo --directory <new-local-demo-directory>
```

It permits one fresh Codex turn, with a 240-second observation deadline,
a 20-command/edit-item threshold and 4 Guard callbacks. Already-started built-in
actions and cleanup may outlast interruption; Guard checks also have their
independent policy wall limit. It requests no retries or extra turn. Codex may internally
make multiple provider requests; this is not a hard provider-token budget.
No raw transcript/reasoning or credentials are saved. Candidate/evidence may
be retained locally via `--directory`; do not publish local machine paths or
private test output. A model failing to edit or request verification remains
an observed failure, not an excuse for an automatic replacement run.

For the executed engineering/model results and limits see
[P2 integration evidence](python-guard-codex-evidence.md).

Official references consulted: [Codex skills](https://developers.openai.com/codex/skills),
[app-server callbacks](https://learn.chatgpt.com/docs/app-server),
[Windows sandbox](https://learn.chatgpt.com/docs/windows/windows-sandbox).
