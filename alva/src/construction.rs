//! RFC-0006 / AEP-0003 v0.1: Typed Semantic Construction.
//!
//! The ConstructionSpec registry is the single source of truth for which
//! semantic kinds can be legally materialized, what children they require,
//! what roles those children play (`expr` / `type_expr` / `record_field` /
//! `update_field` / `case`), and what the resulting expression type is.
//!
//! Both gateway surfaces derive from this table, so documentation cannot
//! drift from the executable layer:
//!
//!   - `describe_construction` reads it (read-only);
//!   - `construct_expression` validates against it and materializes through
//!     the same spec.
//!
//! v0.1 surface is evidence-driven from FORMAL-72 (see RFC-0006 §2.4/§5.1):
//! `field record record_update veclit fold match ok err not` are standalone
//! AIR node kinds; `range` is a fold sub-form (range_start/range_end), NOT a
//! standalone node, and `construct_expression kind=range` validates/returns
//! the sub-form without creating a node (zero transactional side effects).
//! `map/maplit` is intentionally NOT in v0.1 (RFC-0006 §5.1 evidence note).

/// A child slot of a constructible kind.
#[derive(Clone, Copy)]
pub struct ChildSpec {
    /// Argument name used by `construct_expression` / advertised by
    /// `describe_construction`.
    pub name: &'static str,
    /// "expr" | "type_expr" | "record_field" | "update_field" | "case"
    pub role: &'static str,
    pub required: bool,
    pub multiple: bool,
}

#[derive(Clone, Copy)]
pub struct FieldSpec {
    pub name: &'static str,
    pub required: bool,
}

pub struct ConstructionSpec {
    /// Canonical AIR node kind (or "range" for the fold sub-form).
    pub kind: &'static str,
    /// Semantic aliases, e.g. result_ok -> ok.
    pub aliases: Vec<&'static str>,
    /// String-valued node fields (e.g. record type name, field name).
    pub fields: Vec<FieldSpec>,
    /// Child slots; multiple slots accept JSON arrays.
    pub children: Vec<ChildSpec>,
    /// Human/machine-readable rule for the resulting expression type.
    pub result_type_rule: &'static str,
    /// Example `construct_expression` invocation.
    pub example: &'static str,
    /// Additional semantics (e.g. range is a fold sub-form).
    pub note: &'static str,
}

const fn field(name: &'static str, required: bool) -> FieldSpec {
    FieldSpec { name, required }
}

const fn child(
    name: &'static str,
    role: &'static str,
    required: bool,
    multiple: bool,
) -> ChildSpec {
    ChildSpec {
        name,
        role,
        required,
        multiple,
    }
}

#[allow(clippy::too_many_arguments)]
const fn spec(
    kind: &'static str,
    aliases: Vec<&'static str>,
    fields: Vec<FieldSpec>,
    children: Vec<ChildSpec>,
    result_type_rule: &'static str,
    example: &'static str,
    note: &'static str,
) -> ConstructionSpec {
    ConstructionSpec {
        kind,
        aliases,
        fields,
        children,
        result_type_rule,
        example,
        note,
    }
}

