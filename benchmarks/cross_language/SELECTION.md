# Pre-execution selection rule

Exactly one public HumanEval problem for each of four predeclared operation
features: scalar arithmetic (41), string length (23), vector mapping (42),
prefix-state detection (3). This is a purposive feasibility sample, not a
random sample of HumanEval. No performance-based replacement is permitted.
If a selected problem cannot be adapted through existing language/AEP features,
record UNSUPPORTED and do not substitute another problem.

Source: https://github.com/openai/human-eval at
`b9453e8f1865df0a0057a1383767caa400acfbcf`, MIT (license retained).
Only task ID, public prompt and entry point are imported; canonical solutions
and upstream hidden tests are not model inputs. All entries use name `solve`.
Independent finite black-box vectors are authored before execution.

Domains: bounded i64 integers, n in [0,10000] for collisions, integer lists of
length <=16 with absolute values <=1000, and ASCII strings <=64 bytes. Unicode
code-point length is explicitly out of coverage because native string length
and Python's general Unicode length are not assumed equivalent. Arbitrary
precision integers, overflow, and mixed element types are also out of coverage.
These are adapted tasks, not official HumanEval/MultiPL-E scores.

All arms start from an equivalent, compiling default-return stub, not a
reference implementation. A uses Python text, B ALVA text, C public AEP only.
Public examples/check vectors and terminal vectors are frozen equally; the
host owns tests. Tests execute actual Python or generated Rust, not AST/source
patterns or a model's PASS label. References prove adaptation only and remain
outside model-visible workspaces and tool results.

Model: explicitly gpt-5.6-sol, OpenAI, low reasoning, same in all arms. Preserve
actual resolved identities/metadata; aliases do not pin an undisclosed backend
weight snapshot. One fresh Codex turn per slot, at most 12 slots. No retries,
replacement, extra turns, or model-result-dependent task changes.

Budgets per slot: 480s observation deadline; 80 study callbacks; 120000
provider-reported total-token observation threshold including cached input.
Token/wall notifications can overshoot in-flight work: these are **not hard
provider token/wall caps**. At threshold request interruption with actual
threadId AND turnId, inspect RPC success/error, await terminal notification for
at most 20s, otherwise force host cleanup and mark termination/usage incomplete.
No further study callbacks after an interruption request; count them withheld.
Command checks have independent finite timeouts. Dollar cost/provider request
count is unavailable through this host and must remain null.

No native shell, network, reference access, external project editing or
delegation is authorized. All arms use host-delivered ordinary edit/check/test
or public AEP; the existing Codex host owns generation/tool iteration. Model
failures, malformed arguments and budget stops remain outcomes. A new shared
infrastructure defect stops subsequent positions, preserving all started slots.

Execution order is a seeded shuffle, recorded before generation. All artifacts,
tool surfaces, initial bytes, examples/tests, runtime and controller hashes are
bound in FREEZE.json and committed/pushed first. This is a new controller,
not the frozen P3 driver. Codex assists development; no model-free-development
claim is made.
