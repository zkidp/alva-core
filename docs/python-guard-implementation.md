# Python Guard P1: standalone local verifier

This implements the [P1 design](python-guard-mvp.md) using Python's standard
library. It leaves Python source authoritative and has no apply/commit command.
It does not change the ALVA MCP server, native Skill, compiler or plugin.

PR #16 was open, targeting `main`, at implementation start. This branch starts
at its tested head `b9bbaaa72cbfa3345683efa2b9f7ccbe272145d5`, not an assumed
merged `main`. The P1 PR is stacked on `codex/codex-integration-p0-guard-design`.
Once P0 merges, review/rebase the dependency explicitly before retargeting.

## Run it

From a clone, Python 3.12 or later is sufficient; there are no package installs:

```text
python examples/python_guard/demo.py
python -m unittest discover -s tests/python_guard -p test_guard.py -v
python -m integrations.python_guard --help
```

The public demo copies a tiny Python library and its unittest suite, calls all
three real CLI operations, and checks good/bad/stale outcomes. Its sources,
requests, approved policy, and evidence are disposable local fixture data.
They are not model outputs, a hidden oracle, or an effectiveness experiment.

For an existing authorized project:

```text
python -m integrations.python_guard --store /private/guard-evidence --policy /approved/policy.json snapshot --request snapshot.json
python -m integrations.python_guard --store /private/guard-evidence --policy /approved/policy.json verify --request verify.json
python -m integrations.python_guard --store /private/guard-evidence report --request report.json
```

Each request is the JSON shape in the P1 design. On Windows use absolute Windows
paths for CLI filesystem arguments and policy root/interpreter paths; paths
*inside the manifest or patch* always use forward-slash relative names. Request
files and patch contents are decoded as UTF-8 without float or newline rewriting.
The module API is `Guard(store, policy_file).snapshot(request)`, `.verify(request)`,
and `Guard(store).report(request)`. Invalid inputs raise `GuardError` in the API;
the CLI emits a JSON `INPUT_REJECTED` or `UNKNOWN` result and a nonzero exit.

## Host-approved policy

The host/user must approve the policy file and invoke the verifier with its
path. Keep it and the evidence/scratch roots outside the project and inaccessible
to untrusted editing tools. A hash identifies approval bytes; it is not an
authentication system against another process with the same account privileges.
Guard does not grant a model authority to create or weaken policy.

The following is the complete version-1 policy shape. Substitute real absolute
paths; the runnable demo shows programmatic construction:

```json
{
  "schema": 1,
  "project_root": "/work/project",
  "scratch_root": "/private/guard-scratch",
  "python": "/usr/bin/python3",
  "trusted_project": true,
  "files": ["calc.py", "tests/test_calc.py", "extra.py"],
  "editable": ["calc.py", "extra.py"],
  "excluded": {".git": "VCS data excluded"},
  "scratch_outputs": ["__pycache__", "tests/__pycache__"],
  "environment": {},
  "checks": [
    {"id": "unit", "argv": ["$PYTHON", "-I", "-m", "unittest", "discover", "-s", "tests"]}
  ],
  "limits": {
    "max_files": 1000,
    "max_source_bytes": 16777216,
    "max_patch_bytes": 1048576,
    "wall_seconds": 120,
    "output_bytes_per_stream": 1048576,
    "max_command_invocations": 16,
    "max_direct_processes": 1,
    "address_space_bytes": null,
    "cpu_seconds": null
  }
}
```

Compute `policy_id` as `sha256:` plus the SHA256 of the exact policy-file bytes.
`files` must cover the entire non-excluded project input tree; undeclared files
are rejected instead of silently omitted. Missing editable paths represent
permitted future additions; missing protected inputs reject snapshot capture.
Tests/configuration are protected unless explicitly in `editable`. `excluded`
requires reasons; it is a scope limitation. `scratch_outputs` permits generated
files only in temporary trees and cannot overlap guarded files. The interpreter
must be an absolute path. Check executables must be absolute or `$PYTHON`; no
shell interpolation or implicit dependency install occurs. `syntax` is reserved.

Only explicit non-secret `PATH`, `LANG`, `LC_ALL`, `TZ`, and `PYTHONHASHSEED`
overrides are supported. Commands receive a clean environment with private
HOME/temp paths, deterministic hash seed and bytecode writing disabled. The
Windows `SystemRoot` is carried for normal OS execution; other host environment
variables, including API credentials, are not inherited.

