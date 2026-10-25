---
name: python-guard
description: Propose Python edits in an isolated candidate and request host-owned Python Guard verification, when the user opts into a prepared Guard workflow. Not the ALVA-native transaction workflow.
---

# Python Guard candidate workflow

Use only a session prepared by the user or trusted host. The host supplies an
immutable source snapshot, candidate root, editable paths and approved checks.
Only the candidate is writable. Policy, original source, verifier code and
evidence must be outside your write authority, enforced by the host sandbox.
Instructions and hashes alone are not an access-control boundary. If the host
cannot establish that separation, stop and ask for a supported launch.

Read and edit the candidate using ordinary tools. Preserve protected tests and
configuration. Do not author or relax a policy, install dependencies, change
trust flags, or apply/commit changes to the original project.

After a meaningful candidate change, call `guard_verify` with `{}` if the host
provides it. The host generates an exact P1 patch against the snapshot and
runs the approved checks in fresh baseline/candidate copies. It never runs
checks from the mutable working copy directly. A completed tool call is not a
passing check: inspect `checks_status` and `applicability_status` independently.
You may repair candidate source within the existing task/budget, then verify
again. Do not weaken tests to obtain PASS.

Before handing off, call `guard_report` with `{}`. Report PASS, FAIL, UNKNOWN
and STALE faithfully, along with baseline failures, exclusions and uncovered
behavior. `candidate_matches_verified_patch` must be true for evidence about
the current candidate. PASS/CURRENT is bounded checking, not proof of correctness
or permission to apply. Leave application to the user.

If dynamic tools are absent, ask the trusted host to run the standalone CLI:
`python -m integrations.python_guard_codex verify --control <host-session>`
and then `report`. Do not run it with elevated write access yourself. Do not
invent a successful result while waiting. No automatic apply or Git commit
operation exists in this workflow.
