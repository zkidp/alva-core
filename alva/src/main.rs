mod aep;
mod air;
mod ast;
mod capability;
mod check;
mod codegen;
mod construction;
mod diag;
mod manifest;
mod mcp;
mod project;
mod s_expr;

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::process::Command;

struct CliArgs {
    file: Option<String>,
    json: bool,
    target: String,
    run_tests: bool,
    run_benches: bool,
    release: bool,
    out_dir: String,
}

fn main() {
    // 不再使用超大 worker 线程栈：dev profile 的 opt-level=1 把巨型 match
    // 函数的栈帧压回几百字节，默认最大 AST 深度（512）在默认线程栈内可承受。
    std::process::exit(run());
}

fn run() -> i32 {
    let args: Vec<String> = std::env::args().collect();
    if args.len() == 2 && matches!(args[1].as_str(), "--version" | "-V" | "version") {
        println!("alva {}", env!("CARGO_PKG_VERSION"));
        return 0;
    }
    if args.len() < 2 {
        usage();
        std::process::exit(2);
    }
    let rest = &args[2..];
    let code = match args[1].as_str() {
        "check" => cmd_check(rest),
        "build" => cmd_build(rest),
        "run" => cmd_run(rest),
        "manifest" => cmd_manifest(rest),
        "project" => cmd_project(rest),
        "impact" => cmd_impact(rest),
        "air" => cmd_air(rest),
        "edit" => cmd_edit(rest),
        "agent" => cmd_agent(rest),
        "mcp" => mcp::cmd_mcp(),
        "hole" => cmd_hole(rest),
        "view" => cmd_view(rest),
        "capabilities" => cmd_capabilities(rest),
        "doctor" => cmd_doctor(rest),
        other => {
            eprintln!("unknown command: {other}");
            usage();
            2
        }
    };
    code
}

fn probe_command(program: &str, arguments: &[&str]) -> Result<String, String> {
    let output = Command::new(program)
        .args(arguments)
        .output()
        .map_err(|e| e.to_string())?;
    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).trim().to_string());
    }
    Ok(String::from_utf8_lossy(&output.stdout)
        .lines()
        .next()
        .unwrap_or("")
        .trim()
        .to_string())
}

fn cmd_doctor(rest: &[String]) -> i32 {
    if !rest.is_empty() {
        eprintln!("usage: alva doctor");
        return 2;
    }

    println!("ALVA compiler      OK (alva {})", env!("CARGO_PKG_VERSION"));

    let rust_ok = match probe_command("rustc", &["--version"]) {
        Ok(version) => {
            println!("Rust toolchain     OK ({version})");
            true
        }
        Err(_) => {
            println!("Rust toolchain     MISSING (required for native build/run)");
            false
        }
    };

    let cargo_ok = match probe_command("cargo", &["--version"]) {
        Ok(version) => {
            println!("Cargo              OK ({version})");
            true
        }
        Err(_) => {
            println!("Cargo              MISSING (required for native build/run)");
            false
        }
    };

    let wasm_ok = Command::new("rustup")
        .args(["target", "list", "--installed"])
        .output()
        .ok()
        .filter(|output| output.status.success())
        .map(|output| {
            String::from_utf8_lossy(&output.stdout)
                .lines()
                .any(|line| line.trim() == "wasm32-wasip1")
        })
        .unwrap_or(false);
    if wasm_ok {
        println!("WASM target        OK (wasm32-wasip1)");
    } else {
        println!("WASM target        MISSING (optional; rustup target add wasm32-wasip1)");
    }

    if rust_ok && cargo_ok {
        0
    } else {
        1
    }
}

/// Offline capability catalog probe interface (compiler-owned; not an AEP
/// surface). `alva capabilities describe <name>` and
/// `alva capabilities list [--category builtin|operator]`.
fn cmd_capabilities(rest: &[String]) -> i32 {
    match rest.first().map(|s| s.as_str()) {
        Some("describe") => {
            let name = rest.get(1).map(|s| s.as_str()).unwrap_or("");
            if name.is_empty() {
                eprintln!("usage: alva capabilities describe <name>");
                return 2;
            }
            match capability::resolve_capability(name) {
                capability::CapabilityOutcome::Supported { cap: c, mapping } => {
                    let mapping_kind = match mapping {
                        capability::MappingKind::Canonical => "canonical",
                        capability::MappingKind::Alias => "alias",
                    };
                    let aliases = c
                        .aliases
                        .iter()
                        .map(|a| format!("\"{a}\""))
                        .collect::<Vec<_>>()
                        .join(",");
                    println!(
                        "{{\"name\":{},\"supported\":true,\"canonical\":{},\"category\":{},\"aliases\":[{}],\"arity\":{},\"mapping_kind\":{}}}",
                        json_str(name),
                        json_str(c.canonical),
                        json_str(c.category.as_str()),
                        aliases,
                        json_str(c.arity),
                        json_str(mapping_kind)
                    );
                }
                capability::CapabilityOutcome::Unsupported {
                    canonical_alternative,
                    supported_alternatives,
                } => {
                    let alts = supported_alternatives
                        .iter()
                        .map(|a| format!("\"{a}\""))
                        .collect::<Vec<_>>()
                        .join(",");
                    match canonical_alternative {
                        Some(canonical) => println!(
                            "{{\"name\":{},\"supported\":false,\"canonical_alternative\":{},\"mapping_kind\":\"declared_synonym\",\"declared_alternatives\":[{}]}}",
                            json_str(name),
                            json_str(canonical),
                            alts
                        ),
                        None => println!(
                            "{{\"name\":{},\"supported\":false,\"canonical_alternative\":null,\"mapping_kind\":null,\"declared_alternatives\":[{}]}}",
                            json_str(name),
                            alts
                        ),
                    }
                }
            }
            0
        }
        Some("list") => {
            let cat = rest
                .iter()
                .position(|a| a == "--category")
                .and_then(|i| rest.get(i + 1))
                .map(|s| s.as_str());
            let cat = match cat {
                Some("builtin") => Some(capability::CapCategory::Builtin),
                Some("operator") => Some(capability::CapCategory::Operator),
                Some("all") | None => None,
                _ => {
                    eprintln!("unknown category (builtin|operator|all)");
                    return 2;
                }
            };
            let caps = capability::list_capabilities(cat);
            let items = caps
                .iter()
                .map(|c| format!("\"{}\"", c.canonical))
                .collect::<Vec<_>>()
                .join(",");
            println!("{{\"capabilities\":[{}]}}", items);
            0
        }
        _ => {
            eprintln!(
                "usage: alva capabilities describe <name> | list [--category builtin|operator]"
            );
            2
        }
    }
}

fn cmd_project(rest: &[String]) -> i32 {
    if rest.is_empty() {
        usage();
        return 2;
    }
    let a = parse_args(&rest[1..]);
    let file = match a.file {
        Some(f) => f,
        None => {
            usage();
            return 2;
        }
    };
    let proj = match project::load_project(Path::new(&file)) {
        Ok(p) => p,
        Err(e) => {
            eprintln!("error: {e}");
            return 1;
        }
    };
    let project_dir = Path::new(&file)
        .parent()
        .unwrap_or(Path::new("."))
        .to_path_buf();
    // 权威存储优先：存在 alva-air/CURRENT 时，check/build 直接消费 AIR。
    let has_authoritative = project_dir
        .join(air::AIR_STORE_DIR)
        .join("current")
        .exists();
    let check_loaded =
        |proj: &project::Project| -> Result<Vec<project::LoadedModule>, Vec<diag::Diag>> {
            if has_authoritative {
                let modules = project::load_modules_air(proj, &project_dir)?;
                project::check_project_loaded(modules)
            } else {
                project::check_project(proj)
            }
        };
    match rest[0].as_str() {
        "check" => match check_loaded(&proj) {
            Ok(modules) => {
                if !a.json {
                    println!(
                        "ok: {} modules checked (project {})",
                        modules.len(),
                        proj.name
                    );
                }
                0
            }
            Err(ds) => {
                print_diags(&ds, a.json);
                1
            }
        },
        "build" => {
            let modules = match check_loaded(&proj) {
                Ok(m) => m,
                Err(ds) => {
                    print_diags(&ds, a.json);
                    return 1;
                }
            };
            let out_dir = PathBuf::from(&a.out_dir);
            match project::codegen_project(&proj, &modules, &out_dir) {
                Ok(root) => {
                    // 写 manifest 文件（供 impact 使用）
                    let mdir = out_dir.join("manifests");
                    std::fs::create_dir_all(&mdir).ok();
                    for lm in &modules {
                        let san = lm.name.replace(['.', '-'], "_");
                        let m = manifest::generate(&lm.module);
                        std::fs::write(mdir.join(format!("{san}.json")), m).ok();
                    }
                    let status = Command::new("cargo")
                        .current_dir(&root)
                        .arg("build")
                        .status()
                        .map(|s| s.success())
                        .unwrap_or(false);
                    if status {
                        if a.run_tests {
                            let t = Command::new("cargo")
                                .current_dir(&root)
                                .arg("test")
                                .status()
                                .map(|s| s.success())
                                .unwrap_or(false);
                            if !t {
                                return 1;
                            }
                        }
                        println!("project built: {}", root.display());
                        0
                    } else {
                        1
                    }
                }
                Err(e) => {
                    eprintln!("error: {e}");
                    1
                }
            }
        }
        other => {
            eprintln!("unknown project command: {other}");
            2
        }
    }
}

fn cmd_impact(rest: &[String]) -> i32 {
    let mut base = None;
    let mut head = None;
    let mut i = 0;
    while i < rest.len() {
        match rest[i].as_str() {
            "--base" => {
                i += 1;
                if i < rest.len() {
                    base = Some(rest[i].clone());
                }
            }
            "--head" => {
                i += 1;
                if i < rest.len() {
                    head = Some(rest[i].clone());
                }
            }
            _ => {}
        }
        i += 1;
    }
    match (base, head) {
        (Some(b), Some(h)) => match project::impact(Path::new(&b), Path::new(&h)) {
            Ok(()) => 0,
            Err(e) => {
                eprintln!("error: {e}");
                1
            }
        },
        _ => {
            eprintln!("usage: alva impact --base <dir> --head <dir>");
            2
        }
    }
}

// ---------------------------------------------------------------------------
// Minimal JSON (protocol input for the AEP edit command)
// ---------------------------------------------------------------------------

#[derive(Clone, Debug)]
enum Json {
    Null,
    Bool(bool),
    Num(f64),
    Str(String),
    Arr(Vec<Json>),
    Obj(BTreeMap<String, Json>),
}

impl Json {
    fn get(&self, key: &str) -> Option<&Json> {
        match self {
            Json::Obj(m) => m.get(key),
            _ => None,
        }
    }
    fn as_str(&self) -> Option<&str> {
        match self {
            Json::Str(s) => Some(s),
            _ => None,
        }
    }
}

fn parse_json(input: &str) -> Result<Json, String> {
    let mut pos = 0;
    fn skip(input: &str, pos: &mut usize) {
        while *pos < input.len() && input.as_bytes()[*pos].is_ascii_whitespace() {
            *pos += 1;
        }
    }
    fn value(input: &str, pos: &mut usize) -> Result<Json, String> {
        skip(input, pos);
        let c = input[*pos..].chars().next().ok_or("unexpected end")?;
        match c {
            '{' => {
                *pos += 1;
                let mut m = BTreeMap::new();
                loop {
                    skip(input, pos);
                    if input[*pos..].starts_with('}') {
                        *pos += 1;
                        break;
                    }
                    let key = match value(input, pos)? {
                        Json::Str(s) => s,
                        _ => return Err("object key must be string".to_string()),
                    };
                    skip(input, pos);
                    if !input[*pos..].starts_with(':') {
                        return Err("expected ':'".to_string());
                    }
                    *pos += 1;
                    let v = value(input, pos)?;
                    m.insert(key, v);
                    skip(input, pos);
                    if input[*pos..].starts_with(',') {
                        *pos += 1;
                    }
                }
                Ok(Json::Obj(m))
            }
            '[' => {
                *pos += 1;
                let mut arr = Vec::new();
                loop {
                    skip(input, pos);
                    if input[*pos..].starts_with(']') {
                        *pos += 1;
                        break;
                    }
                    arr.push(value(input, pos)?);
                    skip(input, pos);
                    if input[*pos..].starts_with(',') {
                        *pos += 1;
                    }
                }
                Ok(Json::Arr(arr))
            }
            '"' => {
                *pos += 1;
                let mut s = String::new();
                let mut chars = input[*pos..].chars();
                loop {
                    match chars.next() {
                        Some('"') => break,
                        Some('\\') => match chars.next() {
                            Some('n') => s.push('\n'),
                            Some('t') => s.push('\t'),
                            Some('r') => s.push('\r'),
                            Some('"') => s.push('"'),
                            Some('\\') => s.push('\\'),
                            Some(other) => s.push(other),
                            None => return Err("bad escape".to_string()),
                        },
                        Some(other) => s.push(other),
                        None => return Err("unterminated string".to_string()),
                    }
                }
                let consumed = input.len() - chars.as_str().len() - *pos;
                *pos += consumed;
                Ok(Json::Str(s))
            }
            't' => {
                *pos += 4;
                Ok(Json::Bool(true))
            }
            'f' => {
                *pos += 5;
                Ok(Json::Bool(false))
            }
            'n' => {
                *pos += 4;
                Ok(Json::Null)
            }
            '-' | '0'..='9' => {
                let start = *pos;
                while *pos < input.len()
                    && (input.as_bytes()[*pos].is_ascii_digit()
                        || input.as_bytes()[*pos] == b'.'
                        || input.as_bytes()[*pos] == b'-'
                        || input.as_bytes()[*pos] == b'e'
                        || input.as_bytes()[*pos] == b'E'
                        || input.as_bytes()[*pos] == b'+')
                {
                    *pos += 1;
                }
                input[start..*pos]
                    .parse::<f64>()
                    .map(Json::Num)
                    .map_err(|e| format!("bad number: {e}"))
            }
            _ => Err(format!("unexpected char {c}")),
        }
    }
    let v = value(input, &mut pos)?;
    skip(input, &mut pos);
    if pos != input.len() {
        return Err("trailing input".to_string());
    }
    Ok(v)
}

fn json_str(s: &str) -> String {
    format!("\"{}\"", diag::json_escape(s))
}

/// 把内部 Json 树序列化为 JSON 字符串（响应体用）。
fn render_json(v: &Json) -> String {
    match v {
        Json::Null => "null".to_string(),
        Json::Bool(b) => b.to_string(),
        Json::Num(n) => format!("{n}"),
        Json::Str(s) => json_str(s),
        Json::Arr(items) => {
            let parts: Vec<String> = items.iter().map(render_json).collect();
            format!("[{}]", parts.join(","))
        }
        Json::Obj(m) => {
            let parts: Vec<String> = m
                .iter()
                .map(|(k, v)| format!("{}:{}", json_str(k), render_json(v)))
                .collect();
            format!("{{{}}}", parts.join(","))
        }
    }
}

// ---------------------------------------------------------------------------
// AIR commands
// ---------------------------------------------------------------------------

fn project_to_air(
    project: &project::Project,
) -> Result<(air::AirGraph, BTreeMap<String, PathBuf>), String> {
    let modules = project::load_modules(project).map_err(|ds| {
        format!(
            "{} module error(s) while loading project",
            ds.iter().filter(|d| d.severity == "error").count()
        )
    })?;
    let mut g = air::AirGraph::new();
    let mut paths = BTreeMap::new();
    for lm in &modules {
        let mg = air::air_from_module(&lm.module);
        g.nodes.extend(mg.nodes);
        g.heads.extend(mg.heads);
        g.module_entities.extend(mg.module_entities);
        if let Some((_, p)) = project.modules.iter().find(|(n, _)| n == &lm.name) {
            paths.insert(lm.name.clone(), p.clone());
        }
    }
    Ok((g, paths))
}

fn write_air_file(path: &Path, g: &air::AirGraph) -> Result<(), String> {
    std::fs::write(path, air::graph_to_bytes(g)).map_err(|e| e.to_string())
}

fn subgraph_for_root(g: &air::AirGraph, root: &str) -> air::AirGraph {
    let mut sub = air::AirGraph::new();
    let mut ids = vec![root.to_string()];
    while let Some(id) = ids.pop() {
        if sub.nodes.contains_key(&id) {
            continue;
        }
        if let Some(n) = g.get(&id) {
            sub.nodes.insert(id.clone(), n.clone());
            for children in n.slots.values() {
                for c in children {
                    ids.push(c.clone());
                }
            }
        }
    }
    for (entity, head) in &g.heads {
        if head == root {
            sub.heads.insert(entity.clone(), head.clone());
        }
    }
    sub.module_entities.push(
        sub.heads
            .iter()
            .find(|(e, _)| e.starts_with("module:"))
            .map(|(e, _)| e.clone())
            .unwrap_or_default(),
    );
    sub
}

fn cmd_air(rest: &[String]) -> i32 {
    let sub = rest.first().map(|s| s.as_str()).unwrap_or("");
    match sub {
        "export" => {
            let file = rest.get(1).map(|s| s.as_str()).unwrap_or("");
            if file.is_empty() {
                eprintln!("usage: alva air export <project.toml> [--out-dir <dir>]");
                return 2;
            }
            let out_dir = flag_value(rest, "--out-dir").unwrap_or_else(|| "out/air".to_string());
            let authoritative = rest.iter().any(|a| a == "--authoritative");
            let proj = match project::load_project(Path::new(file)) {
                Ok(p) => p,
                Err(e) => {
                    eprintln!("error: {e}");
                    return 1;
                }
            };
            let (g, paths) = match project_to_air(&proj) {
                Ok(x) => x,
                Err(e) => {
                    eprintln!("error: {e}");
                    return 1;
                }
            };
            if let Err(e) = std::fs::create_dir_all(&out_dir) {
                eprintln!("error: {e}");
                return 1;
            }
            let out = PathBuf::from(&out_dir);
            let _ = &paths;
            if authoritative {
                let project_dir = Path::new(file).parent().unwrap_or(Path::new("."));
                match air::write_authoritative(project_dir, &g, None) {
                    Ok(gen) => println!(
                        "authoritative AIR generation {gen} written to {}",
                        project_dir.join(air::AIR_STORE_DIR).display()
                    ),
                    Err(e) => {
                        eprintln!("error: {e}");
                        return 1;
                    }
                }
            }
            if let Err(e) = write_air_file(&out.join(format!("{}.air", proj.name)), &g) {
                eprintln!("error: {e}");
                return 1;
            }
            for entity in &g.module_entities {
                if let Some(head) = g.heads.get(entity) {
                    let name = entity.trim_start_matches("module:");
                    let sub = subgraph_for_root(&g, head);
                    let san = name.replace('.', "_");
                    if let Err(e) = write_air_file(&out.join(format!("{san}.air")), &sub) {
                        eprintln!("error: {e}");
                        return 1;
                    }
                    println!("{name} {head}");
                }
            }
            println!("air export written to {out_dir}");
            0
        }
        "verify" => {
            let file = rest.get(1).map(|s| s.as_str()).unwrap_or("");
            if file.is_empty() {
                eprintln!("usage: alva air verify <air-file>");
                return 2;
            }
            match read_air_verify(Path::new(file)) {
                Ok(g) => {
                    println!(
                        "ok: {} nodes, semantic hash {}",
                        g.nodes.len(),
                        g.semantic_hash()
                    );
                    0
                }
                Err(e) => {
                    eprintln!("FAIL: {e}");
                    1
                }
            }
        }
        "reachable" => {
            // E3 runner support: load the committed authoritative store and
            // print every reachable revision (module heads + descendants).
            // Used by the frozen churn classifier's SUPERSEDED category.
            let file = rest.get(1).map(|s| s.as_str()).unwrap_or("");
            if file.is_empty() {
                eprintln!("usage: alva air reachable <project.toml>");
                return 2;
            }
            let project_dir = Path::new(file).parent().unwrap_or(Path::new("."));
            match air::load_authoritative(project_dir) {
                Ok(g) => {
                    for rev in g.reachable() {
                        println!("{rev}");
                    }
                    0
                }
                Err(e) => {
                    eprintln!("error: {e}");
                    1
                }
            }
        }
        "import" => {
            let file = rest.get(1).map(|s| s.as_str()).unwrap_or("");
            if file.is_empty() {
                eprintln!("usage: alva air import <air-file> [--out-dir <dir>]");
                return 2;
            }
            let out_dir = flag_value(rest, "--out-dir");
            let g = match read_air_verify(Path::new(file)) {
                Ok(g) => g,
                Err(e) => {
                    eprintln!("FAIL: {e}");
                    return 1;
                }
            };
            for entity in &g.module_entities {
                if let Some(head) = g.heads.get(entity) {
                    let name = entity.trim_start_matches("module:");
                    let sexpr = air::module_to_sexpr(&g, head);
                    match &out_dir {
                        Some(dir) => {
                            std::fs::create_dir_all(dir).ok();
                            let p = PathBuf::from(dir).join(format!("{name}.alva"));
                            if let Err(e) = std::fs::write(&p, &sexpr) {
                                eprintln!("error: {e}");
                                return 1;
                            }
                            println!("wrote {}", p.display());
                        }
                        None => print!("{sexpr}"),
                    }
                }
            }
            0
        }
        "diff" => {
            let base = rest.get(1).map(|s| s.as_str()).unwrap_or("");
            let head = rest.get(2).map(|s| s.as_str()).unwrap_or("");
            if base.is_empty() || head.is_empty() {
                eprintln!("usage: alva air diff <base.air> <head.air>");
                return 2;
            }
            let bg = match air::graph_from_bytes(
                &std::fs::read(base)
                    .map_err(|e| e.to_string())
                    .unwrap_or_default(),
            ) {
                Ok(g) => g,
                Err(_) => {
                    eprintln!("cannot read base");
                    return 1;
                }
            };
            let hg = match air::graph_from_bytes(
                &std::fs::read(head)
                    .map_err(|e| e.to_string())
                    .unwrap_or_default(),
            ) {
                Ok(g) => g,
                Err(_) => {
                    eprintln!("cannot read head");
                    return 1;
                }
            };
            let report = air::diff_graphs(&bg, &hg);
            print!("{}", report.summary);
            0
        }
        "view" => {
            let file = rest.get(1).map(|s| s.as_str()).unwrap_or("");
            if file.is_empty() {
                eprintln!("usage: alva air view <air-file> [--budget N]");
                return 2;
            }
            let g = match read_air_verify(Path::new(file)) {
                Ok(g) => g,
                Err(e) => {
                    eprintln!("FAIL: {e}");
                    return 1;
                }
            };
            let budget = flag_value(rest, "--budget").and_then(|b| b.parse::<usize>().ok());
            println!("{}", air::graph_to_json(&g, budget));
            0
        }
        _ => {
            eprintln!("usage: alva air export|import|verify|diff|view ...");
            2
        }
    }
}

