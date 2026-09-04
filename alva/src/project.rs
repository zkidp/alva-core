use crate::ast;
use crate::check::{self, ExtFn, ExtType};
use crate::codegen;
use crate::diag::Diag;
use std::collections::{HashMap, HashSet};
use std::path::{Path, PathBuf};

#[derive(Debug)]
pub struct Project {
    pub name: String,
    pub modules: Vec<(String, PathBuf)>,
}

fn confined_module_path(base: &Path, configured: &str) -> Result<PathBuf, String> {
    let relative = Path::new(configured);
    if relative.is_absolute() {
        return Err(format!(
            "module path must be relative to the project root: {configured}"
        ));
    }
    let root = std::fs::canonicalize(base)
        .map_err(|e| format!("cannot resolve project root {}: {e}", base.display()))?;
    let candidate = std::fs::canonicalize(base.join(relative)).map_err(|e| {
        format!(
            "cannot resolve module path {}: {e}",
            base.join(relative).display()
        )
    })?;
    if !candidate.starts_with(&root) {
        return Err(format!("module path escapes project root: {configured}"));
    }
    Ok(candidate)
}

// 极简 alva.toml 解析：
//   [project]
//   name = "store"
//   [modules]
//   "store.model" = "src/model.alva"
pub fn load_project(path: &Path) -> Result<Project, String> {
    let text = std::fs::read_to_string(path)
        .map_err(|e| format!("cannot read {}: {e}", path.display()))?;
    let base = path.parent().unwrap_or(Path::new("."));
    let mut name = String::new();
    let mut modules = Vec::new();
    let mut section = String::new();
    for line in text.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        if line.starts_with('[') && line.ends_with(']') {
            section = line[1..line.len() - 1].trim().to_string();
            continue;
        }
        if let Some((k, v)) = line.split_once('=') {
            let key = k.trim().trim_matches('"');
            let val = v.trim().trim_matches('"');
            match section.as_str() {
                "project" => {
                    if key == "name" {
                        name = val.to_string();
                    }
                }
                "modules" => {
                    modules.push((key.to_string(), confined_module_path(base, val)?));
                }
                _ => {}
            }
        }
    }
    if name.is_empty() {
        return Err("alva.toml missing [project] name".to_string());
    }
    if modules.is_empty() {
        return Err("alva.toml missing [modules] entries".to_string());
    }
    Ok(Project { name, modules })
}

#[cfg(test)]
mod path_confinement_tests {
    use super::load_project;
    use std::fs;
    use std::path::PathBuf;

    fn fixture(name: &str) -> PathBuf {
        let thread_name = std::thread::current()
            .name()
            .unwrap_or("test")
            .replace(':', "_");
        let root = std::env::temp_dir().join(format!(
            "alva-project-{name}-{}-{}",
            std::process::id(),
            thread_name
        ));
        let _ = fs::remove_dir_all(&root);
        fs::create_dir_all(root.join("workspace/src")).unwrap();
        root
    }

