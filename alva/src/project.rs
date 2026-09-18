use crate::ast;
use crate::check::{self, ExtFn, ExtType};
use crate::codegen;
use crate::diag::Diag;
use serde::Deserialize;
use std::collections::{BTreeMap, HashMap, HashSet};
use std::path::{Path, PathBuf};

/// 编译器托管的 std 模块：源码以 .alva 形式内嵌进二进制，当项目任一模块
/// 声明 `(use "alva.std.*" ...)` 依赖时自动注入，无需在 alva.toml 列出。
/// std 模块本身是普通模块：类型检查走 check_with_external，AIR/manifest/
/// AEP 全部自然可用；运行时实现通过 glue externs 绑定。
pub const STD_SOURCES: &[(&str, &str)] = &[
    ("alva.std.io", include_str!("std_src/io.alva")),
    ("alva.std.json", include_str!("std_src/json.alva")),
    ("alva.std.string", include_str!("std_src/string.alva")),
];

pub struct Project {
    pub name: String,
    pub modules: Vec<(String, PathBuf)>,
    pub dependencies: Vec<LibraryDependency>,
    pub manifest_path: PathBuf,
}

#[derive(Clone, Debug)]
pub struct LibraryDependency {
    pub name: String,
    pub manifest_path: PathBuf,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum ModuleOrigin {
    Application {
        manifest_path: PathBuf,
    },
    Library {
        name: String,
        manifest_path: PathBuf,
    },
    StandardLibrary,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ManifestDocument {
    project: Option<ManifestIdentity>,
    library: Option<ManifestIdentity>,
    modules: BTreeMap<String, String>,
    #[serde(default)]
    dependencies: BTreeMap<String, String>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ManifestIdentity {
    name: String,
}

fn canonical_manifest(path: &Path, context: &str) -> Result<PathBuf, String> {
    std::fs::canonicalize(path)
        .map_err(|e| format!("{context}: cannot resolve manifest {}: {e}", path.display()))
}

fn parse_manifest(path: &Path) -> Result<ManifestDocument, String> {
    let text = std::fs::read_to_string(path)
        .map_err(|e| format!("manifest {}: cannot read: {e}", path.display()))?;
    toml::from_str(&text).map_err(|e| format!("manifest {}: invalid TOML: {e}", path.display()))
}

fn dependency_path(
    base: &Path,
    manifest: &Path,
    name: &str,
    value: &str,
) -> Result<PathBuf, String> {
    let lower = value.to_ascii_lowercase();
    if value.contains("://")
        || lower.starts_with("git+")
        || lower.starts_with("ssh:")
        || lower.starts_with("file:")
    {
        return Err(format!(
            "manifest {} dependency '{name}': only local filesystem manifest paths are supported, got '{value}'",
            manifest.display()
        ));
    }
    Ok(base.join(value))
}

pub fn load_project(path: &Path) -> Result<Project, String> {
    let manifest_path = canonical_manifest(path, "application")?;
    let doc = parse_manifest(&manifest_path)?;
    let identity = match (doc.project, doc.library) {
        (Some(project), None) => project,
        (None, Some(_)) => {
            return Err(format!(
                "manifest {}: expected application [project], found [library]",
                manifest_path.display()
            ))
        }
        (Some(_), Some(_)) => {
            return Err(format!(
                "manifest {}: cannot contain both [project] and [library]",
                manifest_path.display()
            ))
        }
        (None, None) => {
            return Err(format!(
                "manifest {}: missing [project] table",
                manifest_path.display()
            ))
        }
    };
    if identity.name.trim().is_empty() {
        return Err(format!(
            "manifest {}: [project].name must not be empty",
            manifest_path.display()
        ));
    }
    if doc.modules.is_empty() {
        return Err(format!(
            "manifest {}: missing [modules] entries",
            manifest_path.display()
        ));
    }
    let base = manifest_path.parent().unwrap_or(Path::new("."));
    let modules = doc
        .modules
        .into_iter()
        .map(|(name, value)| (name, base.join(value)))
        .collect();
    let dependencies = doc
        .dependencies
        .into_iter()
        .map(|(name, value)| {
            dependency_path(base, &manifest_path, &name, &value).map(|manifest_path| {
                LibraryDependency {
                    name,
                    manifest_path,
                }
            })
        })
        .collect::<Result<Vec<_>, _>>()?;
    Ok(Project {
        name: identity.name,
        modules,
        dependencies,
        manifest_path,
    })
}

pub struct LoadedModule {
    pub name: String,
    pub module: ast::Module,
    pub origin: ModuleOrigin,
    pub source_path: Option<PathBuf>,
}

pub fn load_modules(project: &Project) -> Result<Vec<LoadedModule>, Vec<Diag>> {
    let mut out = Vec::new();
    let mut diags = Vec::new();
    for (name, path) in &project.modules {
        load_declared_module(
            name,
            path,
            ModuleOrigin::Application {
                manifest_path: project.manifest_path.clone(),
            },
            &project.manifest_path,
            &mut out,
            &mut diags,
        );
    }
    if diags.is_empty() {
        let mut loaded_libraries = HashMap::new();
        let mut visiting = Vec::new();
        for dependency in &project.dependencies {
            load_library(
                dependency,
                &mut out,
                &mut loaded_libraries,
                &mut visiting,
                &mut diags,
                &project.manifest_path,
            );
        }
    }
    if diags.is_empty() {
        validate_loaded_modules(project, &out)?;
        inject_std_modules(&mut out)?;
        Ok(out)
    } else {
        Err(diags)
    }
}

fn load_declared_module(
    name: &str,
    path: &Path,
    origin: ModuleOrigin,
    manifest_path: &Path,
    out: &mut Vec<LoadedModule>,
    diags: &mut Vec<Diag>,
) {
    match load_one(path) {
        Ok(module) => {
            if module.name != name {
                diags.push(Diag::error(format!(
                    "manifest {} module '{}': source {} declares module '{}'",
                    manifest_path.display(),
                    name,
                    path.display(),
                    module.name
                )));
            } else {
                out.push(LoadedModule {
                    name: name.to_string(),
                    module,
                    origin,
                    source_path: Some(path.to_path_buf()),
                });
            }
        }
        Err(ds) => {
            let prefix = format!(
                "manifest {} module '{}' source {}",
                manifest_path.display(),
                name,
                path.display()
            );
            diags.extend(ds.into_iter().map(|mut d| {
                d.message = format!("{prefix}: {}", d.message);
                d
            }));
        }
    }
}

fn load_library(
    dependency: &LibraryDependency,
    out: &mut Vec<LoadedModule>,
    loaded: &mut HashMap<PathBuf, String>,
    visiting: &mut Vec<(PathBuf, String)>,
    diags: &mut Vec<Diag>,
    declaring_manifest: &Path,
) {
    let manifest_path = match canonical_manifest(
        &dependency.manifest_path,
        &format!(
            "manifest {} dependency '{}'",
            declaring_manifest.display(),
            dependency.name
        ),
    ) {
        Ok(path) => path,
        Err(e) => {
            diags.push(Diag::error(e));
            return;
        }
    };
    if let Some(pos) = visiting.iter().position(|(path, _)| path == &manifest_path) {
        let mut chain: Vec<String> = visiting[pos..]
            .iter()
            .map(|(path, name)| format!("{name} ({})", path.display()))
            .collect();
        chain.push(format!("{} ({})", dependency.name, manifest_path.display()));
        diags.push(Diag::error(format!(
            "manifest {} dependency '{}': cyclic library dependency: {}",
            declaring_manifest.display(),
            dependency.name,
            chain.join(" -> ")
        )));
        return;
    }
    if let Some(loaded_name) = loaded.get(&manifest_path) {
        if loaded_name != &dependency.name {
            diags.push(Diag::error(format!(
                "manifest {} dependency '{}': library manifest {} was already loaded as '{}'",
                declaring_manifest.display(),
                dependency.name,
                manifest_path.display(),
                loaded_name
            )));
        }
        return;
    }
    let doc = match parse_manifest(&manifest_path) {
        Ok(doc) => doc,
        Err(e) => {
            diags.push(Diag::error(format!(
                "manifest {} dependency '{}': {e}",
                declaring_manifest.display(),
                dependency.name
            )));
            return;
        }
    };
    let identity = match (doc.project, doc.library) {
        (None, Some(library)) => library,
        (Some(_), None) => {
            diags.push(Diag::error(format!(
                "manifest {} dependency '{}': {} is an application manifest; expected [library]",
                declaring_manifest.display(),
                dependency.name,
                manifest_path.display()
            )));
            return;
        }
        (Some(_), Some(_)) => {
            diags.push(Diag::error(format!(
                "library manifest {}: cannot contain both [project] and [library]",
                manifest_path.display()
            )));
            return;
        }
        (None, None) => {
            diags.push(Diag::error(format!(
                "library manifest {}: missing [library] table",
                manifest_path.display()
            )));
            return;
        }
    };
    if identity.name != dependency.name {
        diags.push(Diag::error(format!(
            "manifest {} dependency '{}': library manifest {} declares name '{}'",
            declaring_manifest.display(),
            dependency.name,
            manifest_path.display(),
            identity.name
        )));
        return;
    }
    if doc.modules.is_empty() {
        diags.push(Diag::error(format!(
            "library manifest {} dependency '{}': missing [modules] entries",
            manifest_path.display(),
            dependency.name
        )));
        return;
    }

    visiting.push((manifest_path.clone(), identity.name.clone()));
    let base = manifest_path.parent().unwrap_or(Path::new("."));
    for (name, value) in doc.modules {
        load_declared_module(
            &name,
            &base.join(value),
            ModuleOrigin::Library {
                name: identity.name.clone(),
                manifest_path: manifest_path.clone(),
            },
            &manifest_path,
            out,
            diags,
        );
    }
    for (name, value) in doc.dependencies {
        let nested_path = match dependency_path(base, &manifest_path, &name, &value) {
            Ok(path) => path,
            Err(e) => {
                diags.push(Diag::error(e));
                continue;
            }
        };
        load_library(
            &LibraryDependency {
                name,
                manifest_path: nested_path,
            },
            out,
            loaded,
            visiting,
            diags,
            &manifest_path,
        );
    }
    visiting.pop();
    loaded.insert(manifest_path, identity.name);
}

fn validate_loaded_modules(project: &Project, modules: &[LoadedModule]) -> Result<(), Vec<Diag>> {
    let mut diags = Vec::new();
    let mut by_name: HashMap<&str, &LoadedModule> = HashMap::new();
    let mut by_rust_name: HashMap<String, &LoadedModule> = HashMap::new();
    for module in modules {
        if module.name.starts_with("alva.std.") {
            diags.push(Diag::error(format!(
                "{} module '{}': compiler-managed alva.std.* modules cannot be declared by a project or library",
                origin_label(&module.origin),
                module.name
            )));
        }
        if let Some(previous) = by_name.insert(&module.name, module) {
            diags.push(Diag::error(format!(
                "module name conflict '{}': {} and {} both declare it",
                module.name,
                module_label(previous),
                module_label(module)
            )));
        }
        let rust_name = rust_module_name(&module.name);
        if let Some(previous) = by_rust_name.insert(rust_name.clone(), module) {
            if previous.name != module.name {
                diags.push(Diag::error(format!(
                    "generated Rust filename conflict '{}.rs': module '{}' from {} conflicts with module '{}' from {}",
                    rust_name,
                    previous.name,
                    module_label(previous),
                    module.name,
                    module_label(module)
                )));
            }
        }
        if matches!(module.origin, ModuleOrigin::Library { .. })
            && module
                .module
                .fns
                .iter()
                .any(|function| function.name == "main")
        {
            diags.push(Diag::error(format!(
                "{} module '{}': local libraries cannot define fn main in this first version",
                origin_label(&module.origin),
                module.name
            )));
        }
    }
    if !project.dependencies.is_empty() {
        let app_entries: Vec<&str> = modules
            .iter()
            .filter(|module| matches!(module.origin, ModuleOrigin::Application { .. }))
            .filter(|module| {
                module
                    .module
                    .fns
                    .iter()
                    .any(|function| function.name == "main")
            })
            .map(|module| module.name.as_str())
            .collect();
        if app_entries.len() > 1 {
            diags.push(Diag::error(format!(
                "manifest {}: ambiguous application entry point; fn main appears in modules {}",
                project.manifest_path.display(),
                app_entries.join(", ")
            )));
        }
    }
    if diags.is_empty() {
        Ok(())
    } else {
        Err(diags)
    }
}

fn origin_label(origin: &ModuleOrigin) -> String {
    match origin {
        ModuleOrigin::Application { manifest_path } => {
            format!("application manifest {}", manifest_path.display())
        }
        ModuleOrigin::Library {
            name,
            manifest_path,
        } => format!("library '{name}' manifest {}", manifest_path.display()),
        ModuleOrigin::StandardLibrary => "compiler standard library".to_string(),
    }
}

fn module_label(module: &LoadedModule) -> String {
    match &module.source_path {
        Some(path) => format!("{} source {}", origin_label(&module.origin), path.display()),
        None => origin_label(&module.origin),
    }
}

fn rust_module_name(name: &str) -> String {
    name.replace(['.', '-'], "_")
}

/// 注入项目依赖的 std 模块（迭代处理 std→std 依赖）。
fn inject_std_modules(out: &mut Vec<LoadedModule>) -> Result<(), Vec<Diag>> {
    let mut diags = Vec::new();
    loop {
        let mut added = false;
        let mut to_add: Vec<&str> = Vec::new();
        for lm in out.iter() {
            for (dep, _) in &lm.module.deps {
                if let Some((name, _)) = STD_SOURCES.iter().find(|(n, _)| *n == dep) {
                    if !out.iter().any(|m| &m.name == name) && !to_add.contains(name) {
                        to_add.push(name);
                    }
                }
            }
        }
        for name in to_add {
            let (_, src) = STD_SOURCES
                .iter()
                .find(|(n, _)| *n == name)
                .expect("std source");
            let limits = crate::s_expr::Limits::from_env();
            match crate::s_expr::parse_with_limits(src, &limits) {
                Ok(tree) => match crate::ast::from_tree(&tree) {
                    Ok(module) => {
                        out.push(LoadedModule {
                            name: name.to_string(),
                            module,
                            origin: ModuleOrigin::StandardLibrary,
                            source_path: None,
                        });
                        added = true;
                    }
                    Err(ds) => diags.extend(ds),
                },
                Err(e) => diags.push(Diag::error_at(e.span(), e.message()).with_code(e.code())),
            }
        }
        if !added {
            break;
        }
    }
    if diags.is_empty() {
        Ok(())
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
                modules.push(LoadedModule {
                    name,
                    module: m,
                    origin: ModuleOrigin::StandardLibrary,
                    source_path: None,
                });
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
                origin: ModuleOrigin::Application {
                    manifest_path: project.manifest_path.clone(),
                },
                source_path: None,
            }),
            Err(e) => return Err(vec![Diag::error(e)]),
        }
    }
    inject_std_modules(&mut out)?;
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
    // glue 的 json 原语（alva.std.json）依赖 serde_json，对所有生成 crate 提供。
    deps.entry("serde_json".to_string())
        .or_insert_with(|| "1".to_string());
    for (c, v) in deps {
        if c == "serde_json" {
            cargo.push_str(&format!(
                "serde_json = {{ version = \"{v}\", features = [\"arbitrary_precision\"] }}\n"
            ));
        } else {
            cargo.push_str(&format!("{c} = \"{v}\"\n"));
        }
    }
    cargo.push_str("\n[profile.release]\n");
    cargo.push_str("overflow-checks = true\n");

    let mut mod_decls = String::new();
    let mut has_main = false;
    for lm in modules {
        let san = rust_module_name(&lm.name);
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
        // 带本地库依赖的项目只允许应用自有模块作为入口；旧项目保留
        // 原有的“最后一个 main”行为以避免无关兼容性变化。
        for lm in modules.iter().rev().filter(|lm| {
            project.dependencies.is_empty() || matches!(lm.origin, ModuleOrigin::Application { .. })
        }) {
            if lm.module.fns.iter().any(|f| f.name == "main") {
                let san = rust_module_name(&lm.name);
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