fn cmd_edit(_rest: &[String]) -> i32 {
    let mut session: Option<air::EditSession> = None;
    let mut real_dir = PathBuf::new();
    let mut base_graph: Option<air::AirGraph> = None;
    let mut code = 0;
    use std::io::BufRead;
    let stdin = std::io::stdin();
    for line in stdin.lock().lines() {
        let line = match line {
            Ok(l) => l,
            Err(_) => break,
        };
        if line.trim().is_empty() {
            continue;
        }
        let req = match parse_json(&line) {
            Ok(Json::Obj(_)) => parse_json(&line).unwrap(),
            Ok(other) => other,
            Err(e) => {
                println!("{}", json_resp(false, "null", &format!("bad JSON: {e}")));
                continue;
            }
        };
        let op = req.get("op").and_then(|v| v.as_str()).unwrap_or("");
        match op {
            "begin" => {
                let file = req.get("project").and_then(|v| v.as_str()).unwrap_or("");
                let base_hash = req.get("base_hash").and_then(|v| v.as_str()).unwrap_or("");
                let proj = match project::load_project(Path::new(file)) {
                    Ok(p) => p,
                    Err(e) => {
                        println!(
                            "{}",
                            json_resp(false, "null", &format!("cannot load project: {e}"))
                        );
                        continue;
                    }
                };
                let project_dir = Path::new(file).parent().unwrap_or(Path::new("."));
                let has_authoritative = project_dir
                    .join(air::AIR_STORE_DIR)
                    .join("current")
                    .exists();
                let (g, _paths) = if has_authoritative {
                    match air::load_authoritative(project_dir) {
                        Ok(g) => {
                            let mut paths = BTreeMap::new();
                            for (name, p) in &proj.modules {
                                paths.insert(name.clone(), p.clone());
                            }
                            (g, paths)
                        }
                        Err(e) => {
                            println!("{}", json_resp(false, "null", &e));
                            continue;
                        }
                    }
                } else {
                    match project_to_air(&proj) {
                        Ok(x) => x,
                        Err(e) => {
                            println!("{}", json_resp(false, "null", &e));
                            continue;
                        }
                    }
                };
                let actual = g.semantic_hash();
                if !base_hash.is_empty() && base_hash != actual {
                    println!(
                        "{}",
                        json_resp(
                            false,
                            "null",
                            &format!("base hash mismatch: expected {base_hash}, actual {actual}")
                        )
                    );
                    continue;
                }
                real_dir = file
                    .rsplit_once(['/', '\\'])
                    .map(|(d, _)| PathBuf::from(d))
                    .unwrap_or_else(|| PathBuf::from("."));
                base_graph = Some(g.clone());
                session = Some(air::EditSession::begin(g, actual.clone()));
                let mut mods = Vec::new();
                if let Some(s) = &session {
                    for entity in &s.graph.module_entities {
                        if let Some(head) = s.graph.heads.get(entity) {
                            mods.push(format!("{entity}:{head}"));
                        }
                    }
                }
                let modules_json: Vec<String> = mods
                    .iter()
                    .map(|m| {
                        let (entity, head) = m.rsplit_once(':').unwrap_or((m, ""));
                        format!("{}:{}", json_str(entity), json_str(head))
                    })
                    .collect();
                println!(
                    "{}",
                    json_resp(
                        true,
                        &format!(
                            "{{\"base_hash\":{},\"modules\":{{{}}}}}",
                            json_str(&actual),
                            modules_json.join(",")
                        ),
                        &format!("begin ok, base hash {actual}")
                    )
                );
            }
            "create_node" => {
                let s = match session.as_mut() {
                    Some(s) => s,
                    None => {
                        println!("{}", json_resp(false, "null", "no transaction"));
                        continue;
                    }
                };
                let kind = req
                    .get("kind")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string();
                let fields = json_fields(&req.get("fields"));
                let slots = json_slots(&req.get("slots"));
                match s.create_node(&kind, fields, slots) {
                    Ok(id) => println!(
                        "{}",
                        json_resp_ok(&format!("{{\"revision\":{}}}", json_str(&id)))
                    ),
                    Err(e) => println!("{}", json_resp(false, "null", &e)),
                }
            }
            "create_hole" => {
                let s = match session.as_mut() {
                    Some(s) => s,
                    None => {
                        println!("{}", json_resp(false, "null", "no transaction"));
                        continue;
                    }
                };
                let expected = req
                    .get("expected_type")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string();
                let effects = match req.get("allowed_effects") {
                    Some(Json::Arr(items)) => items
                        .iter()
                        .filter_map(|x| x.as_str().map(|s| s.to_string()))
                        .collect(),
                    _ => Vec::new(),
                };
                match s.create_hole(&expected, effects) {
                    Ok(id) => println!(
                        "{}",
                        json_resp_ok(&format!("{{\"revision\":{}}}", json_str(&id)))
                    ),
                    Err(e) => println!("{}", json_resp(false, "null", &e)),
                }
            }
            "replace_node" => {
                let s = match session.as_mut() {
                    Some(s) => s,
                    None => {
                        println!("{}", json_resp(false, "null", "no transaction"));
                        continue;
                    }
                };
                let target = req.get("target").and_then(|v| v.as_str()).unwrap_or("");
                let replacement = req
                    .get("replacement")
                    .and_then(|v| v.as_str())
                    .unwrap_or("");
                match s.replace_node(target, replacement) {
                    Ok(rev) => println!(
                        "{}",
                        json_resp_ok(&format!("{{\"new_revision\":{}}}", json_str(&rev)))
                    ),
                    Err(e) => println!("{}", json_resp(false, "null", &e)),
                }
            }
            "replace_slot" | "append_child" => {
                let s = match session.as_mut() {
                    Some(s) => s,
                    None => {
                        println!("{}", json_resp(false, "null", "no transaction"));
                        continue;
                    }
                };
                let parent = req.get("parent").and_then(|v| v.as_str()).unwrap_or("");
                let slot = req.get("slot").and_then(|v| v.as_str()).unwrap_or("");
                let child = req.get("child").and_then(|v| v.as_str()).unwrap_or("");
                let res = if op == "replace_slot" {
                    s.replace_slot(parent, slot, child)
                } else {
                    s.append_child(parent, slot, child)
                };
                match res {
                    Ok(rev) => println!(
                        "{}",
                        json_resp_ok(&format!("{{\"new_parent_revision\":{}}}", json_str(&rev)))
                    ),
                    Err(e) => println!("{}", json_resp(false, "null", &e)),
                }
            }
            "bind_symbol" => {
                let s = match session.as_mut() {
                    Some(s) => s,
                    None => {
                        println!("{}", json_resp(false, "null", "no transaction"));
                        continue;
                    }
                };
                let scope = req.get("scope").and_then(|v| v.as_str()).unwrap_or("");
                let name = req.get("name").and_then(|v| v.as_str()).unwrap_or("");
                let ty = req.get("type").and_then(|v| v.as_str()).unwrap_or("");
                let value = req.get("value").and_then(|v| v.as_str()).unwrap_or("");
                match s.bind_symbol(scope, name, ty, value) {
                    Ok(()) => println!("{}", json_resp_ok("{\"bound\":true}")),
                    Err(e) => println!("{}", json_resp(false, "null", &e)),
                }
            }
            "rename_symbol" => {
                let s = match session.as_mut() {
                    Some(s) => s,
                    None => {
                        println!("{}", json_resp(false, "null", "no transaction"));
                        continue;
                    }
                };
                let symbol = req.get("symbol").and_then(|v| v.as_str()).unwrap_or("");
                let new_name = req.get("new_name").and_then(|v| v.as_str()).unwrap_or("");
                match s.rename_symbol(symbol, new_name) {
                    Ok(()) => println!("{}", json_resp_ok("{\"renamed\":true}")),
                    Err(e) => println!("{}", json_resp(false, "null", &e)),
                }
            }
            "delete_entity" => {
                let s = match session.as_mut() {
                    Some(s) => s,
                    None => {
                        println!("{}", json_resp(false, "null", "no transaction"));
                        continue;
                    }
                };
                let id = req.get("id").and_then(|v| v.as_str()).unwrap_or("");
                match s.delete_entity(id) {
                    Ok(()) => println!(
                        "{}",
                        json_resp_ok(&format!("{{\"deleted\":{}}}", json_str(id)))
                    ),
                    Err(e) => println!("{}", json_resp(false, "null", &e)),
                }
            }
            "check" => {
                let s = match session.as_mut() {
                    Some(s) => s,
                    None => {
                        println!("{}", json_resp(false, "null", "no transaction"));
                        continue;
                    }
                };
                let errs = s.check();
                if errs.is_empty() {
                    println!("{}", json_resp_ok("{\"problems\":[]}"));
                } else {
                    println!(
                        "{}",
                        json_resp(
                            false,
                            &format!(
                                "{{\"problems\":[{}]}}",
                                errs.iter()
                                    .map(|e| json_str(e))
                                    .collect::<Vec<_>>()
                                    .join(",")
                            ),
                            &format!("check failed: {}", errs.join("; "))
                        )
                    );
                }
            }
            "snapshot" => {
                let s = match session.as_ref() {
                    Some(s) => s,
                    None => {
                        println!("{}", json_resp(false, "null", "no transaction"));
                        continue;
                    }
                };
                let path = req.get("path").and_then(|v| v.as_str()).unwrap_or("");
                if path.is_empty() {
                    println!("{}", json_resp(false, "null", "snapshot requires path"));
                    continue;
                }
                match write_air_file(Path::new(path), &s.graph) {
                    Ok(()) => println!(
                        "{}",
                        json_resp_ok(&format!("{{\"path\":{}}}", json_str(path)))
                    ),
                    Err(e) => println!("{}", json_resp(false, "null", &e)),
                }
            }
            "commit" => {
                let mut s = match session.take() {
                    Some(s) => s,
                    None => {
                        println!("{}", json_resp(false, "null", "no transaction"));
                        continue;
                    }
                };
                let errs = s.check();
                if !errs.is_empty() {
                    println!(
                        "{}",
                        json_resp(false, "null", &format!("check failed: {}", errs.join("; ")))
                    );
                    session = Some(s);
                    continue;
                }
                // full semantic check directly on the AIR-reconstructed modules
                let mut modules = Vec::new();
                let mut air_ok = true;
                for entity in &s.graph.module_entities {
                    match air::air_to_module(&s.graph, entity) {
                        Ok(m) => {
                            let name = entity.trim_start_matches("module:").to_string();
                            modules.push(project::LoadedModule {
                                name: name.clone(),
                                module: m,
                            });
                        }
                        Err(e) => {
                            air_ok = false;
                            println!(
                                "{}",
                                json_resp(false, "null", &format!("air->ast failed: {e}"))
                            );
                            break;
                        }
                    }
                }
                if !air_ok {
                    session = Some(s);
                    continue;
                }
                if let Err(ds) = project::check_project_loaded(modules) {
                    let msgs: Vec<String> = ds.iter().map(|d| d.render()).collect();
                    println!(
                        "{}",
                        json_resp(
                            false,
                            "null",
                            &format!("semantic check failed: {}", msgs.join(" | "))
                        )
                    );
                    session = Some(s);
                    continue;
                }
                // authoritative commit: generation + atomic CURRENT pointer
                let base = s.base_hash.clone();
                let gen = match air::write_authoritative(&real_dir, &s.graph, Some(&base)) {
                    Ok(g) => g,
                    Err(e) => {
                        println!(
                            "{}",
                            json_resp(
                                false,
                                "{\"diagnostics\":[{\"code\":\"E_AEP_CONFLICT\"}]}",
                                &format!("commit write failed: {e}")
                            )
                        );
                        session = Some(s);
                        continue;
                    }
                };
                let report = s.diff_vs_base(base_graph.as_ref().unwrap_or(&air::AirGraph::new()));
                let mut changed: Vec<String> = report.changed_modules.clone();
                for (m, f) in &report.changed_functions {
                    changed.push(format!("{m}.{f}"));
                }
                println!(
                    "{}",
                    json_resp(
                        true,
                        &format!(
                            "{{\"generation\":{},\"revision\":{},\"changed\":[{}]}}",
                            gen,
                            json_str(&s.graph.semantic_hash()),
                            changed
                                .iter()
                                .map(|c| json_str(c))
                                .collect::<Vec<_>>()
                                .join(",")
                        ),
                        &format!("committed generation {gen}; {}", report.summary.trim())
                    )
                );
                code = 0;
                break;
            }
            "abort" => {
                println!("{}", json_resp(true, "null", "aborted"));
                break;
            }
            other => {
                println!(
                    "{}",
                    json_resp(false, "null", &format!("unknown op {other}"))
                );
            }
        }
    }
    code
}

fn json_fields(v: &Option<&Json>) -> BTreeMap<String, air::Value> {
    let mut out = BTreeMap::new();
    if let Some(Json::Obj(m)) = v {
        for (k, val) in m {
            let av = match val {
                Json::Str(s) => air::Value::Str(s.clone()),
                Json::Num(n) => air::Value::Int(*n as i64),
                Json::Bool(b) => air::Value::Bool(*b),
                Json::Arr(items) => air::Value::Names(
                    items
                        .iter()
                        .filter_map(|x| x.as_str().map(|s| s.to_string()))
                        .collect(),
                ),
                _ => continue,
            };
            out.insert(k.clone(), av);
        }
    }
    out
}

fn json_slots(v: &Option<&Json>) -> BTreeMap<String, Vec<String>> {
    let mut out = BTreeMap::new();
    if let Some(Json::Obj(m)) = v {
        for (k, val) in m {
            if let Json::Arr(items) = val {
                out.insert(
                    k.clone(),
                    items
                        .iter()
                        .filter_map(|x| x.as_str().map(|s| s.to_string()))
                        .collect(),
                );
            }
        }
    }
    out
}

/// Structured protocol response: {"ok":bool,"result":{...},"message":"..."}
fn json_resp(ok: bool, result_obj: &str, message: &str) -> String {
    format!(
        "{{\"ok\":{},\"result\":{},\"message\":{}}}",
        ok,
        result_obj,
        json_str(message)
    )
}

fn json_resp_ok(result_obj: &str) -> String {
    json_resp(true, result_obj, "ok")
}

