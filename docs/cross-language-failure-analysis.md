# P21 failure analysis and prospective harness hardening

Baseline: PR #21 at `ecadfea51ccd147f99f58ec5e891869744bc664c`.
This node reads existing evidence; it does not rerun P21, rescore its twelve
slots, or repair its frozen evaluator/controller. Codex assisted analysis and
engineering; zero model **task generation** does not mean model-free authorship.

## Evidence and scope

Read REPORT/ANALYSIS/RESULTS/VALIDATION and the original local archive.
SHA256 `ba357cbaff787c3a514266fd439707b787eb7fb7ee5ba33efe63b4fb223edb3c`
matches the historical manifest (58 entries). The targeted analysis reads the
three Text failure result records and four C result/AEP records directly from
the ZIP, without extracting/executing candidates. No hidden reasoning is used.
The derived [machine-readable record](../evidence/benchmark-hardening/P21-FAILURE-ANALYSIS.json)
retains first-edit code/digests, actual diagnostics/check chronology, AEP progress
and schema-follow-up events. `scripts/analyze_p21_failures.py` reproduces it;
without the ZIP it reports unavailable details and uses only public summaries.
A hash mismatch is an error, not permission to reconstruct replacement traces.

Ordinals below are **tool callback ordinals**, not provider generation ordinals.
Provider generation-request counts remain unavailable. All seven slots ended
with TOKEN_OBSERVATION_LIMIT and confirmed interrupted turns. An observation
threshold is not a hard token cap; no claim is made that another turn would work.

## ALVA Text: three construction failures

| Slot / task | First accepted edit | Actual subsequent check sequence | Final terminal check |
|---|---:|---|---|
| 05 / HE41 arithmetic | 2 | unknown `mul` -> unknown `binary` -> unknown `binop` -> call requires function name | unknown `var`; COMPILE_FAIL |
| 06 / HE3 prefix state | 5 | let requires symbol -> let form/block error plus unknown `for` -> unknown `lt` | unknown `binary`; COMPILE_FAIL |
| 07 / HE42 list mapping | 4 | expected type form -> bare `foo` -> unknown `foo` -> call requires function name | call requires function name; COMPILE_FAIL |

All diagnostics above were actually returned in tool responses. A generic
secondary diagnostic, `solve requires a (body ...) with at least one expression`,
recurs after rejected syntax; it is not independent evidence that a valid
function body could not be expressed. Initial checks before edits for HE3/42
were PASS on the **default stub**, not task correctness.

- HE41 first wrote `(mul (var n) (var n))`. `binary`/`binop` are AST-like
  terminology, not supported source spellings. Later forms continued to fail.
- HE3 first used `(let (binding ...))`, `for`, `set`, `add`, `lt` and `return`
  forms. The received diagnostics identified malformed let/body expressions;
  revisions changed forms but did not reach a check-valid final candidate.
- HE42 first attempted a `map` expression with an embedded function form, then
  used `foo` probes and a malformed call. These are observed syntax/API guesses,
  not proof a list transformation needs a new language primitive.

The actual final sources can differ from the last model-requested check: edits
occurred before interruption and terminal host checking. The JSON retains both
observations; neither is substituted for the other. Classification for all
three is **generated unsupported/malformed syntax and unclosed diagnostic
repair**, not **necessary language feature absent**. P21's pre-generation
qualification already contains passing Text/AEP witnesses for these same
bounded requirements. That witness does not imply all implementation strategies
are supported; the documented vector-accumulator construction path was limited,
while a recursive mapping witness worked.

## AEP: discovery/argument use, not failed committed behavior

C exposed one `study` dynamic tool with JSON-string arguments that forwarded
requests to `alva agent`. It did **not** expose P0's individually advertised
native MCP schemas or load the full native ALVA Skill. Prompt wording such as
"discovery" was a workflow description, not an existing operation of that name.

| Slot | Native calls | Discovery/schema/entity progress | Construction / publication |
|---|---:|---|---|
| 04 / HE23 | 30 | repeated guessed names; valid capability queries; schemas for replace_expression, create_call, add_call_arg | empty create_call accepted as a detached node; no target edit/check/commit |
| 08 / HE42 | 31 | capability listing; inspect_project; inspect_function succeeds once with `name`; inspect_entity succeeds with `entity` | guessed loop/vector/ref operations fail; no target edit/check/commit |
| 10 / HE3 | 10 | name guesses; capability list; inspect_function succeeds using `name` | `construct` unknown; no target edit/check/commit |
| 12 / HE41 | 10 | name guesses; capability list and inspect_project; wrong inspect_function keys | no successful target edit/check/commit |

All four began transactions successfully. `discovery`, `discover`, `list_tools`
and other guessed names are unknown operations. Supplying `operation` rather
than `name` to describe_operation, or `function`/`function_id`/`target` rather
than `name` to inspect_function, is a distinct missing/wrong-argument issue.
`describe_construction` without `kind` is not a failed proof of construction
coverage. Some `ok:true` replies only describe capabilities or create nodes;
they do not attest intended program changes.

