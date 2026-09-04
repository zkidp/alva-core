//! RFC-0005 / AEP-0002 v0.1: Intent -> Applicable Semantic Operations.
//!
//! The operation registry is the single source of truth for AEP tool names,
//! aliases, argument schemas, target kinds, effects, examples, and feature
//! gates. Gateway dispatch (name/alias lookup), `applicable_operations`,
//! `describe_operation`, and unknown-tool recovery all derive from this table,
//! so documentation cannot drift from the executable layer.

pub struct ArgSpec {
    pub name: &'static str,
    pub schema: ArgSchema,
    pub required: bool,
}

/// Executable argument vocabulary shared by AEP discovery and MCP JSON Schema.
///
/// The display text remains useful to humans, but JSON types are selected by
/// the enum variant rather than inferred by parsing that text.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ArgSchema {
    String(&'static str),
    Text(&'static str),
    Bool(&'static str),
    Revision(&'static str),
    EntityRef(&'static str),
    Symbol(&'static str),
    Enum(&'static str, &'static [&'static str]),
    Array(&'static str),
    Object(&'static str),
    TypeExpr(&'static str),
    Path(&'static str),
    Flexible(&'static str),
}

impl ArgSchema {
    pub fn shape(self) -> &'static str {
        match self {
            Self::String(s)
            | Self::Text(s)
            | Self::Bool(s)
            | Self::Revision(s)
            | Self::EntityRef(s)
            | Self::Symbol(s)
            | Self::Enum(s, _)
            | Self::Array(s)
            | Self::Object(s)
            | Self::TypeExpr(s)
            | Self::Path(s)
            | Self::Flexible(s) => s,
        }
    }

    pub fn json_schema(self) -> serde_json::Value {
        let description = self.shape();
        match self {
            Self::Bool(_) => serde_json::json!({"type":"boolean","description":description}),
            Self::Enum(_, values) => serde_json::json!({
                "type":"string", "enum":values, "description":description
            }),
            Self::Array(_) => serde_json::json!({
                "type":"array", "items":{}, "description":description
            }),
            Self::Object(_) => serde_json::json!({
                "type":"object", "additionalProperties":true, "description":description
            }),
            Self::Flexible(_) => serde_json::json!({"description":description}),
            Self::Revision(_) => serde_json::json!({
                "type":"string", "minLength":1, "description":description
            }),
            Self::Text(_) => serde_json::json!({"type":"string","description":description}),
            Self::EntityRef(_)
            | Self::Symbol(_)
            | Self::TypeExpr(_)
            | Self::Path(_)
            | Self::String(_) => {
                serde_json::json!({"type":"string","minLength":1,"description":description})
            }
        }
    }
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

/// Canonical friendly position vocabulary for `replace_expression`.
///
/// Single source of truth: the executor (`friendly_slot` / `valid_positions`
/// in main.rs) accepts a position only if it is in this table for the node's
/// kind, and every discovery surface (`describe_operation`,
/// invalid-position recovery) advertises positions derived from this table.
/// A position name may map to a different AIR slot name (e.g. `step` ->
/// `steps`, `arg` -> `args`).
pub const POSITION_NAMES: &[&str] = &[
    "value",
    "body",
    "cond",
    "then",
    "else",
    "left",
    "right",
    "step",
    "arg",
    "collection",
    "predicate",
    "start",
    "end",
    "init",
    "cond2",
    "catch",
    "scrutinee",
    "range_start",
    "range_end",
    "acc_init",
];

fn arg(name: &'static str, shape: &'static str, required: bool) -> ArgSpec {
    ArgSpec {
        name,
        schema: schema_for_shape(shape),
        required,
    }
}

/// Closed migration map from the historical display vocabulary into typed
/// schemas. This is deliberately exhaustive rather than heuristic: an unknown
/// description fails during registry construction instead of silently
/// producing an incorrect MCP schema.
fn schema_for_shape(shape: &'static str) -> ArgSchema {
    match shape {
        "bool" => ArgSchema::Bool(shape),
        "revision" | "record-construction revision" => ArgSchema::Revision(shape),
        "entity-id|name" | "entity-id|qualified fn" | "hole-id" => ArgSchema::EntityRef(shape),
        "symbol" | "field" | "field name" | "target" => ArgSchema::Symbol(shape),
        "type" | "type string" | "type name" | "record type name" => ArgSchema::TypeExpr(shape),
        "path to alva.toml" | "project-relative module path" => ArgSchema::Path(shape),
        "text" => ArgSchema::Text(shape),
        "revisions (repeatable)" | "param specs" => ArgSchema::Array(shape),
        "field=value pairs" => ArgSchema::Object(shape),
        "revision | type string | json array" => ArgSchema::Flexible(shape),
        "string(module|function|type|record|enum)" => {
            ArgSchema::Enum(shape, &["module", "function", "type", "record", "enum"])
        }
        "string(field|record|record_update|veclit|fold|match|ok|err|not|range)" => ArgSchema::Enum(
            shape,
            &[
                "field",
                "record",
                "record_update",
                "veclit",
                "fold",
                "match",
                "ok",
                "err",
                "not",
                "range",
            ],
        ),
        "string(builtin|operator|all)" => ArgSchema::Enum(shape, &["builtin", "operator", "all"]),
        "string|i64|bool|bytes|nil" => {
            ArgSchema::Enum(shape, &["string", "i64", "bool", "bytes", "nil"])
        }
        "contains|any|all|find" => ArgSchema::Enum(shape, &["contains", "any", "all", "find"]),
        "string(pure|io)" => ArgSchema::Enum(shape, &["pure", "io"]),
        "io|clock|unsafe-ffi" => ArgSchema::Enum(shape, &["io", "clock", "unsafe-ffi"]),
        "string"
        | "string(qualified module.fn)"
        | "qualified fn or builtin"
        | "module fn"
        | "module name"
        | "==|+|..."
        | "kind-dependent slot position (see describe_operation expected_positions)" => {
            ArgSchema::String(shape)
        }
        other => panic!("untyped AEP argument shape: {other}"),
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
            "prepare_edit",
            vec![],
            vec!["any"],
            vec![
                arg("entity", "entity-id|name", true),
                arg("kind", "string(module|function|type|record|enum)", false),
                arg("module", "string", false),
                arg("operation", "string", false),
            ],
            vec!["transaction"],
            "inspection",
            "transaction",
            "prepare_edit entity=queue.engine.claim kind=function operation=rename_entity",
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
        // RFC-0006 / AEP-0003: Typed Semantic Construction (v0.1).
        spec(
            "describe_construction",
            vec!["describe_kind", "construction_schema"],
            vec!["any"],
            vec![
                arg(
                    "kind",
                    "string(field|record|record_update|veclit|fold|match|ok|err|not|range)",
                    true,
                ),
                arg("include_candidates", "bool", false),
            ],
            vec!["transaction"],
            "inspection",
            "construction",
            "describe_construction kind=fold",
            None,
        ),
        spec(
            "construct_expression",
            vec!["construct_kind", "make_expression"],
            vec!["any"],
            vec![
                arg(
                    "kind",
                    "string(field|record|record_update|veclit|fold|match|ok|err|not|range)",
                    true,
                ),
                arg("expected_type", "type string", false),
                arg("...children", "revision | type string | json array", false),
            ],
            vec!["transaction"],
            "mutation",
            "construction",
            "construct_expression kind=err value=<rev> expected_type=(result string string)",
            None,
        ),
        // Capability catalog (pre-RFC): compiler-owned builtin/operator
        // vocabulary; no applicability, no entity navigation, no fuzzy.
        spec(
            "describe_capability",
            vec!["capability_info", "describe_builtin"],
            vec!["any"],
            vec![arg("name", "string", true)],
            vec!["transaction"],
            "inspection",
            "construction",
            "describe_capability name=sort",
            None,
        ),
        spec(
            "list_capabilities",
            vec!["capability_list", "list_builtins"],
            vec!["any"],
            vec![arg("category", "string(builtin|operator|all)", true)],
            vec!["transaction"],
            "inspection",
            "construction",
            "list_capabilities category=operator",
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
            "stage_and_check",
            vec![],
            vec!["any"],
            vec![
                arg("operation", "string", true),
                arg("arguments", "field=value pairs", true),
            ],
            vec!["transaction", "nested operation must be a mutation"],
            "mutation",
            "transaction",
            "stage_and_check operation=change_field arguments={<mutation arguments>}",
            None,
        ),
        spec(
            "stage_text_patch",
            vec![],
            vec!["any"],
            vec![
                arg("path", "project-relative module path", true),
                arg("expected_sha256", "string", true),
                arg("old", "string", true),
                arg("new", "text", true),
                arg("replace_all", "bool", false),
            ],
            vec![
                "transaction",
                "path is a manifest-declared module",
                "source-derived graph is unchanged",
            ],
            "mutation",
            "transaction",
            "stage_text_patch path=src/app.alva expected_sha256=<sha> old=<exact> new=<text>",
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
                arg(
                    "position",
                    "kind-dependent slot position (see describe_operation expected_positions)",
                    true,
                ),
            ],
            vec!["transaction"],
            "mutation",
            "expression",
            "replace_expression parent=<rev> child=<rev> position=step",
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

/// Deterministic JSON Schema 2020-12 input schema generated from the same
/// typed operation registry used by AEP discovery and dispatch.
pub fn operation_input_schema(spec: &OperationSpec) -> serde_json::Value {
    let mut properties = serde_json::Map::new();
    let mut required = Vec::new();
    let mut additional_properties = serde_json::Value::Bool(false);
    for argument in &spec.arguments {
        if argument.name.starts_with("...") {
            additional_properties = argument.schema.json_schema();
            continue;
        }
        properties.insert(argument.name.to_string(), argument.schema.json_schema());
        if argument.required {
            required.push(serde_json::json!(argument.name));
        }
    }
    serde_json::json!({
        "$schema":"https://json-schema.org/draft/2020-12/schema",
        "type":"object",
        "properties":properties,
        "required":required,
        "additionalProperties":additional_properties
    })
}

/// Validate the executable JSON argument contract derived from the registry.
///
/// `allowed_envelope_fields` are transport-owned fields such as an MCP
/// transaction handle. Operation arguments remain defined only by the
/// registry, including the explicit `...children` open tail used by typed
/// construction.
pub fn validate_json_arguments(
    spec: &OperationSpec,
    arguments: &serde_json::Map<String, serde_json::Value>,
    allowed_envelope_fields: &[&str],
) -> Result<(), String> {
    let dynamic = spec
        .arguments
        .iter()
        .find(|argument| argument.name.starts_with("..."));

    for argument in &spec.arguments {
        if argument.name.starts_with("...") {
            continue;
        }
        match arguments.get(argument.name) {
            Some(value) => validate_json_value(argument.name, argument.schema, value)?,
            None if argument.required => {
                return Err(format!(
                    "E_AEP_INVALID_ARGUMENTS: missing required field '{}'",
                    argument.name
                ))
            }
            None => {}
        }
    }

    for (name, value) in arguments {
        if allowed_envelope_fields.contains(&name.as_str())
            || spec.arguments.iter().any(|argument| argument.name == name)
        {
            continue;
        }
        if let Some(dynamic) = dynamic {
            validate_json_value(name, dynamic.schema, value)?;
        } else {
            return Err(format!(
                "E_AEP_INVALID_ARGUMENTS: unknown field '{name}' for '{}'",
                spec.name
            ));
        }
    }
    Ok(())
}

fn validate_json_value(
    name: &str,
    schema: ArgSchema,
    value: &serde_json::Value,
) -> Result<(), String> {
    let valid = match schema {
        ArgSchema::Bool(_) => value.is_boolean(),
        ArgSchema::Array(_) => value.is_array(),
        ArgSchema::Object(_) => value.is_object(),
        ArgSchema::Flexible(_) => true,
        ArgSchema::Text(_) => value.is_string(),
        // Operation-specific handlers retain responsibility for vocabulary
        // membership so they can return richer recovery candidates and stable
        // domain error codes. The protocol boundary enforces the JSON type.
        ArgSchema::Enum(_, _) => value
            .as_str()
            .map(|candidate| !candidate.is_empty())
            .unwrap_or(false),
        ArgSchema::Revision(_)
        | ArgSchema::EntityRef(_)
        | ArgSchema::Symbol(_)
        | ArgSchema::TypeExpr(_)
        | ArgSchema::Path(_)
        | ArgSchema::String(_) => value
            .as_str()
            .map(|candidate| !candidate.is_empty())
            .unwrap_or(false),
    };
    if valid {
        Ok(())
    } else {
        Err(format!(
            "E_AEP_INVALID_ARGUMENTS: field '{name}' does not match {}",
            schema.shape()
        ))
    }
}

#[cfg(test)]
mod argument_validation_tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn closed_operation_rejects_unknown_and_missing_fields() {
        let spec = lookup("set_effect").unwrap();
        let unknown = json!({"function":"demo.run","effect":"io","surprise":true});
        let missing = json!({"function":"demo.run"});
        assert!(
            validate_json_arguments(spec, unknown.as_object().unwrap(), &[])
                .unwrap_err()
                .contains("unknown field 'surprise'")
        );
        assert!(
            validate_json_arguments(spec, missing.as_object().unwrap(), &[])
                .unwrap_err()
                .contains("missing required field 'effect'")
        );
    }

    #[test]
    fn dynamic_construction_accepts_typed_child_keys() {
        let spec = lookup("construct_expression").unwrap();
        let arguments = json!({"kind":"not","value":"revision-1"});
        validate_json_arguments(spec, arguments.as_object().unwrap(), &[]).unwrap();
    }

    #[test]
    fn enum_strings_preserve_operation_recovery_and_boolean_shape_is_enforced() {
        let list = lookup("list_capabilities").unwrap();
        let bad_enum = json!({"category":"everything"});
        validate_json_arguments(list, bad_enum.as_object().unwrap(), &[]).unwrap();

        let describe = lookup("describe_construction").unwrap();
        let bad_bool = json!({"kind":"fold","include_candidates":"true"});
        assert!(validate_json_arguments(describe, bad_bool.as_object().unwrap(), &[]).is_err());
    }
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
