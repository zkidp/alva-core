//! Thin MCP STDIO adapter over the existing AEP semantic gateway.
//!
//! The adapter deliberately owns no semantic mutation implementation. Each
//! explicit MCP transaction handle is backed by an `alva agent` child, so the
//! CLI and MCP surfaces execute the same registry and AIR transaction code.

use crate::aep;
use serde_json::{json, Value};
use std::io::{BufRead, BufReader, BufWriter, Write};
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};

const MODERN_VERSION: &str = "2026-07-28";
const LEGACY_VERSION: &str = "2025-11-25";
const SERVER_NAME: &str = "alva";

const MCP_TOOLS: &[&str] = &[
    "begin_transaction",
    "resolve_entity",
    "prepare_edit",
    "applicable_operations",
    "describe_operation",
    "inspect_project",
    "inspect_entity",
    "inspect_body",
    "describe_construction",
    "construct_expression",
    "change_field",
    "stage_and_check",
    "preview_semantic_diff",
    "check_transaction",
    "commit_transaction",
    "abort_transaction",
];

const MCP_STAGE_MUTATIONS: &[&str] = &["construct_expression", "change_field", "stage_text_patch"];

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
enum ProtocolEra {
    #[default]
    Undecided,
    Legacy,
    Modern,
}

struct AgentChild {
    child: Child,
    input: BufWriter<ChildStdin>,
    output: BufReader<ChildStdout>,
}

impl AgentChild {
    fn spawn() -> Result<Self, String> {
        let exe = std::env::current_exe().map_err(|e| format!("cannot locate alva: {e}"))?;
        let mut child = Command::new(exe)
            .arg("agent")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()
            .map_err(|e| format!("cannot start semantic gateway: {e}"))?;
        let input = child.stdin.take().ok_or("semantic gateway has no stdin")?;
        let output = child
            .stdout
            .take()
            .ok_or("semantic gateway has no stdout")?;
        Ok(Self {
            child,
            input: BufWriter::new(input),
            output: BufReader::new(output),
        })
    }

    fn call(&mut self, request: &Value) -> Result<Value, String> {
        serde_json::to_writer(&mut self.input, request)
            .map_err(|e| format!("cannot encode gateway request: {e}"))?;
        self.input
            .write_all(b"\n")
            .and_then(|_| self.input.flush())
            .map_err(|e| format!("cannot write gateway request: {e}"))?;
        let mut line = String::new();
        let read = self
            .output
            .read_line(&mut line)
            .map_err(|e| format!("cannot read gateway response: {e}"))?;
        if read == 0 {
            return Err("semantic gateway exited before responding".to_string());
        }
        serde_json::from_str(line.trim_end())
            .map_err(|e| format!("semantic gateway returned invalid JSON: {e}"))
    }
}

