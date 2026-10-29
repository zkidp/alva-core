# P34 — Host-owned precommit scope guard

**HOST_GUARD_INTEGRATED / PASS**, with fixed-component, function-body-only
coverage. This is authorization engineering, not a Core semantic repair or a
model-effectiveness experiment. Model generation calls **0**; input-token API
calls **0**. Codex assisted the implementation and deterministic witnesses.

Base: P33 `46f5398c0ea591674df6f1c9604a0c983af426bc`.
P29's MM02 failure, P32's completed maintenance, and P33's confirmed shared-parent
propagation remain CLOSED and unchanged. No historical result is rescored.

## Implementation and trusted policy

`integrations/codex/precommit_scope_guard.py` supplies `GuardedNative`, an opt-in
trusted wrapper of the existing persistent Native MCP transport. No Core/AEP/
MCP operation, schema, destructive annotation or official Skill is changed.
`benchmarks/p34_scope_guard/service.py` adapts the existing P26/P23 service so
**every** native session opened by that Host is wrapped, including fresh reads.
It reuses the original relay/process owner and actual Linux OS isolation.

The Host fixes and deep-copies its policy at construction. `cases.py` contains
the trusted module/function/type inventory for the two public components;
`POLICIES.json` records exact case policies and bundle hashes. The only authorized
function is prefix for MM02 or touch_size for MM01. UNKNOWN_COVERAGE deliberately
removes one trusted inventory record as a Host fault injection, not a candidate
or Core change. No policy-update tool exists; commit accepts only transaction_id,
not an Agent-proposed affected set or expanded authorization.

The policy file, service, socket and inner raw Native object stay in the trusted
Host process, outside candidate mounts. The model-facing catalogue contains only
one guarded `alva` server with the existing twenty allowlisted tools; no raw
server/commit alias, Host shell/web or write-capable candidate filesystem tool.
Trusted Host code can of course access its own transports: a compromised Host
or another same-user administrator is outside this enforcement claim.

## Actual precommit algorithm

1. Forward begin to Native MCP. Before returning its result, inspect the **same
   transaction** and capture a trusted baseline, or permanently mark that
   transaction's baseline unverified. No mutation is admitted in between.
2. `inspect_project` provides the actual structured module→revision map. Require
   exact module identity/coverage against the trusted inventory. Traverse actual
   `inspect_entity` slots from every module root, memoizing shared nodes. Bound
   traversal to 2048 nodes; inspection failure, missing data or an unknown shape
   is unverified, never silent truncation or allow.
3. Require exact function/type lists and function order. Capture every module
   field (including exports/dependencies/capabilities/version/Rust dependencies),
   type/test slots and function metadata. The known module slots are functions,
   types, tests, externs, benches. Externs/benches are supported only when empty
   in this implementation. Unknown additional slots are rejected.
4. Record each function's body revision separately from **all** fields and all
   non-body slots: params, returns, pre, post, inv. Do not drop metadata simply
   because the requested edit is a body edit. Traversal verifies coverage of
   current reachable declarations; the trusted Native implementation supplies
   their Merkle revisions, not a model-provided hash list.
5. At commit, recapture actual staged state in that transaction. Any module,
   type, test, signature, contract, added/removed declaration or unsupported
   structural difference is **SCOPE_UNVERIFIED** under this body-only policy.
   The implementation declines those categories; it does not pretend to support
   arbitrary API/interface evolution. A changed function body outside the fixed
   authorized set is **SCOPE_VIOLATION**. Only a complete comparison with no
   unauthorized body change is **SCOPE_ALLOWED**.
6. Only then forward the **original model-tool commit** to the existing Native
   MCP, preserving its `_meta.callId`. Ordinary Core commit-time validation and
   stale-base protections still apply. A Core failure after SCOPE_ALLOWED stays
   a Core failure, not a scope rejection. No Host rescue commit is issued.

The scope check does **not** parse preview text. Preview remains a separate
model-visible descriptive view; a misleading or incomplete preview cannot
override actual declaration comparison. In the fixed cases, preview still
correctly advertises the observed changes.

