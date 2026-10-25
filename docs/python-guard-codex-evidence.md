# P2 integration evidence

Base: P1 `a83e94956c459e87bd489dd7a4efd4e43d6adf84`, PR #17.
P0/P1 are explicitly stacked dependencies, not assumed merged into main.
No original ALVA MCP/Skill semantics or P1 Guard implementation changed.

## Engineering calls (no model turn)

Local platform: Windows 11 x64, Python 3.14.0, desktop Codex CLI
`0.163.0-alpha.11.2`. Candidate workflow regressions: 13/13 PASS.
This is P2 implementation regression, not another P0/P1 capability audit.

Real app-server acceptance PASS:

- Optional `python-guard` Skill copied into a disposable Codex home and discovered
  enabled through `skills/list`; no user's installed Skill/plugin changed.
- Real `command/exec` denied writes to policy, source, control, and verifier
  directory with the same candidate-only sandbox policy used for the model turn.
- A real sandboxed command edited only candidate `cart.py` (`sum(values) + 0`).
- Actual P1 verify/report returned the expected FAIL / CURRENT because that
  benign edit does not implement the public feature. Candidate/evidence matched.
- Original source remained byte-identical. Two engineering command calls,
  zero model turns, no automatic apply or commit. Measured host portion: 1.164 s.

Concrete development corrections retained in the example:

1. An app-server launched without an explicit Windows backend did not enforce
   the requested write policy in the initial probe. **No model ran in that
   configuration.** The example explicitly selects `unelevated` and requires
   actual denied-write probes. It does not infer enforcement from JSON settings.
2. This backend rejects a custom `outputBytesCap` on `command/exec`; the example
   uses Codex's default capture for these tiny engineering commands.
3. Python `TemporaryDirectory`'s restrictive parent permissions prevented
   restricted-token candidate reads. The supported example uses a normally
   created, uniquely named host-owned `.local/` directory, not that parent ACL.
4. Tests using isolated Python (`-I`) need explicit project import setup in the
   public test fixture. This was corrected in the fixture, not by changing P1.
5. The first CI host runs found a missing Linux `bubblewrap` dependency and a
   Windows cleanup lock from unrelated background plugin cloning. CI installs
   the sandbox runtime; the standalone Guard host disables unrelated plugins.
   Neither correction bypasses the sandbox or changes Guard verification.
6. Linux denied writes return `EROFS` with a read-only bind mount. The probe
   accepts only explicit `EACCES`/`EPERM`/`EROFS` denials, not missing paths or
   arbitrary execution errors. Windows and Linux must both execute the probe.

## One actual model-generated candidate (not engineering-only)

One fresh Codex turn was executed against the public standalone cart fixture.
The task was to retain exact sums and reject negative/non-integer inputs; public
tests were visible and protected. No reference patch or prior model output was
supplied. The fixture uses no ALVA language, AIR, MCP server or native Skill.

| Observation | Actual result |
|---|---|
| Resolved model/provider | `gpt-5.6-sol` / `openai` (user's Codex configuration) |
| Reasoning setting requested | low |
| Codex host | `0.163.0-alpha.11.2` |
| Fresh model turns started | 1 |
| Completed turn | yes |
| Command or edit items | 7 |
| Guard callbacks | 2 |
| Final required checks | PASS |
| Source applicability | CURRENT |
| Current candidate matches verified patch | true |
| Source bytes changed | no |
| Automatic source apply / Git commit | neither |
| Elapsed host/demo time | 66.377 s |

The host independently read the final report after the model turn. Local
candidate, patch and content-addressed evidence were retained in ignored local
storage; no raw transcript, reasoning, credential or machine-specific state is
published. Only these bounded observations are reported.

The driver uses a 240-second observation deadline, a 20 command/edit-item
threshold and four Guard callbacks; it does not issue another model turn or
retry the example. An already-started built-in action may finish before
interruption/cleanup. Guard checks have the policy's independent 30-second wall
limit. Provider requests/tokens are managed by Codex and were **not** independently
counted here; one turn does not mean one provider request. No token/correctness
improvement, autonomous policy safety, or arbitrary Python coverage is claimed.

## Reproducibility and remaining limits

The public CI workflow runs P2 regressions and the no-model real-host fixture on
Linux/Windows with official Codex 0.164.0. CI does not run paid/model behavior
tests. Check the PR's CI links for the actual platform results; this document
does not infer Linux success from the local Windows run.

The Skill is instruction-only and separately opt-in. Discovery/explicit loading
and this one observed use do not prove reliable automatic selection on arbitrary
tasks. The host must enforce write roots and own the approved policy. P1 still
executes only trusted-local checks; malicious candidate code requires an external
execution sandbox, which P2 does not provide. Public tests may miss defects.
PASS/CURRENT never authorizes application, proves task completeness, or makes a
later source write atomic. New evidence is needed after source/candidate changes.
