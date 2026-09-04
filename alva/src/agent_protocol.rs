//! Transport-neutral request and response primitives for the Agent Execution
//! Protocol (AEP).
//!
//! Keep protocol parsing and registry validation here so the CLI and MCP
//! transports can share one execution service without reimplementing wire
//! semantics.

use std::collections::BTreeMap;

#[derive(Clone, Debug)]
pub(crate) enum Json {
    Null,
    Bool(bool),
    Num(f64),
    Str(String),
    Arr(Vec<Json>),
    Obj(BTreeMap<String, Json>),
}

impl Json {
    pub(crate) fn get(&self, key: &str) -> Option<&Json> {
        match self {
            Json::Obj(fields) => fields.get(key),
            _ => None,
        }
    }

    pub(crate) fn as_str(&self) -> Option<&str> {
        match self {
            Json::Str(value) => Some(value),
            _ => None,
        }
    }
}

pub(crate) fn parse_json(input: &str) -> Result<Json, String> {
    fn convert(value: serde_json::Value) -> Result<Json, String> {
        match value {
            serde_json::Value::Null => Ok(Json::Null),
            serde_json::Value::Bool(value) => Ok(Json::Bool(value)),
            serde_json::Value::Number(value) => value
                .as_f64()
                .map(Json::Num)
                .ok_or_else(|| "number is outside the supported range".to_string()),
            serde_json::Value::String(value) => Ok(Json::Str(value)),
            serde_json::Value::Array(values) => values
                .into_iter()
                .map(convert)
                .collect::<Result<Vec<_>, _>>()
                .map(Json::Arr),
            serde_json::Value::Object(values) => values
                .into_iter()
                .map(|(key, value)| convert(value).map(|value| (key, value)))
                .collect::<Result<BTreeMap<_, _>, _>>()
                .map(Json::Obj),
        }
    }

    serde_json::from_str(input)
        .map_err(|error| error.to_string())
        .and_then(convert)
}

fn json_to_serde(value: &Json) -> serde_json::Value {
    match value {
        Json::Null => serde_json::Value::Null,
        Json::Bool(value) => serde_json::Value::Bool(*value),
        Json::Num(value) => serde_json::Number::from_f64(*value)
            .map(serde_json::Value::Number)
            .unwrap_or(serde_json::Value::Null),
        Json::Str(value) => serde_json::Value::String(value.clone()),
        Json::Arr(values) => serde_json::Value::Array(values.iter().map(json_to_serde).collect()),
        Json::Obj(values) => serde_json::Value::Object(
            values
                .iter()
                .map(|(key, value)| (key.clone(), json_to_serde(value)))
                .collect(),
        ),
    }
}

pub(crate) fn validate_arguments(
    request: &Json,
    spec: &crate::aep::OperationSpec,
) -> Result<(), String> {
    let Json::Obj(fields) = request else {
        return Err("E_AEP_INVALID_ARGUMENTS: request must be an object".to_string());
    };
    let mut arguments: serde_json::Map<String, serde_json::Value> = fields
        .iter()
        .filter(|(name, _)| name.as_str() != "request_id" && name.as_str() != "tool")
        .map(|(name, value)| (name.clone(), json_to_serde(value)))
        .collect();

    // The historical aep.py key=value bridge encoded booleans as strings.
    // Normalize that documented compatibility form. MCP remains strictly typed.
    for argument in &spec.arguments {
        if matches!(argument.schema, crate::aep::ArgSchema::Bool(_)) {
            if let Some(serde_json::Value::String(value)) = arguments.get(argument.name) {
                let normalized = match value.as_str() {
                    "true" | "1" => Some(true),
                    "false" | "0" => Some(false),
                    _ => None,
                };
                if let Some(normalized) = normalized {
                    arguments.insert(
                        argument.name.to_string(),
                        serde_json::Value::Bool(normalized),
                    );
                }
            }
        }
    }
    crate::aep::validate_json_arguments(spec, &arguments, &[])
}

pub(crate) fn json_str(value: &str) -> String {
    format!("\"{}\"", crate::diag::json_escape(value))
}

pub(crate) fn render_json(value: &Json) -> String {
    match value {
        Json::Null => "null".to_string(),
        Json::Bool(value) => value.to_string(),
        Json::Num(value) => format!("{value}"),
        Json::Str(value) => json_str(value),
        Json::Arr(items) => {
            let parts: Vec<String> = items.iter().map(render_json).collect();
            format!("[{}]", parts.join(","))
        }
        Json::Obj(fields) => {
            let parts: Vec<String> = fields
                .iter()
                .map(|(key, value)| format!("{}:{}", json_str(key), render_json(value)))
                .collect();
            format!("{{{}}}", parts.join(","))
        }
    }
}

pub(crate) fn response(
    request_id: Option<&str>,
    op_index: usize,
    ok: bool,
    result: &str,
    message: &str,
    diagnostics: Vec<String>,
) -> String {
    let error_code = if ok {
        "ok"
    } else {
        match message.split(':').next() {
            Some(token) if token.trim().starts_with("E_") => token.trim(),
            _ => "E_AEP_OP",
        }
    };
    format!(
        "{{\"protocol_version\":\"0.7-replication\",\"request_id\":{},\"op_index\":{},\"ok\":{},\"error_code\":{},\"result\":{},\"diagnostics\":[{}],\"message\":{}}}",
        request_id.map(json_str).unwrap_or_else(|| "null".to_string()),
        op_index,
        ok,
        json_str(error_code),
        result,
        diagnostics
            .iter()
            .map(|diagnostic| json_str(diagnostic))
            .collect::<Vec<_>>()
            .join(","),
        json_str(message)
    )
}

#[cfg(test)]
mod tests {
    use super::{parse_json, validate_arguments, Json};

    #[test]
    fn parses_standard_unicode_escapes() {
        let parsed = parse_json(r#"{"project":"Documents/\u65e5\u5e38/alva.toml"}"#).unwrap();
        assert_eq!(
            parsed.get("project").and_then(Json::as_str),
            Some("Documents/日常/alva.toml")
        );
    }

    #[test]
    fn parses_surrogate_pairs() {
        let parsed = parse_json(r#"{"symbol":"\ud83e\udd16"}"#).unwrap();
        assert_eq!(parsed.get("symbol").and_then(Json::as_str), Some("🤖"));
    }

    #[test]
    fn rejects_invalid_escape_and_trailing_input() {
        assert!(parse_json(r#"{"bad":"\q"}"#).is_err());
        assert!(parse_json(r#"{"ok":true} trailing"#).is_err());
    }

    #[test]
    fn direct_agent_rejects_unknown_fields() {
        let request = parse_json(
            r#"{"tool":"set_effect","function":"demo.run","effect":"io","surprise":true}"#,
        )
        .unwrap();
        let spec = crate::aep::lookup("set_effect").unwrap();
        assert!(validate_arguments(&request, spec)
            .unwrap_err()
            .contains("unknown field 'surprise'"));
    }

    #[test]
    fn direct_agent_preserves_documented_boolean_string_compatibility() {
        let request = parse_json(
            r#"{"tool":"describe_construction","kind":"fold","include_candidates":"true"}"#,
        )
        .unwrap();
        let spec = crate::aep::lookup("describe_construction").unwrap();
        validate_arguments(&request, spec).unwrap();
    }
}