    #[test]
    fn accepts_existing_module_inside_project_root() {
        let root = fixture("inside");
        fs::write(root.join("workspace/src/日常.alva"), "(module demo)").unwrap();
        fs::write(
            root.join("workspace/alva.toml"),
            "[project]\nname = \"demo\"\n[modules]\n\"demo\" = \"src/日常.alva\"\n",
        )
        .unwrap();

        let project = load_project(&root.join("workspace/alva.toml")).unwrap();
        assert!(project.modules[0].1.starts_with(root.join("workspace")));
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn rejects_parent_traversal_outside_project_root() {
        let root = fixture("parent");
        fs::write(root.join("secret.alva"), "(module secret)").unwrap();
        fs::write(
            root.join("workspace/alva.toml"),
            "[project]\nname = \"demo\"\n[modules]\n\"secret\" = \"../secret.alva\"\n",
        )
        .unwrap();

        let error = load_project(&root.join("workspace/alva.toml")).unwrap_err();
        assert!(error.contains("escapes project root"), "{error}");
        fs::remove_dir_all(root).unwrap();
    }

    #[cfg(unix)]
    #[test]
    fn rejects_symlink_that_resolves_outside_project_root() {
        use std::os::unix::fs::symlink;

        let root = fixture("symlink");
        fs::write(root.join("secret.alva"), "(module secret)").unwrap();
        symlink(
            root.join("secret.alva"),
            root.join("workspace/src/link.alva"),
        )
        .unwrap();
        fs::write(
            root.join("workspace/alva.toml"),
            "[project]\nname = \"demo\"\n[modules]\n\"secret\" = \"src/link.alva\"\n",
        )
        .unwrap();

        let error = load_project(&root.join("workspace/alva.toml")).unwrap_err();
        assert!(error.contains("escapes project root"), "{error}");
        fs::remove_dir_all(root).unwrap();
    }
}

pub struct LoadedModule {
    pub name: String,
    pub module: ast::Module,
}

pub fn load_modules(project: &Project) -> Result<Vec<LoadedModule>, Vec<Diag>> {
    let mut out = Vec::new();
    let mut diags = Vec::new();
    for (name, path) in &project.modules {
        match load_one(path) {
            Ok(m) => out.push(LoadedModule {
                name: name.clone(),
                module: m,
            }),
            Err(d) => diags.extend(d),
        }
    }
    if diags.is_empty() {
        Ok(out)
    } else {
        Err(diags)
    }
}

fn load_one(path: &Path) -> Result<ast::Module, Vec<Diag>> {
    let limits = crate::s_expr::Limits::from_env();
    if let Ok(meta) = std::fs::metadata(path) {
        if meta.len() as usize > limits.max_source_bytes {
            return Err(vec![Diag::error(format!(
                "source file is {} bytes, exceeding limit of {} bytes",
                meta.len(),
                limits.max_source_bytes
            ))
            .with_code("E_PARSE_004")]);
        }
    }
    let text = std::fs::read_to_string(path)
        .map_err(|e| vec![Diag::error(format!("cannot read {}: {e}", path.display()))])?;
    let tree = crate::s_expr::parse_with_limits(&text, &limits)
        .map_err(|e| vec![Diag::error_at(e.span(), e.message()).with_code(e.code())])?;
    ast::from_tree(&tree)
}

// 依赖图 + 环检测（DFS）
pub fn detect_cycles(modules: &[LoadedModule]) -> Result<(), String> {
    let names: HashSet<&str> = modules.iter().map(|m| m.name.as_str()).collect();
    let mut state: HashMap<&str, u8> = HashMap::new(); // 0=unvisited 1=visiting 2=done
    let mut stack = Vec::new();

    fn visit<'a>(
        name: &'a str,
        modules: &'a [LoadedModule],
        names: &HashSet<&'a str>,
        state: &mut HashMap<&'a str, u8>,
        stack: &mut Vec<String>,
    ) -> Result<(), String> {
        match state.get(name) {
            Some(1) => {
                stack.push(name.to_string());
                return Err(format!("cyclic dependency: {}", stack.join(" -> ")));
            }
            Some(2) => return Ok(()),
            _ => {}
        }
        state.insert(name, 1);
        stack.push(name.to_string());
        let module = modules.iter().find(|m| m.name == name).unwrap();
        for (dep, _) in &module.module.deps {
            if !names.contains(dep.as_str()) {
                return Err(format!("module '{name}' depends on unknown module '{dep}'"));
            }
            visit(dep, modules, names, state, stack)?;
        }
        stack.pop();
        state.insert(name, 2);
        Ok(())
    }

    for m in modules {
        visit(&m.name, modules, &names, &mut state, &mut stack)?;
    }
    Ok(())
}

pub fn check_project(project: &Project) -> Result<Vec<LoadedModule>, Vec<Diag>> {
    let modules = load_modules(project)?;
    check_project_loaded(modules)
}

/// Check pre-loaded modules (used when the authoritative AIR store provides
/// the modules instead of .alva files).
pub fn check_project_loaded(modules: Vec<LoadedModule>) -> Result<Vec<LoadedModule>, Vec<Diag>> {
    if let Err(e) = detect_cycles(&modules) {
        return Err(vec![Diag::error(e).with_code("E_MODULE_005")]);
    }
    // 第二遍：带外部符号
    let mut all_diags = Vec::new();
    for lm in &modules {
        let (fns, types) = externals_of_deps(lm, &modules);
        let diags = check::check_with_external(&lm.module, fns, types);
        if diags.iter().any(|d| d.severity == "error") {
            all_diags.extend(diags);
            return Err(all_diags);
        }
    }
    Ok(modules)
}

