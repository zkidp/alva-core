# Prior art reviewed before AEC implementation

Review date: 2026-10-31. This is a bounded primary-source review, not a
systematic literature survey or a priority claim. “Not established here” does
not mean absent from another implementation. No model generation was used.

| Work and primary evidence | Established capability | Assumptions / difference from this study | Gap or uncertainty |
| --- | --- | --- | --- |
| [CodeStruct paper](https://aclanthology.org/2026.acl-long.607/), [source](https://github.com/amazon-science/CodeStruct) | Named AST entity retrieval and syntax-validated insert/delete/replace actions; also string replacement. | An agent action interface over existing source files. The inspected writer selects nodes, builds replacement source, validates Python syntax, then writes the file. ALVA instead stages changes against AIR revisions and publishes AIR authority. | A trusted behavioral publication contract is not established by this inspected writer. This is not evidence that no surrounding application can implement one. |
| [SWE-agent / ACI](https://arxiv.org/abs/2405.15793), [ACI documentation](https://github.com/SWE-agent/SWE-agent/blob/main/docs/background/aci.md) | Specialized navigation, editing and test interfaces for software agents. | Interface design affects agent work; not equivalent to authorization of the resulting program's behavior. | P38 tests no agent-performance hypothesis and cannot claim superiority over ACI. |
| [Serena source and documentation](https://github.com/oraios/serena) | Language-server-based symbol retrieval, references and semantic editing exposed to agents through MCP. | Operates across mainstream languages; ALVA's authoritative graph is a different persistence representation. | Complete transactional or policy guarantees of all Serena configurations were not verified. Symbol editing is established prior art. |
| [OpenRewrite LST documentation](https://docs.openrewrite.org/concepts-and-explanations/lossless-semantic-trees) | Semantic trees preserve formatting and carry type information for automated source transformation. | Recipes transform source trees; persistence and publication policy need separate analysis. | No claim that typed trees or automated semantic transformation originate in ALVA. Complete recipe safety is outside this review. |
| [ChangeGuard paper](https://arxiv.org/abs/2410.16092), [authors' implementation](https://github.com/sola-st/ChangeGuard) | Pairwise learning-guided execution detects behavioral differences between Python function versions. | Differential executions provide observations rather than general equivalence proofs. P38 is deterministic and uses explicitly authorized changes, without learned input generation. | The possible gap is binding observations to trusted intent and publication; differential validation itself is established. No claim that ChangeGuard cannot be composed with a gate. |
| [Progent paper](https://arxiv.org/abs/2504.11703) | Programmable privilege policies constrain agent tool use. | Tool-call privileges and the behavior of the program produced by permitted calls are distinct policy objects. | Enforcement is prior art; general resulting-program behavioral authorization was not verified. |
| [AgentBound authors' page](https://www.guardiagent.com/research/agentbound), [paper](https://arxiv.org/abs/2510.21236), [replication package](https://doi.org/10.5281/zenodo.19571298) | MCP server manifests, resource grants and container enforcement constrain server execution. | Its boundary is access to system resources, not an edited program's downstream functional behavior. | Do not equate MCP permissions with behavioral equivalence. Full replication package was not executed here. |
| [Weiser, Program Slicing](https://www.cs.kent.edu/~jmaletic/cs63901/readings/Weiser84.pdf) | Dependency-directed extraction relative to a slicing criterion. | P38's reverse direct-call closure is much weaker than a sound general slicer. | Potential impact is not observed change. No slicing novelty claimed. |
| [Ren et al., Chianti](https://prolangs.cs.vt.edu/refs/docs/oopsla04.pdf) | Java change impact analysis relates atomic changes, call graphs and affected tests. | Affected tests / dependencies help select evidence, not automatically decide a user's authorization policy. | Impact analysis is established; P38 supplies explicit policy rather than a new impact algorithm. |
| [Lucassen and Gifford, Polymorphic Effect Systems](https://doi.org/10.1145/73560.73564) | Static types, effects and regions support reasoning about effects. | P38's “effect footprint” is only dependency reachability and runtime samples, not a type-and-effect system or sound abstract interpretation. | A general sound effect checker is not implemented or claimed. |
| [Meyer, Applying Design by Contract](https://files.ifi.uzh.ch/rerg/amadeus/teaching/courses/ase_fs10/Meyer1992.pdf) | Explicit preconditions, postconditions and invariants specify obligations. | P38 associates versioned modification permission and required evidence with a change, rather than inventing contracts. | Contract-based validation is established; policy composition may be useful engineering without scientific novelty. |
| [Eclipse LTK](https://www.eclipse.org/articles/Article-LTK/ltk.html), [PerformChangeOperation](https://help.eclipse.org/latest/rtopic/org.eclipse.platform.doc.isv/reference/api/org/eclipse/ltk/core/refactoring/PerformChangeOperation.html) | Refactoring conditions, change objects, validation and undo support coordinated transformation. | Undo / batching are not automatically identical to crash-atomic AIR authority publication. Neither implies behavioral safety. | Transactional transformations predate P38. Exact crash semantics across all LTK changes were not verified. |
| [Goguen and Meseguer, Security Policies and Security Models](https://www.cs.purdue.edu/homes/ninghui/readings/AccessControl/goguen_meseguer_82.pdf), [Pitts, Operational Semantics and Program Equivalence](https://www.cl.cam.ac.uk/~amp12/papers/opespe/opespe-lncs.pdf) | Noninterference policies and contextual equivalence formalize relationships between executions / observations. | A few regression samples do not establish either general property. Protected outputs here are explicitly bounded unless proof is required. | P38 must return UNKNOWN when proof is required and absent. No new equivalence theory. |
| [Necula, Proof-Carrying Code](https://people.eecs.berkeley.edu/~necula/pcc.html) | A consumer checks a producer-supplied proof against a safety policy. | P38 carries revision-bound evidence but no machine-checked semantic proof. | “Evidence-carrying” must not be mislabeled proof-carrying. Proof-carrying changes broadly remain UNVERIFIED by this limited review. |

## CodeStruct implementation comparison

Source inspected at commit `d89efa473754f455d38ab47b4dc938cfc8334a0d`:

- [`codewrite_server.py:30`](https://github.com/amazon-science/CodeStruct/blob/d89efa473754f455d38ab47b4dc938cfc8334a0d/SWE-agent/tools/ast_edit/lib/codewrite_server.py#L30): path, operation, selector and replacement schema; CLI dispatch at lines 130–158.
- [`editCode:420`](https://github.com/amazon-science/CodeStruct/blob/d89efa473754f455d38ab47b4dc938cfc8334a0d/SWE-agent/tools/ast_edit/bin/editCode#L420): operation implementation; Python validation before the write at lines 598–606.
- [`file_operations.py:136`](https://github.com/amazon-science/CodeStruct/blob/d89efa473754f455d38ab47b4dc938cfc8334a0d/SWE-agent/tools/ast_edit/lib/file_operations.py#L136): ordinary file writer.

ALVA evidence at the canonical P38 base is `alva/src/aep.rs`, `alva/src/air.rs` and
`integrations/codex/precommit_scope_guard.py`, together with the frozen P34/P35
reports. Named source selection and authoritative revision addressing are real
representation differences. Syntax validity, transaction validity, structural
permission and permitted behavior are four separate questions. Neither
representation alone answers the last question. A Git commit, a source hash,
an AST differencer and a trusted test runner can also bind evidence to a
candidate. P38 must compare that strong alternative fairly.

## Falsifiable research opportunity

Test whether combining trusted intent, exact actual structural delta, explicit
potential impact and evidence strength changes decisions beyond strong
diff-plus-tests. A result matching that baseline supports useful integration
and clearer explanations, not new expressive power or global originality.
General cross-language completeness, hostile evidence producers, concurrent
publication and proof automation remain unverified.
