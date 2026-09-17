use std::io::{self, Read, Write};

use json_patch::Patch;
use serde_json::Value;

const MAX_INPUT_BYTES: u64 = 1024 * 1024;

fn field<'a>(request: &'a Value, name: &str) -> Result<&'a Value, String> {
    request
        .as_object()
        .and_then(|object| object.get(name))
        .ok_or_else(|| format!("json.patch.reference: missing field: {name}"))
}

fn string_field<'a>(request: &'a Value, name: &str) -> Result<&'a str, String> {
    field(request, name)?
        .as_str()
        .ok_or_else(|| format!("json.patch.reference: field must be a string: {name}"))
}

fn run() -> Result<(), String> {
    let mut input = Vec::new();
    io::stdin()
        .take(MAX_INPUT_BYTES + 1)
        .read_to_end(&mut input)
        .map_err(|error| format!("io.read-stdin: {error}"))?;
    if input.len() as u64 > MAX_INPUT_BYTES {
        return Err(format!(
            "io.read-stdin: input exceeds {MAX_INPUT_BYTES} byte limit"
        ));
    }
    let request: Value =
        serde_json::from_slice(&input).map_err(|error| format!("json.patch.reference: {error}"))?;
    let mode = string_field(&request, "mode")?;
    let document = field(&request, "doc")?.clone();
    let output = match mode {
        "pointer" => {
            let pointer = string_field(&request, "pointer")?;
            document
                .pointer(pointer)
                .cloned()
                .ok_or_else(|| "json.pointer.reference: target does not exist".to_string())?
        }
        "patch" => {
            let patch: Patch = serde_json::from_value(field(&request, "patch")?.clone())
                .map_err(|error| format!("json.patch.reference: {error}"))?;
            let mut result = document;
            // `patch` is fixed before measurement: unlike `patch_unsafe`, it rolls
            // back its in-memory document on an operation failure. That matches the
            // component's all-or-error external contract without moving work into
            // the benchmark driver.
            json_patch::patch(&mut result, &patch)
                .map_err(|error| format!("json.patch.reference: {error}"))?;
            result
        }
        _ => return Err("json.patch.reference: mode must be pointer or patch".to_string()),
    };
    let encoded = serde_json::to_vec(&output)
        .map_err(|error| format!("json.patch.reference: {error}"))?;
    io::stdout()
        .write_all(&encoded)
        .and_then(|_| io::stdout().flush())
        .map_err(|error| format!("io.write-stdout: {error}"))
}

fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        std::process::exit(1);
    }
}