/// Run the full semantic checker (types/effects/contracts with external
/// symbols) over all modules reconstructed from an AIR graph. Returns
/// rendered diagnostic strings on failure.
pub fn check_graph_semantic(g: &crate::air::AirGraph) -> Result<(), Vec<String>> {
    let mut modules = Vec::new();
    for entity in &g.module_entities {
        match crate::air::air_to_module(g, entity) {
            Ok(m) => {
                let name = m.name.clone();
                modules.push(LoadedModule { name, module: m });
            }
            Err(e) => return Err(vec![e]),
        }
    }
    match check_project_loaded(modules) {
        Ok(_) => Ok(()),
        Err(ds) => Err(ds.iter().map(|d| d.render()).collect()),
    }
}

/// Load modules from the authoritative AIR store (project_dir/alva-air/CURRENT).
/// Falls back to .alva parsing only if no authoritative store exists.
pub fn load_modules_air(
    project: &Project,
    project_dir: &std::path::Path,
) -> Result<Vec<LoadedModule>, Vec<Diag>> {
    let graph = crate::air::load_authoritative(project_dir)
        .map_err(|e| vec![Diag::error(e).with_code("E_STORAGE_008")])?;
    let mut out = Vec::new();
    for (name, _) in &project.modules {
        let entity = format!("module:{name}");
        match crate::air::air_to_module(&graph, &entity) {
            Ok(m) => out.push(LoadedModule {
                name: name.clone(),
                module: m,
            }),
            Err(e) => return Err(vec![Diag::error(e)]),
        }
    }
    Ok(out)
}

fn externals_of_deps(
    lm: &LoadedModule,
    all: &[LoadedModule],
) -> (HashMap<String, ExtFn>, HashMap<String, ExtType>) {
    let mut fns = HashMap::new();
    let mut types = HashMap::new();
    let dep_names: HashSet<&str> = lm.module.deps.iter().map(|(n, _)| n.as_str()).collect();
    for other in all {
        if !dep_names.contains(other.name.as_str()) {
            continue;
        }
        for f in &other.module.fns {
            if other.module.exports.contains(&f.name) {
                fns.insert(
                    format!("{}.{}", other.name, f.name),
                    ExtFn {
                        params: f
                            .params
                            .iter()
                            .map(|(_, t)| qualify_type(t, &other.name))
                            .collect(),
                        returns: qualify_type(&f.returns, &other.name),
                        eff: f.eff.clone(),
                    },
                );
            }
        }
        for t in &other.module.types {
            if other.module.exports.contains(&t.name) {
                types.insert(
                    format!("{}.{}", other.name, t.name),
                    ExtType {
                        kind: qualify_kind(&t.kind, &other.name),
                    },
                );
            }
        }
    }
    (fns, types)
}

fn qualify_type(te: &ast::TypeExpr, mod_name: &str) -> ast::TypeExpr {
    match te {
        ast::TypeExpr::Named(n) if !n.contains('.') => {
            ast::TypeExpr::Named(format!("{mod_name}.{n}"))
        }
        ast::TypeExpr::Named(n) => ast::TypeExpr::Named(n.clone()),
        ast::TypeExpr::Vec(t) => ast::TypeExpr::Vec(Box::new(qualify_type(t, mod_name))),
        ast::TypeExpr::Map(k, v) => ast::TypeExpr::Map(
            Box::new(qualify_type(k, mod_name)),
            Box::new(qualify_type(v, mod_name)),
        ),
        ast::TypeExpr::Result(a, b) => ast::TypeExpr::Result(
            Box::new(qualify_type(a, mod_name)),
            Box::new(qualify_type(b, mod_name)),
        ),
        ast::TypeExpr::Prim(p) => ast::TypeExpr::Prim(p.clone()),
    }
}

fn qualify_kind(kind: &ast::TypeKind, mod_name: &str) -> ast::TypeKind {
    match kind {
        ast::TypeKind::Record(fields) => ast::TypeKind::Record(
            fields
                .iter()
                .map(|(n, te)| (n.clone(), qualify_type(te, mod_name)))
                .collect(),
        ),
        ast::TypeKind::Enum(vs) => ast::TypeKind::Enum(vs.clone()),
        ast::TypeKind::Alias(te) => ast::TypeKind::Alias(qualify_type(te, mod_name)),
    }
}

