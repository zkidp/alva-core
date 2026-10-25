# Python Guard MVP: snapshot, verify, report

Status: P1 design only. P0 exercises the existing ALVA-native Codex plugin;
this document proposes a separate, source-authoritative Python patch checker.
There is no Python Guard implementation or new public API in this change.

## Intended use

A coding host supplies a proposed text patch and an explicit verification
policy. Guard checks the patch in a disposable copy and returns evidence tied
to those exact source bytes. Python source stays authoritative. The host keeps
its existing editor, agent loop, Git workflow, and decision about applying the
patch. ALVA's native AIR transactions are not imported into Python projects.

The MVP supports one local Python project, regular UTF-8 source/configuration
files, bounded exact patches, syntax checks, and user-authorized check commands.
It reuses Python's compiler and the project's existing tests or linters. It
does not create another agent harness, MCP server, or language analysis engine.
A later adapter may expose these three operations through the existing host
boundary after implementation and tests; no plugin defaults change in P1.

## Shared policy and preconditions

The host, not model-authored repository text, approves the project root, file
allowlist, verification argv arrays, interpreter/environment identity, writable
scratch root, and resource limits. Policy bytes have a SHA256 identity. The
initial supported tree excludes symlinks, junctions/reparse points, devices,
submodules, external path dependencies, and files outside the approved root.
Unsupported input is reported explicitly. Never silently omit a required file.

The input manifest lists all material needed by the checks, including source,
tests, configuration, and dependency lockfiles. Exclusions such as `.venv`,
`.git`, generated caches, and secrets are explicit and reported. An omitted
runtime data file is a limitation, not evidence of correctness. Editable paths
are narrower than copied paths; tests and policy are read-only by default.
Permission to change a protected test/specification requires a new approved
policy, not a patch that weakens the current checker.

Dirty source is supported by hashing actual bytes; Git HEAD alone is not the
snapshot identity. Concurrent edits during capture must be excluded by a
cooperating workspace lock or detected by validating the full manifest after
copying. Without a stable capture, return UNKNOWN and no usable snapshot.
This cannot prove consistency against an adversarial writer ignoring the lock.

## `snapshot`

Input:

```json
{
  "project_root": "/workspace/project",
  "policy_id": "sha256:<approved-policy>",
  "files": ["src/example.py", "tests/test_example.py", "pyproject.toml"],
  "limits": {"max_files": 1000, "max_source_bytes": 16777216}
}
```

Output: `snapshot_id`, schema version, policy hash, canonical root identity,
ordered relative-path manifest (file SHA256, length, executable mode), immutable
tree digest, capture method, excluded paths/reasons, and environment identity.
The private local snapshot retains the exact bytes. The digest includes path
and mode as well as content, so additions/deletions are visible. IDs are opaque;
a caller cannot substitute a new tree under an existing ID. Snapshot capture
does not import project modules or execute tests. It leaves the project intact.

Errors include `UNSTABLE_CAPTURE`, `UNSUPPORTED_FILE`, `PATH_OUTSIDE_ROOT`,
`INPUT_LIMIT`, and `POLICY_UNAVAILABLE`. No partial snapshot is accepted.

## `verify`

Input:

```json
{
  "snapshot_id": "snapshot:<id>",
  "patch_utf8": "<bounded unified text diff>",
  "expected_files": {"src/example.py": "sha256:<snapshot-file>"},
  "policy_id": "sha256:<same-approved-policy>",
  "limits": {"wall_seconds": 120, "output_bytes_per_stream": 1048576}
}
```

The policy also fixes a tool-call count, process-count and available OS resource
envelope. It cannot be expanded by the request. The initial patch format permits
regular-file additions, replacements, and deletions only. Reject binary patches,
renames, mode changes, absolute/traversing paths and writes to protected files.
Require the expected existence and hash of every affected file (null for an
addition). Apply against the immutable copy using exact preimages/context;
reject ambiguous/fuzzy matches. Do not apply against live source.

Processing order:

1. Validate snapshot and policy identity, patch size, paths and preimages.
2. Create distinct baseline and candidate scratch trees from the same snapshot;
   apply the patch only to the candidate. Record candidate manifest/digest.
3. Run syntax compilation in the candidate with the selected Python interpreter.
   Syntax success is not import or behavioral success.