In HE23 the valid create_call schema arrived **after** an empty create_call;
there was no later create_call using it. The add_call_arg and replace_expression
schemas were acquired but their mutations were never invoked. The detached
call had no target attachment and no commit. Across all four, transaction
check requests = 0, commit attempts = 0 and committed candidates = 0. Accordingly
the terminal TEST_FAIL rows evaluate unchanged default source, not four wrong
committed AIR programs. Entity lookup/schema success must not be relabeled
effective staging or recovery success.

For these bounded targets, "current operations cannot express the goal" is
**not supported** by the traces and is contradicted by the frozen qualification
witnesses. The supported classification is discovery/argument-use failure to
reach staging/publication under the frozen bridge/budget. No internal motive,
attention failure or causal effect of a particular prompt is inferred.

## A: prospective OS isolation, not a historical score repair

The targeted finding is confirmed in old `common.py`: both Python execution and
ALVA project/build/cargo testing reach `subprocess.run` as the controller user.
Python `-I` and clean environment values do not enforce filesystem/network
isolation. The existing review's demonstrated out-of-tree write is consistent
with that code path; no unsafe historical exploit or pilot is rerun here.
Historical PASS rows are preserved as recorded, not upgraded to safely isolated
evidence. This node does not retroactively certify absence of tampering.

New opt-in `integrations/benchmark_runtime_v2/sandbox.py` creates an empty-root
Linux bubblewrap boundary: separate user/mount/PID/network/IPC namespaces,
dropped capabilities, no host home/mount tree, minimal read-only public runtime,
read-only input and SDK, writable disposable `/work` and `/tmp`, and clean
launcher/child environments. No broad host `/etc` or Cargo home is mounted;
only compiler aliases are recreated. Public registry data is copied into scratch.
Actual ALVA check/build, Cargo build scripts and generated tests run **inside**
this boundary, not just the final Python interpreter. The host owns SDK/input
selection; model-controlled arbitrary bind mounts are not an interface.

Synthetic OS probes cover reference/other-slot/private markers, read-only input
and root writes, host-loopback and TEST-NET egress, parent environment, wall and
output termination. ENOENT for hidden host paths is **namespace isolation**,
not a claim of EACCES. EROFS confirms read-only mounts; refused/unreachable
connections occur while the synthetic host listener is live. A Rust build.rs
and generated-code test repeat host-file/network probes inside the same ALVA
build/test boundary. No company/private data or real credential was probed.

Native Windows/macOS have **UNSUPPORTED / FAIL-CLOSED**, not a fallback. Linux
under WSL2 was actually tested; that is not a native Windows security backend.
Missing/broken namespace/SDK setup refuses execution. Temporary directories,
path validation and `-I` are supporting mechanics, not the security boundary.
See [runtime contract](../integrations/benchmark_runtime_v2/README.md) and the
test logs under `evidence/benchmark-hardening/`.

## B: exactly two checkout-byte mismatches

| Input | Git LF bytes | Historical CRLF bytes | Difference |
|---|---:|---:|---:|
| tests/integrations/codex_native_test.py | 9,819 | 10,017 | 198 inserted CR bytes |
| feasibility/native_api/run.py | 12,278 | 12,553 | 275 inserted CR bytes |

The JSON record provides complete SHA256 values. Their historical hashes
match **only** the CRLF conversions, not the committed LF blobs. P21's attribute
rule covered only its benchmark directory, leaving these two external inputs
checkout-dependent. A successful final-code replay was not a test of freeze
transport reproducibility. None of the old hashes/files are changed here.

v2 packs the explicit dependency list from a resolved commit's **Git blobs**,
with path/origin/length/SHA256 and base64 payload. A caller-approved bundle ID
binds canonical transport metadata. Runtime files are materialized from decoded
bytes with no text-mode write or EOL normalization, then strictly checked as a
complete set. Modified CRLF code, added files and tampered payloads are rejected;
there is no "either newline version is fine" branch. Real autocrlf=true/false
checkouts on both Windows and Linux produce identical bundle contents/runtime
bytes. A clean Linux clone was used for local WSL Git tests because a Windows
managed-worktree .git pointer is not a native Linux Git path; no repository
metadata was rewritten to hide that platform constraint.

## Resolved and deliberately unresolved

Resolved for the new version: isolated batch check/build/test execution on the
tested Linux backend; native Windows fail-closed; deterministic Git-blob
transport and strict runtime verification; evidence-grounded seven-case analysis.
No P21/P3 script is replaced or wired to v2. No Core, Guard, MCP, Skill or operation
set changes, no model calls, and no historical gate/score reruns occur.

Not delivered: a Windows/macOS sandbox, protection against kernel/toolchain
vulnerabilities, whole-machine denial-of-service resistance, a persistent native
MCP stdio sandbox adapter, automatic dependency discovery or a ready-to-run new
model protocol. Per-process resource limits are not aggregate quotas. Future
controllers must bind approved SDK/runtime artifacts and the full input closure
before execution. [Native MCP design](native-mcp-benchmark-design.md) is only a
proposal for that separate, pre-frozen study, not authorization or results.