impl Drop for AgentChild {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

#[derive(Default)]
struct Gateway {
    active: Option<(String, AgentChild)>,
    next_transaction: u64,
}

impl Gateway {
    fn call_tool(&mut self, name: &str, arguments: &Value) -> Result<Value, String> {
        if !MCP_TOOLS.contains(&name) {
            return Err(format!("E_MCP_UNKNOWN_TOOL: unknown tool '{name}'"));
        }
        let args = arguments
            .as_object()
            .ok_or("E_MCP_INVALID_ARGUMENTS: arguments must be an object")?;
        let spec = aep::lookup(name)
            .ok_or_else(|| format!("E_MCP_UNKNOWN_TOOL: unknown tool '{name}'"))?;
        let envelope_fields = if name == "begin_transaction" {
            &[][..]
        } else {
            &["transaction_id"][..]
        };
        aep::validate_json_arguments(spec, args, envelope_fields)
            .map_err(|error| error.replacen("E_AEP_", "E_MCP_", 1))?;
        if name == "stage_and_check" {
            let nested = args
                .get("operation")
                .and_then(Value::as_str)
                .ok_or("E_MCP_STAGE_BAD_OPERATION: operation must be a string")?;
            let nested_spec = aep::lookup(nested).ok_or_else(|| {
                format!("E_MCP_STAGE_OPERATION_FORBIDDEN: unknown nested operation '{nested}'")
            })?;
            if nested_spec.effects != "mutation"
                || nested_spec.name == "stage_and_check"
                || !MCP_STAGE_MUTATIONS.contains(&nested_spec.name)
            {
                return Err(format!(
                    "E_MCP_STAGE_OPERATION_FORBIDDEN: '{}' is not an exposed MCP mutation",
                    nested_spec.name
                ));
            }
        }

        if name == "begin_transaction" {
            if self.active.is_some() {
                return Err(
                    "E_MCP_TRANSACTION_ACTIVE: abort or commit the active transaction first"
                        .to_string(),
                );
            }
            let mut child = AgentChild::spawn()?;
            let mut request = Value::Object(args.clone());
            request["request_id"] = json!("mcp-begin");
            request["tool"] = json!(name);
            if let Some(project) = request.get("project").and_then(Value::as_str) {
                let path = std::path::Path::new(project);
                if path.is_relative() {
                    if let Ok(root) = std::env::var("CLAUDE_PROJECT_DIR") {
                        request["project"] = json!(std::path::Path::new(&root).join(path));
                    }
                }
            }
            let response = child.call(&request)?;
            ensure_agent_ok(&response)?;
            self.next_transaction += 1;
            let transaction_id =
                format!("tx_{:x}_{:016x}", std::process::id(), self.next_transaction);
            let mut result = response
                .get("result")
                .and_then(Value::as_object)
                .cloned()
                .unwrap_or_default();
            result.insert("transaction_id".to_string(), json!(transaction_id));
            self.active = Some((transaction_id, child));
            return Ok(Value::Object(result));
        }

        let transaction_id = args
            .get("transaction_id")
            .and_then(Value::as_str)
            .ok_or("E_MCP_TRANSACTION_REQUIRED: transaction_id is required")?;
        let (active_id, child) = self
            .active
            .as_mut()
            .ok_or("E_MCP_NO_TRANSACTION: no active transaction")?;
        if active_id != transaction_id {
            return Err("E_MCP_TRANSACTION_NOT_FOUND: transaction_id is not active".to_string());
        }
        let mut forwarded = args.clone();
        forwarded.remove("transaction_id");
        forwarded.insert("request_id".to_string(), json!(format!("mcp-{name}")));
        forwarded.insert("tool".to_string(), json!(name));
        let response = child.call(&Value::Object(forwarded))?;
        ensure_agent_ok(&response)?;
        let mut result = response.get("result").cloned().unwrap_or(Value::Null);
        if name == "applicable_operations" {
            filter_applicable_operations(&mut result);
        }
        if matches!(name, "commit_transaction" | "abort_transaction") {
            self.active = None;
        }
        Ok(result)
    }
}

fn filter_applicable_operations(result: &mut Value) {
    let Some(object) = result.as_object_mut() else {
        return;
    };
    for key in ["inspection", "mutation", "context_operations"] {
        if let Some(operations) = object.get_mut(key).and_then(Value::as_array_mut) {
            operations.retain(|operation| {
                operation
                    .as_str()
                    .is_some_and(|name| MCP_TOOLS.contains(&name))
            });
        }
    }
}

fn ensure_agent_ok(response: &Value) -> Result<(), String> {
    if response.get("ok").and_then(Value::as_bool) == Some(true) {
        return Ok(());
    }
    Err(response
        .get("message")
        .and_then(Value::as_str)
        .unwrap_or("E_AEP_OP: semantic operation failed")
        .to_string())
}

fn server_info() -> Value {
    json!({"name": SERVER_NAME, "version": env!("CARGO_PKG_VERSION")})
}

fn claims_modern(request: &Value) -> bool {
    if request.get("method").and_then(Value::as_str) == Some("server/discover") {
        return true;
    }
    request
        .pointer("/params/_meta")
        .and_then(Value::as_object)
        .is_some_and(|meta| {
            meta.keys()
                .any(|key| key.starts_with("io.modelcontextprotocol/"))
        })
}

fn validate_modern_envelope(request: &Value) -> Result<(), Value> {
    let Some(meta) = request.pointer("/params/_meta").and_then(Value::as_object) else {
        return Err(error(
            request.get("id").cloned().unwrap_or(Value::Null),
            -32602,
            "Invalid params: modern MCP requests require params._meta",
            None,
        ));
    };
    let Some(version) = meta
        .get("io.modelcontextprotocol/protocolVersion")
        .and_then(Value::as_str)
    else {
        return Err(error(
            request.get("id").cloned().unwrap_or(Value::Null),
            -32602,
            "Invalid params: modern MCP metadata requires protocolVersion",
            None,
        ));
    };
    if version != MODERN_VERSION {
        return Err(error(
            request.get("id").cloned().unwrap_or(Value::Null),
            -32022,
            "Unsupported protocol version",
            Some(json!({"supported":[MODERN_VERSION],"requested":version})),
        ));
    }
    if !meta
        .get("io.modelcontextprotocol/clientCapabilities")
        .is_some_and(Value::is_object)
        || meta
            .get("io.modelcontextprotocol/clientInfo")
            .is_some_and(|value| {
                !value.is_object()
                    || value.get("name").and_then(Value::as_str).is_none()
                    || value.get("version").and_then(Value::as_str).is_none()
            })
    {
        return Err(error(
            request.get("id").cloned().unwrap_or(Value::Null),
            -32602,
            "Invalid params: malformed modern MCP metadata",
            None,
        ));
    }
    Ok(())
}

fn era_mismatch(id: Value, established: ProtocolEra, requested: ProtocolEra) -> Value {
    error(
        id,
        -32602,
        "Invalid params: protocol era does not match this STDIO connection",
        Some(json!({
            "established": match established {
                ProtocolEra::Legacy => "legacy",
                ProtocolEra::Modern => MODERN_VERSION,
                ProtocolEra::Undecided => "undecided",
            },
            "requested": match requested {
                ProtocolEra::Legacy => "legacy",
                ProtocolEra::Modern => MODERN_VERSION,
                ProtocolEra::Undecided => "undecided",
            }
        })),
    )
}

fn modernize_result(mut result: Value, modern: bool) -> Value {
    if !modern {
        return result;
    }
    if let Some(object) = result.as_object_mut() {
        object.insert("resultType".to_string(), json!("complete"));
        let meta = object
            .entry("_meta".to_string())
            .or_insert_with(|| json!({}));
        if let Some(meta) = meta.as_object_mut() {
            meta.insert(
                "io.modelcontextprotocol/serverInfo".to_string(),
                server_info(),
            );
        }
    }
    result
}

fn success(id: Value, result: Value, modern: bool) -> Value {
    json!({"jsonrpc":"2.0", "id":id, "result":modernize_result(result, modern)})
}

fn error(id: Value, code: i64, message: impl Into<String>, data: Option<Value>) -> Value {
    let mut body = json!({"code":code, "message":message.into()});
    if let Some(data) = data {
        body["data"] = data;
    }
    json!({"jsonrpc":"2.0", "id":id, "error":body})
}

fn compact_schema(value: &mut Value) {
    match value {
        Value::Object(object) => {
            object.remove("$schema");
            object.remove("description");
            for child in object.values_mut() {
                compact_schema(child);
            }
        }
        Value::Array(values) => {
            for child in values {
                compact_schema(child);
            }
        }
        _ => {}
    }
}

fn tool_definition(name: &str, compact: bool) -> Option<Value> {
    let spec = aep::lookup(name)?;
    if spec.gate.is_some_and(|gate| !aep::gate_enabled(gate)) {
        return None;
    }
    let mut input_schema = aep::operation_input_schema(spec);
    if name != "begin_transaction" {
        let object = input_schema.as_object_mut()?;
        object
            .get_mut("properties")?
            .as_object_mut()?
            .insert(
                "transaction_id".to_string(),
                json!({"type":"string","pattern":"^tx_[A-Za-z0-9_]+$","description":"Explicit ALVA transaction handle returned by begin_transaction."}),
            );
        object
            .get_mut("required")?
            .as_array_mut()?
            .insert(0, json!("transaction_id"));
    }
    if name == "stage_and_check" {
        input_schema["properties"]["operation"] = json!({
            "type": "string",
            "enum": MCP_STAGE_MUTATIONS,
            "description": "Exposed mutation to stage before bounded diff and check."
        });
    }
    let read_only = spec.effects == "inspection";
    let destructive = name == "commit_transaction";
    let description = if compact {
        format!("ALVA {}: {}.", spec.effects, name.replace('_', " "))
    } else {
        format!("ALVA semantic operation. Example: {}", spec.example)
    };
    if compact {
        compact_schema(&mut input_schema);
    }
    Some(json!({
        "name": name,
        "description": description,
        "inputSchema": input_schema,
        "annotations": {
            "readOnlyHint": read_only,
            "destructiveHint": destructive,
            "openWorldHint": false
        }
    }))
}

fn list_tools(modern: bool) -> Value {
    let tools: Vec<Value> = MCP_TOOLS
        .iter()
        .filter_map(|name| tool_definition(name, modern))
        .collect();
    let surface_hash = if modern {
        use sha2::{Digest, Sha256};
        Some(format!(
            "{:x}",
            Sha256::digest(serde_json::to_vec(&tools).unwrap_or_default())
        ))
    } else {
        None
    };
    let mut result = json!({"tools":tools});
    if modern {
        result["ttlMs"] = json!(3_600_000);
        result["cacheScope"] = json!("private");
        result["toolSurfaceHash"] = json!(surface_hash.unwrap_or_default());
        result["schemaProfile"] = json!("compact-v1");
    }
    result
}

fn call_result(value: Value, is_error: bool, modern: bool) -> Value {
    let text = if modern {
        if is_error {
            "ALVA tool call failed; see structuredContent.".to_string()
        } else {
            "ALVA tool call completed; see structuredContent.".to_string()
        }
    } else {
        // Legacy clients may not expose structuredContent, so preserve the
        // complete JSON text fallback for the legacy protocol era.
        serde_json::to_string(&value).unwrap_or_else(|_| "null".to_string())
    };
    json!({
        "content":[{"type":"text","text":text}],
        "structuredContent":value,
        "isError":is_error
    })
}

fn dispatch(
    request: &Value,
    gateway: &mut Gateway,
    protocol_era: &mut ProtocolEra,
) -> Option<Value> {
    let id = request.get("id").cloned().unwrap_or(Value::Null);
    let method = match request.get("method").and_then(Value::as_str) {
        Some(method) => method,
        None => return Some(error(id, -32600, "Invalid Request", None)),
    };
    // JSON-RPC notifications never receive a response. Era selection is made
    // by the opening request, not by follow-up notifications.
    request.get("id")?;
    let modern = claims_modern(request);
    let requested_era = if modern {
        ProtocolEra::Modern
    } else {
        ProtocolEra::Legacy
    };
    if modern {
        if let Err(response) = validate_modern_envelope(request) {
            return Some(response);
        }
    }
    if *protocol_era != ProtocolEra::Undecided && *protocol_era != requested_era {
        return Some(era_mismatch(id, *protocol_era, requested_era));
    }
    if *protocol_era == ProtocolEra::Undecided {
        *protocol_era = requested_era;
    }
    match method {
        "server/discover" => Some(success(
            id,
            json!({
                "supportedVersions":[MODERN_VERSION],
                "capabilities":{"tools":{"listChanged":false}},
                "ttlMs":0,
                "cacheScope":"private"
            }),
            true,
        )),
        "initialize" => {
            let requested = request
                .pointer("/params/protocolVersion")
                .and_then(Value::as_str)
                .unwrap_or(LEGACY_VERSION);
            let selected = if requested.starts_with("2024-") || requested.starts_with("2025-") {
                requested
            } else {
                LEGACY_VERSION
            };
            Some(success(
                id,
                json!({
                    "protocolVersion":selected,
                    "capabilities":{"tools":{"listChanged":false}},
                    "serverInfo":server_info(),
                    "instructions":"Use begin_transaction first, then pass its transaction_id to every ALVA semantic tool."
                }),
                false,
            ))
        }
        "tools/list" => Some(success(id, list_tools(modern), modern)),
        "tools/call" => {
            let name = match request.pointer("/params/name").and_then(Value::as_str) {
                Some(name) => name,
                None => {
                    return Some(error(
                        id,
                        -32602,
                        "Invalid params: tool name is required",
                        None,
                    ))
                }
            };
            let arguments = request
                .pointer("/params/arguments")
                .cloned()
                .unwrap_or_else(|| json!({}));
            let result = match gateway.call_tool(name, &arguments) {
                Ok(value) => call_result(value, false, modern),
                Err(message) => call_result(json!({"error":message}), true, modern),
            };
            Some(success(id, result, modern))
        }
        _ => Some(error(
            id,
            -32601,
            "Method not found",
            Some(json!({"method":method})),
        )),
    }
}

pub fn cmd_mcp() -> i32 {
    let stdin = std::io::stdin();
    let stdout = std::io::stdout();
    let mut output = BufWriter::new(stdout.lock());
    let mut gateway = Gateway::default();
    let mut protocol_era = ProtocolEra::default();
    for line in stdin.lock().lines() {
        let line = match line {
            Ok(line) => line,
            Err(error) => {
                eprintln!("ALVA MCP stdin error: {error}");
                break;
            }
        };
        if line.trim().is_empty() {
            continue;
        }
        let response = match serde_json::from_str::<Value>(&line) {
            Ok(request) => dispatch(&request, &mut gateway, &mut protocol_era),
            Err(parse_error) => Some(error(
                Value::Null,
                -32700,
                "Parse error",
                Some(json!({"detail":parse_error.to_string()})),
            )),
        };
        if let Some(response) = response {
            if serde_json::to_writer(&mut output, &response).is_err()
                || output.write_all(b"\n").is_err()
                || output.flush().is_err()
            {
                eprintln!("ALVA MCP stdout closed");
                return 1;
            }
        }
    }
    0
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tool_list_is_deterministic_and_hides_gated_a1() {
        let first = list_tools(false);
        let second = list_tools(false);
        assert_eq!(first, second);
        let names: Vec<&str> = first["tools"]
            .as_array()
            .unwrap()
            .iter()
            .filter_map(|tool| tool["name"].as_str())
            .collect();
        assert!(!names.contains(&"inspect_change_impact"));
        assert!(!names.contains(&"inspect_schema_gaps"));
        assert!(names.contains(&"change_field"));
    }

    #[test]
    fn modern_results_have_required_wire_fields() {
        let result = modernize_result(json!({"tools":[]}), true);
        assert_eq!(result["resultType"], "complete");
        assert_eq!(
            result["_meta"]["io.modelcontextprotocol/serverInfo"]["name"],
            SERVER_NAME
        );
    }

    #[test]
    fn registry_schema_golden_digest() {
        use sha2::{Digest, Sha256};
        let encoded = serde_json::to_vec(&list_tools(false)).unwrap();
        let digest = format!("{:x}", Sha256::digest(encoded));
        assert_eq!(
            digest,
            "eda671b86c48f0b99da934e2b1558e0571f72dff779ac58495276548185851ee"
        );
    }

    #[test]
    fn construction_schema_advertises_dynamic_typed_children() {
        let tool = tool_definition("construct_expression", false).unwrap();
        assert!(tool["inputSchema"]["additionalProperties"].is_object());
        assert!(tool["inputSchema"]["properties"]
            .get("...children")
            .is_none());
    }

    #[test]
    fn modern_tool_surface_is_compact_and_fingerprinted() {
        let legacy = list_tools(false);
        let modern = list_tools(true);
        let legacy_bytes = serde_json::to_vec(&legacy).unwrap().len();
        let modern_bytes = serde_json::to_vec(&modern).unwrap().len();

        assert!(modern_bytes < legacy_bytes * 3 / 4);
        assert_eq!(modern["schemaProfile"], "compact-v1");
        assert_eq!(modern["toolSurfaceHash"].as_str().unwrap().len(), 64);
        assert!(!modern.to_string().contains("Example:"));
        for tool in modern["tools"].as_array().unwrap() {
            assert!(!tool["inputSchema"].to_string().contains("\"description\""));
        }
    }

    #[test]
    fn modern_call_results_do_not_duplicate_structured_payload_as_text() {
        let value = json!({"revision":"a".repeat(64),"diagnostics":[1,2,3]});
        let modern = call_result(value.clone(), false, true);
        let legacy = call_result(value.clone(), false, false);

        assert_eq!(modern["structuredContent"], value);
        assert_ne!(
            modern["content"][0]["text"],
            serde_json::to_string(&value).unwrap()
        );
        assert_eq!(
            legacy["content"][0]["text"],
            serde_json::to_string(&value).unwrap()
        );
    }
}
