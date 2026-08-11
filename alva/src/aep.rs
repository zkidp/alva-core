//! RFC-0005 / AEP-0002 v0.1: Intent -> Applicable Semantic Operations.
//!
//! The operation registry is the single source of truth for AEP tool names,
//! aliases, argument schemas, target kinds, effects, examples, and feature
//! gates. Gateway dispatch (name/alias lookup), `applicable_operations`,
//! `describe_operation`, and unknown-tool recovery all derive from this table,
//! so documentation cannot drift from the executable layer.

pub struct ArgSpec {
    pub name: &'static str,
    pub shape: &'static str,
    pub required: bool,
}

pub struct OperationSpec {
    pub name: &'static str,
    pub aliases: Vec<&'static str>,
    /// Entity kinds this operation applies to ("any" = all).
    pub target_kinds: Vec<&'static str>,
    pub arguments: Vec<ArgSpec>,
    pub preconditions: Vec<&'static str>,
    /// "inspection" (read-only) | "mutation" (writes transaction) | "transaction"
    pub effects: &'static str,
    /// "entity" | "expression" | "construction" | "transaction"
    pub scope: &'static str,
    pub example: &'static str,
    /// Feature gate env var; the operation is hidden when the var is unset.
    pub gate: Option<&'static str>,
}

pub const GATE_A1: &str = "ALVA_AEP_ENABLE_EXPERIMENTAL_A1";

const fn arg(name: &'static str, shape: &'static str, required: bool) -> ArgSpec {
    ArgSpec {
        name,
        shape,
        required,
    }
}

#[allow(clippy::too_many_arguments)]
fn spec(
    name: &'static str,
    aliases: Vec<&'static str>,
    target_kinds: Vec<&'static str>,
    arguments: Vec<ArgSpec>,
    preconditions: Vec<&'static str>,
    effects: &'static str,
    scope: &'static str,
    example: &'static str,
    gate: Option<&'static str>,
) -> OperationSpec {
    OperationSpec {
        name,
        aliases,
        target_kinds,
        arguments,
        preconditions,
        effects,
        scope,
        example,
        gate,
    }
}