/// RFC-0006 v0.1 evidence-driven kind surface (frozen 2026-08-16).
pub static REGISTRY: std::sync::LazyLock<Vec<ConstructionSpec>> = std::sync::LazyLock::new(|| {
    vec![
            spec(
                "field",
                vec![],
                vec![field("name", true)],
                vec![child("value", "expr", true, false)],
                "field value expr 的类型（取决于 record；v0.1 不静态推导）",
                "construct_expression kind=field name=\"valid\" value=<expr rev>",
                "record field access: (field <value> \"name\")",
            ),
            spec(
                "ok",
                vec!["result_ok"],
                vec![],
                vec![child("value", "expr", true, false)],
                "(result T E)，T = value 类型；v0.1 仅对 literal 静态推导",
                "construct_expression kind=ok value=<expr rev>",
                "result success constructor: (ok <value>)",
            ),
            spec(
                "err",
                vec!["result_err"],
                vec![],
                vec![child("value", "expr", true, false)],
                "(result T E)，E = value 类型；v0.1 仅对 literal 静态推导",
                "construct_expression kind=err value=<expr rev>",
                "result failure constructor: (err <value>)",
            ),
            spec(
                "not",
                vec![],
                vec![],
                vec![child("value", "expr", true, false)],
                "(prim bool)",
                "construct_expression kind=not value=<expr rev>",
                "boolean negation: (not <value>)",
            ),
            spec(
                "veclit",
                vec!["vec_lit", "veclist"],
                vec![],
                vec![
                    child("elem_type", "type_expr", true, false),
                    child("items", "expr", false, true),
                ],
                "(vec <elem_type>)",
                "construct_expression kind=veclit elem_type=\"(prim i64)\" items=[<rev>, ...]",
                "vector literal: (vec <elem_type> item...)",
            ),
            spec(
                "record",
                vec!["record_lit"],
                vec![field("type", true)],
                vec![child("fields", "record_field", false, true)],
                "record <type>",
                "construct_expression kind=record type=\"Entry\" fields=[{\"name\":\"category\",\"value\":<rev>}]",
                "record literal: (record <type> (name value)...)",
            ),
            spec(
                "record_update",
                vec!["record_upd"],
                vec![field("type", true)],
                vec![
                    child("base", "expr", true, false),
                    child("updates", "update_field", false, true),
                ],
                "record <type>",
                "construct_expression kind=record_update type=\"Agg\" base=<rev> updates=[{\"name\":\"count\",\"value\":<rev>}]",
                "partial record update: (record-update <type> <base> (name value)...)",
            ),
            spec(
                "fold",
                vec!["result_fold"],
                vec![field("index", true), field("acc_name", true)],
                vec![
                    child("range_start", "expr", true, false),
                    child("range_end", "expr", true, false),
                    child("acc_type", "type_expr", true, false),
                    child("acc_init", "expr", true, false),
                    child("body", "expr", true, false),
                ],
                "acc_type",
                "construct_expression kind=fold index=\"i\" acc_name=\"out\" range_start=<rev> range_end=<rev> acc_type=\"(prim i64)\" acc_init=<rev> body=<rev>",
                "fold over range: (fold i (range start end) (acc out <T> init) body)",
            ),
            spec(
                "match",
                vec![],
                vec![field("type", true)],
                vec![
                    child("scrutinee", "expr", true, false),
                    child("cases", "case", false, true),
                ],
                "case body 类型（v0.1 不静态推导）",
                "construct_expression kind=match type=\"Option\" scrutinee=<rev> cases=[{\"variant\":\"Some\",\"body\":<rev>}]",
                "variant match: (match <type> <scrutinee> (case <variant> <body>)...)",
            ),
            spec(
                "range",
                vec![],
                vec![],
                vec![
                    child("range_start", "expr", true, false),
                    child("range_end", "expr", true, false),
                ],
                "range（fold 子形式）",
                "construct_expression kind=range range_start=<rev> range_end=<rev>",
                "fold 子形式：AIR 无独立 range 节点；验证后返回 range_start/range_end，传给 kind=fold",
            ),
        ]
});

/// Resolve a kind name or alias to its canonical spec.
pub fn construction_spec(name: &str) -> Option<&'static ConstructionSpec> {
    REGISTRY
        .iter()
        .find(|s| s.kind == name || s.aliases.contains(&name))
}

/// Deterministic closest-kind candidates for unknown-kind recovery.
pub fn closest_kind(name: &str, limit: usize) -> Vec<&'static str> {
    let mut scored: Vec<(usize, &'static str)> = REGISTRY
        .iter()
        .flat_map(|s| {
            let mut names = vec![s.kind];
            names.extend(s.aliases.iter().copied());
            names
        })
        .map(|n| (edit_distance(name, n), n))
        .collect();
    scored.sort_by(|a, b| a.0.cmp(&b.0).then(a.1.cmp(b.1)));
    scored.truncate(limit);
    scored.into_iter().map(|(_, n)| n).collect()
}

fn edit_distance(a: &str, b: &str) -> usize {
    let a: Vec<char> = a.chars().collect();
    let b: Vec<char> = b.chars().collect();
    let mut prev: Vec<usize> = (0..=b.len()).collect();
    for i in 1..=a.len() {
        let mut cur = vec![i];
        for j in 1..=b.len() {
            let cost = if a[i - 1] == b[j - 1] { 0 } else { 1 };
            let v = (cur[j - 1] + 1).min(prev[j] + 1).min(prev[j - 1] + cost);
            cur.push(v);
        }
        prev = cur;
    }
    prev[b.len()]
}