/// 为模块 lm 计算直接依赖导出的外部函数签名表
/// （key 为 qualified 名，返回类型按所属模块限定）。
/// 用于 codegen 按签名推导表达式返回类型（produces_result 修复）。
fn external_sigs_for(lm: &LoadedModule, all: &[LoadedModule]) -> crate::codegen::SigTable {
    let mut sigs = crate::codegen::SigTable::new();
    let dep_names: HashSet<&str> = lm.module.deps.iter().map(|(n, _)| n.as_str()).collect();
    for other in all {
        if !dep_names.contains(other.name.as_str()) {
            continue;
        }
        for f in &other.module.fns {
            if other.module.exports.contains(&f.name) {
                sigs.insert(
                    format!("{}.{}", other.name, f.name),
                    qualify_type(&f.returns, &other.name),
                );
            }
        }
    }
    sigs
}

/// 为模块 lm 计算直接依赖导出的 record 类型字段表
/// （qualified 名 -> 字段名列表），供 codegen 展开 record_update。
fn external_record_fields_for(
    lm: &LoadedModule,
    all: &[LoadedModule],
) -> std::collections::HashMap<String, Vec<String>> {
    let mut fields = std::collections::HashMap::new();
    let dep_names: HashSet<&str> = lm.module.deps.iter().map(|(n, _)| n.as_str()).collect();
    for other in all {
        if !dep_names.contains(other.name.as_str()) {
            continue;
        }
        for t in &other.module.types {
            if other.module.exports.contains(&t.name) {
                if let ast::TypeKind::Record(fs) = &t.kind {
                    fields.insert(
                        format!("{}.{}", other.name, t.name),
                        fs.iter().map(|(n, _)| n.clone()).collect(),
                    );
                }
            }
        }
    }
    fields
}

// 生成一个 Rust crate：每个模块一个文件，lib.rs/main.rs 声明 mod
pub fn codegen_project(
    project: &Project,
    modules: &[LoadedModule],
    out_dir: &Path,
) -> Result<PathBuf, String> {
    let crate_name = project.name.replace(['.', '-'], "_");
    let root = out_dir.join(&crate_name);
    let src = root.join("src");
    std::fs::create_dir_all(&src).map_err(|e| e.to_string())?;

    let mut cargo = String::new();
    cargo.push_str("[package]\n");
    cargo.push_str(&format!("name = \"{crate_name}\"\n"));
    cargo.push_str("version = \"0.1.0\"\n");
    cargo.push_str("edition = \"2021\"\n\n[dependencies]\n");
    let mut deps: HashMap<String, String> = HashMap::new();
    for lm in modules {
        for (c, v) in &lm.module.rust_deps {
            deps.insert(c.clone(), v.clone());
        }
    }
    // glue 的 fs 原语依赖 sha2（内容寻址校验），对所有生成 crate 提供。
    deps.entry("sha2".to_string())
        .or_insert_with(|| "0.10".to_string());
    for (c, v) in deps {
        cargo.push_str(&format!("{c} = \"{v}\"\n"));
    }

    let mut mod_decls = String::new();
    let mut has_main = false;
    for lm in modules {
        let san = lm.name.replace(['.', '-'], "_");
        let gen = codegen::codegen_with_external(
            &lm.module,
            external_sigs_for(lm, modules),
            external_record_fields_for(lm, modules),
        );
        let file = src.join(format!("{san}.rs"));
        std::fs::write(&file, gen.source_rs).map_err(|e| e.to_string())?;
        mod_decls.push_str(&format!("mod {san};\n"));
        if lm.module.fns.iter().any(|f| f.name == "main") {
            has_main = true;
        }
    }

    std::fs::write(root.join("Cargo.toml"), &cargo).map_err(|e| e.to_string())?;
    if has_main {
        let mut main = String::from(
            "#![allow(unused_parens, unused_variables, unused_imports, dead_code, while_true)]\n",
        );
        main.push_str(&mod_decls);
        main.push_str("fn main() -> Result<(), String> {\n");
        // 找到导出 main 的模块（取最后一个）
        for lm in modules.iter().rev() {
            if lm.module.fns.iter().any(|f| f.name == "main") {
                let san = lm.name.replace(['.', '-'], "_");
                main.push_str(&format!("    {san}::main()\n"));
                break;
            }
        }
        main.push_str("}\n");
        std::fs::write(src.join("main.rs"), &main).map_err(|e| e.to_string())?;
        std::fs::remove_file(src.join("lib.rs")).ok();
    } else {
        let mut lib = String::from(
            "#![allow(unused_parens, unused_variables, unused_imports, dead_code, while_true)]\n",
        );
        lib.push_str(&mod_decls);
        std::fs::write(src.join("lib.rs"), &lib).map_err(|e| e.to_string())?;
        std::fs::remove_file(src.join("main.rs")).ok();
    }
    Ok(root)
}

