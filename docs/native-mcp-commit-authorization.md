# P31: scoped Native MCP commit authorization

**PASS — MODEL_APPROVAL_PATH_VERIFIED_WITH_SYNTHETIC_RESPONSES.**
Base: `c0696e033f630d045916b1323bad3fd1edd4157b` (P30).
Model generation calls: **0**. Input-token counter calls: **0**.
This is an integration repair, not a Coding Agent effectiveness result.

## Root cause and supported repair

P30 correctly advertised `commit_transaction` as destructive. Its Host used
`approvalPolicy: never` with default MCP approval behavior. On the ordinary
model-tool path, AppServer refused the destructive commit before the Linux MCP
received it. The direct trusted-host `mcpServer/tool/call` preflight did not
exercise this approval decision.

The tested CLI is **codex-cli 0.163.0-alpha.11.2**, executable SHA256
`c81ed464e5e7cafd09a5fa26af390c480bed8e9fab2a87a54b285fbd56e7122a`.
The [official MCP configuration documentation](https://learn.chatgpt.com/docs/extend/mcp)
specifies server/tool approval overrides. The [approval documentation](https://learn.chatgpt.com/docs/agent-approvals-security)
describes destructive tool approvals. P31 does not rely on those pages alone:
the actual executable accepted `--strict-config`; `config/read` returned the
exact tool-scoped policy; and real AppServer dispatch verified its effect.

The prospective Host policy adds only this grant to an explicitly allowlisted
server:

```toml
[mcp_servers.alva]
# command/args are trusted Host values terminating in P22/P23 Linux isolation.
enabled_tools = ["begin_transaction", "inspect_body", "change_field",
                 "preview_semantic_diff", "check_transaction",
                 "commit_transaction", "abort_transaction"]
default_tools_approval_mode = "auto"

[mcp_servers.alva.tools.commit_transaction]
approval_mode = "approve"
```

The snippet illustrates a minimal allowlist, not the fixture's entire list.
Callers explicitly authorize the operations they need. There is no global
`approve` default, annotation rewrite, approval reviewer/model, shell fallback,
`danger-full-access`, `--yolo`, or Host-side rescue commit.

`integrations/codex/native_commit_authorization.py` provides:

- `scoped_server(command, args, enabled_tools=...)`: trusted transport plus exact
  allowlist; only `commit_transaction` gets the approval override.
- `host_options(server)`: strict parsing, unchanged global `never` policy and
  read-only sandbox, disabled shell/web/apps/plugins/image/delegation tools,
  and the single named server. Widened defaults or additional grants are rejected.

Use the options with the existing AppServer transport and a fresh, isolated
CODEX_HOME; create the thread with `approvalPolicy: never` and read-only
sandbox too. The helper does not install/update user plugins or edit user
configuration. Policy and transport must be owned by a trusted Host, outside
candidate-writable paths. It is not an OS sandbox and does not make arbitrary
MCP servers trustworthy. Candidate execution must retain P22/P23 isolation.
Historical P26/P30 runners are not patched in place: future pilots must opt in
and freeze this new Host configuration explicitly.

## Real zero-model approval-path validation

`tests/integrations/native_commit_authorization_test.py` reuses the P26 slot
service, P21 controller/transport and P23 process owner. Its independent public
fixture is a tiny string-returning project, not MM01, an old model candidate,
or a maintenance solution witness.

A loopback-only Responses fixture supplies deterministic **synthetic**
`functions.exec` events calling actual native tools. That is this CLI's ordinary
code-mode model-tool dispatch channel. It is not a real model response and not
a trusted-host `mcpServer/tool/call` substitute. No upstream provider is called;
the fresh CLI home has no auth file, no credential is read/copied/hashed, and
the process environment contains no provider credentials. Mock usage fields
belong only to the transport fixture, not model cost accounting.

The real chain is:

```text
local scripted Responses event → real AppServer model-tool router/approval
→ original Native MCP schema → P23 Linux-isolated MCP → staged AIR → commit
→ close candidate MCP → fresh MCP AIR read → isolated project build/tests
```

The positive probe performs initialize/discovery, begin, body inspection,
existing `change_field`, semantic preview, transaction check and commit. Before
commit the complete authority/source snapshot remains unchanged. Commit keeps
the original destructive annotation, reaches the actual MCP, and creates AIR.
Fresh-process body hash changes; generated code returns the new string for two
independent inputs. Source projection is not rewritten and is not the final
behavioral authority. AppServer native call IDs equal the isolated commit
ledger's `_meta.callId` values, ruling out a direct Host rescue commit.

| Final validation | Actual result |
|---|---|
| Scoped real AppServer model-tool commit | PASS |
| Wrong transaction ID | Rejected; complete authority unchanged |
| Already closed transaction ID | Rejected; complete authority unchanged |
| Staged mixed-type arithmetic/check failure | Commit rejected; authority unchanged |
| Unallowlisted `describe_operation` | Unavailable; no native dispatch |
| Host shell/web/image tools | Absent from real runtime tool inventory |
| Host `apply_patch` write attempt | Denied; sentinel file not created |
| Fresh MCP authority read / independent build/behavior | PASS |
| Default-auto negative control | Model-tool commit denied before MCP |
| Same negative control's direct trusted RPC | PASS, demonstrating path difference |

The positive probe dispatches four actual commit requests: one legal success,
two bad/closed handles and one invalid transaction rejection. The negative
control uses a separate workspace. Its direct no-op commit retains original
behavior, so its terminal new-behavior assertion intentionally FAILS; this is
not confused with the positive fixture's independent behavioral PASS.

This validates the production approval path with scripted tool events; it does
not demonstrate a model's willingness/ability to select or compose these tools.
It is stronger than `DIRECT_RPC_COMMIT_PASS / MODEL_APPROVAL_PATH_UNVERIFIED`
for this exact tested CLI, but not a claim about untested Codex versions.
Unsupported fields/versions must fail closed rather than silently falling back.

## Reproduction and actual regressions

Trusted Windows Host + Ubuntu-26.04 WSL was used for AppServer-to-MCP validation;
untrusted/project compilation and tests run only inside Linux OS namespaces.
The approved ALVA binary SHA256 is
`29e5abd692206876a3929112e471cb99ce457d478dcd81c50cb006aa3b958257`.
No native Windows/macOS candidate execution backend is added or claimed.

```text
python tests/integrations/test_native_commit_authorization.py -v
python tests/integrations/native_commit_authorization_test.py --attempt <new-id> --alva <approved-Linux-binary> --toolchain <Linux-Rust-sysroot> --registry <public-registry>
```

Local results: 5 portable policy/protocol unit tests PASS; the existing Controller
simulation PASS; 4 existing exact-byte/unsupported-backend tests PASS; 4 existing
Linux OS probes PASS; 14 existing persistent Native MCP probes PASS. The latter
uses exact original public Git blobs transported from Windows Git because its
managed worktree pointer is not a Linux Git path. No historical test source,
result, model slot or frozen package is changed. These are implementation
regressions, not reopened scientific gates.

CI runs the portable policy/protocol and Controller tests on Linux/Windows,
plus the repository's existing Core CI. It does not claim to install or test
this exact proprietary desktop CLI build on GitHub runners. Real approval-path
and Linux sandbox results above are local execution evidence, separate from CI.

Raw local traces/config/requests and evaluator outputs are **not in Git**.
Controlled archive: `.local/p31-commit-authorization/P31-EVIDENCE-FINAL.zip`,
676,896 bytes; SHA256
`a25c6d634aca492d6455137ee7f0680ae1a1deb8eee62b3dc89715e2eee1c6c5`.
Development attempts, including initially invalid fixture/tool encodings, remain
local too; no failed attempt is presented as the final passing probe.

## Preserved history and limits

P30 remains exactly: T completed correct maintenance; S no committed candidate
with Host authorization blocker; Native staged target changed; uncommitted
candidate behavior NOT_INDEPENDENTLY_EVALUATED. No P30 rescue commit or rerun,
no altered FREEZE/RESULTS/ANALYSIS/REPORT/SCIENTIFIC-DISPOSITION, and no Core,
AEP, MCP operation/annotation, official Skill, or canonical main changes.

This narrowly repairs a Host admission decision. It does not add semantic
operations, prove general behavioral preservation, authorize arbitrary servers,
make filesystem/network safety universal, or demonstrate agent correctness
gain. No new MM01 model task is started. Stop for independent review; no merge.
