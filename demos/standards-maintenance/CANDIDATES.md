# Bounded requirement search (2026-09-19 UTC)

Read existing component/consumer/local-library documentation, CHANGE-001 and
the existing maintenance-evaluation design first. Excluded all completed items
listed in the task: release safety, comparator types, numeric round trips,
line endings, benchmark deadlines, owned-mutator clones and path dependencies.
The current consumer provides no observed new integration defect at selection.

Three external requirement records were examined in detail (limit: 12).
Supporting RFC grammar documents are normative references, not extra candidates.

| Record | Status / version | Actual behavior requested | ALVA baseline / decision | Executable oracle / reference exposure |
| --- | --- | --- | --- | --- |
| [JSON Schema Core §5](https://json-schema.org/draft/2020-12/json-schema-core#section-5), [RFC 6901 §6](https://www.rfc-editor.org/rfc/rfc6901.html#section-6) | Published 2020-12 dialect; RFC April 2013 | Interpret Pointer URI fragments for an explicitly designated media type | JSON-string only; selected as an explicit library feature extension | Normative grammar + literal examples; no implementation inspected |
| [json-schema-spec #328](https://github.com/json-schema-org/json-schema-spec/issues/328) | Closed, draft-06 question / draft-07 milestone, opened 2017-06-07 | Clarify string versus fragment meaning of `format: json-pointer` | No schema-format validator; useful motivation for separate APIs, not another task | Issue body read; no fix/implementation inspected; full schema-format validation outside scope |
| [python-jsonschema/jsonschema #758](https://github.com/python-jsonschema/jsonschema/issues/758) | Closed, opened 2020-11-20, draft-7 cited; affected package version / fix commit not established | Do not interpret `#properties/version` as a Pointer; distinguish anchors | ALVA already rejects non-leading-slash JSON-string Pointers; fragment negative incorporated into selected feature | Public input and syntax; issue body read, no linked code or full repair read; anchor resolution outside scope |

Sources were read-only. Closed issues are historical context, not unseen tasks
or evidence their authors want, use, or endorse ALVA. Search stopped once the
first suitable standards-based requirement was identified; no claim of global
novelty. No Rust performance-reference behavior was used to choose the task.
No remaining examined item is presently a fair, unsolved, in-scope comparison
task; see COMPARISON.md rather than inventing one.