## Evidence and result semantics

Snapshot captures actual UTF-8 bytes, relative paths, lengths and executable
flags, then compares a second full manifest. Uncommitted changes are part of
the identity. Content-addressed snapshot/verification IDs bind canonical JSON
metadata; source, approved policy, candidate and patch blobs are independently
hashed. Report validates those dependencies. This detects alteration relative
to an ID supplied by the trusted caller, not an attacker substituting both an
entire store and caller IDs. Store data is local and may contain project source;
protect it like a checkout. Never commit it to Core or upload it automatically.

Verify rejects stale input before execution. It applies strict unified-diff
hunks at their declared positions with exact preimages and expected hashes,
then creates separate baseline/candidate trees. There is no fuzz, offset search,
rename, binary patch, mode change, path traversal, symlink or junction support.
CRLF and missing final newlines must be represented exactly by the patch.
All required tests/data must be in the approved file set; empty directories
are not separately materialized. File permissions are reduced to executable
versus non-executable semantics, not a full filesystem/ACL snapshot.

Both trees run syntax compilation and the same approved argv arrays with the
same bound interpreter and environment policy. Baseline then candidate are run
for each check. Syntax compilation does not import modules or prove behavior.
Results label `NEW_REGRESSION`, `BASELINE_AND_CANDIDATE_FAIL`,
`BASELINE_FAILURE_CLOSED`, `BOTH_PASS`, or `UNKNOWN` per check. Two failures of
one command do not prove identical defects. Timeout, output limit, missing
runtime/dependency, modified check inputs, or unavailable resources yield UNKNOWN.
Existing candidate failures remain FAIL. Lack of complete baseline evidence
prevents claiming regression equivalence. No failure is retried until green.

`checks_status` is independent of `applicability_status`. Live source is checked
again at verification completion, so a concurrent edit produces STALE while
retaining historical check evidence. Report without `current_snapshot_id`
projects historical checks, exposes `recorded_applicability_status`, and returns
applicability UNKNOWN (or retains STALE); it never gives a fresh green result.
To establish current applicability, supply a new snapshot from the same root
and approved policy. Report compares it to the verified base and rechecks its
live bytes without running commands or rewriting evidence.

CLI exit status: 0 only for a captured snapshot or PASS + CURRENT; 1 for a
completed candidate FAIL; 2 for UNKNOWN, STALE, rejected inputs or invalid
evidence. Callers must inspect both status fields even when retaining a FAIL
with STALE applicability. PASS means the bound checks passed, not complete task
correctness, a future atomic source write, or external-side-effect rollback.

## Execution boundaries

Only host-approved **trusted local projects and commands** execute. Set
`trusted_project=false` for an untrusted project: verify retains bound input
evidence but runs nothing and returns UNKNOWN. There is no sandbox backend in
this version. An approved command that intentionally writes absolute paths,
uses the network or accesses external state is not contained by a working
directory. The caller must trust it not to affect the original project or use
an external sandbox; Guard itself only writes to its private store/scratch trees.

Execution is sequential with at most one directly launched command; the
invocation count includes both syntax checks and both arms of every approved
check. A shared execution-phase wall budget covers all invocations. Per-stream
output retention is bounded; hashes/counts refer to bytes actually read and
truncation is explicit. Spawn time and cleanup-inclusive elapsed time are
recorded. Process creation cannot be interrupted from inside Python, and
cleanup has a separate finite allowance.

On POSIX, checks get their own process group and optional per-process
`RLIMIT_AS` / `RLIMIT_CPU`. On Windows, a Job Object owns descendants for cleanup;
unsupported POSIX resource limits return UNKNOWN. Assignment happens after
process creation and is not hostile-code containment. Descendant process count,
whole-tree memory, network and external filesystem access are **not enforced**;
evidence explicitly records this. Processes escaping the owned group are outside
the trusted backend's guarantees. A requirement for those limits needs another
backend rather than silently claiming they are active.

Logs are bounded and common secret-assignment patterns are redacted. This is
not complete secret discovery; approve commands that do not print private data.
External interpreter dependencies/site packages are not content-locked. Their
absence is UNKNOWN when identifiable from process errors; flaky tests and
dependency/platform differences remain limitations disclosed with the evidence.

No Codex/MCP adapter is added in P1: the native MCP API operates on ALVA/AIR,
and silently reusing its transaction tools for Python would change their meaning.
Existing editors can use the standalone CLI without changing their mutation path.
