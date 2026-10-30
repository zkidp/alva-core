# AEC v0: registered research contract

This specification follows the prior-art review. It is a small research
comparator, not a production protocol or universal correctness system.

## Trusted inputs and binding

Host-owned intent fixes the original source bytes, allowed function bodies,
protected declaration structure, permitted downstream observations, required
invariants, evidence strength and publication conditions. Agent statements
cannot grant authority. Exact original hashes and candidate source bytes are
registered in COUNTEREXAMPLES.json and fixtures. At execution, public Native
inspection supplies baseline/staged/fresh body revisions and metadata.

Evidence must be bound to the same candidate: independently compile the Text
candidate, compare its inspected function body revisions with actual staged
Native revisions, publish in a disposable quarantine solely for observation,
re-read from a fresh process and independently check/build/test authoritative
AIR. No unconnected-node credit. No direct AIR editing. Replay under actual
P34 separately; compare replay roots with the quarantined candidate. A stale,
missing or mismatched identity gives UNKNOWN. Changes to protected metadata,
module inventory or unauthorized bodies give REJECT when exactly established.

## Separate footprints

1. Structural: actual before/after body roots, function metadata and module
   structure, plus shared reachable revision identities. Shared immutable
   children alone are permitted; changed roots outside the authorized set are
   not. Declaration identities that necessarily change with body revisions
   are recorded but not mistaken for signature changes.
2. Potential: reverse closure of direct calls in these closed single-module
   fixtures, using actual inspected call nodes in both versions. This is a
   conservative dependency report for this restricted syntax, not a general
   slicer. Unresolved calls / unsupported constructs mark analysis incomplete.
3. Observed: separately executed baseline and candidate tests record actual
   outputs at registered inputs. A caller can change without structural
   editing; a reachable caller need not change. Every protected sample is
   checked; permitted downstream changes are explicitly specified.
4. Unknown: finite samples leave all unsampled inputs unproved. Unsupported
   dependencies and absent required proofs stay unknown.

## Decision order

The implementation receives intent, actual structural comparison, dependency
coverage, candidate-bound check/build and sample results. It receives no
expected authorization verdict or scoring labels.

- REJECT: confirmed unauthorized structural change, or executed required
  invariant/postcondition failure. Test failure must be a real assertion
  failure; infrastructure failure instead gives UNKNOWN.
- UNKNOWN: otherwise, incomplete/mismatched evidence, unverified dependency
  coverage, missing required observations, or proof-required policy without a
  checked proof. UNKNOWN is not permission to publish.
- ALLOW: otherwise, all requirements of the explicitly bounded test policy
  hold. This permits exactly that policy's finite evidence, never universal
  semantic equivalence.

No proof checker is implemented. Case 4 requires a proof and therefore cannot
obtain ALLOW merely from passing tests. Confirmed failures take precedence
over insufficient evidence. Potential impact alone never causes REJECT.

## Comparison and publication boundaries

A: strong Text + Git diff + all available tests. A trusted source-region diff
checker checks declaration body edits against the same intent, and gets the
same evidence-strength policy. It does not depend on AIR for its decision.
B: structural editing + ordinary checks and all available tests. This baseline
checks exact structural scope and ordinary tests but has no proof-strength
gate; do not weaken its tests. C: actual unchanged P34 Guard, which decides
structural body scope, with all behavior evidence reported alongside it.
D: AEC v0 applies the above rules and adds a potential-impact explanation.

A, B and D are **decision simulations over actual executed evidence**, not
deployed publication gates. C alone exercises a real guarded publication
chain. Quarantine commits have no behavioral publication authorization and
must not be counted as final publications. Report hypothetical invalid
allows separately from actual C publications contrary to the stronger intent.
P34 is not defective when it correctly allows a structurally scoped behavioral
regression; its guarantee is narrower.

## Trust, limitations and non-goals

Host registry, compiler, SDK, Guard, independent runner and evidence collector
are trusted. P22/P23 Linux isolation is reused unchanged. The comparator is
offline, single-candidate and single-threaded. No hostile collector, concurrent
TOCTOU protection, external I/O effect model, general name resolution, proof
production, new Core primitives or model performance claim is in scope.
Cryptographic revision identities bind states; they do not certify semantics.

Finite test outcomes can be bound to Git revisions as well as AIR revisions.
Decision equality with strong A means no observed incremental authorization
capability over that baseline, even if D provides clearer provenance.