One reentrant lock serializes all operations on an owned Native session,
including baseline capture and the complete staged-snapshot→commit interval.
The existing trusted service also serializes its relay. Mutation calls cannot
interleave in that interval through the mediator. Native session/process handles
are not given to the Agent. Unknown protocol methods, commit aliases and
tools/call notifications are rejected to prevent an alternate dispatch path.
This is not a new cross-process lock or a replacement for Core stale checking;
P23 process ownership and Core publication preconditions remain necessary.

Guard outcomes are returned in a distinct `structuredContent.host_scope`
record. Denials use MCP isError and never enter the underlying commit. AppServer
normalizes isError to a failed mcpToolCall status; it preserves structuredContent
but not arbitrary envelope extensions. Tests check both the real AppServer item
and the independently recorded underlying Native dispatch, rather than assuming
the raw and normalized envelopes are identical.

## Four fixed cases: real AppServer model-tool path

`verify_host.py` reuses P31's **local scripted Responses** fixture and real
AppServer tool router. No upstream API/model is called; mock usage fields are
transport fixtures, not model costs. Empty temporary CODEX_HOME contains no
auth file; no credential is discovered/read/copied/hashed/archived.

P31 `host_options` is used unchanged: strict config, server default auto, global
and thread approval never, read-only Host, shell/web/apps/plugins/image/delegation
disabled, only commit_transaction gets approval_mode=approve. Actual config/read,
single-server tool inventory and destructiveHint=true are checked. See the
[official MCP policy documentation](https://learn.chatgpt.com/docs/extend/mcp)
and the unchanged P31 report for that version-specific configuration; actual
dispatch, not documentation alone, establishes this result.

| Fixed case | check_transaction | Guard | Underlying native commit | Final independent task / regressions |
|---|---|---|---:|---|
| Original MM02 shared parent | problems: [] | SCOPE_VIOLATION | **0** | expected baseline FAIL / PASS |
| P33 alpha-renamed MM02 | problems: [] | SCOPE_ALLOWED | **1** | PASS / PASS |
| Original MM01 valid local witness | problems: [] | SCOPE_ALLOWED | **1** | PASS / PASS |
| Missing trusted MM01 declaration record | problems: [] | SCOPE_UNVERIFIED | **0** | expected baseline FAIL / PASS |

**Actual protected commits: 2 forwarded, 2 denied before Native dispatch.**
Each allowed dispatch's `_meta.callId` matches the AppServer model-tool item.
Denied items pass P31's approval route (no AppServer approval error) and reach
the Host guard, but have no underlying commit event. This is not a direct
mcpServer/tool/call-only demonstration and not a Host-written substitute commit.
A scripted attempt to call a second raw server endpoint fails in every case.

Original MM02 stages changes in both prefix and delimiter using the unchanged
P29 mutation sequence. Its actual staged snapshot has 196 reachable nodes, and
the guard identifies delimiter as unauthorized. Complete source/AIR bytes remain
unchanged across the denied commit; the transaction is then explicitly aborted.
The dangerous `/` implementation is **not published**, unlike the unchanged P33
unguarded result. The surviving authoritative program returns `!` in the original
delimiter assertion; its unimplemented new prefix requirement still FAILS. Guard
success is prevention of unauthorized publication, **not task completion**.

The nonshared control covers 198 staged nodes and changes only prefix. MM01
covers 51 and changes only touch_size. Their actual commits create AIR; fresh
MCP processes read the exact committed revisions and show only the authorized
function body changed. Original independent target/regression assertions run
against generated code in Linux isolation and PASS. Protected source projection
bytes remain unchanged. This independently observed final scope plus unchanged
manifest/source bytes and regression checks supplies the bounded scope PASS;
it is not merely trust in a SCOPE_ALLOWED label.

UNKNOWN_COVERAGE intentionally has no valid trusted baseline: the actual
inventory includes size_of but the faulty trusted record does not. Begin and
engineering staging remain possible, ordinary type checking still succeeds,
but publication is refused as FUNCTION_COVERAGE_MISMATCH. The summary records
baseline_valid=false, not a fictional complete baseline. Authority stays at
the original revision and the transaction is aborted.

## Supported scope versus unsupported conclusions

| Concept | What this implementation actually establishes |
|---|---|
| Changed function body | Actual body-root revisions across the complete fixed inventory, not source projection or preview text |
| Metadata / signature / contracts | All returned fields and non-body slots are compared; changes are unsupported and fail-closed |
| Added/removed declarations | Exact inventory mismatch is unverified; no automatic policy expansion |
| Module/export/type/test change | Exact module fields/non-function slot roots must remain unchanged; otherwise unverified |
| Statically affected declarations | **Not computed** as a transitive impact closure; changed declarations are not all semantic dependents |
| Runtime behavioral dependencies | **Not proven** unchanged by body equality; finite independent tests remain separate |

An authorized function can change its callers' observable behavior without
changing their body hashes. This guard authorizes edited declaration scope,
not every downstream behavior. No automatic proof of correctness, semantic
noninterference, arbitrary dependency analysis, new occurrence-scoped operation
or copy-on-write fix is claimed. It does not fix shared-node mutation semantics;
it blocks this known spill before publication. It can conservatively refuse
benign metadata/test changes or incomplete coverage. Those are explicit scope
limits/possible false refusals, not evidence that the candidate is wrong.

Inspection exceptions/unknown results deny. A transport loss **after** an allowed
commit is sent can have an unknown outcome; P23 fail-closed session ownership
and no-blind-retry behavior remain, not a promise to undo a completed commit.
No new stale/concurrency experiment, external-effect rollback or atomic
source-projection/AIR update is claimed. No production/default plugin is updated.

## Reproduction, evidence, tests and CI

Local actual chain: Windows trusted Codex CLI `0.163.0-alpha.11.2` → synthetic
loopback Responses → real model-tool approval/router → Host scope mediator →
original MCP inside Ubuntu-26.04 P22/P23 Linux namespaces → AIR → fresh MCP read
→ separately isolated compiler/generated behavior tests.
CLI SHA256 `c81ed464e5e7cafd09a5fa26af390c480bed8e9fab2a87a54b285fbd56e7122a`;
ALVA ELF remains `29e5abd692206876a3929112e471cb99ce457d478dcd81c50cb006aa3b958257`.
SDK/runtime and source bindings are recorded in RESULTS.json. Native Windows/
macOS candidate execution remains unsupported; there is no unsandboxed fallback.

```text
python -m unittest tests.integrations.test_precommit_scope_guard -v
python benchmarks/p34_scope_guard/verify_host.py --attempt <new-controlled-id> --alva <Linux-ELF> --toolchain <Rust-sysroot> --registry <public-registry>
python benchmarks/p34_scope_guard/publish.py <controlled-attempt-folder>
```

Seven new unit tests cover allowed body edits, immutable caller policy, spill,
missing baseline/inspection failure, signature/return/export/declaration changes,
unknown structure, notification/alias/argument bypasses, serialization, and
ordinary Core rejection kept distinct. These units use explicit stubs; they
are **not** substituted for real Native/AppServer evidence. Seven existing
P31 portable policy/protocol regressions also PASS locally.

CI runs the units on Linux/Windows and all four real Native+guard cases inside
Linux OS isolation using a freshly built unchanged SDK. CI does **not** claim
the proprietary Windows AppServer/model-router probe ran on GitHub; that is the
separate local evidence above. Its logs/native ledgers are Actions artifacts,
not public Git files. No historical model slots/gates are rerun.

Controlled final local archive: `.local/p34-scope-guard/final-02/RAW.zip`,
9689228 bytes, SHA256
`d9a2a9591adc8bea3813de171d2a472cce59e7dd1ff909de0fc299b3856b03ff`.
It contains per-session guard reads/baselines/decisions, actual dispatch ledger,
AppServer items, script requests, snapshots/AIR and isolated evaluations. Session
IDs distinguish initial/final Host reads from the model-tool transaction.
`publish.py` verifies archive/ledger hashes, matching call IDs, before/after
authority and independent results before producing public derived summaries.
Raw records never enter Git. Earlier engineering attempts remain local; their
issues were unsupported module-slot handling and normalized response envelopes,
fixed in this new layer, not Core changes or historical result replacements.

Public files: minimal guard, fixed policy, service adapter, two thin validation
drivers, archive-verification/publication code, derived results and tests. No
new provider model task, no model adoption/correctness gain claim, and no
additional sample. P20–P33 frozen records are unchanged. STOP for reviewer;
no automatic merge, Core repair, P35 or further model experiment.
