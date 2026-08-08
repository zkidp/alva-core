mod air;
mod ast;
mod check;
mod codegen;
mod diag;
mod manifest;
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
        "hole" => cmd_hole(rest),
        "view" => cmd_view(rest),
        other => {
            eprintln!("unknown command: {other}");
            usage();
            2
        }
    };
    code
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

fn friendly_slot(kind: &str, position: &str) -> Option<&'static str> {
    Some(match position {
        "value" => match kind {
            "binding" | "as" | "field" | "record_field" | "ok" | "err" | "raise" | "try"
            | "not" | "len" | "keys" | "unwrap" | "errvalue" | "tostring" | "parseint"
            | "tobytes" | "isok" | "sort" | "urldecode" | "tohex" | "slice" => "value",
            _ => return None,
        },
        "body" => match kind {
            "binding" | "fold" | "loop" | "case" | "test" | "bench" | "contract" => "body",
            _ => return None,
        },
        "cond" if kind == "if" => "cond",
        "then" if kind == "if" => "then",
        "else" if kind == "if" => "else",
        "left"
            if matches!(
                kind,
                "binary"
                    | "get"
                    | "append"
                    | "lookup"
                    | "contains"
                    | "remove"
                    | "split"
                    | "concat"
                    | "join"
                    | "stripprefix"
                    | "before"
                    | "endswith"
                    | "cteq"
            ) =>
        {
            "left"
        }
        "right"
            if matches!(
                kind,
                "binary"
                    | "get"
                    | "append"
                    | "lookup"
                    | "contains"
                    | "remove"
                    | "split"
                    | "concat"
                    | "join"
                    | "stripprefix"
                    | "before"
                    | "endswith"
                    | "cteq"
            ) =>
        {
            "right"
        }
        "step" if kind == "block" => "steps",
        "arg" if kind == "call" => "args",
        "start" if kind == "slice" => "start",
        "end" if kind == "slice" => "end",
        "init" if kind == "loop" => "init",
        "cond2" if kind == "loop" => "cond",
        "catch" if kind == "try" => "catch",
        "scrutinee" if kind == "match" => "scrutinee",
        "range_start" if kind == "fold" => "range_start",
        "range_end" if kind == "fold" => "range_end",
        "acc_init" if kind == "fold" => "acc_init",
        _ => return None,
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
        let out = match tool.as_str() {
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
                match s.graph.resolve(&format!("module:{name}")) {
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
                }
            }
            "inspect_function" => {
                let s = need_session!();
                let name = req.get("name").and_then(|v| v.as_str()).unwrap_or("");
                match resolve_entity_in_graph(&s.graph, name) {
                    Some(rev) => {
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
                                json_str(&view)
                                ,
                                json_str(&body)
                            ),
                            "ok"
                        )
                    }
                    None => resp!(false, "null", &not_found(&s.graph, name)),
                }
            }
            "inspect_entity" => {
                let s = need_session!();
                let id = req
                    .get("entity")
                    .or_else(|| req.get("name"))
                    .and_then(|v| v.as_str())
                    .unwrap_or("");
                match s.graph.resolve(id).cloned() {
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
                    let fn_rev =
                        resolve_entity_in_graph(&s.graph, function).ok_or("function not found")?;
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
                let parent = req.get("parent").and_then(|v| v.as_str()).unwrap_or("");
                let child = req.get("child").and_then(|v| v.as_str()).unwrap_or("");
                let position = req
                    .get("position")
                    .and_then(|v| v.as_str())
                    .unwrap_or("value");
                match (|| -> Result<String, String> {
                    let pr = s.graph.resolve_rev(parent).ok_or("parent not found")?;
                    let kind = s.graph.get(&pr).map(|n| n.kind.clone()).unwrap_or_default();
                    let slot = friendly_slot(&kind, position)
                        .ok_or_else(|| format!("unsupported position '{position}' for {kind}"))?;
                    s.replace_slot(&pr, slot, child)
                })() {
                    Ok(rev) => resp!(
                        true,
                        &format!("{{\"new_revision\":{}}}", json_str(&rev)),
                        "ok"
                    ),
                    Err(e) => resp!(false, "null", &e),
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
                                    .map(|e| if e == &old { new_name.to_string() } else { e.clone() })
                                    .collect();
                                s.set_field(&me, "exports", air::Value::Names(updated))?;
                            }
                            if exports.contains(&old) {
                                s.rename_symbol(
                                    &format!("{module_name}.{old}"),
                                    &format!("{module_name}.{new_name}"))?;
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
                match resolve_entity_in_graph(&s.graph, function) {
                    Some(fn_rev) => {
                        let eff = s
                            .graph
                            .get(&fn_rev)
                            .and_then(|n| match n.fields.get("eff") {
                                Some(air::Value::Names(ns)) => Some(ns.join(",")),
                                _ => None,
                            })
                            .unwrap_or_default();
                        let pure = s
                            .graph
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
                                        json_str(&pure.map(|b| b.to_string()).unwrap_or_default()),
                                        json_str(&tree)
                                    ),
                                    "ok"
                                )
                            }
                            None => resp!(false, "null", "function has no body block"),
                        }
                    }
                    None => resp!(false, "null", &not_found(&s.graph, function)),
                }
            }
            "inspect_test" => {
                let s = need_session!();
                let module = req.get("module").and_then(|v| v.as_str()).unwrap_or("");
                let name = req.get("name").and_then(|v| v.as_str()).unwrap_or("");
                let mut found = None;
                if let Some(m) = resolve_entity_in_graph(&s.graph, module) {
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
                }
                match found {
                    Some(rev) => {
                        let mut budget = 0usize;
                        let tree = body_tree(&s.graph, &rev, 0, &mut budget);
                        resp!(
                            true,
                            &format!("{{\"revision\":{},\"body\":{}}}", json_str(&rev), json_str(&tree)),
                            "ok"
                        )
                    }
                    None => resp!(false, "null", &not_found(&s.graph, name)),
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
                            Ok(rev) => resp!(true, &format!("{{\"revision\":{}}}", json_str(&rev)), "ok"),
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
                let type_name = req
                    .get("type")
                    .and_then(|v| v.as_str())
                    .unwrap_or("string");
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
                            Ok(rev) => resp!(true, &format!("{{\"revision\":{}}}", json_str(&rev)), "ok"),
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
                                        let rev2 =
                                            resolve_entity_in_graph(&s.graph, function)
                                                .unwrap_or_else(|| fn_rev.clone());
                                        s.set_field(&rev2, "eff", air::Value::Names(vec![]))
                                    }
                                    Err(e) => Err(e),
                                }
                            }
                            "io" => {
                                match s.set_field(&fn_rev, "pure", air::Value::Bool(false)) {
                                    Ok(_) => {
                                        let rev2 =
                                            resolve_entity_in_graph(&s.graph, function)
                                                .unwrap_or_else(|| fn_rev.clone());
                                        s.set_field(
                                            &rev2,
                                            "eff",
                                            air::Value::Names(vec!["io".to_string()]),
                                        )
                                    }
                                    Err(e) => Err(e),
                                }
                            }
                            other => Err(format!("unknown effect '{other}'")),
                        };
                        match r {
                            Ok(rev) => resp!(true, &format!("{{\"revision\":{}}}", json_str(&rev)), "ok"),
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
                            Ok(rev) => resp!(true, &format!("{{\"revision\":{}}}", json_str(&rev)), "ok"),
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
            other => resp!(false, "null", &format!("E_AEP_UNKNOWN_TOOL: {other}")),
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
        let want = name.strip_prefix(&format!("{module_name}.")).unwrap_or(name);
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
    hits.iter().map(|s| s.as_str()).collect::<Vec<_>>().join(", ")
}

fn not_found(g: &air::AirGraph, name: &str) -> String {
    format!(
        "E_AEP_ENTITY_NOT_FOUND: {name}; candidates={}",
        entity_candidates(g, name)
    )
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
    eprintln!("usage: alva <check|build|run|manifest> <file.alva> [--json] [--target native|wasm] [--test] [--bench] [--release] [--out-dir <path>]");
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