static REGISTRY: std::sync::LazyLock<Vec<OperationSpec>> = std::sync::LazyLock::new(|| {
    vec![
        spec(
            "resolve_entity",
            vec![],
            vec!["any"],
            vec![
                arg("name", "string", true),
                arg("kind", "string(module|function|type|record|enum)", false),
                arg("module", "string", false),
            ],
            vec!["transaction"],
            "inspection",
            "transaction",
            "resolve_entity name=Job kind=record",
            None,
        ),
        spec(
            "applicable_operations",
            vec![],
            vec!["any"],
            vec![arg("entity", "entity-id|name", true)],
            vec!["transaction"],
            "inspection",
            "entity",
            "applicable_operations entity=Job",
            None,
        ),
        spec(
            "describe_operation",
            vec![],
            vec!["any"],
            vec![arg("name", "string", true)],
            vec![],
            "inspection",
            "transaction",
            "describe_operation name=update_record_fields",
            None,
        ),
        spec(
            "inspect_project",
            vec![],
            vec!["any"],
            vec![],
            vec!["transaction"],
            "inspection",
            "transaction",
            "inspect_project",
            None,
        ),
        spec(
            "inspect_module",
            vec![],
            vec!["module"],
            vec![arg("name", "string", true)],
            vec!["transaction"],
            "inspection",
            "entity",
            "inspect_module name=queue.model",
            None,
        ),
        spec(
            "inspect_function",
            vec![],
            vec!["function"],
            vec![arg("name", "string(qualified module.fn)", true)],
            vec!["transaction"],
            "inspection",
            "entity",
            "inspect_function name=queue.engine.claim",
            None,
        ),
        spec(
            "inspect_entity",
            vec![],
            vec!["any"],
            vec![
                arg("entity", "entity-id|name", true),
                arg("name", "string", false),
            ],
            vec!["transaction"],
            "inspection",
            "entity",
            "inspect_entity entity=Job",
            None,
        ),
        spec(
            "inspect_body",
            vec![],
            vec!["function"],
            vec![arg("function", "entity-id|qualified fn", true)],
            vec!["transaction"],
            "inspection",
            "entity",
            "inspect_body function=queue.engine.claim",
            None,
        ),
        spec(
            "inspect_test",
            vec![],
            vec!["function"],
            vec![arg("module", "string", true), arg("name", "string", true)],
            vec!["transaction"],
            "inspection",
            "entity",
            "inspect_test module=queue.main name=test_x",
            None,
        ),
        spec(
            "list_candidates",
            vec![],
            vec!["any"],
            vec![arg("hole", "hole-id", true)],
            vec!["transaction"],
            "inspection",
            "transaction",
            "list_candidates hole=<rev>",
            None,
        ),
        spec(
            "preview_semantic_diff",
            vec![],
            vec!["any"],
            vec![],
            vec!["transaction"],
            "inspection",
            "transaction",
            "preview_semantic_diff",
            None,
        ),
        spec(
            "begin_transaction",
            vec![],
            vec!["any"],
            vec![arg("project", "path to alva.toml", true)],
            vec![],
            "transaction",
            "transaction",
            "begin_transaction project=/workspace/alva.toml",
            None,
        ),
        spec(
            "check_transaction",
            vec![],
            vec!["any"],
            vec![],
            vec!["transaction"],
            "transaction",
            "transaction",
            "check_transaction",
            None,
        ),
        spec(
            "commit_transaction",
            vec![],
            vec!["any"],
            vec![],
            vec!["transaction"],
            "transaction",
            "transaction",
            "commit_transaction",
            None,
        ),
        spec(
            "abort_transaction",
            vec![],
            vec!["any"],
            vec![],
            vec!["transaction"],
            "transaction",
            "transaction",
            "abort_transaction",
            None,
        ),
        spec(
            "create_literal",
            vec![],
            vec!["any"],
            vec![
                arg("type", "string|i64|bool|bytes|nil", true),
                arg("value", "string", true),
            ],
            vec!["transaction"],
            "mutation",
            "construction",
            "create_literal type=i64 value=42",
            None,
        ),
        spec(
            "create_reference",
            vec![],
            vec!["any"],
            vec![arg("name", "symbol", true)],
            vec!["transaction"],
            "mutation",
            "construction",
            "create_reference name=root",
            None,
        ),
        spec(
            "create_call",
            vec![],
            vec!["any"],
            vec![
                arg("name", "qualified fn or builtin", true),
                arg("args", "revisions (repeatable)", false),
            ],
            vec!["transaction"],
            "mutation",
            "construction",
            "create_call name=queue.fs.read_string args=<rev>",
            None,
        ),
        spec(
            "create_binding",
            vec![],
            vec!["any"],
            vec![
                arg("name", "symbol", true),
                arg("type_name", "type", true),
                arg("value", "revision", true),
            ],
            vec!["transaction"],
            "mutation",
            "construction",
            "create_binding name=x type_name=i64 value=<rev>",
            None,
        ),
        spec(
            "create_block",
            vec![],
            vec!["any"],
            vec![arg("steps", "revisions (repeatable)", false)],
            vec!["transaction"],
            "mutation",
            "construction",
            "create_block steps=<rev> steps=<rev>",
            None,
        ),
        spec(
            "create_if",
            vec![],
            vec!["any"],
            vec![
                arg("cond", "revision", true),
                arg("then", "revision", true),
                arg("else", "revision", true),
            ],
            vec!["transaction"],
            "mutation",
            "construction",
            "create_if cond=<rev> then=<rev> else=<rev>",
            None,
        ),
        spec(
            "create_binary",
            vec![],
            vec!["any"],
            vec![
                arg("op", "==|+|...", true),
                arg("left", "revision", true),
                arg("right", "revision", true),
            ],
            vec!["transaction"],
            "mutation",
            "construction",
            "create_binary op== left=<rev> right=<rev>",
            None,
        ),
        spec(
            "create_query",
            vec![],
            vec!["any"],
            vec![
                arg("kind", "contains|any|all|find", true),
                arg("collection", "revision", true),
                arg("target", "revision", false),
                arg("elem_var", "symbol", false),
                arg("predicate", "revision", false),
            ],
            vec!["transaction"],
            "mutation",
            "construction",
            "create_query kind=contains collection=<rev> target=<rev>",
            None,
        ),
        spec(
            "append_step",
            vec![],
            vec!["function"],
            vec![
                arg("function", "module fn", true),
                arg("step", "revision", true),
            ],
            vec!["transaction"],
            "mutation",
            "entity",
            "append_step function=queue.main.main step=<rev>",
            None,
        ),
        spec(
            "replace_expression",
            vec!["replace_expr"],
            vec!["any"],
            vec![
                arg("parent", "revision", true),
                arg("child", "revision", true),
                arg("position", "steps/0|args/0|...", true),
            ],
            vec!["transaction"],
            "mutation",
            "expression",
            "replace_expression parent=<rev> child=<rev> position=steps/0",
            None,
        ),
        spec(
            "add_function",
            vec![],
            vec!["module"],
            vec![
                arg("module", "module name", true),
                arg("name", "symbol", true),
                arg("returns", "type", true),
                arg("params", "param specs", false),
            ],
            vec!["transaction"],
            "mutation",
            "entity",
            "add_function module=queue.engine name=foo returns=(prim i64)",
            None,
        ),
        spec(
            "change_field",
            vec![],
            vec!["any"],
            vec![
                arg("entity", "revision", true),
                arg("field", "field", true),
                arg("value", "string", false),
            ],
            vec!["transaction"],
            "mutation",
            "entity",
            "change_field entity=<rev> field=pure value=true",
            None,
        ),
        spec(
            "rename_entity",
            vec![],
            vec!["any"],
            vec![
                arg("entity", "entity-id|name", true),
                arg("new_name", "target", true),
            ],
            vec!["transaction"],
            "mutation",
            "entity",
            "rename_entity entity=queue.model.Job new_name=Task",
            None,
        ),
        spec(
            "add_field",
            vec![],
            vec!["type", "record", "enum"],
            vec![
                arg("type", "type name", true),
                arg("name", "field name", true),
                arg("type_name", "type", true),
            ],
            vec!["transaction"],
            "mutation",
            "entity",
            "add_field type=queue.model.Job name=last_error type_name=(prim string)",
            None,
        ),
        spec(
            "add_record_field",
            vec![],
            vec!["any"],
            vec![
                arg("record", "record-construction revision", true),
                arg("name", "field name", true),
                arg("value", "revision", true),
            ],
            vec!["transaction"],
            "mutation",
            "expression",
            "add_record_field record=<rev> name=last_error value=<rev>",
            None,
        ),
        spec(
            "add_param",
            vec![],
            vec!["function"],
            vec![
                arg("function", "module fn", true),
                arg("name", "symbol", true),
                arg("type", "type", true),
            ],
            vec!["transaction"],
            "mutation",
            "entity",
            "add_param function=queue.engine.fail name=error type=(prim string)",
            None,
        ),
        spec(
            "add_call_arg",
            vec![],
            vec!["any"],
            vec![arg("call", "revision", true), arg("arg", "revision", true)],
            vec!["transaction"],
            "mutation",
            "expression",
            "add_call_arg call=<rev> arg=<rev>",
            None,
        ),
        spec(
            "set_effect",
            vec![],
            vec!["function"],
            vec![
                arg("function", "module fn", true),
                arg("effect", "string(pure|io)", true),
            ],
            vec!["transaction"],
            "mutation",
            "entity",
            "set_effect function=queue.engine.foo effect=pure",
            None,
        ),
        spec(
            "add_cap",
            vec![],
            vec!["module"],
            vec![
                arg("module", "module name", true),
                arg("cap", "io|clock|unsafe-ffi", true),
            ],
            vec!["transaction"],
            "mutation",
            "entity",
            "add_cap module=queue.main cap=io",
            None,
        ),
        spec(
            "update_record_fields",
            vec![],
            vec!["type", "record"],
            vec![
                arg("type", "record type name", true),
                arg("base", "revision", true),
                arg("updates", "field=value pairs", true),
            ],
            vec!["transaction"],
            "mutation",
            "entity",
            "update_record_fields type=queue.model.Job base=<rev> updates={attempt:<rev>}",
            None,
        ),
        spec(
            "inspect_change_impact",
            vec![],
            vec!["type", "record", "function"],
            vec![arg("entity", "entity-id|name", true)],
            vec!["transaction"],
            "inspection",
            "entity",
            "inspect_change_impact entity=queue.model.Job",
            Some(GATE_A1),
        ),
        spec(
            "inspect_schema_gaps",
            vec![],
            vec!["type", "record"],
            vec![arg("entity", "entity-id|name", true)],
            vec!["transaction"],
            "inspection",
            "entity",
            "inspect_schema_gaps entity=queue.model.Job",
            Some(GATE_A1),
        ),
    ]
});

