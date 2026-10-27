# P26 prospective native MCP/Skill coding pilot

Independent twelve-slot developmental wave based on P25 closeout
`ba9d85a69e827a046d79bc3740ed8b2a3c26490d`. P24 remains historically
BLOCKED / NOT_STARTED. This is not a retrospective execution of its Phase B.

## Frozen comparison

Four unchanged public HumanEval adaptations HE41/23/42/3, exact P24 stub Git
blobs, no replacement, one new session/workspace for each T/B/N. Selection,
source/license and bounded domains are in FREEZE.json. They are public adapted
tasks with contamination risk, not official HumanEval scores or a held-out
generalization sample. Old model candidates and P25 engineering witnesses are
never inputs. Fixed randomized schedule uses seed 250126, before any generation.

- T: source editing through bounded `study` callback; isolated check/test.
- B: thin JSON `study` callback into an actual persistent CLI Gateway.
- N: actual individually advertised native MCP schemas; official Skill discovered
  from a fresh `.agents/skills/alva` directory, and its complete exact text and
  all three references delivered in initial input. This uses optional workspace
  Skill discovery and per-process MCP configuration, not a user plugin upgrade.
  It deliberately adds documentation/schema support compared to B.

Common `study` schema is frozen; unavailable actions return a condition error.
The native MCP API and CLI semantics are unchanged. No source mutation is
available in B/N; no AIR-byte mutation is available to any arm. Only N receives
the Skill/reference material. No engineering witness or evaluator source is
mounted for the model. Test returns only status and ordinary check diagnostics;
it never returns hidden vectors or expected values. Host-owned final evaluation
executes in a separate Linux namespace from the candidate MCP/CLI process.

The primary contrast is concurrent B vs N. T is a same-language coding reference.
No pooled historical counts, significance test or superiority claim. A change
may reflect schema/documentation/discovery support, not AEP semantic advantage.

## Real resource and stopping contract

One AppServer turn per slot, gpt-5.6-sol / OpenAI / low (P21 configuration),
80 dispatched model tool actions, 480-second observed model wall threshold,
120000 observed cumulative tokens, twenty-second interrupt grace. Token and
wall notification/cancellation are observational, **not hard provider caps**;
record actual overshoot and missing usage as null. Provider request count and
dollar cost are unavailable, not zero. Cache is not subtracted. No slot retry,
replacement or extra slot. Ordinary candidate compile/test/API failure continues
the schedule; a common infrastructure failure stops subsequent positions.

P21's actual thread/turn IDs, error-aware RPC and acknowledged interrupt plus
terminal-status protocol are reused. Only native MCP events are newly admitted
in N; shell/file/web/delegation events stop execution. Duplicate dynamic calls
are not executed twice. The Linux dispatch boundary independently limits actions.
AppServer-managed native calls already in progress may finish when cancellation
is requested; their real outcomes remain in evidence.

P22/P23 namespaces, mount allowlist, network isolation, cleared environment,
process limits and kill/termination behavior remain the execution boundary. SDK
compiler, toolchain and public offline registry are the only additional mounts.
Candidate source/AIR and generated Rust/test execution never run with host
permissions. Persistent prewarm MCP contexts are separate disposable namespaces;
only the context receiving semantic tool calls is eligible as final authority.
Multiple semantic contexts fail closed rather than selecting a preferred output.
Linux is supported; Windows is only the trusted Codex orchestrator through an
explicit WSL Linux backend. No native Windows/macOS candidate backend exists.

Each Codex invocation uses an isolated temporary configuration home. Its normal
authenticated CLI accesses the existing credential through a transient file
link, not by reading/copying/hashing/logging credential contents in this code.
The link/config home is outside model files, candidate mounts and raw archives,
and is removed after host shutdown. No installed user plugin/configuration is
changed. Shared local credentials must be provisioned independently on another
machine; they are never part of the freeze.

## Reproduction

Run unit tests with `python -m unittest benchmarks.native_prospective.test_pilot`.
`pilot.py prepare --attempt <new> --alva <approved-linux-binary> --toolchain
<approved-sysroot> --registry <approved-public-registry>` performs zero-model
transport/discovery checks and builds FREEZE.json. Source bytes use exact Git
blobs; runtime closure is recorded as exact base64 bytes and hashes, with no
CRLF/LF alternatives. The SDK aggregate binds all approved file contents and
the CLI executable hash. Freeze must be committed/pushed with a clean tree
before `pilot.py run` can issue a generation request. A local exclusive STARTED
ledger prevents restarting that attempt.

Do not rerun a scientific slot. Local runtime evidence, candidate/AIR bytes,
observable tool records and model results stay under ignored `.local/` in a
controlled ZIP. Never commit raw execution logs or transcripts (AGENTS.md).
Git contains normative inputs/code and bounded derived results only. CI uploads
new unit-test logs via Actions Artifacts. P25 logs remain in its own CI artifacts.

Final scoring distinguishes publication, fresh-process target-body change,
check/commit, independent compilation and independent behavior. Detached-node
success/no-op is not a useful edit. Transaction check is not a return-type
soundness proof. No further model experiment is authorized by this README.