// impact: 对比两个 manifest 目录，输出受影响模块
pub fn impact(base: &Path, head: &Path) -> Result<(), String> {
    let mut base_map: HashMap<String, (String, Vec<String>)> = HashMap::new();
    let mut head_map: HashMap<String, (String, Vec<String>)> = HashMap::new();
    read_manifests(base, &mut base_map)?;
    read_manifests(head, &mut head_map)?;
    let mut names: Vec<&String> = base_map
        .keys()
        .chain(head_map.keys())
        .collect::<HashSet<_>>()
        .into_iter()
        .collect();
    names.sort();
    for n in names {
        match (base_map.get(n), head_map.get(n)) {
            (Some((b, _)), Some((h, _))) => {
                if b != h {
                    println!("CHANGED  {n}");
                }
            }
            (Some(_), None) => println!("REMOVED  {n}"),
            (None, Some(_)) => println!("ADDED    {n}"),
            _ => {}
        }
    }
    // 传递影响：依赖了 CHANGED/ADDED/REMOVED 的模块也受影响
    let mut affected: HashSet<String> = head_map
        .iter()
        .filter(|(n, (h, _))| base_map.get(*n).map(|(b, _)| b != h).unwrap_or(true))
        .map(|(n, _)| n.clone())
        .collect();
    loop {
        let mut added = false;
        for (n, (_, deps)) in &head_map {
            if !affected.contains(n) && deps.iter().any(|d| affected.contains(d)) {
                affected.insert(n.clone());
                added = true;
            }
        }
        if !added {
            break;
        }
    }
    let mut affected_sorted: Vec<&String> = affected.iter().collect();
    affected_sorted.sort();
    for n in affected_sorted {
        let base_has = base_map.contains_key(n);
        let head_has = head_map.contains_key(n);
        if head_has && base_has && base_map[n].0 == head_map[n].0 {
            println!("AFFECTED {n}");
        }
    }
    Ok(())
}

fn read_manifests(
    dir: &Path,
    out: &mut HashMap<String, (String, Vec<String>)>,
) -> Result<(), String> {
    for entry in std::fs::read_dir(dir).map_err(|e| e.to_string())? {
        let entry = entry.map_err(|e| e.to_string())?;
        if entry
            .path()
            .extension()
            .map(|e| e == "json")
            .unwrap_or(false)
        {
            let text = std::fs::read_to_string(entry.path()).map_err(|e| e.to_string())?;
            let module = manifest_module(&text);
            let hash = manifest_hash(&text);
            let deps = manifest_deps(&text);
            out.insert(module, (hash, deps));
        }
    }
    Ok(())
}

fn manifest_deps(json: &str) -> Vec<String> {
    let mut deps = Vec::new();
    if let Some(inner) = json
        .split("\"deps\":[")
        .nth(1)
        .and_then(|s| s.split(']').next())
    {
        for part in inner.split(',') {
            let p = part.trim().trim_matches('"');
            if !p.is_empty() {
                deps.push(p.to_string());
            }
        }
    }
    deps
}

fn manifest_module(json: &str) -> String {
    json.split("\"module\":\"")
        .nth(1)
        .and_then(|s| s.split('"').next())
        .unwrap_or("?")
        .to_string()
}

fn manifest_hash(json: &str) -> String {
    json.split("\"interface_hash\":\"")
        .nth(1)
        .and_then(|s| s.split('"').next())
        .unwrap_or("?")
        .to_string()
}
