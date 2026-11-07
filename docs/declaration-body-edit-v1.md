# Declaration body editing, v1 prototype

Start the opt-in interface with `alva mcp --profile maintenance`. The default
`alva mcp` and explicit `--profile native` retain the original 20 MCP tools
and their schema digest. This profile is an engineering prototype, not the
interface used in any frozen study or a demonstrated token improvement.

The maintenance profile has nine tools:

| Tool | Purpose |
| --- | --- |
| `begin_transaction` | Open the authoritative project and return a transaction ID. |
| `read_function` | Return declaration metadata (body omitted), one editable `(body ...)` fragment, and complete body revision. |
| `inspect_project` | Inspect staged module roots; also used by the trusted Guard. |
| `inspect_entity` | Inspect staged nodes; also used by the trusted Guard. |
| `replace_function_body` | Parse, check, and reconnect exactly one named function body. |
| `preview_semantic_diff` | Review the staged change. |
| `check_transaction` | Run the existing transaction checks. |
| `commit_transaction` | Publish through the existing Native commit mechanism. |
| `abort_transaction` | Discard the transaction. |

Every call after begin requires its returned `transaction_id`. To change a
function, read it, submit a complete body fragment, review/check, and commit.
For example, after reading `demo.model.size_of`:

```json
{
  "transaction_id": "<returned transaction ID>",
  "function": "demo.model.size_of",
  "expected_body_revision": "<complete body_revision from read_function>",
  "body": "(body (field (ref m) \"size\"))"
}
```

Send these arguments to `replace_function_body`. The declaration projection
is read-only context: do not send a module, signature, declaration, or metadata
as the body. Body fragments use the existing ALVA grammar and lexical scope;
this does not introduce another programming language. Multiple body steps
are supported. The fragment limit is 65,536 UTF-8 bytes, in addition to parser
resource limits. Rewriting a large body can itself be expensive; local text
patches are still a relevant comparator in a future study.

`replace_function_body` requires an exact fully qualified function name and a
64-character lowercase body revision. It locates the module's unique function
occurrence, verifies its head and body revision, constructs new expressions,
copies the function and module references, then checks the candidate before
swapping session state. It preserves the signature, contracts, effect metadata,
other declarations, and old content-addressed nodes. Even an entire function
node shared between modules can be changed at one occurrence. Stored entity
metadata is preserved separately from the selected declaration's head.

One snapshot-read correction applies to both MCP profiles: `inspect_entity`
with an existing complete revision now returns that exact node, including
historical and shared named nodes. It no longer redirects that read through
the node's stored entity label to a different current head. Named handles
retain their existing resolution behavior. This is required for the Guard
to inspect shared function occurrences accurately; it does not change mutation
resolution for the legacy low-level operations.

Parse, stale revision, semantic, return type, scope, and invariant failures
leave the transaction graph, bindings and diagnostics untouched. The new
entry point also checks the target's body result against its declared return
type, using the existing type inference/unification implementation. Legacy
project checking previously omitted that comparison; its behavior is not
silently changed by enabling this prototype. Type inference retains its
existing limitations; successful staging is not a proof of behavior or a
substitute for building and testing.

On a stale body error, re-read and reassess the change. This precondition is
relative to the staged transaction. The existing base-revision check at commit
separately protects against another process publishing first. Neither guard
automatically merges or rebases edits. Missing/ambiguous declaration paths,
inconsistent heads, and a pre-existing content revision with conflicting entity
metadata are refused explicitly. No guessed ancestor or partial revision is
used to recover a write.

Staging does not publish AIR or rewrite source files. A no-op replacement can
succeed but does not establish task completion. This interface does not impose
Host authorization by itself: deploy it behind the existing `GuardedNative`
mediator with a trusted function policy and this profile's explicit tool list.
The Guard must continue to own the only agent-accessible commit route.
The inspection tools support the Guard's unchanged full scope collection;
their private calls must be counted separately from model-visible calls.

This profile intentionally excludes low-level expression constructors and
field mutations. The existing official Skill describes the default Native
profile and is unchanged; this document is the prototype's interface guide.
Do not silently substitute the profile or this guide into an old frozen run.

Verification uses compiler unit tests, real MCP transport, actual P34 allow
and deny decisions, underlying commits, fresh-process AIR reads, project builds,
and the original MM02 independent task/regression assertions. See
[the engineering report](research/declaration-body-edit-v1.md).