4. Run the same approved commands against baseline and candidate under equivalent
   recorded environments. For example, `["python", "-m", "pytest", "-q"]` is
   an explicit policy choice, not a mandatory dependency or an inferred shell
   command. No shell interpolation, automatic dependency install, or generated
   replacement tests. Missing tools/dependencies produce UNKNOWN.
5. Record every invocation, exit/signal, timeout, duration, bounded output,
   output digest/truncation, and any coverage/completeness limitation. Stop owned
   process trees on timeout using platform-supported cleanup. Do not relabel a
   timeout as a Python defect, silently retry, or treat missing output as PASS.
6. Compare live project bytes with the snapshot manifest before finalizing. If
   they differ, retain historical evidence but return STALE for applicability.
   Detect checker modification of guarded source/test/config inputs as UNKNOWN;
   declare allowed scratch outputs separately.

Output: `verification_id`, `snapshot_id`, patch SHA256, candidate tree digest,
policy/environment hashes, all baseline/candidate check rows, `checks_status`,
`applicability_status`, reasons, and an evidence manifest. Live source is never
written. Runtime checking is execution of project code: a temporary directory
is not a security sandbox. Production credentials must not be inherited. For
untrusted projects require an external container/OS sandbox with enforced
network, filesystem and process policy; otherwise report unsupported execution
and UNKNOWN. Denying arbitrary network access is not achieved merely by using
argv arrays. The execution backend and its actual guarantees are reported.

## `report`

Input: `verification_id` and an optional `current_snapshot_id` for applicability
comparison. Output is a read-only deterministic JSON projection of the stored
evidence, plus optional human-readable text. Validate evidence digests before
rendering. A report never reruns checks, rewrites snapshots, applies a patch,
commits Git, or converts old evidence into fresh evidence.

Checks use `PASS`, `FAIL`, `UNKNOWN`, or `NOT_RUN` per row. Overall semantics:

| Status | Meaning |
|---|---|
| PASS | All required candidate checks completed and passed under the bound policy/environment. |
| FAIL | A completed required candidate check failed; baseline results distinguish an observed regression from an existing failure. |
| UNKNOWN | A required check was missing, unsupported, timed out, had an infrastructure error, or its evidence/input integrity could not be established. |

Applicability is independently `CURRENT`, `STALE`, or `UNKNOWN`. Invalid paths,
preimages or policy produce `INPUT_REJECTED` before execution. An unchanged
baseline failure is still a candidate failure; it must not be called a new
regression. An unavailable baseline makes regression attribution UNKNOWN even
if candidate checks pass. No status means the task is fully correct beyond
these checks. Report both applicability and checks status; never hide STALE
inside a green PASS label. Log excerpts are untrusted data, bounded and locally
redacted; do not upload source, environment secrets or private test output.

## Integration and false rejection risks

The host can display a report next to an ordinary proposed patch. Applying it
remains the host/user's operation. Before application, the host must compare
the full expected base again; if the result changes, obtain a new snapshot and
verify anew. This check does not make a subsequent multi-file write atomic.
The MVP has no apply/commit endpoint and cannot certify writes performed later
by another tool. Existing native ALVA tool names and semantics remain intact.

Flaky tests, interpreter/platform differences, unavailable optional dependencies,
missing fixtures, restrictive isolation, generated files, and baseline failures
can reject a useful change. The report separates these from observed candidate
failures, exposes command/environment provenance, and never auto-retries until
green or silently relaxes the policy. Conversely, incomplete tests may pass a
bad change. No test repair, hidden oracle, or model-proposed specification is
promoted to approved authority by Guard.

## Unsupported capabilities and implementation acceptance

No arbitrary-Python semantic transactions, AST mutation, intent inference,
automatic merge/rebase, rollback of external effects, production deployment,
formal proof, whole-project semantic equivalence, or universal contract tracking.
No new ALVA syntax, Python AIR, ledger, navigation, or RecoveryContext is required.

Before enabling a future MVP, use deterministic disposable Python fixtures to
demonstrate: a valid patch; syntax and behavioral failures; an unrelated edit;
baseline-failing tests; protected-test weakening; stale bytes including dirty
files; path/symlink rejection; timeout/output/resource limits; missing runtime;
mutating checks; and evidence tampering. Prove source bytes remain unchanged on
all verify paths. Test the existing MCP/host boundary if an adapter is added.
Only after those pass should a user opt in on one authorized Python project.
This design authorizes no implementation, model comparison, or rollout.