fn resolve_entity(g: &air::AirGraph, id_or_name: &str) -> Option<String> {
    if g.resolve_rev(id_or_name).is_some() {
        return Some(id_or_name.to_string());
    }
    for entity in &g.module_entities {
        if entity == id_or_name || entity.trim_start_matches("module:") == id_or_name {
            return Some(entity.clone());
        }
    }
    // functions by qualified name module.fn (module names contain dots, so
    // try the longest module-name prefix)
    for entity in &g.module_entities {
        let root_name = entity.trim_start_matches("module:");
        if let Some(rest) = id_or_name.strip_prefix(&format!("{root_name}.")) {
            if let Some(mn) = g.resolve(entity) {
                if let Some(ids) = mn.slots.get("functions") {
                    for id in ids {
                        if let Some(fn_) = g.get(id) {
                            if let Some(air::Value::Str(name)) = fn_.fields.get("name") {
                                if name == rest {
                                    return Some(id.clone());
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    None
}

fn cmd_hole(rest: &[String]) -> i32 {
    let sub = rest.first().map(|s| s.as_str()).unwrap_or("");
    let file = rest.get(1).map(|s| s.as_str()).unwrap_or("");
    if file.is_empty() {
        eprintln!("usage: alva hole inspect|candidates|fill <air-file> ...");
        return 2;
    }
    let g = match read_air_verify(Path::new(file)) {
        Ok(g) => g,
        Err(e) => {
            eprintln!("FAIL: {e}");
            return 1;
        }
    };
    match sub {
        "inspect" => {
            let hole = rest.get(2).map(|s| s.as_str()).unwrap_or("");
            let id = resolve_hole(&g, hole);
            match id {
                Some(id) => println!("{}", air::hole_constraints(&g, &id)),
                None => println!("{}", json_resp(false, "null", "hole not found")),
            }
            0
        }
        "candidates" => {
            let hole = rest.get(2).map(|s| s.as_str()).unwrap_or("");
            let id = resolve_hole(&g, hole);
            let cands = match id {
                Some(id) => air::hole_candidates(&g, &id),
                None => Vec::new(),
            };
            for c in cands {
                println!("{c}");
            }
            0
        }
        "fill" => {
            let hole = rest.get(2).map(|s| s.as_str()).unwrap_or("");
            let node = rest.get(3).map(|s| s.as_str()).unwrap_or("");
            if g.get(hole).map(|n| n.kind == "hole").unwrap_or(false) && g.get(node).is_some() {
                println!(
                    "{}",
                    json_resp(
                        true,
                        "null",
                        &format!("hole {hole} can be replaced by node {node} (via replace_slot/replace_node)")
                    )
                );
                0
            } else {
                println!("{}", json_resp(false, "null", "hole or node not found"));
                1
            }
        }
        _ => {
            eprintln!("usage: alva hole inspect|candidates|fill <air-file> ...");
            2
        }
    }
}

fn resolve_hole(g: &air::AirGraph, id_or_prefix: &str) -> Option<String> {
    if g.get(id_or_prefix)
        .map(|n| n.kind == "hole")
        .unwrap_or(false)
    {
        return Some(id_or_prefix.to_string());
    }
    for (id, n) in &g.nodes {
        if n.kind == "hole" && id.starts_with(id_or_prefix) {
            return Some(id.clone());
        }
    }
    None
}

fn cmd_view(rest: &[String]) -> i32 {
    let sub = rest.first().map(|s| s.as_str()).unwrap_or("");
    match sub {
        "impact" => {
            let base = rest.get(1).map(|s| s.as_str()).unwrap_or("");
            let head = rest.get(2).map(|s| s.as_str()).unwrap_or("");
            if base.is_empty() || head.is_empty() {
                eprintln!("usage: alva view impact <base.air> <head.air>");
                return 2;
            }
            let bg =
                air::graph_from_bytes(&std::fs::read(base).unwrap_or_default()).unwrap_or_default();
            let hg =
                air::graph_from_bytes(&std::fs::read(head).unwrap_or_default()).unwrap_or_default();
            print!("{}", air::diff_graphs(&bg, &hg).summary);
            0
        }
        _ => {
            let file = rest.get(1).map(|s| s.as_str()).unwrap_or("");
            let entity = rest.get(2).map(|s| s.as_str()).unwrap_or("");
            if file.is_empty() || entity.is_empty() {
                eprintln!("usage: alva view module|function|dependencies|callers|impact <air-file> <entity> [--budget N]");
                return 2;
            }
            let g = match read_air_verify(Path::new(file)) {
                Ok(g) => g,
                Err(e) => {
                    eprintln!("FAIL: {e}");
                    return 1;
                }
            };
            let id = match resolve_entity(&g, entity) {
                Some(id) => id,
                None => {
                    eprintln!("entity not found: {entity}");
                    return 1;
                }
            };
            let budget = flag_value(rest, "--budget").and_then(|b| b.parse::<usize>().ok());
            match sub {
                "module" => print!("{}", air::view_module(&g, &id, budget)),
                "function" => print!("{}", air::view_function(&g, &id)),
                "dependencies" => print!("{}", air::view_dependencies(&g, &id)),
                "callers" => print!("{}", air::view_callers(&g, &id)),
                _ => {
                    eprintln!("unknown view {sub}");
                    return 2;
                }
            }
            0
        }
    }
}

// ---------------------------------------------------------------------------
// v0.6 Agent Runtime: high-level tools over the AEP session.
// The agent never constructs raw AIR nodes or touches .alva text.
// ---------------------------------------------------------------------------

/// Whether a friendly position name is accepted for a node kind. This is the
/// single source of truth shared by the executor (`friendly_slot`) and every
/// discovery surface; advertised positions are always executable.
fn position_valid_for(kind: &str, position: &str) -> bool {
    match position {
        "value" => matches!(
            kind,
            "binding"
                | "as"
                | "field"
                | "record_field"
                | "ok"
                | "err"
                | "raise"
                | "try"
                | "not"
                | "len"
                | "keys"
                | "unwrap"
                | "errvalue"
                | "tostring"
                | "parseint"
                | "tobytes"
                | "isok"
                | "sort"
                | "urldecode"
                | "tohex"
                | "slice"
        ),
        "body" => matches!(
            kind,
            "binding" | "fold" | "loop" | "case" | "test" | "bench" | "contract"
        ),
        "cond" | "then" | "else" => kind == "if",
        "left" | "right" => matches!(
            kind,
            "binary"
                | "get"
                | "append"
                | "lookup"
                | "contains"
                | "veccontains"
                | "remove"
                | "split"
                | "concat"
                | "join"
                | "stripprefix"
                | "before"
                | "endswith"
                | "cteq"
        ),
        "step" => kind == "block",
        "arg" => kind == "call",
        "collection" | "predicate" => matches!(kind, "any" | "all" | "find"),
        "start" | "end" => kind == "slice",
        "init" | "cond2" => kind == "loop",
        "catch" => kind == "try",
        "scrutinee" => kind == "match",
        "range_start" | "range_end" | "acc_init" => kind == "fold",
        _ => false,
    }
}

/// Valid friendly positions for a node kind, derived from `aep::POSITION_NAMES`
/// and `position_valid_for`.
fn valid_positions(kind: &str) -> Vec<&'static str> {
    let mut out: Vec<&'static str> = aep::POSITION_NAMES
        .iter()
        .copied()
        .filter(|p| position_valid_for(kind, p))
        .collect();
    out.sort_unstable();
    out
}

fn friendly_slot(kind: &str, position: &str) -> Option<&'static str> {
    if !position_valid_for(kind, position) {
        return None;
    }
    Some(match position {
        "value" => "value",
        "body" => "body",
        "cond" | "cond2" => "cond",
        "then" => "then",
        "else" => "else",
        "left" => "left",
        "right" => "right",
        "step" => "steps",
        "arg" => "args",
        "collection" => "collection",
        "predicate" => "predicate",
        "start" => "start",
        "end" => "end",
        "init" => "init",
        "catch" => "catch",
        "scrutinee" => "scrutinee",
        "range_start" => "range_start",
        "range_end" => "range_end",
        "acc_init" => "acc_init",
        _ => unreachable!("position_valid_for guaranteed the position"),
    })
}

fn prim_value_for(name: &str, value: &str) -> Result<air::Value, String> {
    Ok(match name {
        "string" => air::Value::Str(value.to_string()),
        "bool" => air::Value::Bool(value == "true"),
        "i64" | "i32" | "i16" | "i8" | "u64" | "u32" | "u16" | "u8" => {
            air::Value::Int(value.parse().map_err(|_| "invalid int literal")?)
        }
        "f64" | "f32" => air::Value::Float(value.parse().map_err(|_| "invalid float literal")?),
        "bytes" => air::Value::Bytes(hex_bytes(value)?),
        "nil" => air::Value::Str("nil".to_string()),
        other => return Err(format!("create_literal: unsupported type {other}")),
    })
}

fn hex_bytes(s: &str) -> Result<Vec<u8>, String> {
    if !s.len().is_multiple_of(2) {
        return Err("hex literal must have even length".to_string());
    }
    let mut out = Vec::with_capacity(s.len() / 2);
    for i in (0..s.len()).step_by(2) {
        out.push(
            u8::from_str_radix(&s[i..i + 2], 16).map_err(|_| "invalid hex literal".to_string())?,
        );
    }
    Ok(out)
}

fn type_expr_for(name: &str, g: &mut air::AirGraph) -> Result<String, String> {
    let mut f = BTreeMap::new();
    if name.contains('<') {
        // vec<inner> / result<ok,err> handled minimally
        f.insert("shape".to_string(), air::Value::Str("named".to_string()));
        f.insert("name".to_string(), air::Value::Str(name.to_string()));
    } else if matches!(
        name,
        "string"
            | "bool"
            | "bytes"
            | "nil"
            | "i64"
            | "i32"
            | "i16"
            | "i8"
            | "u64"
            | "u32"
            | "u16"
            | "u8"
            | "f64"
            | "f32"
    ) {
        f.insert("shape".to_string(), air::Value::Str("prim".to_string()));
        f.insert("name".to_string(), air::Value::Str(name.to_string()));
    } else {
        f.insert("shape".to_string(), air::Value::Str("named".to_string()));
        f.insert("name".to_string(), air::Value::Str(name.to_string()));
    }
    Ok(g.add("type_expr", "", f, BTreeMap::new()))
}

fn cmd_agent(_rest: &[String]) -> i32 {
    let mut session: Option<air::EditSession> = None;
    let mut base_graph: Option<air::AirGraph> = None;
    let mut real_dir = PathBuf::new();
    let mut op_index = 0usize;
    use std::io::BufRead;
    let stdin = std::io::stdin();
    for line in stdin.lock().lines() {
        let line = match line {
            Ok(l) => l,
            Err(_) => break,
        };
        if line.trim().is_empty() {
            continue;
        }
        let req = match parse_json(&line) {
            Ok(v) => v,
            Err(e) => {
                println!(
                    "{}",
                    agent_resp(
                        None,
                        op_index,
                        false,
                        "null",
                        &format!("E_AEP_BAD_JSON: {e}"),
                        Vec::new()
                    )
                );
                op_index += 1;
                continue;
            }
        };
        op_index += 1;
        let request_id = req
            .get("request_id")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        let tool = req
            .get("tool")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        macro_rules! resp {
            ($ok:expr, $result:expr, $msg:expr) => {
                agent_resp(Some(&request_id), op_index, $ok, $result, $msg, Vec::new())
            };
        }
        macro_rules! need_session {
            () => {
                match session.as_mut() {
                    Some(s) => s,
                    None => {
                        let out = resp!(false, "null", "E_AEP_NO_TRANSACTION");
                        println!("{out}");
                        continue;
                    }
                }
            };
        }
        // RFC-0005: registry is the single source of truth — canonicalize
        // aliases before dispatch so introspection and execution agree.
        let canonical_tool: &str = aep::lookup(&tool).map(|s| s.name).unwrap_or(tool.as_str());
        let out = match canonical_tool {
            "inspect_project" => {
                let s = need_session!();
                let mods: Vec<String> = s
                    .graph
                    .module_entities
                    .iter()
                    .map(|m| {
                        let head = s.graph.heads.get(m).cloned().unwrap_or_default();
                        format!("{}:{}", json_str(m), json_str(&head))
                    })
                    .collect();
                resp!(
                    true,
                    &format!(
                        "{{\"project_revision\":{},\"modules\":{{{}}}}}",
                        json_str(&s.graph.semantic_hash()),
                        mods.join(",")
                    ),
                    "ok"
                )
            }
            "inspect_module" => {
                let s = need_session!();
                let name = req.get("name").and_then(|v| v.as_str()).unwrap_or("");
                match canonical_entity_rev(&s.graph, "inspect_module", "name", name, &["module"]) {
                    Err(Some((r, msg))) => resp!(false, &r, &msg),
                    Err(None) => resp!(false, "null", &not_found(&s.graph, name)),
                    Ok(entity) => match s.graph.resolve(&entity) {
                        Some(n) => {
                            let view = air::view_module(&s.graph, &n.revision, None);
                            resp!(
                                true,
                                &format!(
                                    "{{\"module\":{},\"view\":{}}}",
                                    json_str(&n.revision),
                                    json_str(&view)
                                ),
                                "ok"
                            )
                        }
                        None => resp!(false, "null", &not_found(&s.graph, name)),
                    },
                }
            }
            "inspect_function" => {
                let s = need_session!();
                let name = req.get("name").and_then(|v| v.as_str()).unwrap_or("");
                match canonical_entity_rev(
                    &s.graph,
                    "inspect_function",
                    "name",
                    name,
                    &["function"],
                ) {
                    Err(Some((r, msg))) => resp!(false, &r, &msg),
                    Err(None) => resp!(false, "null", &not_found(&s.graph, name)),
                    Ok(entity) => match s.graph.resolve(&entity) {
                        Some(n) => {
                            let rev = n.revision.clone();
                            let view = air::view_function(&s.graph, &rev);
                            let mut budget = 0usize;
                            let body = s
                                .graph
                                .get(&rev)
                                .and_then(|n| n.slots.get("body").and_then(|b| b.first()).cloned())
                                .map(|b| body_tree(&s.graph, &b, 0, &mut budget))
                                .unwrap_or_default();
                            let eff = s
                                .graph
                                .get(&rev)
                                .and_then(|n| match n.fields.get("eff") {
                                    Some(air::Value::Names(ns)) => Some(ns.join(",")),
                                    _ => None,
                                })
                                .unwrap_or_default();
                            resp!(
                                true,
                                &format!(
                                    "{{\"revision\":{},\"eff\":{},\"view\":{},\"body\":{}}}",
                                    json_str(&rev),
                                    json_str(&eff),
                                    json_str(&view),
                                    json_str(&body)
                                ),
                                "ok"
                            )
                        }
                        None => resp!(false, "null", &not_found(&s.graph, name)),
                    },
                }
            }
            "inspect_entity" => {
                let s = need_session!();
                let id = req
                    .get("entity")
                    .or_else(|| req.get("name"))
                    .and_then(|v| v.as_str())
                    .unwrap_or("");
                match canonical_entity_rev(&s.graph, "inspect_entity", "entity", id, &["any"]) {
                    Err(Some((r, msg))) => resp!(false, &r, &msg),
                    Err(None) => resp!(false, "null", &not_found(&s.graph, id)),
                    Ok(entity) => match s.graph.resolve(&entity).cloned() {
                        Some(n) => {
                            let mut fields = Vec::new();
                            for (k, v) in &n.fields {
                                fields.push(format!("{}:{}", json_str(k), value_json(v)));
                            }
                            let mut slots = Vec::new();
                            for (k, kids) in &n.slots {
                                slots.push(format!(
                                    "{}:[{}]",
                                    json_str(k),
                                    kids.iter()
                                        .map(|c| json_str(c))
                                        .collect::<Vec<_>>()
                                        .join(",")
                                ));
                            }
                            resp!(
                            true,
                            &format!(
                                "{{\"entity\":{},\"revision\":{},\"kind\":{},\"fields\":{{{}}},\"slots\":{{{}}}}}",
                                json_str(&n.entity),
                                json_str(&n.revision),
                                json_str(&n.kind),
                                fields.join(","),
                                slots.join(",")
                            ),
                            "ok"
                        )
                        }
                        None => resp!(false, "null", &not_found(&s.graph, id)),
                    },
                }
            }
            "list_candidates" => {
                let s = need_session!();
                let hole = req.get("hole").and_then(|v| v.as_str()).unwrap_or("");
                match resolve_hole(&s.graph, hole) {
                    Some(h) => {
                        let cands = air::hole_candidates(&s.graph, &h);
                        resp!(
                            true,
                            &format!(
                                "{{\"candidates\":[{}]}}",
                                cands
                                    .iter()
                                    .map(|c| json_str(c))
                                    .collect::<Vec<_>>()
                                    .join(",")
                            ),
                            "ok"
                        )
                    }
                    None => resp!(false, "null", "hole not found"),
                }
            }
            "begin_transaction" => match begin_agent_session(
                req.get("project").and_then(|v| v.as_str()).unwrap_or(""),
                &mut session,
                &mut base_graph,
                &mut real_dir,
            ) {
                Ok(rev) => resp!(
                    true,
                    &format!("{{\"project_revision\":{}}}", json_str(&rev)),
                    "ok"
                ),
                Err(e) => resp!(false, "null", &e),
            },
            "create_literal" => {
                let s = need_session!();
                let ty = req.get("type").and_then(|v| v.as_str()).unwrap_or("string");
                let value = req.get("value").and_then(|v| v.as_str()).unwrap_or("");
                match (|| -> Result<String, String> {
                    let v = prim_value_for(ty, value)?;
                    let mut f = BTreeMap::new();
                    f.insert("value".to_string(), v);
                    s.create_node("literal", f, BTreeMap::new())
                })() {
                    Ok(rev) => resp!(true, &format!("{{\"revision\":{}}}", json_str(&rev)), "ok"),
                    Err(e) => resp!(false, "null", &e),
                }
            }
            "create_reference" => {
                let s = need_session!();
                let name = req.get("name").and_then(|v| v.as_str()).unwrap_or("");
                let mut f = BTreeMap::new();
                f.insert("name".to_string(), air::Value::Str(name.to_string()));
                match s.create_node("ref", f, BTreeMap::new()) {
                    Ok(rev) => resp!(true, &format!("{{\"revision\":{}}}", json_str(&rev)), "ok"),
                    Err(e) => resp!(false, "null", &e),
                }
            }
            "create_call" => {
                let s = need_session!();
                let name = req.get("name").and_then(|v| v.as_str()).unwrap_or("");
                let args: Vec<String> = req
                    .get("args")
                    .map(|a| match a {
                        Json::Arr(items) => items
                            .iter()
                            .filter_map(|x| x.as_str().map(|s| s.to_string()))
                            .collect(),
                        _ => Vec::new(),
                    })
                    .unwrap_or_default();
                let mut f = BTreeMap::new();
                f.insert("name".to_string(), air::Value::Str(name.to_string()));
                let mut slots = BTreeMap::new();
                slots.insert("args".to_string(), args);
                match s.create_node("call", f, slots) {
                    Ok(rev) => resp!(true, &format!("{{\"revision\":{}}}", json_str(&rev)), "ok"),
                    Err(e) => resp!(false, "null", &e),
                }
            }
            "create_binding" => {
                let s = need_session!();
                let name = req.get("name").and_then(|v| v.as_str()).unwrap_or("");
                let ty = req.get("type_name").and_then(|v| v.as_str());
                let value = req.get("value").and_then(|v| v.as_str()).unwrap_or("");
                match (|| -> Result<String, String> {
                    let ty_id = match ty {
                        Some(t) => Some(type_expr_for(t, &mut s.graph)?),
                        None => None,
                    };
                    let mut slots = BTreeMap::new();
                    if let Some(t) = ty_id {
                        slots.insert("type".to_string(), vec![t]);
                    }
                    slots.insert("value".to_string(), vec![value.to_string()]);
                    let mut f = BTreeMap::new();
                    f.insert("name".to_string(), air::Value::Str(name.to_string()));
                    s.create_node("binding", f, slots)
                })() {
                    Ok(rev) => resp!(true, &format!("{{\"revision\":{}}}", json_str(&rev)), "ok"),
                    Err(e) => resp!(false, "null", &e),
                }
            }
            "create_block" => {
                let s = need_session!();
                let steps: Vec<String> = req
                    .get("steps")
                    .map(|a| match a {
                        Json::Arr(items) => items
                            .iter()
                            .filter_map(|x| x.as_str().map(|s| s.to_string()))
                            .collect(),
                        _ => Vec::new(),
                    })
                    .unwrap_or_default();
                let mut slots = BTreeMap::new();
                slots.insert("steps".to_string(), steps);
                match s.create_node("block", BTreeMap::new(), slots) {
                    Ok(rev) => resp!(true, &format!("{{\"revision\":{}}}", json_str(&rev)), "ok"),
                    Err(e) => resp!(false, "null", &e),
                }
            }
            "append_step" => {
                let s = need_session!();
                let function = req.get("function").and_then(|v| v.as_str()).unwrap_or("");
                let step = req.get("step").and_then(|v| v.as_str()).unwrap_or("");
                match (|| -> Result<String, String> {
                    let fn_rev = match canonical_entity_rev(
                        &s.graph,
                        "append_step",
                        "function",
                        function,
                        &["function"],
                    ) {
                        Ok(e) => s
                            .graph
                            .resolve(&e)
                            .map(|n| n.revision.clone())
                            .ok_or_else(|| "function not found".to_string())?,
                        Err(_) => return Err("function not found".to_string()),
                    };
                    let n = s.graph.get(&fn_rev).ok_or("function not found")?;
                    let body = n
                        .slots
                        .get("body")
                        .and_then(|b| b.first())
                        .cloned()
                        .ok_or("function has no body block")?;
                    s.append_child(&body, "steps", step)
                })() {
                    Ok(rev) => resp!(
                        true,
                        &format!("{{\"new_revision\":{}}}", json_str(&rev)),
                        "ok"
                    ),
                    Err(e) => resp!(false, "null", &e),
                }
            }
            "replace_expression" => {
                let s = need_session!();
                let position = req
                    .get("position")
                    .and_then(|v| v.as_str())
                    .unwrap_or("value");
                // RFC-0007: parent/child operands resolve through the strict
                // operand resolver (bare revision OR semantic handle); a stale
                // or missing operand returns structured recovery instead of a
                // bare error, breaking the D02-style repeated-retry loop.
                let parent_res = req
                    .get("parent")
                    .map(|v| resolve_operand_strict(s, "replace_expression", "parent", v))
                    .unwrap_or_else(|| {
                        let r = construction_type_mismatch_json(
                            "replace_expression",
                            "parent",
                            "revision | semantic handle",
                            "missing",
                        );
                        Err((r, "E_AEP_OPERAND_NOT_FOUND: parent missing".to_string()))
                    });
                match parent_res {
                    Err((r, msg)) => resp!(false, &r, &msg),
                    Ok(pr) => {
                        let kind = s.graph.get(&pr).map(|n| n.kind.clone()).unwrap_or_default();
                        match friendly_slot(&kind, position) {
                            None => resp!(
                                false,
                                &format!(
                                    "{{\"operation\":\"replace_expression\",\"argument\":\"position\",\"requested\":{},\"expected_positions\":[{}],\"recovery\":{{\"tool\":\"describe_operation\",\"name\":\"replace_expression\"}}}}",
                                    json_str(position),
                                    valid_positions(&kind)
                                        .iter()
                                        .map(|p| json_str(p))
                                        .collect::<Vec<_>>()
                                        .join(",")
                                ),
                                "E_AEP_OP: invalid position"
                            ),
                            Some(slot) => {
                                let child_res = req
                                    .get("child")
                                    .map(|v| resolve_operand_strict(s, "replace_expression", "child", v))
                                    .unwrap_or_else(|| {
                                        let r = construction_type_mismatch_json(
                                            "replace_expression",
                                            "child",
                                            "revision | semantic handle",
                                            "missing",
                                        );
                                        Err((
                                            r,
                                            "E_AEP_OPERAND_NOT_FOUND: child missing".to_string(),
                                        ))
                                    });
                                match child_res {
                                    Err((r, msg)) => resp!(false, &r, &msg),
                                    Ok(cr) => match s.replace_slot(&pr, slot, &cr) {
                                        Ok(rev) => resp!(
                                            true,
                                            &format!("{{\"new_revision\":{}}}", json_str(&rev)),
                                            "ok"
                                        ),
                                        Err(e) => resp!(false, "null", &e),
                                    },
                                }
                            }
                        }
                    }
                }
            }
            "add_function" => {
                let s = need_session!();
                let module = req.get("module").and_then(|v| v.as_str()).unwrap_or("");
                let name = req.get("name").and_then(|v| v.as_str()).unwrap_or("");
                let returns = req
                    .get("returns")
                    .and_then(|v| v.as_str())
                    .unwrap_or("string");
                let params = req.get("params");
                match (|| -> Result<String, String> {
                    let ret_id = type_expr_for(returns, &mut s.graph)?;
                    let mut slots = BTreeMap::new();
                    slots.insert("returns".to_string(), vec![ret_id]);
                    let mut param_ids = Vec::new();
                    if let Some(Json::Arr(items)) = params {
                        for it in items {
                            let pname = it
                                .get("name")
                                .and_then(|v| v.as_str())
                                .unwrap_or("p")
                                .to_string();
                            let ptype = it.get("type").and_then(|v| v.as_str()).unwrap_or("string");
                            let ty_id = type_expr_for(ptype, &mut s.graph)?;
                            let mut pf = BTreeMap::new();
                            pf.insert("name".to_string(), air::Value::Str(pname));
                            let mut ps = BTreeMap::new();
                            ps.insert("type".to_string(), vec![ty_id]);
                            param_ids.push(s.create_node("param", pf, ps)?);
                        }
                    }
                    slots.insert("params".to_string(), param_ids);
                    let mut bs = BTreeMap::new();
                    bs.insert("steps".to_string(), Vec::new());
                    let body = s.create_node("block", BTreeMap::new(), bs)?;
                    slots.insert("body".to_string(), vec![body]);
                    slots.insert("pre".to_string(), Vec::new());
                    slots.insert("post".to_string(), Vec::new());
                    slots.insert("inv".to_string(), Vec::new());
                    let mut f = BTreeMap::new();
                    f.insert("name".to_string(), air::Value::Str(name.to_string()));
                    f.insert("pure".to_string(), air::Value::Bool(true));
                    let fn_id = s.create_node("function", f, slots)?;
                    s.append_child(&format!("module:{module}"), "functions", &fn_id)?;
                    Ok(fn_id)
                })() {
                    Ok(rev) => resp!(true, &format!("{{\"revision\":{}}}", json_str(&rev)), "ok"),
                    Err(e) => resp!(false, "null", &e),
                }
            }
            "change_field" => {
                let s = need_session!();
                let entity = req.get("entity").and_then(|v| v.as_str()).unwrap_or("");
                let field = req.get("field").and_then(|v| v.as_str()).unwrap_or("");
                let value = req.get("value").and_then(|v| v.as_str()).unwrap_or("");
                match s.set_field(entity, field, air::Value::Str(value.to_string())) {
                    Ok(rev) => resp!(
                        true,
                        &format!("{{\"new_revision\":{}}}", json_str(&rev)),
                        "ok"
                    ),
                    Err(e) => resp!(false, "null", &e),
                }
            }
            "rename_entity" => {
                let s = need_session!();
                let entity = req.get("entity").and_then(|v| v.as_str()).unwrap_or("");
                let new_name = req.get("new_name").and_then(|v| v.as_str()).unwrap_or("");
                match (|| -> Result<(), String> {
                    let rev = resolve_entity_in_graph(&s.graph, entity)
                        .ok_or_else(|| format!("entity not found: {entity}"))?;
                    let old = s
                        .graph
                        .get(&rev)
                        .and_then(|n| match n.fields.get("name") {
                            Some(air::Value::Str(s)) => Some(s.clone()),
                            _ => None,
                        })
                        .ok_or("entity has no name field")?;
                    s.set_field(&rev, "name", air::Value::Str(new_name.to_string()))?;
                    s.rename_symbol(&old, new_name)?;
                    // 跨模块调用方使用限定名 module.old，需要一并重命名；
                    // 同时更新所属模块的 exports 列表。
                    for me in s.graph.module_entities.clone() {
                        let module_name = me.trim_start_matches("module:").to_string();
                        if let Some(mn) = s.graph.resolve(&me) {
                            let exports = match mn.fields.get("exports") {
                                Some(air::Value::Names(ns)) => ns.clone(),
                                _ => Vec::new(),
                            };
                            if exports.contains(&old) {
                                let updated: Vec<String> = exports
                                    .iter()
                                    .map(|e| {
                                        if e == &old {
                                            new_name.to_string()
                                        } else {
                                            e.clone()
                                        }
                                    })
                                    .collect();
                                s.set_field(&me, "exports", air::Value::Names(updated))?;
                            }
                            if exports.contains(&old) {
                                s.rename_symbol(
                                    &format!("{module_name}.{old}"),
                                    &format!("{module_name}.{new_name}"),
                                )?;
                            }
                        }
                    }
                    Ok(())
                })() {
                    Ok(()) => resp!(true, "{\"renamed\":true}", "ok"),
                    Err(e) => resp!(false, "null", &e),
                }
            }
            "inspect_body" => {
                let s = need_session!();
                let function = req.get("function").and_then(|v| v.as_str()).unwrap_or("");
                match canonical_entity_rev(
                    &s.graph,
                    "inspect_body",
                    "function",
                    function,
                    &["function"],
                ) {
                    Err(Some((r, msg))) => resp!(false, &r, &msg),
                    Err(None) => resp!(false, "null", &not_found(&s.graph, function)),
                    Ok(entity) => match s.graph.resolve(&entity) {
                        Some(n) => {
                            let fn_rev = n.revision.clone();
                            let eff = s
                                .graph
                                .get(&fn_rev)
                                .and_then(|n| match n.fields.get("eff") {
                                    Some(air::Value::Names(ns)) => Some(ns.join(",")),
                                    _ => None,
                                })
                                .unwrap_or_default();
                            let pure =
                                s.graph
                                    .get(&fn_rev)
                                    .and_then(|n| match n.fields.get("pure") {
                                        Some(air::Value::Bool(b)) => Some(*b),
                                        _ => None,
                                    });
                            let body = s
                                .graph
                                .get(&fn_rev)
                                .and_then(|n| n.slots.get("body").and_then(|b| b.first()).cloned());
                            match body {
                                Some(body_rev) => {
                                    let mut budget = 0usize;
                                    let tree = body_tree(&s.graph, &body_rev, 0, &mut budget);
                                    resp!(
                                        true,
                                        &format!(
                                            "{{\"eff\":{},\"pure\":{},\"body\":{}}}",
                                            json_str(&eff),
                                            json_str(
                                                &pure.map(|b| b.to_string()).unwrap_or_default()
                                            ),
                                            json_str(&tree)
                                        ),
                                        "ok"
                                    )
                                }
                                None => resp!(false, "null", "function has no body block"),
                            }
                        }
                        None => resp!(false, "null", &not_found(&s.graph, function)),
                    },
                }
            }
            "inspect_test" => {
                let s = need_session!();
                let module = req.get("module").and_then(|v| v.as_str()).unwrap_or("");
                let name = req.get("name").and_then(|v| v.as_str()).unwrap_or("");
                let mut found = None;
                let mod_res =
                    canonical_entity_rev(&s.graph, "inspect_test", "module", module, &["module"]);
                match mod_res {
                    Err(Some((r, msg))) => resp!(false, &r, &msg),
                    Err(None) => resp!(false, "null", &not_found(&s.graph, module)),
                    Ok(m) => {
                        if let Some(mn) = s.graph.resolve(&m) {
                            for id in mn.slots.get("tests").cloned().unwrap_or_default() {
                                if let Some(t) = s.graph.get(&id) {
                                    if t.fields
                                        .get("name")
                                        .map(|v| v == &air::Value::Str(name.to_string()))
                                        .unwrap_or(false)
                                    {
                                        found = Some(id);
                                        break;
                                    }
                                }
                            }
                        }
                        match found {
                            Some(rev) => {
                                let mut budget = 0usize;
                                let tree = body_tree(&s.graph, &rev, 0, &mut budget);
                                resp!(
                                    true,
                                    &format!(
                                        "{{\"revision\":{},\"body\":{}}}",
                                        json_str(&rev),
                                        json_str(&tree)
                                    ),
                                    "ok"
                                )
                            }
                            None => resp!(false, "null", &not_found(&s.graph, name)),
                        }
                    }
                }
            }
            // RFC-0002/AEP-0001: change-impact query（只读，结构化引用）
            "inspect_change_impact" => {
                // RFC-0002 是 DRAFT：默认不可调用（opt-in），避免未接受的
                // 实验工具默认暴露给 agent。
                if std::env::var("ALVA_AEP_ENABLE_EXPERIMENTAL_A1").is_err() {
                    resp!(
                        false,
                        "null",
                        "E_AEP_UNKNOWN_TOOL: inspect_change_impact (experimental; set ALVA_AEP_ENABLE_EXPERIMENTAL_A1=1)"
                    )
                } else {
                    let s = need_session!();
                    let entity = req.get("entity").and_then(|v| v.as_str()).unwrap_or("");
                    match change_impact(&s.graph, entity) {
                        Ok(json) => resp!(true, &json, "ok"),
                        Err(e) => resp!(false, "null", &e),
                    }
                }
            }
            // RFC-0002/AEP-0001: 批量 schema 缺口诊断
            // （E_RECORD_SCHEMA_INCOMPLETE：一次列出所有缺字段的构造点）
            "inspect_schema_gaps" => {
                if std::env::var("ALVA_AEP_ENABLE_EXPERIMENTAL_A1").is_err() {
                    resp!(
                        false,
                        "null",
                        "E_AEP_UNKNOWN_TOOL: inspect_schema_gaps (experimental; set ALVA_AEP_ENABLE_EXPERIMENTAL_A1=1)"
                    )
                } else {
                    let s = need_session!();
                    let entity = req.get("entity").and_then(|v| v.as_str()).unwrap_or("");
                    match schema_gaps(&s.graph, entity) {
                        Ok(json) => resp!(true, &json, "ok"),
                        Err(e) => resp!(false, "null", &e),
                    }
                }
            }
            "add_field" => {
                let s = need_session!();
                let type_name = req.get("type").and_then(|v| v.as_str()).unwrap_or("");
                let field = req.get("name").and_then(|v| v.as_str()).unwrap_or("");
                let type_name2 = req
                    .get("type_name")
                    .and_then(|v| v.as_str())
                    .unwrap_or("string");
                match resolve_type_in_graph(&s.graph, type_name) {
                    Some(type_rev) => {
                        match (|| -> Result<String, String> {
                            let ty = type_expr_for(type_name2, &mut s.graph)?;
                            let mut f = BTreeMap::new();
                            f.insert("name".to_string(), air::Value::Str(field.to_string()));
                            let mut slots = BTreeMap::new();
                            slots.insert("type".to_string(), vec![ty]);
                            let field_rev = s.create_node("type_field", f, slots)?;
                            s.append_child(&type_rev, "fields", &field_rev)?;
                            Ok(field_rev)
                        })() {
                            Ok(rev) => {
                                resp!(true, &format!("{{\"revision\":{}}}", json_str(&rev)), "ok")
                            }
                            Err(e) => resp!(false, "null", &e),
                        }
                    }
                    None => resp!(false, "null", &not_found(&s.graph, type_name)),
                }
            }
            "add_record_field" => {
                let s = need_session!();
                let record = req.get("record").and_then(|v| v.as_str()).unwrap_or("");
                let field = req.get("name").and_then(|v| v.as_str()).unwrap_or("");
                let value = req.get("value").and_then(|v| v.as_str()).unwrap_or("");
                match (|| -> Result<String, String> {
                    let record_rev = s.graph.resolve_rev(record).ok_or("record not found")?;
                    let value_rev = s.graph.resolve_rev(value).ok_or("value node not found")?;
                    let mut f = BTreeMap::new();
                    f.insert("name".to_string(), air::Value::Str(field.to_string()));
                    let mut slots = BTreeMap::new();
                    slots.insert("value".to_string(), vec![value_rev]);
                    let field_rev = s.create_node("record_field", f, slots)?;
                    s.append_child(&record_rev, "fields", &field_rev)?;
                    Ok(field_rev)
                })() {
                    Ok(rev) => resp!(true, &format!("{{\"revision\":{}}}", json_str(&rev)), "ok"),
                    Err(e) => resp!(false, "null", &e),
                }
            }
            "add_param" => {
                let s = need_session!();
                let function = req.get("function").and_then(|v| v.as_str()).unwrap_or("");
                let name = req.get("name").and_then(|v| v.as_str()).unwrap_or("");
                let type_name = req.get("type").and_then(|v| v.as_str()).unwrap_or("string");
                match resolve_entity_in_graph(&s.graph, function) {
                    Some(fn_rev) => {
                        match (|| -> Result<String, String> {
                            let ty = type_expr_for(type_name, &mut s.graph)?;
                            let mut f = BTreeMap::new();
                            f.insert("name".to_string(), air::Value::Str(name.to_string()));
                            let mut slots = BTreeMap::new();
                            slots.insert("type".to_string(), vec![ty]);
                            let param_rev = s.create_node("param", f, slots)?;
                            s.append_child(&fn_rev, "params", &param_rev)?;
                            Ok(param_rev)
                        })() {
                            Ok(rev) => {
                                resp!(true, &format!("{{\"revision\":{}}}", json_str(&rev)), "ok")
                            }
                            Err(e) => resp!(false, "null", &e),
                        }
                    }
                    None => resp!(false, "null", &not_found(&s.graph, function)),
                }
            }
            "add_call_arg" => {
                let s = need_session!();
                let call = req.get("call").and_then(|v| v.as_str()).unwrap_or("");
                let arg = req.get("arg").and_then(|v| v.as_str()).unwrap_or("");
                match (|| -> Result<String, String> {
                    let call_rev = s.graph.resolve_rev(call).ok_or("call node not found")?;
                    let arg_rev = s.graph.resolve_rev(arg).ok_or("arg node not found")?;
                    s.append_child(&call_rev, "args", &arg_rev)?;
                    Ok(call_rev)
                })() {
                    Ok(rev) => resp!(true, &format!("{{\"revision\":{}}}", json_str(&rev)), "ok"),
                    Err(e) => resp!(false, "null", &e),
                }
            }
            "set_effect" => {
                let s = need_session!();
                let function = req.get("function").and_then(|v| v.as_str()).unwrap_or("");
                let effect = req.get("effect").and_then(|v| v.as_str()).unwrap_or("");
                match resolve_entity_in_graph(&s.graph, function) {
                    Some(fn_rev) => {
                        let r = match effect {
                            "pure" => {
                                match s.set_field(&fn_rev, "pure", air::Value::Bool(true)) {
                                    Ok(_) => {
                                        // 第一次 set_field 会改变函数节点 revision，
                                        // 必须重新解析实体再更新 eff 字段。
                                        let rev2 = resolve_entity_in_graph(&s.graph, function)
                                            .unwrap_or_else(|| fn_rev.clone());
                                        s.set_field(&rev2, "eff", air::Value::Names(vec![]))
                                    }
                                    Err(e) => Err(e),
                                }
                            }
                            "io" => match s.set_field(&fn_rev, "pure", air::Value::Bool(false)) {
                                Ok(_) => {
                                    let rev2 = resolve_entity_in_graph(&s.graph, function)
                                        .unwrap_or_else(|| fn_rev.clone());
                                    s.set_field(
                                        &rev2,
                                        "eff",
                                        air::Value::Names(vec!["io".to_string()]),
                                    )
                                }
                                Err(e) => Err(e),
                            },
                            other => Err(format!("unknown effect '{other}'")),
                        };
                        match r {
                            Ok(rev) => {
                                resp!(true, &format!("{{\"revision\":{}}}", json_str(&rev)), "ok")
                            }
                            Err(e) => resp!(false, "null", &e),
                        }
                    }
                    None => resp!(false, "null", &not_found(&s.graph, function)),
                }
            }
            "add_cap" => {
                let s = need_session!();
                let module = req.get("module").and_then(|v| v.as_str()).unwrap_or("");
                let cap = req.get("cap").and_then(|v| v.as_str()).unwrap_or("");
                match resolve_entity_in_graph(&s.graph, module) {
                    Some(m) => {
                        let mut caps = s
                            .graph
                            .get(&m)
                            .and_then(|n| match n.fields.get("caps") {
                                Some(air::Value::Names(ns)) => Some(ns.clone()),
                                _ => None,
                            })
                            .unwrap_or_default();
                        if !caps.contains(&cap.to_string()) {
                            caps.push(cap.to_string());
                        }
                        match s.set_field(&m, "caps", air::Value::Names(caps)) {
                            Ok(rev) => {
                                resp!(true, &format!("{{\"revision\":{}}}", json_str(&rev)), "ok")
                            }
                            Err(e) => resp!(false, "null", &e),
                        }
                    }
                    None => resp!(false, "null", &not_found(&s.graph, module)),
                }
            }
            "create_if" => {
                let s = need_session!();
                let cond = req.get("cond").and_then(|v| v.as_str()).unwrap_or("");
                let then = req.get("then").and_then(|v| v.as_str()).unwrap_or("");
                let els = req.get("else").and_then(|v| v.as_str()).unwrap_or("");
                match (|| -> Result<String, String> {
                    let cond_rev = s.graph.resolve_rev(cond).ok_or("cond node not found")?;
                    let then_rev = s.graph.resolve_rev(then).ok_or("then node not found")?;
                    let else_rev = s.graph.resolve_rev(els).ok_or("else node not found")?;
                    let mut slots = BTreeMap::new();
                    slots.insert("cond".to_string(), vec![cond_rev]);
                    slots.insert("then".to_string(), vec![then_rev]);
                    slots.insert("else".to_string(), vec![else_rev]);
                    s.create_node("if", BTreeMap::new(), slots)
                })() {
                    Ok(rev) => resp!(true, &format!("{{\"revision\":{}}}", json_str(&rev)), "ok"),
                    Err(e) => resp!(false, "null", &e),
                }
            }
            "create_binary" => {
                let s = need_session!();
                let op = req.get("op").and_then(|v| v.as_str()).unwrap_or("");
                let left = req.get("left").and_then(|v| v.as_str()).unwrap_or("");
                let right = req.get("right").and_then(|v| v.as_str()).unwrap_or("");
                match (|| -> Result<String, String> {
                    let left_rev = s.graph.resolve_rev(left).ok_or("left node not found")?;
                    let right_rev = s.graph.resolve_rev(right).ok_or("right node not found")?;
                    let mut f = BTreeMap::new();
                    f.insert("op".to_string(), air::Value::Str(op.to_string()));
                    let mut slots = BTreeMap::new();
                    slots.insert("left".to_string(), vec![left_rev]);
                    slots.insert("right".to_string(), vec![right_rev]);
                    s.create_node("binary", f, slots)
                })() {
                    Ok(rev) => resp!(true, &format!("{{\"revision\":{}}}", json_str(&rev)), "ok"),
                    Err(e) => resp!(false, "null", &e),
                }
            }
            "create_query" => {
                // RFC-0003: 创建查询表达式节点。
                //   contains: kind=contains collection=<rev> target=<rev>
                //   any/all/find: kind=<any|all|find> collection=<rev>
                //                 elem_var=<name> predicate=<rev>
                // 用 resolve_current（AEP 0.7）解析句柄，避免 stale revision
                // grounding 失败；结构错误即时拒绝。
                let s = need_session!();
                let kind = req.get("kind").and_then(|v| v.as_str()).unwrap_or("");
                let collection = req.get("collection").and_then(|v| v.as_str()).unwrap_or("");
                let target = req.get("target").and_then(|v| v.as_str()).unwrap_or("");
                let elem_var = req.get("elem_var").and_then(|v| v.as_str()).unwrap_or("");
                let predicate = req.get("predicate").and_then(|v| v.as_str()).unwrap_or("");
                match (|| -> Result<String, String> {
                    let coll_rev = s.resolve_current(collection)?;
                    if kind == "contains" {
                        if target.is_empty() {
                            return Err(
                                "E_QUERY_TARGET_MISSING: contains requires target".to_string()
                            );
                        }
                        let tgt_rev = s.resolve_current(target)?;
                        let mut slots = BTreeMap::new();
                        slots.insert("left".to_string(), vec![coll_rev]);
                        slots.insert("right".to_string(), vec![tgt_rev]);
                        s.create_node("veccontains", BTreeMap::new(), slots)
                    } else if kind == "any" || kind == "all" || kind == "find" {
                        if elem_var.is_empty() {
                            return Err(format!(
                                "E_QUERY_ELEM_VAR_MISSING: {kind} requires elem_var"
                            ));
                        }
                        if !check::valid_ident(elem_var) {
                            return Err(format!(
                                "E_QUERY_ELEM_VAR_INVALID: {kind} elem_var '{elem_var}' is not a valid identifier (no Rust keyword, no __ prefix)"
                            ));
                        }
                        if predicate.is_empty() {
                            return Err(format!(
                                "E_QUERY_PREDICATE_MISSING: {kind} requires predicate"
                            ));
                        }
                        let pred_rev = s.resolve_current(predicate)?;
                        let mut f = BTreeMap::new();
                        f.insert(
                            "elem_var".to_string(),
                            air::Value::Str(elem_var.to_string()),
                        );
                        let mut slots = BTreeMap::new();
                        slots.insert("collection".to_string(), vec![coll_rev]);
                        slots.insert("predicate".to_string(), vec![pred_rev]);
                        s.create_node(kind, f, slots)
                    } else {
                        Err(format!("E_QUERY_UNKNOWN_KIND: unknown query kind '{kind}'"))
                    }
                })() {
                    Ok(rev) => resp!(true, &format!("{{\"revision\":{}}}", json_str(&rev)), "ok"),
                    Err(e) => resp!(false, "null", &e),
                }
            }
            "update_record_fields" => {
                // RFC-0001: 创建 record_update 表达式节点。
                // 入参：type（record 类型名）、base（表达式 entity）、
                // updates（{field: value_entity}）。未指定字段语义上保留。
                // 结构性错误（空/重复）即时拒绝；字段存在性/类型兼容通过把
                // 节点临时挂载到 base 所在函数体做完整语义校验，失败回滚。
                let s = need_session!();
                let ty = req.get("type").and_then(|v| v.as_str()).unwrap_or("");
                let base = req.get("base").and_then(|v| v.as_str()).unwrap_or("");
                let mut updates: Vec<(String, String)> = Vec::new();
                if let Some(Json::Obj(map)) = req.get("updates") {
                    for (k, v) in map {
                        if let Some(id) = v.as_str() {
                            updates.push((k.clone(), id.to_string()));
                        }
                    }
                }
                match (|| -> Result<(String, Vec<String>), String> {
                    if ty.is_empty() {
                        return Err(
                            "E_RECORD_UPDATE_TYPE_MISSING: record-update requires a record type"
                                .to_string(),
                        );
                    }
                    if base.is_empty() {
                        return Err(
                            "E_AEP_BAD_REQUEST: update_record_fields requires base".to_string()
                        );
                    }
                    if updates.is_empty() {
                        return Err(
                            "E_RECORD_UPDATE_EMPTY: record-update must update at least one field"
                                .to_string(),
                        );
                    }
                    let mut seen = std::collections::HashSet::new();
                    for (f, _) in &updates {
                        if !seen.insert(f.clone()) {
                            return Err(format!(
                                "E_RECORD_UPDATE_DUPLICATE_FIELD: duplicate update field '{f}'"
                            ));
                        }
                    }
                    let base_rev = s.resolve_current(base)?;
                    let mut value_revs = Vec::new();
                    for (_, vid) in &updates {
                        value_revs.push(s.resolve_current(vid)?);
                    }
                    let saved = s.graph.clone();
                    let make_nodes =
                        |s: &mut air::EditSession| -> Result<(String, Vec<String>), String> {
                            let mut update_ids = Vec::new();
                            for ((f, _), vrev) in updates.iter().zip(value_revs.iter()) {
                                let mut ff = BTreeMap::new();
                                ff.insert("name".to_string(), air::Value::Str(f.clone()));
                                let mut fs = BTreeMap::new();
                                fs.insert("value".to_string(), vec![vrev.clone()]);
                                let id = s.create_node("update_field", ff, fs)?;
                                update_ids.push(id);
                            }
                            let mut f = BTreeMap::new();
                            f.insert("type".to_string(), air::Value::Str(ty.to_string()));
                            let mut slots = BTreeMap::new();
                            slots.insert("base".to_string(), vec![base_rev.clone()]);
                            slots.insert("updates".to_string(), update_ids.clone());
                            let rev = s.create_node("record_update", f, slots)?;
                            Ok((rev, update_ids))
                        };
                    let (rev, _) = make_nodes(s)?;
                    // 找 base 所属函数的 body block（向上走 parent 链）
                    let parents = air::parent_index(&s.graph);
                    let mut cur = base_rev.clone();
                    let mut block_rev: Option<String> = None;
                    let mut guard = 0;
                    while guard < 100_000 {
                        guard += 1;
                        match parents.get(&cur).and_then(|p| p.first()) {
                            Some((pref, _)) => {
                                if let Some(pn) = s.graph.get(pref) {
                                    if pn.kind == "function" {
                                        block_rev =
                                            pn.slots.get("body").and_then(|b| b.first()).cloned();
                                        break;
                                    }
                                }
                                cur = pref.clone();
                            }
                            None => break,
                        }
                    }
                    let temp_checked = if let Some(block) = block_rev {
                        // 插到 steps 开头，避免改变函数返回类型判定
                        s.insert_child(&block, "steps", &rev, 0).is_ok()
                    } else {
                        false
                    };
                    let errs = if temp_checked { s.check() } else { Vec::new() };
                    s.graph = saved;
                    s.errors = Vec::new();
                    if !errs.is_empty() {
                        return Err(errs.join("; "));
                    }
                    // 校验通过：重建节点（未挂载），交 agent 挂载
                    let (rev, update_ids) = make_nodes(s)?;
                    Ok((rev, update_ids))
                })() {
                    Ok((rev, update_ids)) => resp!(
                        true,
                        &format!(
                            "{{\"revision\":{},\"updates\":{}}}",
                            json_str(&rev),
                            json_str(&update_ids.join(","))
                        ),
                        "ok"
                    ),
                    Err(e) => resp!(false, "null", &e),
                }
            }
            "check_transaction" => {
                let s = need_session!();
                let errs = s.check();
                if errs.is_empty() {
                    resp!(true, "{\"problems\":[]}", "check ok")
                } else {
                    resp!(false, "null", &format!("check failed: {}", errs.join("; ")))
                }
            }
            "preview_semantic_diff" => {
                let s = need_session!();
                let report = s.diff_vs_base(base_graph.as_ref().unwrap_or(&air::AirGraph::new()));
                resp!(
                    true,
                    &format!("{{\"diff\":{}}}", json_str(report.summary.trim())),
                    "ok"
                )
            }
            "commit_transaction" => match session.take() {
                Some(mut s) => {
                    let errs = s.check();
                    if !errs.is_empty() {
                        session = Some(s);
                        resp!(false, "null", &format!("check failed: {}", errs.join("; ")))
                    } else {
                        let base = s.base_hash.clone();
                        match air::write_authoritative(&real_dir, &s.graph, Some(&base)) {
                            Ok(gen) => resp!(
                                true,
                                &format!(
                                    "{{\"generation\":{},\"revision\":{}}}",
                                    gen,
                                    json_str(&s.graph.semantic_hash())
                                ),
                                "committed"
                            ),
                            Err(e) => {
                                session = Some(s);
                                resp!(false, "null", &e)
                            }
                        }
                    }
                }
                None => resp!(false, "null", "E_AEP_NO_TRANSACTION"),
            },
            "abort_transaction" => {
                session = None;
                resp!(true, "{\"aborted\":true}", "aborted")
            }
            // RFC-0005 / AEP-0002: Intent -> Applicable Semantic Operations.
            "resolve_entity" => {
                let s = need_session!();
                let name = req
                    .get("name")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string();
                // Layer A: normalize quotes / prefixes / path suffixes before
                // the existing exact resolution (representation hygiene only).
                let name = air::normalize_handle(&name);
                let kind_f = req
                    .get("kind")
                    .and_then(|v| v.as_str())
                    .map(|s| s.to_string());
                let module_f = req
                    .get("module")
                    .and_then(|v| v.as_str())
                    .map(|s| s.to_string());
                if name.is_empty() {
                    resp!(
                        false,
                        "null",
                        "E_AEP_BAD_REQUEST: resolve_entity requires 'name'"
                    )
                } else {
                    match resolve_entity_full(
                        &s.graph,
                        &name,
                        kind_f.as_deref(),
                        module_f.as_deref(),
                    ) {
                        ResolveOutcome::Exact {
                            id,
                            kind,
                            module,
                            display,
                        } => resp!(
                            true,
                            &format!(
                                "{{\"entity\":{},\"kind\":{},\"module\":{},\"display\":{}}}",
                                json_str(&id),
                                json_str(&kind),
                                json_str(&module),
                                json_str(&display)
                            ),
                            "ok"
                        ),
                        out => {
                            let (code, msg) = match &out {
                                ResolveOutcome::Ambiguous { .. } => {
                                    ("E_AEP_AMBIGUOUS_ENTITY", "ambiguous entity")
                                }
                                _ => ("E_AEP_ENTITY_NOT_FOUND", "entity not found"),
                            };
                            resp!(
                                false,
                                &resolve_result_json(&out, &name),
                                &format!("{code}: {msg}")
                            )
                        }
                    }
                }
            }
            "applicable_operations" => {
                let s = need_session!();
                let entity = req
                    .get("entity")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string();
                if entity.is_empty() {
                    resp!(
                        false,
                        "null",
                        "E_AEP_BAD_REQUEST: applicable_operations requires 'entity'"
                    )
                } else {
                    match resolve_entity_full(&s.graph, &entity, None, None) {
                        ResolveOutcome::Exact { id, kind, .. } => {
                            let ops = aep::for_entity(&kind);
                            let inspection: Vec<String> = ops
                                .iter()
                                .filter(|o| o.effects == "inspection")
                                .map(|o| json_str(o.name))
                                .collect();
                            let mutation: Vec<String> = ops
                                .iter()
                                .filter(|o| o.effects == "mutation")
                                .map(|o| json_str(o.name))
                                .collect();
                            let context: Vec<String> = aep::context_ops()
                                .iter()
                                .map(|o| json_str(o.name))
                                .collect();
                            resp!(
                                true,
                                &format!(
                                    "{{\"entity\":{},\"kind\":{},\"inspection\":[{}],\"mutation\":[{}],\"context_operations\":[{}]}}",
                                    json_str(&id),
                                    json_str(&kind),
                                    inspection.join(","),
                                    mutation.join(","),
                                    context.join(",")
                                ),
                                "ok"
                            )
                        }
                        out => {
                            let (code, msg) = match &out {
                                ResolveOutcome::Ambiguous { .. } => {
                                    ("E_AEP_AMBIGUOUS_ENTITY", "ambiguous entity")
                                }
                                _ => ("E_AEP_ENTITY_NOT_FOUND", "entity not found"),
                            };
                            resp!(
                                false,
                                &resolve_result_json(&out, &entity),
                                &format!("{code}: {msg}")
                            )
                        }
                    }
                }
            }
            "describe_operation" => {
                let name = req
                    .get("name")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string();
                match aep::lookup(&name) {
                    Some(op) => {
                        if let Some(gate) = op.gate {
                            if !aep::gate_enabled(gate) {
                                let cands = aep::closest(&name, 6);
                                resp!(
                                    false,
                                    &unknown_tool_json(&name, &cands),
                                    "E_AEP_UNKNOWN_TOOL: unknown operation"
                                )
                            } else {
                                resp!(true, &describe_json(op), "ok")
                            }
                        } else {
                            resp!(true, &describe_json(op), "ok")
                        }
                    }
                    None => {
                        let cands = aep::closest(&name, 6);
                        resp!(
                            false,
                            &unknown_tool_json(&name, &cands),
                            "E_AEP_UNKNOWN_TOOL: unknown operation"
                        )
                    }
                }
            }
            "describe_construction" => {
                let s = need_session!();
                let kind = req
                    .get("kind")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string();
                let include_candidates = req
                    .get("include_candidates")
                    .and_then(|v| match v {
                        Json::Bool(b) => Some(*b),
                        // the aep.py CLI forwards key=value as strings, so the
                        // agent's `include_candidates=true` arrives as
                        // Json::Str("true"); parse it or the semantic-handle
                        // affordance is unreachable in the real environment.
                        Json::Str(s) => match s.as_str() {
                            "true" | "1" => Some(true),
                            "false" | "0" => Some(false),
                            _ => None,
                        },
                        _ => None,
                    })
                    .unwrap_or(false);
                match construction::construction_spec(&kind) {
                    Some(spec) => resp!(
                        true,
                        &construction_describe_json(spec, &s.graph, include_candidates),
                        "ok"
                    ),
                    None => {
                        let cands = construction::closest_kind(&kind, 6);
                        resp!(
                            false,
                            &construction_unknown_kind_json(&kind, &cands),
                            "E_AEP_CONSTRUCTION_UNKNOWN_KIND: unknown construction kind"
                        )
                    }
                }
            }
            "construct_expression" => {
                let s = need_session!();
                match handle_construct_expression(s, &req) {
                    Ok((result, msg)) => resp!(true, &result, &msg),
                    Err((result, msg)) => resp!(false, &result, &msg),
                }
            }
            "describe_capability" => {
                let _s = need_session!();
                let name = req
                    .get("name")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string();
                match capability::resolve_capability(&name) {
                    capability::CapabilityOutcome::Supported { cap: c, mapping } => {
                        let mapping_kind = match mapping {
                            capability::MappingKind::Canonical => "canonical",
                            capability::MappingKind::Alias => "alias",
                        };
                        let aliases: Vec<String> =
                            c.aliases.iter().map(|a| format!("\"{a}\"")).collect();
                        let synonyms: Vec<String> = capability::SYNONYMS
                            .iter()
                            .filter(|(_, canon)| *canon == c.canonical)
                            .map(|(s, _)| format!("\"{s}\""))
                            .collect();
                        resp!(
                            true,
                            &format!(
                                "{{\"supported\":true,\"canonical_name\":{},\"category\":{},\"aliases\":[{}],\"declared_synonyms\":[{}],\"arity\":{},\"mapping_kind\":{}}}",
                                json_str(c.canonical),
                                json_str(c.category.as_str()),
                                aliases.join(","),
                                synonyms.join(","),
                                json_str(c.arity),
                                json_str(mapping_kind)
                            ),
                            "ok"
                        )
                    }
                    capability::CapabilityOutcome::Unsupported {
                        canonical_alternative,
                        supported_alternatives,
                    } => {
                        let alts: Vec<String> = supported_alternatives
                            .iter()
                            .map(|a| format!("\"{a}\""))
                            .collect();
                        match canonical_alternative {
                            Some(canonical) => resp!(
                                true,
                                &format!(
                                    "{{\"supported\":false,\"requested\":{},\"canonical_alternative\":{},\"mapping_kind\":\"declared_synonym\",\"declared_alternatives\":[{}]}}",
                                    json_str(&name),
                                    json_str(canonical),
                                    alts.join(",")
                                ),
                                "ok"
                            ),
                            None => resp!(
                                true,
                                &format!(
                                    "{{\"supported\":false,\"requested\":{},\"canonical_alternative\":null,\"mapping_kind\":null,\"declared_alternatives\":[{}]}}",
                                    json_str(&name),
                                    alts.join(",")
                                ),
                                "ok"
                            ),
                        }
                    }
                }
            }
            "list_capabilities" => {
                let _s = need_session!();
                let category = req
                    .get("category")
                    .and_then(|v| v.as_str())
                    .unwrap_or("all")
                    .to_string();
                let cat_res: Result<Option<capability::CapCategory>, String> =
                    match category.as_str() {
                        "builtin" => Ok(Some(capability::CapCategory::Builtin)),
                        "operator" => Ok(Some(capability::CapCategory::Operator)),
                        "all" | "" => Ok(None),
                        other => Err(other.to_string()),
                    };
                match cat_res {
                    Err(other) => {
                        let r = format!(
                            "{{\"requested_category\":{},\"allowed\":[\"builtin\",\"operator\",\"all\"]}}",
                            json_str(&other)
                        );
                        resp!(false, &r, "E_AEP_BAD_REQUEST: unknown capability category")
                    }
                    Ok(cat) => {
                        let caps = capability::list_capabilities(cat);
                        let total = caps.len();
                        const MAX_LIST: usize = 40;
                        let truncated = total > MAX_LIST;
                        let shown = caps
                            .iter()
                            .take(MAX_LIST)
                            .map(|c| format!("\"{}\"", c.canonical))
                            .collect::<Vec<_>>()
                            .join(",");
                        resp!(
                            true,
                            &format!(
                                "{{\"category\":{},\"capabilities\":[{}],\"count\":{},\"truncated\":{}}}",
                                json_str(&category),
                                shown,
                                total,
                                truncated
                            ),
                            "ok"
                        )
                    }
                }
            }
            "migrate_signature" => {
                // E3 feasibility: SAME BINARY + env gate. When the gate is
                // off, the operation is invisible to discovery AND inert at
                // dispatch; it composes only existing EditSession APIs and
                // does NOT check or commit (the agent still calls
                // check_transaction / commit_transaction itself).
                if !aep::gate_enabled(aep::GATE_E3_HIGH) {
                    resp!(false, "null", "E_AEP_UNKNOWN_TOOL: unknown operation")
                } else {
                    let s = need_session!();
                    let function = req.get("function").and_then(|v| v.as_str()).unwrap_or("");
                    let param = req.get("param").and_then(|v| v.as_str()).unwrap_or("");
                    let type_name = req
                        .get("type")
                        .and_then(|v| v.as_str())
                        .unwrap_or("string");
                    let value = req.get("value").and_then(|v| v.as_str()).unwrap_or("");
                    match (|| -> Result<String, String> {
                        if param.is_empty() {
                            return Err("migrate_signature: param name required".to_string());
                        }
                        let fn_entity = resolve_entity_in_graph(&s.graph, function)
                            .ok_or_else(|| format!("entity not found: {function}"))?;
                        let (fn_rev, fn_name) = s
                            .graph
                            .resolve(&fn_entity)
                            .map(|n| {
                                let name = match n.fields.get("name") {
                                    Some(air::Value::Str(s)) => s.clone(),
                                    _ => String::new(),
                                };
                                (n.revision.clone(), name)
                            })
                            .ok_or_else(|| format!("entity not found: {function}"))?;
                        if fn_name.is_empty() {
                            return Err(format!("entity has no name field: {function}"));
                        }
                        // 2. Compute module-scoped caller matching BEFORE the
                        //    mutation: appending the parameter rebuilds
                        //    revisions bottom-up, so the function's revision
                        //    is only valid before the mutation. Module
                        //    context is the same information a LOW agent has
                        //    from inspections. A call belongs to the target
                        //    iff:
                        //      (a) it uses the unqualified source name AND
                        //          its enclosing function lives in the
                        //          target's module; or
                        //      (b) it uses the qualified "module.fn" name
                        //          from anywhere.
                        //    This deliberately avoids a global name match,
                        //    which would mis-migrate same-named functions in
                        //    other modules.
                        let target_module: String = s
                            .graph
                            .module_entities
                            .iter()
                            .find(|me| {
                                s.graph.resolve(me).and_then(|mn| {
                                    mn.slots
                                        .get("functions")
                                        .map(|f| f.contains(&fn_rev))
                                }).unwrap_or(false)
                            })
                            .map(|me| me.trim_start_matches("module:").to_string())
                            .unwrap_or_default();
                        let qualified = if target_module.is_empty() {
                            fn_name.clone()
                        } else {
                            format!("{target_module}.{fn_name}")
                        };
                        let mut fn_module: BTreeMap<String, String> = BTreeMap::new();
                        for me in s.graph.module_entities.clone() {
                            let mname = me.trim_start_matches("module:").to_string();
                            if let Some(mn) = s.graph.resolve(&me) {
                                for fid in mn.slots.get("functions").cloned().unwrap_or_default() {
                                    fn_module.insert(fid, mname.clone());
                                }
                            }
                        }
                        // 1. new parameter (same construction as add_param)
                        let ty = type_expr_for(type_name, &mut s.graph)?;
                        let mut f = BTreeMap::new();
                        f.insert("name".to_string(), air::Value::Str(param.to_string()));
                        let mut slots = BTreeMap::new();
                        slots.insert("type".to_string(), vec![ty]);
                        let param_rev = s.create_node("param", f, slots)?;
                        s.append_child(&fn_rev, "params", &param_rev)?;
                        // 3. migrate the module-scoped call sites. The
                        //    literal value is parsed ONLY when there are
                        //    callers (a zero-caller parameter addition does
                        //    not need a value).
                        let callers: Vec<String> = air::walk_expressions(&s.graph)
                            .into_iter()
                            .filter(|(rev, kind, fn_e, _)| {
                                if kind != "call" {
                                    return false;
                                }
                                let Some(n) = s.graph.get(rev) else {
                                    return false;
                                };
                                let Some(air::Value::Str(cname)) = n.fields.get("name") else {
                                    return false;
                                };
                                if cname == &qualified {
                                    return true;
                                }
                                if cname == &fn_name {
                                    return !fn_e.is_empty()
                                        && fn_module
                                            .get(fn_e)
                                            .map(|m| m == &target_module)
                                            .unwrap_or(false);
                                }
                                false
                            })
                            .map(|(rev, _, _, _)| rev.clone())
                            .collect();
                        if !callers.is_empty() {
                            let arg_val = prim_value_for(type_name, value)?;
                            let mut af = BTreeMap::new();
                            af.insert("value".to_string(), arg_val);
                            for call_rev in callers {
                                let arg_rev = s.create_node(
                                    "literal", af.clone(), BTreeMap::new())?;
                                s.append_child(&call_rev, "args", &arg_rev)?;
                            }
                        }
                        Ok(fn_entity)
                    })() {
                        Ok(entity) => resp!(
                            true,
                            &format!("{{\"entity\":{}}}", json_str(&entity)),
                            "ok"
                        ),
                        Err(e) => resp!(false, "null", &e),
                    }
                }
            }
            other => {
                let cands = aep::closest(other, 6);
                resp!(
                    false,
                    &unknown_tool_json(other, &cands),
                    "E_AEP_UNKNOWN_TOOL: unknown operation"
                )
            }
        };
        println!("{out}");
    }
    0
}

fn agent_resp(
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
            Some(t) if t.trim().starts_with("E_") => t.trim(),
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
        diagnostics.iter().map(|d| json_str(d)).collect::<Vec<_>>().join(","),
        json_str(message)
    )
}

fn value_json(v: &air::Value) -> String {
    match v {
        air::Value::Str(s) => json_str(s),
        air::Value::Int(i) => i.to_string(),
        air::Value::UInt(u) => u.to_string(),
        air::Value::Float(x) => x.to_string(),
        air::Value::Bool(b) => b.to_string(),
        air::Value::Bytes(b) => json_str(&b.iter().map(|x| format!("{x:02x}")).collect::<String>()),
        air::Value::Names(ns) => format!(
            "[{}]",
            ns.iter().map(|x| json_str(x)).collect::<Vec<_>>().join(",")
        ),
    }
}

fn resolve_entity_in_graph(g: &air::AirGraph, name: &str) -> Option<String> {
    if g.resolve_rev(name).is_some() {
        return Some(name.to_string());
    }
    for entity in &g.module_entities {
        if entity == name || entity.trim_start_matches("module:") == name {
            return Some(entity.clone());
        }
        let module_name = entity.trim_start_matches("module:");
        if let Some(rest) = name.strip_prefix(&format!("{module_name}.")) {
            if let Some(mn) = g.resolve(entity) {
                for id in mn.slots.get("functions").cloned().unwrap_or_default() {
                    if let Some(fn_) = g.get(&id) {
                        if fn_
                            .fields
                            .get("name")
                            .map(|v| v == &air::Value::Str(rest.to_string()))
                            .unwrap_or(false)
                        {
                            return Some(id);
                        }
                    }
                }
            }
        }
    }
    None
}

fn resolve_type_in_graph(g: &air::AirGraph, name: &str) -> Option<String> {
    if g.resolve_rev(name).is_some() {
        return Some(name.to_string());
    }
    for entity in &g.module_entities {
        let module_name = entity.trim_start_matches("module:");
        let want = name
            .strip_prefix(&format!("{module_name}."))
            .unwrap_or(name);
        if let Some(mn) = g.resolve(entity) {
            for id in mn.slots.get("types").cloned().unwrap_or_default() {
                if let Some(t) = g.get(&id) {
                    let tname = match t.fields.get("name") {
                        Some(air::Value::Str(s)) => s.clone(),
                        _ => continue,
                    };
                    if tname == want || tname == name || format!("{module_name}.{tname}") == name {
                        return Some(id);
                    }
                }
            }
        }
    }
    None
}

/// RFC-0005: semantic entity kinds we expose for resolution / applicability.
fn entity_kind(g: &air::AirGraph, rev: &str) -> String {
    match g.get(rev) {
        Some(n) => match n.kind.as_str() {
            "function" => "function".to_string(),
            "type" => match n.fields.get("kind") {
                Some(air::Value::Str(s)) => s.clone(), // record | enum
                _ => "type".to_string(),
            },
            other => other.to_string(),
        },
        None => "unknown".to_string(),
    }
}

/// Collect every resolvable semantic entity (module / function / type) with
/// display name, module, kind. Used by resolve_entity and recovery hints.
fn all_entities(g: &air::AirGraph) -> Vec<(String, String, String, String)> {
    // (id, display, module, kind)
    let mut out: Vec<(String, String, String, String)> = Vec::new();
    for m in &g.module_entities {
        let module_name = m.trim_start_matches("module:").to_string();
        out.push((
            m.clone(),
            module_name.clone(),
            module_name.clone(),
            "module".to_string(),
        ));
        if let Some(mn) = g.resolve(m) {
            for id in mn.slots.get("functions").cloned().unwrap_or_default() {
                if let Some(f) = g.get(&id) {
                    if let Some(air::Value::Str(s)) = f.fields.get("name") {
                        let kind = entity_kind(g, &id);
                        out.push((id, format!("{module_name}.{s}"), module_name.clone(), kind));
                    }
                }
            }
            for id in mn.slots.get("types").cloned().unwrap_or_default() {
                if let Some(t) = g.get(&id) {
                    if let Some(air::Value::Str(s)) = t.fields.get("name") {
                        let kind = entity_kind(g, &id);
                        out.push((id, format!("{module_name}.{s}"), module_name.clone(), kind));
                    }
                }
            }
        }
    }
    out
}

enum ResolveOutcome {
    Exact {
        id: String,
        kind: String,
        module: String,
        display: String,
    },
    Ambiguous {
        candidates: Vec<String>,
    },
    NotFound {
        candidates: Vec<String>,
    },
}

/// RFC-0005 resolve_entity: exact-first, kind/module filters, ambiguity
/// reported as candidates (no silent guessing).
fn resolve_entity_full(
    g: &air::AirGraph,
    name: &str,
    kind_filter: Option<&str>,
    module_filter: Option<&str>,
) -> ResolveOutcome {
    let mut matches: Vec<(String, String, String, String)> = Vec::new();
    // direct revision / entity id first
    if let Some(rev) = g.resolve_rev(name) {
        if g.get(&rev).is_some() {
            let kind = entity_kind(g, &rev);
            let module = g
                .module_entities
                .iter()
                .find(|m| {
                    g.resolve(m)
                        .map(|mn| {
                            let mut all = mn.slots.get("functions").cloned().unwrap_or_default();
                            all.extend(mn.slots.get("types").cloned().unwrap_or_default());
                            all.contains(&rev)
                        })
                        .unwrap_or(false)
                })
                .map(|m| m.trim_start_matches("module:").to_string())
                .unwrap_or_default();
            // Rebuild semantic display from the resolved node's name field,
            // not the input string (opaque entity ids must not leak into
            // display names).
            let display = match g.get(&rev).and_then(|n| n.fields.get("name")) {
                Some(air::Value::Str(s)) => {
                    if module.is_empty() {
                        s.clone()
                    } else {
                        format!("{module}.{s}")
                    }
                }
                _ => name.to_string(),
            };
            matches.push((rev, display, module, kind));
        }
    }
    if matches.is_empty() {
        for (id, display, module, kind) in all_entities(g) {
            let last = display.rsplit('.').next().unwrap_or("");
            let mut ok = display == name || id == name || (name == last);
            if !ok {
                if let Some(rest) = name.strip_prefix(&format!("{module}.")) {
                    ok = rest == last;
                }
            }
            if ok {
                matches.push((id, display, module, kind));
            }
        }
    }
    // kind / module filters
    if let Some(kf) = kind_filter {
        matches.retain(|(_, _, _, k)| {
            k == kf || (kf == "type" && k == "record") || (kf == "type" && k == "enum")
        });
    }
    if let Some(mf) = module_filter {
        matches.retain(|(_, _, m, _)| m == mf);
    }
    match matches.len() {
        1 => {
            let (id, display, module, kind) = matches.pop().unwrap();
            ResolveOutcome::Exact {
                id,
                kind,
                module,
                display,
            }
        }
        n if n > 1 => {
            let mut cands: Vec<String> = matches
                .iter()
                .map(|(_, d, _, k)| format!("{d} ({k})"))
                .collect();
            cands.sort();
            cands.truncate(8);
            ResolveOutcome::Ambiguous { candidates: cands }
        }
        _ => {
            let cands: Vec<String> = all_entities(g)
                .iter()
                .filter(|(_, d, _, _)| d.contains(name) || (name.len() >= 3 && d.starts_with(name)))
                .map(|(_, d, _, _)| d.clone())
                .take(8)
                .collect();
            ResolveOutcome::NotFound { candidates: cands }
        }
    }
}

/// RFC-0005 describe_operation: machine-readable schema from the registry.
fn describe_json(op: &aep::OperationSpec) -> String {
    let args: Vec<String> = op
        .arguments
        .iter()
        .map(|a| {
            format!(
                "{{\"name\":{},\"shape\":{},\"required\":{}}}",
                json_str(a.name),
                json_str(a.schema.shape()),
                if a.required { "true" } else { "false" }
            )
        })
        .collect();
    let kinds: Vec<String> = op.target_kinds.iter().map(|k| json_str(k)).collect();
    let pres: Vec<String> = op.preconditions.iter().map(|p| json_str(p)).collect();
    let aliases: Vec<String> = op.aliases.iter().map(|a| json_str(a)).collect();
    // replace_expression positions are kind-dependent; advertise the complete
    // vocabulary from the shared table (aep::POSITION_NAMES) so discovery
    // and execution cannot drift.
    let positions_extra = if op.name == "replace_expression" {
        format!(
            ",\"expected_positions\":[{}]",
            aep::POSITION_NAMES
                .iter()
                .map(|p| json_str(p))
                .collect::<Vec<_>>()
                .join(",")
        )
    } else {
        String::new()
    };
    format!(
        "{{\"name\":{},\"aliases\":[{}],\"target_kinds\":[{}],\"arguments\":[{}],\"preconditions\":[{}],\"effects\":{},\"example\":{},\"gated\":{}{}}}",
        json_str(op.name),
        aliases.join(","),
        kinds.join(","),
        args.join(","),
        pres.join(","),
        json_str(op.effects),
        json_str(op.example),
        if op.gate.is_some() { "true" } else { "false" },
        positions_extra
    )
}

/// Structured recovery payload for unknown operations / typos.
fn unknown_tool_json(requested: &str, cands: &[&'static aep::OperationSpec]) -> String {
    format!(
        "{{\"requested\":{},\"candidates\":[{}]}}",
        json_str(requested),
        cands
            .iter()
            .map(|c| json_str(c.name))
            .collect::<Vec<_>>()
            .join(",")
    )
}

/// Structured recovery payload for entity resolution failures.
fn resolve_result_json(outcome: &ResolveOutcome, requested: &str) -> String {
    let cands: Vec<String> = match outcome {
        ResolveOutcome::Ambiguous { candidates } => candidates.clone(),
        ResolveOutcome::NotFound { candidates } => candidates.clone(),
        ResolveOutcome::Exact { .. } => Vec::new(),
    };
    format!(
        "{{\"requested\":{},\"candidates\":[{}]}}",
        json_str(requested),
        cands
            .iter()
            .map(|c| json_str(c))
            .collect::<Vec<_>>()
            .join(",")
    )
}

// ---------------------------------------------------------------------------
// RFC-0006 / AEP-0003: Typed Semantic Construction (v0.1)
// ---------------------------------------------------------------------------

/// candidate_bindings 上限（RFC-0006 §5.2 评审第 3 项）。
const CANDIDATE_BINDING_LIMIT: usize = 8;

/// Minimal type_expr node spec (mirrors `type_expr_for` without graph
/// mutation, so construct_expression can validate-then-materialize).
fn type_expr_spec(
    name: &str,
) -> (
    String,
    BTreeMap<String, air::Value>,
    BTreeMap<String, Vec<String>>,
) {
    let mut f = BTreeMap::new();
    let shape = if matches!(
        name,
        "string"
            | "bool"
            | "bytes"
            | "nil"
            | "i64"
            | "i32"
            | "i16"
            | "i8"
            | "u64"
            | "u32"
            | "u16"
            | "u8"
            | "f64"
            | "f32"
    ) {
        "prim"
    } else {
        "named"
    };
    f.insert("shape".to_string(), air::Value::Str(shape.to_string()));
    f.insert("name".to_string(), air::Value::Str(name.to_string()));
    ("type_expr".to_string(), f, BTreeMap::new())
}

fn value_str(v: &air::Value) -> Option<&str> {
    match v {
        air::Value::Str(s) => Some(s),
        _ => None,
    }
}

/// Short type sexpr from a type_expr node (prim -> name, else named name).
fn type_sexpr_short(g: &air::AirGraph, rev: &str) -> String {
    g.get(rev)
        .and_then(|n| n.fields.get("name").and_then(value_str))
        .map(|s| s.to_string())
        .unwrap_or_else(|| "?".to_string())
}

/// Collect visible symbols (name, type) across the transaction: function
/// params, body bindings and fold/loop accumulators. Deterministic (sorted by
/// name, deduped). Bounded by CANDIDATE_BINDING_LIMIT at the caller.
/// Collect visible symbols (name, type, priority) across the transaction.
/// Ranking (RFC-0006 review blocker 4): function params (0) -> body bindings
/// (1) -> fold/loop accumulators (2), then stable name tie-break. This keeps
/// the top candidates semantically reasonable (params are the most stable,
/// module-visible symbols) and fully deterministic.
/// RFC-0007: one resolvable operand (function param / body binding /
/// fold/loop accumulator). `revision` is the CURRENT head at collection time;
/// `scope` is the enclosing function's qualified name.
#[derive(Clone, Debug)]
struct OperandCandidate {
    symbol: String,
    type_name: String,
    revision: String,
    kind: String,
    scope: String,
    priority: u8,
}

fn collect_operands(g: &air::AirGraph) -> Vec<OperandCandidate> {
    let mut out: Vec<OperandCandidate> = Vec::new();
    for me in &g.module_entities {
        let Some(mn) = g.resolve(me) else {
            continue;
        };
        let module_name = mn
            .fields
            .get("name")
            .and_then(value_str)
            .unwrap_or("")
            .to_string();
        let mut stack: Vec<(String, String)> = Vec::new();
        for id in mn
            .slots
            .get("functions")
            .cloned()
            .unwrap_or_default()
            .into_iter()
            .chain(mn.slots.get("tests").cloned().unwrap_or_default())
        {
            stack.push((id, String::new()));
        }
        while let Some((id, carried_scope)) = stack.pop() {
            let Some(n) = g.get(&id) else {
                continue;
            };
            let fn_name = n
                .fields
                .get("name")
                .and_then(value_str)
                .unwrap_or("")
                .to_string();
            // enclosing scope: functions/tests define their own scope; all
            // other nodes (blocks, bindings, ...) inherit the carried scope.
            let scope = if matches!(n.kind.as_str(), "function" | "test") {
                if fn_name.is_empty() {
                    n.entity.clone()
                } else if module_name.is_empty() {
                    fn_name.clone()
                } else {
                    format!("{module_name}.{fn_name}")
                }
            } else if !carried_scope.is_empty() {
                carried_scope.clone()
            } else {
                String::new()
            };
            if matches!(n.kind.as_str(), "function" | "test") {
                for p in n.slots.get("params").cloned().unwrap_or_default() {
                    if let Some(pn) = g.get(&p) {
                        out.push(OperandCandidate {
                            symbol: pn
                                .fields
                                .get("name")
                                .and_then(value_str)
                                .unwrap_or("")
                                .to_string(),
                            type_name: pn
                                .slots
                                .get("type")
                                .and_then(|t| t.first())
                                .map(|r| type_sexpr_short(g, r))
                                .unwrap_or_else(|| "?".to_string()),
                            revision: p.clone(),
                            kind: pn.kind.clone(),
                            scope: scope.clone(),
                            priority: 0,
                        });
                    }
                }
            }
            for children in n.slots.values() {
                for c in children {
                    if let Some(cn) = g.get(c) {
                        let prio = match cn.kind.as_str() {
                            "binding" => 1,
                            "fold" | "loop" => 2,
                            _ => u8::MAX,
                        };
                        if prio != u8::MAX {
                            let (sym, ty) = if cn.kind == "binding" {
                                (
                                    cn.fields
                                        .get("name")
                                        .and_then(value_str)
                                        .unwrap_or("")
                                        .to_string(),
                                    cn.slots
                                        .get("type")
                                        .and_then(|t| t.first())
                                        .map(|r| type_sexpr_short(g, r))
                                        .unwrap_or_else(|| "?".to_string()),
                                )
                            } else {
                                (
                                    cn.fields
                                        .get("acc_name")
                                        .and_then(value_str)
                                        .unwrap_or("")
                                        .to_string(),
                                    cn.slots
                                        .get("acc_type")
                                        .and_then(|t| t.first())
                                        .map(|r| type_sexpr_short(g, r))
                                        .unwrap_or_else(|| "?".to_string()),
                                )
                            };
                            out.push(OperandCandidate {
                                symbol: sym,
                                type_name: ty,
                                revision: c.clone(),
                                kind: cn.kind.clone(),
                                scope: scope.clone(),
                                priority: prio,
                            });
                        }
                        stack.push((c.clone(), scope.clone()));
                    }
                }
            }
        }
    }
    out.sort_by(|a, b| {
        a.priority
            .cmp(&b.priority)
            .then(a.symbol.cmp(&b.symbol))
            .then(a.revision.cmp(&b.revision))
    });
    out
}

/// RFC-0007: semantic operand resolution outcome.
enum OperandResolve {
    Resolved(OperandCandidate),
    NotFound,
    Ambiguous(Vec<OperandCandidate>),
}

/// Resolve `symbol` (optionally scoped) against the CURRENT staged graph.
/// 0 matches -> NotFound; 1 -> Resolved; >1 -> Ambiguous (deterministic order
/// only for display; NEVER a silent pick).
fn resolve_semantic_operand(
    g: &air::AirGraph,
    symbol: &str,
    scope: Option<&str>,
) -> OperandResolve {
    let matches: Vec<OperandCandidate> = collect_operands(g)
        .into_iter()
        .filter(|c| c.symbol == symbol)
        .filter(|c| match scope {
            None => true,
            Some(s) => c.scope == s || c.scope.ends_with(&format!(".{s}")),
        })
        .collect();
    match matches.len() {
        0 => OperandResolve::NotFound,
        1 => OperandResolve::Resolved(matches.into_iter().next().unwrap()),
        _ => OperandResolve::Ambiguous(matches),
    }
}

fn operand_candidate_json(c: &OperandCandidate) -> String {
    format!(
        "{{\"symbol\":{},\"type\":{},\"kind\":{},\"scope\":{},\"current_revision\":{},\"semantic_handle\":{{\"symbol\":{},\"scope\":{},\"expected_type\":{}}}}}",
        json_str(&c.symbol),
        json_str(&c.type_name),
        json_str(&c.kind),
        json_str(&c.scope),
        json_str(&c.revision),
        json_str(&c.symbol),
        json_str(&c.scope),
        json_str(&c.type_name)
    )
}

fn operand_candidates_json(cands: &[OperandCandidate], limit: usize) -> String {
    cands
        .iter()
        .take(limit)
        .map(operand_candidate_json)
        .collect::<Vec<_>>()
        .join(",")
}

/// RFC-0007 §3.3 / review contract 6: `expected_type` is a CONSTRAINT on an
/// already-uniquely-resolved operand, never a search hint or cast.
fn operand_expected_type_check(
    c: &OperandCandidate,
    expected: Option<&str>,
) -> Result<(), (String, String)> {
    if let Some(exp) = expected {
        if !type_matches(exp, &c.type_name) {
            let r = format!(
                "{{\"symbol\":{},\"scope\":{},\"expected\":{},\"actual\":{}}}",
                json_str(&c.symbol),
                json_str(&c.scope),
                json_str(exp),
                json_str(&c.type_name)
            );
            return Err((
                r,
                "E_AEP_OPERAND_TYPE_MISMATCH: expected_type is a constraint".to_string(),
            ));
        }
    }
    Ok(())
}

fn operand_not_found_json(
    parent_kind: &str,
    slot: &str,
    requested: &str,
    cands: &[OperandCandidate],
) -> String {
    format!(
        "{{\"operation\":{},\"argument\":{},\"requested\":{},\"candidates\":[{}]}}",
        json_str(parent_kind),
        json_str(slot),
        json_str(requested),
        operand_candidates_json(cands, 6)
    )
}

fn operand_ambiguous_json(
    parent_kind: &str,
    slot: &str,
    requested: &str,
    cands: &[OperandCandidate],
) -> String {
    format!(
        "{{\"operation\":{},\"argument\":{},\"requested\":{},\"candidates\":[{}]}}",
        json_str(parent_kind),
        json_str(slot),
        json_str(requested),
        operand_candidates_json(cands, 8)
    )
}

fn operand_stale_json(
    parent_kind: &str,
    slot: &str,
    requested: &str,
    entity: &str,
    current: &str,
    cands: &[OperandCandidate],
) -> String {
    format!(
        "{{\"operation\":{},\"argument\":{},\"requested\":{},\"entity\":{},\"current_revision\":{},\"replacement_candidates\":[{}]}}",
        json_str(parent_kind),
        json_str(slot),
        json_str(requested),
        json_str(entity),
        json_str(current),
        operand_candidates_json(cands, 6)
    )
}

/// RFC-0007: a bare revision is STALE iff it resolves to a node that carries
/// an entity whose current head is a different revision. Returns the current
/// head when stale, None otherwise. No silent refresh at the caller.
fn stale_revision(g: &air::AirGraph, rev: &str) -> Option<String> {
    let n = g.get(rev)?;
    if n.entity.is_empty() {
        return None;
    }
    let head = g.heads.get(&n.entity)?;
    if *head != rev {
        Some(head.clone())
    } else {
        None
    }
}

/// RFC-0007: resolve ONE operand reference (bare revision OR semantic handle)
/// against the CURRENT staged transaction, with strict resolution: stale bare
/// revisions are NOT silently refreshed; ambiguity is never auto-resolved.
/// `operation`/`argument` are only used for structured error payloads.
fn resolve_operand_strict(
    s: &air::EditSession,
    operation: &str,
    argument: &str,
    arg: &Json,
) -> Result<String, (String, String)> {
    let rev = match arg {
        Json::Str(handle) => {
            // Layer A: normalization first (quotes / prefixes / entity-path);
            // the strict 0/1/>1 and stale semantics below are unchanged.
            let handle = air::normalize_handle(handle);
            match s.graph.resolve_rev(&handle) {
                None => {
                    let cands = collect_operands(&s.graph);
                    let r = operand_not_found_json(operation, argument, &handle, &cands);
                    // keep the existing E_AEP_ENTITY_NOT_FOUND contract for
                    // bare revisions; OPERAND_NOT_FOUND is for semantic handles.
                    return Err((r, "E_AEP_ENTITY_NOT_FOUND: revision not found".to_string()));
                }
                Some(rev) => {
                    if let Some(current) = stale_revision(&s.graph, &rev) {
                        if let Some(n) = s.graph.get(&rev) {
                            let cands = collect_operands(&s.graph);
                            let r = operand_stale_json(
                                operation, argument, &handle, &n.entity, &current, &cands,
                            );
                            return Err((
                                r,
                                "E_AEP_OPERAND_STALE: revision is stale; no silent refresh"
                                    .to_string(),
                            ));
                        }
                    }
                    rev
                }
            }
        }
        Json::Obj(_) => {
            let symbol = arg.get("symbol").and_then(|v| v.as_str()).ok_or_else(|| {
                let r = construction_type_mismatch_json(
                    operation,
                    argument,
                    "semantic handle",
                    "missing symbol",
                );
                (
                    r,
                    "E_AEP_OPERAND_NOT_FOUND: semantic handle needs symbol".to_string(),
                )
            })?;
            let scope = arg.get("scope").and_then(|v| v.as_str());
            let expected = arg.get("expected_type").and_then(|v| v.as_str());
            match resolve_semantic_operand(&s.graph, symbol, scope) {
                OperandResolve::NotFound => {
                    let cands = collect_operands(&s.graph);
                    let r = operand_not_found_json(operation, argument, symbol, &cands);
                    return Err((
                        r,
                        "E_AEP_OPERAND_NOT_FOUND: no matching operand".to_string(),
                    ));
                }
                OperandResolve::Ambiguous(cands) => {
                    let r = operand_ambiguous_json(operation, argument, symbol, &cands);
                    return Err((
                        r,
                        "E_AEP_OPERAND_AMBIGUOUS: multiple operands match".to_string(),
                    ));
                }
                OperandResolve::Resolved(c) => {
                    operand_expected_type_check(&c, expected)?;
                    c.revision
                }
            }
        }
        _ => {
            let r = construction_type_mismatch_json(
                operation,
                argument,
                "revision | semantic handle",
                "other",
            );
            return Err((
                r,
                "E_AEP_OPERAND_NOT_FOUND: expected revision or semantic handle".to_string(),
            ));
        }
    };
    Ok(rev)
}

/// RFC-0007: resolve a construct child operand, then apply the slot kind
/// check shared with RFC-0006.
fn resolve_operand_child(
    s: &air::EditSession,
    parent_kind: &str,
    slot: &str,
    arg: &Json,
) -> Result<String, (String, String)> {
    let rev = resolve_operand_strict(s, parent_kind, slot, arg)?;
    // slot kind check (shared with RFC-0006)
    let child_kind = s
        .graph
        .get(&rev)
        .map(|n| n.kind.clone())
        .unwrap_or_default();
    let allowed = if parent_kind == "range" {
        air::is_expr_kind(&child_kind)
    } else {
        air::slot_allows_kind(parent_kind, slot, &child_kind)
    };
    if !allowed {
        let r = construction_type_mismatch_json(parent_kind, slot, "expr", &child_kind);
        return Err((
            r,
            "E_AEP_CONSTRUCTION_TYPE_MISMATCH: child kind not allowed in slot".to_string(),
        ));
    }
    Ok(rev)
}

/// RFC-0006 §5.2: bounded candidate_bindings (`total/returned/truncated`),
/// RFC-0007: each item carries `current_revision` + `semantic_handle`.
fn candidate_bindings_json(g: &air::AirGraph, include_items: bool) -> String {
    let all = collect_operands(g);
    let mut seen = std::collections::BTreeSet::new();
    let all: Vec<OperandCandidate> = all
        .into_iter()
        .filter(|c| seen.insert(c.symbol.clone()))
        .collect();
    let total = all.len();
    let items: Vec<String> = all
        .iter()
        .take(CANDIDATE_BINDING_LIMIT)
        .map(|c| {
            format!(
                "{{\"name\":{},\"type\":{},\"kind\":{},\"current_revision\":{},\"semantic_handle\":{{\"symbol\":{},\"scope\":{},\"expected_type\":{}}}}}",
                json_str(&c.symbol),
                json_str(&c.type_name),
                json_str(&c.kind),
                json_str(&c.revision),
                json_str(&c.symbol),
                json_str(&c.scope),
                json_str(&c.type_name)
            )
        })
        .collect();
    let returned = items.len();
    let truncated = total > returned;
    if include_items {
        format!(
            "{{\"items\":[{}],\"total\":{},\"returned\":{},\"truncated\":{}}}",
            items.join(","),
            total,
            returned,
            truncated
        )
    } else {
        format!(
            "{{\"total\":{},\"returned\":{},\"truncated\":{}}}",
            total, returned, truncated
        )
    }
}

fn construction_unknown_kind_json(kind: &str, cands: &[&'static str]) -> String {
    format!(
        "{{\"requested\":{},\"candidates\":[{}]}}",
        json_str(kind),
        cands
            .iter()
            .map(|c| json_str(c))
            .collect::<Vec<_>>()
            .join(",")
    )
}

fn construction_children_json(
    spec: &construction::ConstructionSpec,
    required_only: bool,
) -> String {
    spec.children
        .iter()
        .filter(|c| !required_only || c.required)
        .map(|c| {
            format!(
                "{{\"name\":{},\"role\":{},\"required\":{},\"multiple\":{}}}",
                json_str(c.name),
                json_str(c.role),
                if c.required { "true" } else { "false" },
                if c.multiple { "true" } else { "false" }
            )
        })
        .collect::<Vec<_>>()
        .join(",")
}

/// Structured E_AEP_CONSTRUCTION_INCOMPLETE payload (not free-form text).
fn construction_requirements_json(
    spec: &construction::ConstructionSpec,
    provided: &[String],
    missing: &[&str],
    g: &air::AirGraph,
    result_type: &str,
) -> String {
    let provided_json: Vec<String> = provided.iter().map(|p| json_str(p)).collect();
    let missing_json: Vec<String> = missing.iter().map(|m| json_str(m)).collect();
    format!(
        "{{\"kind\":{},\"required\":[{}],\"provided\":[{}],\"missing\":[{}],\"candidate_bindings\":{},\"result_type\":{}}}",
        json_str(spec.kind),
        construction_children_json(spec, true),
        provided_json.join(","),
        missing_json.join(","),
        candidate_bindings_json(g, true),
        json_str(result_type)
    )
}

/// RFC-0006 §5.2: describe_construction (read-only, concise by default).
fn construction_describe_json(
    spec: &construction::ConstructionSpec,
    g: &air::AirGraph,
    include_candidates: bool,
) -> String {
    let aliases: Vec<String> = spec.aliases.iter().map(|a| json_str(a)).collect();
    let fields: Vec<String> = spec
        .fields
        .iter()
        .map(|f| {
            format!(
                "{{\"name\":{},\"required\":{}}}",
                json_str(f.name),
                if f.required { "true" } else { "false" }
            )
        })
        .collect();
    let required: Vec<String> = spec
        .children
        .iter()
        .filter(|c| c.required)
        .map(|c| {
            format!(
                "{{\"name\":{},\"role\":{},\"multiple\":{}}}",
                json_str(c.name),
                json_str(c.role),
                if c.multiple { "true" } else { "false" }
            )
        })
        .collect();
    let optional: Vec<String> = spec
        .children
        .iter()
        .filter(|c| !c.required)
        .map(|c| {
            format!(
                "{{\"name\":{},\"role\":{},\"multiple\":{}}}",
                json_str(c.name),
                json_str(c.role),
                if c.multiple { "true" } else { "false" }
            )
        })
        .collect();
    format!(
        "{{\"canonical_kind\":{},\"aliases\":[{}],\"fields\":[{}],\"required_children\":[{}],\"optional_children\":[{}],\"result_type_rule\":{},\"candidate_bindings\":{},\"example\":{},\"note\":{}}}",
        json_str(spec.kind),
        aliases.join(","),
        fields.join(","),
        required.join(","),
        optional.join(","),
        json_str(spec.result_type_rule),
        candidate_bindings_json(g, include_candidates),
        json_str(spec.example),
        json_str(spec.note)
    )
}

fn literal_prim_type(g: &air::AirGraph, rev: &str) -> Option<String> {
    let n = g.get(rev)?;
    if n.kind != "literal" {
        return None;
    }
    match n.fields.get("value")? {
        air::Value::Int(_) => Some("i64".to_string()),
        air::Value::Str(s) if s == "nil" => Some("nil".to_string()),
        air::Value::Str(_) => Some("string".to_string()),
        air::Value::Bool(_) => Some("bool".to_string()),
        air::Value::Float(_) => Some("f64".to_string()),
        air::Value::Bytes(_) => Some("bytes".to_string()),
        _ => None,
    }
}

/// Structural type comparison for `expected_type` (RFC-0006 review blocker 1).
///
/// `?` is a wildcard that matches EXACTLY ONE semantic type subtree (a single
/// atom OR a balanced `(...)`/`<...>` group). It cannot swallow tokens across
/// bracket structures: `(result ? string)` matches `result (vec string)
/// string` but never `(vec string)` or `(result string string string)`.
/// Parentheses/angle brackets are grouping syntax, not content.
enum TypeWord {
    Atom(String),
    Group(Vec<TypeWord>),
}

fn type_words(s: &str) -> Vec<TypeWord> {
    let chars: Vec<char> = s.chars().collect();
    let mut out = Vec::new();
    let mut i = 0;
    while i < chars.len() {
        let c = chars[i];
        if c == '(' || c == '<' || c == '[' {
            let close = match c {
                '(' => ')',
                '<' => '>',
                _ => ']',
            };
            let mut depth = 1usize;
            let mut j = i + 1;
            while j < chars.len() && depth > 0 {
                if chars[j] == c {
                    depth += 1;
                } else if chars[j] == close {
                    depth -= 1;
                }
                j += 1;
            }
            let inner: String = chars[i + 1..j.saturating_sub(1)].iter().collect();
            out.push(TypeWord::Group(type_words(&inner)));
            i = j;
        } else if c.is_alphanumeric() || c == '_' || c == '.' || c == '?' {
            let mut j = i;
            while j < chars.len()
                && (chars[j].is_alphanumeric()
                    || chars[j] == '_'
                    || chars[j] == '.'
                    || chars[j] == '?')
            {
                j += 1;
            }
            out.push(TypeWord::Atom(chars[i..j].iter().collect()));
            i = j;
        } else {
            i += 1;
        }
    }
    out
}

fn words_compatible(e: &TypeWord, a: &TypeWord) -> bool {
    match (e, a) {
        (TypeWord::Atom(x), TypeWord::Atom(y)) => x == y || x == "?" || y == "?",
        (TypeWord::Atom(x), _) => x == "?",
        (_, TypeWord::Atom(y)) => y == "?",
        (TypeWord::Group(eg), TypeWord::Group(ag)) => {
            eg.len() == ag.len()
                && eg
                    .iter()
                    .zip(ag.iter())
                    .all(|(x, y)| words_compatible(x, y))
        }
    }
}

fn type_matches(expected: &str, actual: &str) -> bool {
    // Normalize so `result ? string` and `(result string string)` share one
    // structure: a fully parenthesized input collapses to its inner group.
    fn as_word(s: &str) -> TypeWord {
        let mut w = type_words(s);
        if w.len() == 1 {
            w.pop().unwrap()
        } else {
            TypeWord::Group(w)
        }
    }
    words_compatible(&as_word(expected), &as_word(actual))
}

/// RFC-0006 v0.1 minimal result-type derivation for constructed kinds.
/// Kinds whose result type is not statically derivable return None (the
/// expected_type check is skipped for them; the rule is advertised in
/// describe_construction).
fn construction_result_type(
    spec: &construction::ConstructionSpec,
    g: &air::AirGraph,
    child_revs: &BTreeMap<String, Vec<String>>,
    fields: &BTreeMap<String, air::Value>,
) -> Option<String> {
    match spec.kind {
        "not" => Some("bool".to_string()),
        "veclit" => child_revs
            .get("elem_type")
            .and_then(|v| v.first())
            .map(|r| type_sexpr_short(g, r))
            .map(|t| format!("vec {t}")),
        "fold" => child_revs
            .get("acc_type")
            .and_then(|v| v.first())
            .map(|r| type_sexpr_short(g, r)),
        "record" | "record_update" => fields
            .get("type")
            .and_then(value_str)
            .map(|t| t.to_string()),
        "ok" => {
            let v = child_revs
                .get("value")
                .and_then(|v| v.first())
                .and_then(|r| literal_prim_type(g, r))?;
            Some(format!("result {v} ?"))
        }
        "err" => {
            let v = child_revs
                .get("value")
                .and_then(|v| v.first())
                .and_then(|r| literal_prim_type(g, r))?;
            Some(format!("result ? {v}"))
        }
        "range" => Some("range (fold sub-form)".to_string()),
        _ => None,
    }
}

fn construction_type_mismatch_json(kind: &str, slot: &str, expected: &str, actual: &str) -> String {
    format!(
        "{{\"kind\":{},\"argument\":{},\"expected\":{},\"actual\":{}}}",
        json_str(kind),
        json_str(slot),
        json_str(expected),
        json_str(actual)
    )
}

/// RFC-0006 §5.3: `construct_expression` (mutation).
///
/// Contract: canonicalize kind -> resolve spec -> validate required fields ->
/// resolve child revisions -> type-check children -> check expected_type ->
/// validate invariants -> materialize ALL nodes in ONE atomic staged commit.
/// Any failure returns before materialization (zero transactional side
/// effects, RFC-0006 §6 invariant 7).
fn handle_construct_expression(
    s: &mut air::EditSession,
    req: &Json,
) -> Result<(String, String), (String, String)> {
    let kind = req.get("kind").and_then(|v| v.as_str()).unwrap_or("");

    // no-source-string guard (RFC-0006 §6.5).
    if req.get("source").is_some() {
        let r = format!(
            "{{\"requested_kind\":{},\"error\":\"source-string construction is forbidden; use typed children\"}}",
            json_str(kind)
        );
        return Err((
            r,
            "E_AEP_CONSTRUCTION_NO_SOURCE: source-string construction forbidden".to_string(),
        ));
    }

    let Some(spec) = construction::construction_spec(kind) else {
        let cands = construction::closest_kind(kind, 6);
        let r = construction_unknown_kind_json(kind, &cands);
        return Err((
            r,
            "E_AEP_CONSTRUCTION_UNKNOWN_KIND: unknown construction kind".to_string(),
        ));
    };

    let expected = req
        .get("expected_type")
        .and_then(|v| v.as_str())
        .map(|x| x.to_string());

    // required children presence check (structured incomplete recovery).
    let provided: Vec<String> = spec
        .children
        .iter()
        .filter(|c| req.get(c.name).is_some())
        .map(|c| c.name.to_string())
        .collect();
    let missing: Vec<&str> = spec
        .children
        .iter()
        .filter(|c| c.required && req.get(c.name).is_none())
        .map(|c| c.name)
        .collect();
    if !missing.is_empty() {
        let r = construction_requirements_json(spec, &provided, &missing, &s.graph, "unknown");
        return Err((
            r,
            "E_AEP_CONSTRUCTION_INCOMPLETE: missing required children".to_string(),
        ));
    }

    // string fields.
    let mut fields = BTreeMap::new();
    for f in &spec.fields {
        match req.get(f.name).and_then(|v| v.as_str()) {
            Some(v) => {
                fields.insert(f.name.to_string(), air::Value::Str(v.to_string()));
            }
            None if f.required => {
                let r =
                    construction_requirements_json(spec, &provided, &[f.name], &s.graph, "unknown");
                return Err((
                    r,
                    "E_AEP_CONSTRUCTION_INCOMPLETE: missing field".to_string(),
                ));
            }
            None => {}
        }
    }

    // Resolve child revisions / build child node specs. All validation
    // happens here, BEFORE any node is materialized.
    let mut pending: Vec<air::NodeSpec> = Vec::new();
    let mut slot_revs: BTreeMap<String, Vec<String>> = BTreeMap::new();
    for c in &spec.children {
        let Some(arg) = req.get(c.name) else {
            continue;
        };
        match c.role {
            "expr" => {
                // RFC-0007: children accept a bare revision OR a semantic
                // handle; resolution is strict (no silent stale refresh, no
                // silent ambiguity pick) and happens against the CURRENT
                // staged transaction graph.
                if c.multiple {
                    let arr = match arg {
                        Json::Arr(a) => a,
                        _ => {
                            let r = construction_type_mismatch_json(
                                spec.kind,
                                c.name,
                                "json array of revisions",
                                "non-array",
                            );
                            return Err((
                                r,
                                "E_AEP_CONSTRUCTION_TYPE_MISMATCH: expected a json array"
                                    .to_string(),
                            ));
                        }
                    };
                    let mut revs = Vec::new();
                    for item in arr {
                        revs.push(resolve_operand_child(s, spec.kind, c.name, item)?);
                    }
                    slot_revs.insert(c.name.to_string(), revs);
                } else {
                    let rev = resolve_operand_child(s, spec.kind, c.name, arg)?;
                    slot_revs.insert(c.name.to_string(), vec![rev]);
                }
            }
            "type_expr" => {
                let tname = arg.as_str().ok_or_else(|| {
                    let r = construction_type_mismatch_json(
                        spec.kind,
                        c.name,
                        "type string",
                        "non-string",
                    );
                    (
                        r,
                        "E_AEP_CONSTRUCTION_TYPE_MISMATCH: expected a type string".to_string(),
                    )
                })?;
                let (k, f, sl) = type_expr_spec(tname);
                let r = s.graph.compute_revision(&k, &f, &sl);
                pending.push((k, f, sl));
                slot_revs.insert(c.name.to_string(), vec![r]);
            }
            "record_field" | "update_field" | "case" => {
                let arr = match arg {
                    Json::Arr(a) => a,
                    _ => {
                        let r = construction_type_mismatch_json(
                            spec.kind,
                            c.name,
                            "json array of child objects",
                            "non-array",
                        );
                        return Err((
                            r,
                            "E_AEP_CONSTRUCTION_TYPE_MISMATCH: expected a json array".to_string(),
                        ));
                    }
                };
                let mut revs = Vec::new();
                for obj in arr {
                    let (k, f, sl) = if c.role == "case" {
                        let variant =
                            obj.get("variant").and_then(|v| v.as_str()).ok_or_else(|| {
                                let r = construction_type_mismatch_json(
                                    c.role, "variant", "string", "missing",
                                );
                                (r, "E_AEP_CONSTRUCTION_INCOMPLETE: case.variant".to_string())
                            })?;
                        let body = obj.get("body").and_then(|v| v.as_str()).ok_or_else(|| {
                            let r = construction_type_mismatch_json(
                                c.role, "body", "revision", "missing",
                            );
                            (r, "E_AEP_CONSTRUCTION_INCOMPLETE: case.body".to_string())
                        })?;
                        let brev = s.resolve_current(body).map_err(|e| {
                            let r = format!(
                                "{{\"kind\":\"case\",\"argument\":\"body\",\"requested\":{}}}",
                                json_str(body)
                            );
                            (r, e)
                        })?;
                        let bkind = s
                            .graph
                            .get(&brev)
                            .map(|n| n.kind.clone())
                            .unwrap_or_default();
                        if !air::slot_allows_kind("case", "body", &bkind) {
                            let r = construction_type_mismatch_json("case", "body", "expr", &bkind);
                            return Err((
                                r,
                                "E_AEP_CONSTRUCTION_TYPE_MISMATCH: case body not an expression"
                                    .to_string(),
                            ));
                        }
                        let mut f = BTreeMap::new();
                        f.insert("variant".to_string(), air::Value::Str(variant.to_string()));
                        let mut sl = BTreeMap::new();
                        sl.insert("body".to_string(), vec![brev]);
                        ("case".to_string(), f, sl)
                    } else {
                        let name = obj.get("name").and_then(|v| v.as_str()).ok_or_else(|| {
                            let r = construction_type_mismatch_json(
                                c.role, "name", "string", "missing",
                            );
                            (r, "E_AEP_CONSTRUCTION_INCOMPLETE: child.name".to_string())
                        })?;
                        let value = obj.get("value").and_then(|v| v.as_str()).ok_or_else(|| {
                            let r = construction_type_mismatch_json(
                                c.role, "value", "revision", "missing",
                            );
                            (r, "E_AEP_CONSTRUCTION_INCOMPLETE: child.value".to_string())
                        })?;
                        let vrev = s.resolve_current(value).map_err(|e| {
                            let r = format!(
                                "{{\"kind\":{},\"argument\":{},\"requested\":{}}}",
                                json_str(c.role),
                                "value",
                                json_str(value)
                            );
                            (r, e)
                        })?;
                        let vkind = s
                            .graph
                            .get(&vrev)
                            .map(|n| n.kind.clone())
                            .unwrap_or_default();
                        if !air::slot_allows_kind(c.role, "value", &vkind) {
                            let r =
                                construction_type_mismatch_json(c.role, "value", "expr", &vkind);
                            return Err((
                                r,
                                "E_AEP_CONSTRUCTION_TYPE_MISMATCH: child value not an expression"
                                    .to_string(),
                            ));
                        }
                        let mut f = BTreeMap::new();
                        f.insert("name".to_string(), air::Value::Str(name.to_string()));
                        let mut sl = BTreeMap::new();
                        sl.insert("value".to_string(), vec![vrev]);
                        (c.role.to_string(), f, sl)
                    };
                    let r = s.graph.compute_revision(&k, &f, &sl);
                    pending.push((k, f, sl));
                    revs.push(r);
                }
                slot_revs.insert(c.name.to_string(), revs);
            }
            _ => {}
        }
    }

    // range is a fold sub-form, not a standalone AIR node: validate and
    // return the sub-form (zero side effects by construction).
    if spec.kind == "range" {
        let start = slot_revs
            .get("range_start")
            .and_then(|v| v.first())
            .cloned()
            .unwrap_or_default();
        let end = slot_revs
            .get("range_end")
            .and_then(|v| v.first())
            .cloned()
            .unwrap_or_default();
        let r = format!(
            "{{\"kind\":\"range\",\"range_start\":{},\"range_end\":{},\"result_type\":{},\"note\":{}}}",
            json_str(&start),
            json_str(&end),
            json_str("range (fold sub-form)"),
            json_str("pass range_start/range_end to construct_expression kind=fold")
        );
        return Ok((r, "ok".to_string()));
    }

    // main node (last in the batch; dependency order children -> parent).
    let mut slots = BTreeMap::new();
    for c in &spec.children {
        if let Some(revs) = slot_revs.get(c.name) {
            slots.insert(c.name.to_string(), revs.clone());
        }
    }
    let main_kind = spec.kind.to_string();
    // expected_type check (only for statically derivable result types).
    let result_type = construction_result_type(spec, &s.graph, &slot_revs, &fields);
    pending.push((main_kind.clone(), fields, slots));
    if let (Some(exp), Some(actual)) = (expected, result_type.clone()) {
        if !type_matches(&exp, &actual) {
            let r = format!(
                "{{\"kind\":{},\"argument\":\"expected_type\",\"expected\":{},\"actual\":{}}}",
                json_str(&main_kind),
                json_str(&exp),
                json_str(&actual)
            );
            return Err((
                r,
                "E_AEP_CONSTRUCTION_TYPE_MISMATCH: expected_type does not match constructed result type".to_string(),
            ));
        }
    }

    let rev = s.create_nodes_atomic(pending).map_err(|e| {
        let r = format!("{{\"kind\":{}}}", json_str(&main_kind));
        (r, e)
    })?;
    let result = match result_type {
        Some(t) => format!(
            "{{\"revision\":{},\"kind\":{},\"result_type\":{}}}",
            json_str(&rev),
            json_str(&main_kind),
            json_str(&t)
        ),
        None => format!(
            "{{\"revision\":{},\"kind\":{},\"result_type\":null}}",
            json_str(&rev),
            json_str(&main_kind)
        ),
    };
    Ok((result, "ok".to_string()))
}

fn value_short(v: &air::Value) -> String {
    match v {
        air::Value::Str(s) => {
            if s.len() > 48 {
                format!("{}...", &s[..48])
            } else {
                s.clone()
            }
        }
        air::Value::Int(i) => i.to_string(),
        air::Value::UInt(u) => u.to_string(),
        air::Value::Float(x) => x.to_string(),
        air::Value::Bool(b) => b.to_string(),
        air::Value::Bytes(b) => b
            .iter()
            .take(12)
            .map(|x| format!("{x:02x}"))
            .collect::<Vec<_>>()
            .join(""),
        air::Value::Names(ns) => ns.join(","),
    }
}

fn entity_candidates(g: &air::AirGraph, name: &str) -> String {
    let mut names: Vec<String> = Vec::new();
    for m in &g.module_entities {
        let mn = m.trim_start_matches("module:").to_string();
        names.push(mn.clone());
        if let Some(node) = g.resolve(m) {
            for id in node.slots.get("functions").cloned().unwrap_or_default() {
                if let Some(f) = g.get(&id) {
                    if let Some(air::Value::Str(s)) = f.fields.get("name") {
                        names.push(format!("{mn}.{s}"));
                    }
                }
            }
            for id in node.slots.get("types").cloned().unwrap_or_default() {
                if let Some(t) = g.get(&id) {
                    if let Some(air::Value::Str(s)) = t.fields.get("name") {
                        names.push(format!("{mn}.{s}"));
                    }
                }
            }
        }
    }
    let hits: Vec<&String> = names
        .iter()
        .filter(|c| c.contains(name) || (name.len() >= 3 && c.starts_with(name)))
        .take(6)
        .collect();
    hits.iter()
        .map(|s| s.as_str())
        .collect::<Vec<_>>()
        .join(", ")
}

fn not_found(g: &air::AirGraph, name: &str) -> String {
    format!(
        "E_AEP_ENTITY_NOT_FOUND: {name}; candidates={}",
        entity_candidates(g, name)
    )
}

/// Layer A: canonical handle resolution for AEP ops. Returns the canonical
/// entity id on exactly one match of an expected kind; otherwise returns the
/// structured (payload, message) to respond with (AMBIGUOUS / KIND_MISMATCH).
/// NotFound -> Err(None) so the caller falls through to its existing
/// not-found path with candidates.
fn canonical_entity_rev(
    g: &air::AirGraph,
    op: &str,
    arg: &str,
    requested: &str,
    expected: &[&str],
) -> Result<String, Option<(String, String)>> {
    match air::resolve_canonical(g, requested, expected) {
        air::CanonicalOutcome::Resolved(entity) => Ok(entity),
        air::CanonicalOutcome::Ambiguous(cands) => {
            let r = format!(
                "{{\"operation\":{},\"argument\":{},\"requested\":{},\"candidates\":[{}]}}",
                json_str(op),
                json_str(arg),
                json_str(requested),
                cands
                    .iter()
                    .map(|c| json_str(c))
                    .collect::<Vec<_>>()
                    .join(",")
            );
            Err(Some((
                r,
                "E_AEP_ENTITY_AMBIGUOUS: multiple entities match".to_string(),
            )))
        }
        air::CanonicalOutcome::WrongKind {
            entity,
            kind,
            expected: exp,
        } => {
            let r = format!(
                "{{\"operation\":{},\"argument\":{},\"requested\":{},\"entity\":{},\"kind\":{},\"expected\":{}}}",
                json_str(op),
                json_str(arg),
                json_str(requested),
                json_str(&entity),
                json_str(&kind),
                json_str(&exp)
            );
            Err(Some((
                r,
                "E_AEP_ENTITY_KIND_MISMATCH: entity exists with a different kind".to_string(),
            )))
        }
        air::CanonicalOutcome::NotFound => {
            // Generic "any" inspection (e.g. inspect_entity) must still accept
            // anonymous node revisions directly.
            if expected.contains(&"any") && g.resolve_rev(requested).is_some() {
                Ok(requested.to_string())
            } else {
                Err(None)
            }
        }
    }
}

fn body_tree(g: &air::AirGraph, rev: &str, depth: usize, budget: &mut usize) -> String {
    if depth > 8 || *budget > 400 {
        return "...".to_string();
    }
    *budget += 1;
    let Some(n) = g.get(rev) else {
        return "?".to_string();
    };
    let mut parts = vec![n.kind.clone()];
    for key in ["name", "value", "type"] {
        if let Some(v) = n.fields.get(key) {
            parts.push(format!("{key}={}", value_short(v)));
        }
    }
    parts.push(format!("rev={rev}"));
    let mut kids = Vec::new();
    for (slot, children) in &n.slots {
        for c in children {
            kids.push(format!("{slot}:({})", body_tree(g, c, depth + 1, budget)));
        }
    }
    if !kids.is_empty() {
        parts.push(kids.join(" "));
    }
    format!("({})", parts.join(" "))
}

// ---------------------------------------------------------------------------
// RFC-0002/AEP-0001: schema change impact（只读查询 + 批量诊断）
// ---------------------------------------------------------------------------

fn node_str_field(n: &air::AirNode, key: &str) -> Option<String> {
    match n.fields.get(key) {
        Some(air::Value::Str(s)) => Some(s.clone()),
        _ => None,
    }
}

fn type_field_names(g: &air::AirGraph, type_rev: &str) -> Vec<String> {
    let mut out = Vec::new();
    if let Some(tn) = g.get(type_rev) {
        for f in tn.slots.get("fields").cloned().unwrap_or_default() {
            if let Some(fn_) = g.get(&f) {
                if let Some(n) = node_str_field(fn_, "name") {
                    out.push(n);
                }
            }
        }
    }
    out
}

fn find_type_entity(
    g: &air::AirGraph,
    entity: &str,
) -> Result<(String, String, String, String), String> {
    let target = entity.strip_prefix("type:").unwrap_or(entity);
    let (mod_name, type_name) = match target.rfind('.') {
        Some(i) => (Some(target[..i].to_string()), target[i + 1..].to_string()),
        None => (None, target.to_string()),
    };
    for me in &g.module_entities {
        let mname = me.trim_start_matches("module:").to_string();
        if let Some(m) = &mod_name {
            if m != &mname {
                continue;
            }
        }
        if let Some(mn) = g.resolve(me) {
            for t in mn.slots.get("types").cloned().unwrap_or_default() {
                if let Some(tn) = g.get(&t) {
                    if node_str_field(tn, "name").as_deref() == Some(&type_name) {
                        return Ok((me.clone(), t, mname, type_name));
                    }
                }
            }
        }
    }
    Err(format!("E_AEP_ENTITY_NOT_FOUND: type {target}"))
}

fn enclosing_fn_name(g: &air::AirGraph, fn_e: &str) -> String {
    if fn_e.is_empty() {
        return String::new();
    }
    let Some(fn_) = g.resolve(fn_e) else {
        return fn_e.to_string();
    };
    let n = node_str_field(fn_, "name").unwrap_or_default();
    // fn_entity 形如 "entity:build.engine.load_manifests"; 取其模块前缀
    let e = fn_e.trim_start_matches("entity:");
    let mod_part = e
        .rsplit_once('.')
        .map(|(m, _)| m.to_string())
        .unwrap_or_default();
    if mod_part.is_empty() {
        n
    } else {
        format!("{mod_part}.{n}")
    }
}

/// change-impact 查询：返回依赖该 type 的 constructors / record_updates /
/// field_accesses / functions / tests / 跨模块引用（结构化 revision）。
fn change_impact(g: &air::AirGraph, entity: &str) -> Result<String, String> {
    let (_, type_rev, mod_name, type_name) = find_type_entity(g, entity)?;
    let fields = type_field_names(g, &type_rev);
    let qualified = if mod_name.is_empty() {
        type_name.clone()
    } else {
        format!("{mod_name}.{type_name}")
    };
    let q_clone = qualified.clone();
    let tn_clone = type_name.clone();
    let type_matches = move |n: &air::AirNode| -> bool {
        match node_str_field(n, "type") {
            Some(t) => t == q_clone || t == tn_clone,
            None => false,
        }
    };
    let mut constructors: Vec<Json> = Vec::new();
    let mut record_updates: Vec<Json> = Vec::new();
    let mut field_accesses: Vec<Json> = Vec::new();
    let mut type_refs: Vec<Json> = Vec::new();
    let mut fn_uses: std::collections::BTreeSet<String> = std::collections::BTreeSet::new();
    let mut tests: Vec<Json> = Vec::new();
    let mut cross_modules: std::collections::BTreeSet<String> = std::collections::BTreeSet::new();
    for (rev, kind, fn_e, test_e) in air::walk_expressions(g) {
        let Some(n) = g.get(&rev) else { continue };
        let fn_name = enclosing_fn_name(g, &fn_e);
        // 只对"确实使用目标类型"的表达式收集跨模块引用（避免 false positive）：
        // mod_part 先计算，插入推迟到 `used` 判定之后。
        let mod_part = if fn_name.is_empty() {
            String::new()
        } else {
            fn_name
                .rsplit_once('.')
                .map(|(m, _)| m.to_string())
                .unwrap_or_default()
        };
        let used = match kind.as_str() {
            "record" if type_matches(n) => {
                constructors.push(Json::Obj(std::collections::BTreeMap::from([
                    ("revision".to_string(), Json::Str(rev.clone())),
                    ("function".to_string(), Json::Str(fn_name.clone())),
                ])));
                true
            }
            "record_update" if type_matches(n) => {
                record_updates.push(Json::Obj(std::collections::BTreeMap::from([
                    ("revision".to_string(), Json::Str(rev.clone())),
                    ("function".to_string(), Json::Str(fn_name.clone())),
                ])));
                true
            }
            "field" => {
                let fname = node_str_field(n, "name").unwrap_or_default();
                if fields.contains(&fname) {
                    field_accesses.push(Json::Obj(std::collections::BTreeMap::from([
                        ("revision".to_string(), Json::Str(rev.clone())),
                        ("field".to_string(), Json::Str(fname)),
                        ("function".to_string(), Json::Str(fn_name.clone())),
                    ])));
                    true
                } else {
                    false
                }
            }
            "type_expr" => {
                let tn = node_str_field(n, "name").unwrap_or_default();
                if tn == qualified || tn == type_name {
                    type_refs.push(Json::Obj(std::collections::BTreeMap::from([
                        ("revision".to_string(), Json::Str(rev.clone())),
                        ("function".to_string(), Json::Str(fn_name.clone())),
                    ])));
                    true
                } else {
                    false
                }
            }
            _ => false,
        };
        if used {
            if !fn_name.is_empty() {
                fn_uses.insert(fn_name);
                if !mod_part.is_empty() && mod_part != mod_name {
                    cross_modules.insert(mod_part);
                }
            }
            if !test_e.is_empty() {
                tests.push(Json::Obj(std::collections::BTreeMap::from([
                    ("revision".to_string(), Json::Str(rev.clone())),
                    ("test".to_string(), Json::Str(test_e)),
                ])));
            }
        }
    }
    let out = Json::Obj(std::collections::BTreeMap::from([
        ("entity".to_string(), Json::Str(format!("type:{qualified}"))),
        (
            "record_fields".to_string(),
            Json::Arr(fields.into_iter().map(Json::Str).collect()),
        ),
        ("constructors".to_string(), Json::Arr(constructors)),
        ("record_updates".to_string(), Json::Arr(record_updates)),
        ("field_accesses".to_string(), Json::Arr(field_accesses)),
        ("type_references".to_string(), Json::Arr(type_refs)),
        (
            "functions_using_type".to_string(),
            Json::Arr(fn_uses.into_iter().map(Json::Str).collect()),
        ),
        ("tests".to_string(), Json::Arr(tests)),
        (
            "cross_module_references".to_string(),
            Json::Arr(cross_modules.into_iter().map(Json::Str).collect()),
        ),
    ]));
    Ok(render_json(&out))
}

/// 批量 schema 缺口诊断：一次列出该 record 类型所有缺 required field 的
/// constructor（E_RECORD_SCHEMA_INCOMPLETE 结构化摘要）。
fn schema_gaps(g: &air::AirGraph, entity: &str) -> Result<String, String> {
    let (_, type_rev, mod_name, type_name) = find_type_entity(g, entity)?;
    let fields = type_field_names(g, &type_rev);
    let qualified = if mod_name.is_empty() {
        type_name.clone()
    } else {
        format!("{mod_name}.{type_name}")
    };
    let mut affected: Vec<Json> = Vec::new();
    for (rev, kind, fn_e, _) in air::walk_expressions(g) {
        if kind != "record" {
            continue;
        }
        let Some(n) = g.get(&rev) else { continue };
        let t = node_str_field(n, "type").unwrap_or_default();
        if t != qualified && t != type_name {
            continue;
        }
        let present: std::collections::HashSet<String> = n
            .slots
            .get("fields")
            .cloned()
            .unwrap_or_default()
            .iter()
            .filter_map(|f| g.get(f).and_then(|fn_| node_str_field(fn_, "name")))
            .collect();
        let missing: Vec<String> = fields
            .iter()
            .filter(|f| !present.contains(*f))
            .cloned()
            .collect();
        if !missing.is_empty() {
            affected.push(Json::Obj(std::collections::BTreeMap::from([
                ("revision".to_string(), Json::Str(rev.clone())),
                (
                    "function".to_string(),
                    Json::Str(enclosing_fn_name(g, &fn_e)),
                ),
                (
                    "missing_fields".to_string(),
                    Json::Arr(missing.into_iter().map(Json::Str).collect()),
                ),
            ])));
        }
    }
    let out = Json::Obj(std::collections::BTreeMap::from([
        (
            "diagnostic".to_string(),
            Json::Str("E_RECORD_SCHEMA_INCOMPLETE".to_string()),
        ),
        ("record_type".to_string(), Json::Str(qualified.clone())),
        ("affected_constructors".to_string(), Json::Arr(affected)),
        (
            "suggested_action".to_string(),
            Json::Str(format!("inspect_change_impact(entity=type:{qualified})")),
        ),
    ]));
    Ok(render_json(&out))
}

fn begin_agent_session(
    file: &str,
    session: &mut Option<air::EditSession>,
    base_graph: &mut Option<air::AirGraph>,
    real_dir: &mut PathBuf,
) -> Result<String, String> {
    if file.is_empty() {
        return Err("begin_transaction requires 'project'".to_string());
    }
    let proj = project::load_project(Path::new(file))?;
    let project_dir = Path::new(file).parent().unwrap_or(Path::new("."));
    let has_authoritative = project_dir
        .join(air::AIR_STORE_DIR)
        .join("current")
        .exists();
    let g = if has_authoritative {
        air::load_authoritative(project_dir)?
    } else {
        project_to_air(&proj)?.0
    };
    let actual = g.semantic_hash();
    *real_dir = project_dir.to_path_buf();
    *base_graph = Some(g.clone());
    *session = Some(air::EditSession::begin(g, actual.clone()));
    Ok(actual)
}

fn flag_value(rest: &[String], flag: &str) -> Option<String> {
    let mut i = 0;
    while i < rest.len() {
        if rest[i] == flag && i + 1 < rest.len() {
            return Some(rest[i + 1].clone());
        }
        i += 1;
    }
    None
}

fn read_air_verify(path: &Path) -> Result<air::AirGraph, String> {
    let data = std::fs::read(path).map_err(|e| format!("cannot read {}: {e}", path.display()))?;
    let g = air::graph_from_bytes(&data)?;
    for n in g.nodes.values() {
        let canonical = air::canonical_encoding(&n.kind, &n.fields, &n.slots);
        let expect = air::hex(&{
            use sha2::Digest;
            let mut h = sha2::Sha256::new();
            h.update(&canonical);
            h.finalize()
        });
        if expect != n.revision {
            return Err(format!(
                "integrity mismatch: node {} (kind {}) stored id does not match content",
                n.revision, n.kind
            ));
        }
    }
    let problems = g.verify();
    if problems.is_empty() {
        Ok(g)
    } else {
        Err(format!("AIR verify failed: {}", problems.join("; ")))
    }
}

// ---------------------------------------------------------------------------
// AEP edit protocol (JSON lines on stdin)
// ---------------------------------------------------------------------------

fn cmd_manifest(rest: &[String]) -> i32 {
    let a = parse_args(rest);
    let file = match a.file {
        Some(f) => f,
        None => {
            usage();
            return 2;
        }
    };
    match load(Path::new(&file), a.json) {
        Ok(m) => {
            println!("{}", manifest::generate(&m));
            0
        }
        Err(()) => 1,
    }
}

fn usage() {
    eprintln!("usage: alva <check|build|run|manifest|project|impact|air|edit|agent|mcp|hole|view|capabilities|doctor> [arguments]");
    eprintln!("       alva --version");
}

fn parse_args(rest: &[String]) -> CliArgs {
    let mut out = CliArgs {
        file: None,
        json: false,
        target: "native".to_string(),
        run_tests: false,
        run_benches: false,
        release: false,
        out_dir: "out".to_string(),
    };
    let mut i = 0;
    while i < rest.len() {
        match rest[i].as_str() {
            "--json" => out.json = true,
            "--target" => {
                i += 1;
                if i < rest.len() {
                    out.target = rest[i].clone();
                }
            }
            "--test" => out.run_tests = true,
            "--bench" => out.run_benches = true,
            "--release" => out.release = true,
            "--out-dir" => {
                i += 1;
                if i < rest.len() {
                    out.out_dir = rest[i].clone();
                }
            }
            _s if rest[i].starts_with('-') => {}
            s => out.file = Some(s.to_string()),
        }
        i += 1;
    }
    out
}

fn load(path: &Path, json: bool) -> Result<ast::Module, ()> {
    let limits = s_expr::Limits::from_env();
    if let Ok(meta) = std::fs::metadata(path) {
        if meta.len() as usize > limits.max_source_bytes {
            let d = diag::Diag::error(format!(
                "source file is {} bytes, exceeding limit of {} bytes",
                meta.len(),
                limits.max_source_bytes
            ))
            .with_code("E_PARSE_004");
            if json {
                print_diags(&[d], true);
            } else {
                eprintln!("{}", d.render());
            }
            return Err(());
        }
    }
    let text = match std::fs::read_to_string(path) {
        Ok(t) => t,
        Err(e) => {
            eprintln!(
                "{}",
                diag::Diag::error(format!("cannot read {}: {e}", path.display())).render()
            );
            return Err(());
        }
    };
    let tree = match s_expr::parse_with_limits(&text, &limits) {
        Ok(t) => t,
        Err(e) => {
            let d = diag::Diag::error_at(e.span(), e.message()).with_code(e.code());
            if json {
                print_diags(&[d], true);
            } else {
                eprintln!("{}", d.render());
            }
            return Err(());
        }
    };
    let module = match ast::from_tree(&tree) {
        Ok(m) => m,
        Err(ds) => {
            print_diags(&ds, json);
            return Err(());
        }
    };
    let ds = check::check(&module);
    let has_error = ds.iter().any(|d| d.severity == "error");
    print_diags(&ds, json);
    if has_error {
        Err(())
    } else {
        Ok(module)
    }
}

fn print_diags(ds: &[diag::Diag], json: bool) {
    if json {
        let items: Vec<String> = ds.iter().map(|d| d.to_json()).collect();
        println!("[{}]", items.join(","));
    } else {
        for d in ds {
            eprintln!("{}", d.render());
        }
    }
}

fn cmd_check(rest: &[String]) -> i32 {
    let a = parse_args(rest);
    let file = match a.file {
        Some(f) => f,
        None => {
            usage();
            return 2;
        }
    };
    match load(Path::new(&file), a.json) {
        Ok(_) => {
            if !a.json {
                println!("ok: {file} (parsed and checked)");
            }
            0
        }
        Err(()) => 1,
    }
}

fn write_generated(gen: &codegen::Generated, out_dir: &str) -> Result<PathBuf, ()> {
    let out_root = PathBuf::from(out_dir).join(&gen.crate_name);
    let src_dir = out_root.join("src");
    if let Err(e) = std::fs::create_dir_all(&src_dir) {
        eprintln!("error: cannot create output dir: {e}");
        return Err(());
    }
    let rs_name = if gen.is_binary { "main.rs" } else { "lib.rs" };
    if let Err(e) = std::fs::write(src_dir.join(rs_name), &gen.source_rs) {
        eprintln!("error: cannot write generated source: {e}");
        return Err(());
    }
    if let Err(e) = std::fs::write(out_root.join("Cargo.toml"), &gen.cargo_toml) {
        eprintln!("error: cannot write Cargo.toml: {e}");
        return Err(());
    }
    println!("generated {}", out_root.join(rs_name).display());
    Ok(out_root)
}

fn build_crate(
    out_root: &Path,
    target: &str,
    run_tests: bool,
    has_tests: bool,
    release: bool,
) -> Result<PathBuf, ()> {
    let mut cargo = Command::new("cargo");
    cargo.current_dir(out_root).arg("build");
    if release {
        cargo.arg("--release");
    }
    if target == "wasm" {
        cargo.arg("--target").arg("wasm32-wasip1");
    }
    let ok = cargo.status().map(|s| s.success()).unwrap_or(false);
    if !ok {
        return Err(());
    }
    if run_tests && has_tests {
        let st = Command::new("cargo")
            .current_dir(out_root)
            .arg("test")
            .arg("--tests")
            .arg("--")
            .arg("--skip")
            .arg("bench_")
            .status()
            .map(|s| s.success())
            .unwrap_or(false);
        if !st {
            return Err(());
        }
    }
    let name = out_root
        .file_name()
        .map(|s| s.to_string_lossy().to_string())
        .unwrap_or_default();
    let profile = if release { "release" } else { "debug" };
    let exe_name = if cfg!(windows) {
        format!("{name}.exe")
    } else {
        name.to_string()
    };
    let artifact = if target == "wasm" {
        out_root
            .join("target/wasm32-wasip1")
            .join(profile)
            .join(format!("{name}.wasm"))
    } else {
        out_root.join("target").join(profile).join(exe_name)
    };
    Ok(artifact)
}

fn cmd_build(rest: &[String]) -> i32 {
    let a = parse_args(rest);
    let file = match a.file {
        Some(f) => f,
        None => {
            usage();
            return 2;
        }
    };
    if a.target != "native" && a.target != "wasm" {
        eprintln!(
            "error: unknown target '{}' (expected native or wasm)",
            a.target
        );
        return 2;
    }
    let module = match load(Path::new(&file), a.json) {
        Ok(m) => m,
        Err(()) => return 1,
    };
    let gen = codegen::codegen(&module);
    let out_root = match write_generated(&gen, &a.out_dir) {
        Ok(r) => r,
        Err(()) => return 1,
    };
    match build_crate(
        &out_root,
        &a.target,
        a.run_tests,
        !module.tests.is_empty(),
        a.release,
    ) {
        Ok(artifact) => {
            println!("artifact: {}", artifact.display());
            if a.run_benches
                && !module.benches.is_empty()
                && a.target != "wasm"
                && !run_bench_tests(&out_root, a.release)
            {
                return 1;
            }
            0
        }
        Err(()) => 1,
    }
}

fn run_bench_tests(out_root: &Path, release: bool) -> bool {
    let mut t = Command::new("cargo");
    t.current_dir(out_root).arg("test");
    if release {
        t.arg("--release");
    }
    t.arg("bench_").arg("--").arg("--nocapture");
    t.status().map(|s| s.success()).unwrap_or(false)
}

fn cmd_run(rest: &[String]) -> i32 {
    let a = parse_args(rest);
    let file = match a.file {
        Some(f) => f,
        None => {
            usage();
            return 2;
        }
    };
    let module = match load(Path::new(&file), a.json) {
        Ok(m) => m,
        Err(()) => return 1,
    };
    let gen = codegen::codegen(&module);
    if !gen.is_binary {
        eprintln!("error: cannot run a library module (no fn main)");
        return 2;
    }
    let out_root = match write_generated(&gen, &a.out_dir) {
        Ok(r) => r,
        Err(()) => return 1,
    };
    let exe = match build_crate(&out_root, "native", false, false, a.release) {
        Ok(a) => a,
        Err(()) => return 1,
    };
    match Command::new(&exe).status() {
        Ok(s) if s.success() => 0,
        Ok(_) => 1,
        Err(e) => {
            eprintln!("error: cannot run {}: {e}", exe.display());
            1
        }
    }
}

#[cfg(test)]
mod construction_type_tests {
    use super::type_matches;

    #[test]
    fn wildcard_matches_one_subtree() {
        // `?` matches a parenthesized subtree, not just one atom.
        assert!(type_matches(
            "(result ? string)",
            "result (vec string) string"
        ));
        assert!(type_matches(
            "(result ? string)",
            "result (vec Candidate) string"
        ));
        assert!(type_matches("(result ? string)", "(result string string)"));
        assert!(type_matches("(result string string)", "result ? string"));
    }

    #[test]
    fn wildcard_does_not_swallow_across_structures() {
        assert!(!type_matches("(result ? string)", "(vec (prim string))"));
        assert!(!type_matches(
            "(result ? string)",
            "(result string string string)"
        ));
        assert!(!type_matches("(result ? string)", "(result string)"));
    }

    #[test]
    fn cross_constructor_no_false_match() {
        assert!(!type_matches("result<A,B>", "(vec A)"));
        assert!(!type_matches("vec string", "result string string"));
        assert!(!type_matches("bool", "string"));
        assert!(!type_matches("Job", "rfc0005.a.Job"));
    }

    #[test]
    fn paren_normalization() {
        assert!(type_matches("vec string", "(vec string)"));
        assert!(type_matches("bool", "bool"));
        assert!(!type_matches("vec string", "vec i64"));
    }
}

#[cfg(test)]
mod operand_tests {
    use super::stale_revision;
    use crate::air::{AirGraph, Value};
    use std::collections::BTreeMap;

    fn node(g: &mut AirGraph, entity: &str, payload: &str) -> String {
        let mut f = BTreeMap::new();
        f.insert("value".to_string(), Value::Str(payload.to_string()));
        g.add("literal", entity, f, BTreeMap::new())
    }

    #[test]
    fn stale_detects_entity_head_move() {
        let mut g = AirGraph::new();
        let h1 = node(&mut g, "e:thing", "a");
        let h2 = node(&mut g, "e:thing", "b");
        assert_ne!(h1, h2);
        assert_eq!(g.heads.get("e:thing"), Some(&h2));
        assert_eq!(stale_revision(&g, &h1), Some(h2.clone()));
        assert_eq!(stale_revision(&g, &h2), None);
    }

    #[test]
    fn anonymous_revision_never_stale() {
        let mut g = AirGraph::new();
        let r = node(&mut g, "", "x");
        assert_eq!(stale_revision(&g, &r), None);
    }

    #[test]
    fn unknown_revision_not_stale() {
        let g = AirGraph::new();
        assert_eq!(stale_revision(&g, "deadbeef"), None);
    }
}