pub fn registry() -> &'static [OperationSpec] {
    &REGISTRY
}

pub fn gate_enabled(gate: &str) -> bool {
    std::env::var(gate).is_ok()
}

pub fn lookup(name: &str) -> Option<&'static OperationSpec> {
    registry()
        .iter()
        .find(|s| s.name == name || s.aliases.contains(&name))
}

pub fn visible<'a>() -> impl Iterator<Item = &'static OperationSpec> + 'a {
    registry().iter().filter(|s| match s.gate {
        Some(g) => gate_enabled(g),
        None => true,
    })
}

/// Deterministic closest-operation candidates for recovery hints.
pub fn closest(name: &str, limit: usize) -> Vec<&'static OperationSpec> {
    let mut out: Vec<&'static OperationSpec> = Vec::new();
    for s in visible() {
        let n = s.name;
        if n == name {
            continue;
        }
        let hit = n.starts_with(name)
            || n.contains(name)
            || name.len() >= 3 && n.contains(&name[..3.min(name.len())])
            || name.len() >= 3 && name.starts_with(&n[..n.len().min(3)]);
        if hit {
            out.push(s);
        }
    }
    out.sort_by_key(|s| s.name);
    out.truncate(limit);
    out
}

/// Entity-targeted operations applicable to an entity kind (scope=entity),
/// respecting feature gates. Expression/construction/transaction-scope
/// operations are NOT "operations on this entity".
pub fn for_entity(kind: &str) -> Vec<&'static OperationSpec> {
    let mut out: Vec<&'static OperationSpec> = visible()
        .filter(|s| s.scope == "entity" && s.target_kinds.iter().any(|k| *k == "any" || *k == kind))
        .collect();
    out.sort_by_key(|s| s.name);
    out
}

/// Context / global operations (construction + transaction scope).
pub fn context_ops() -> Vec<&'static OperationSpec> {
    let mut out: Vec<&'static OperationSpec> = visible().filter(|s| s.scope != "entity").collect();
    out.sort_by_key(|s| s.name);
    out
}
