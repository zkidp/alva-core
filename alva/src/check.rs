use crate::ast::{self, BinOp, Expr, FnDef, Module, Prim, TypeDef, TypeExpr};
use crate::diag::{Diag, Repair};
use crate::s_expr::Span;
use std::collections::{HashMap, HashSet};

const RUST_KEYWORDS: &[&str] = &[
    "as", "break", "const", "continue", "crate", "dyn", "else", "enum", "extern", "false", "fn",
    "for", "if", "impl", "in", "let", "loop", "match", "mod", "move", "mut", "pub", "ref",
    "return", "self", "Self", "static", "struct", "super", "trait", "true", "type", "unsafe",
    "use", "where", "while", "async", "await",
];

const KNOWN_CAPS: &[&str] = &[
    "read",
    "write",
    "network",
    "process",
    "clock",
    "io",
    "unsafe-ffi",
];
const BUILTIN_EXTERN_CRATES: &[&str] = &["glue", "http", "fs"];

pub fn check(module: &Module) -> Vec<Diag> {
    let mut c = Checker::new(module);
    c.run();
    c.finalize()
}

pub fn check_with_external(
    module: &Module,
    external_fns: HashMap<String, ExtFn>,
    external_types: HashMap<String, ExtType>,
) -> Vec<Diag> {
    let mut c = Checker::with_external(module, external_fns, external_types);
    c.run();
    c.finalize()
}

#[derive(Clone, Debug, PartialEq)]
pub enum Ty {
    Unknown,
    Prim(Prim),
    Named(String),
    Vec(Box<Ty>),
    Map(Box<Ty>, Box<Ty>),
    Result(Box<Ty>, Box<Ty>),
}

fn ty_name(t: &Ty) -> String {
    match t {
        Ty::Unknown => "?".to_string(),
        Ty::Prim(p) => ast::prim_name(p).to_string(),
        Ty::Named(n) => n.clone(),
        Ty::Vec(t) => format!("vec<{}>", ty_name(t)),
        Ty::Map(k, v) => format!("map<{}, {}>", ty_name(k), ty_name(v)),
        Ty::Result(a, b) => format!("result<{}, {}>", ty_name(a), ty_name(b)),
    }
}

fn is_numeric(t: &Ty) -> bool {
    matches!(
        t,
        Ty::Prim(
            Prim::U8
                | Prim::U16
                | Prim::U32
                | Prim::U64
                | Prim::I8
                | Prim::I16
                | Prim::I32
                | Prim::I64
                | Prim::F32
                | Prim::F64
        )
    )
}

fn is_integer(t: &Ty) -> bool {
    matches!(
        t,
        Ty::Prim(
            Prim::U8
                | Prim::U16
                | Prim::U32
                | Prim::U64
                | Prim::I8
                | Prim::I16
                | Prim::I32
                | Prim::I64
        )
    )
}

fn is_hashable_key(t: &Ty) -> bool {
    match t {
        Ty::Prim(p) => !matches!(p, Prim::F32 | Prim::F64),
        _ => false,
    }
}

fn valid_ident(s: &str) -> bool {
    if s.is_empty() || RUST_KEYWORDS.contains(&s) {
        return false;
    }
    let mut chars = s.chars();
    match chars.next() {
        Some(c) if c.is_ascii_lowercase() || c == '_' => {}
        _ => return false,
    }
    chars.all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == '_')
}

// 类型名：允许 PascalCase（首字母大写），直接映射 Rust 类型标识符
fn valid_type_ident(s: &str) -> bool {
    if s.is_empty() || RUST_KEYWORDS.contains(&s) {
        return false;
    }
    let mut chars = s.chars();
    match chars.next() {
        Some(c) if c.is_ascii_uppercase() || c == '_' => {}
        _ => return false,
    }
    chars.all(|c| c.is_ascii_alphanumeric() || c == '_')
}

fn ty_of(te: &TypeExpr) -> Ty {
    match te {
        TypeExpr::Prim(p) => Ty::Prim(p.clone()),
        TypeExpr::Named(n) => Ty::Named(n.clone()),
        TypeExpr::Vec(t) => Ty::Vec(Box::new(ty_of(t))),
        TypeExpr::Map(k, v) => Ty::Map(Box::new(ty_of(k)), Box::new(ty_of(v))),
        TypeExpr::Result(a, b) => Ty::Result(Box::new(ty_of(a)), Box::new(ty_of(b))),
    }
}

#[derive(Clone)]
pub struct ExtFn {
    pub params: Vec<TypeExpr>,
    pub returns: TypeExpr,
    pub eff: Vec<String>,
}

#[derive(Clone)]
pub struct ExtType {
    pub kind: ast::TypeKind,
}

struct Env {
    vars: Vec<(String, Ty)>,
    result: Option<Ty>,
    effects: Vec<String>,
    is_pure: bool,
}

impl Env {
    fn new() -> Self {
        Env {
            vars: Vec::new(),
            result: None,
            effects: Vec::new(),
            is_pure: false,
        }
    }

    fn get(&self, name: &str) -> Option<Ty> {
        self.vars
            .iter()
            .rev()
            .find(|(n, _)| n == name)
            .map(|(_, t)| t.clone())
    }
}

struct Checker<'a> {
    module: &'a Module,
    types: HashMap<String, &'a TypeDef>,
    fns: HashMap<String, &'a FnDef>,
    exts: HashMap<String, &'a ast::ExternDef>,
    rust_crates: HashSet<String>,
    diags: Vec<Diag>,
    current_fn: Option<String>,
    external_fns: HashMap<String, ExtFn>,
    external_types: HashMap<String, ExtType>,
    in_project: bool,
}

impl<'a> Checker<'a> {
    fn new(module: &'a Module) -> Self {
        Self::with_external(module, HashMap::new(), HashMap::new())
    }

    fn with_external(
        module: &'a Module,
        external_fns: HashMap<String, ExtFn>,
        external_types: HashMap<String, ExtType>,
    ) -> Self {
        let mut types = HashMap::new();
        for t in &module.types {
            types.insert(t.name.clone(), t);
        }
        let mut fns = HashMap::new();
        for f in &module.fns {
            fns.insert(f.name.clone(), f);
        }
        let mut exts = HashMap::new();
        for e in &module.exts {
            exts.insert(e.name.clone(), e);
        }
        let rust_crates = module.rust_deps.iter().map(|(c, _)| c.clone()).collect();
        Checker {
            module,
            types,
            fns,
            exts,
            rust_crates,
            diags: Vec::new(),
            current_fn: None,
            external_fns,
            external_types,
            in_project: true,
        }
    }

    fn run(&mut self) {
        self.check_module_name();
        self.check_caps();
        self.check_types();
        self.check_fns();
        self.check_externs();
        self.check_exports();
        self.check_tests();
        self.check_benches();
        for (dep, _) in &self.module.deps {
            if !self.in_project {
                self.diags.push(Diag::warn(format!(
                    "module dependency '{dep}' is declared but no project context was given (use: alva project check <alva.toml>)"
                )));
            }
        }
    }

    fn check_module_name(&mut self) {
        for seg in self.module.name.split('.') {
            if !valid_ident(seg) {
                self.diags.push(Diag::error(format!(
                    "invalid module name segment '{seg}' (v0.1 identifiers: lowercase snake_case, not a Rust keyword)"
                ))
                .with_code("E_MODULE_003")
                .with_module(self.module.name.clone()));
            }
        }
    }

    fn check_caps(&mut self) {
        for cap in &self.module.caps {
            if !KNOWN_CAPS.contains(&cap.as_str()) {
                self.diags.push(
                    Diag::error(format!(
                        "unknown capability '{cap}' (known: read write network process clock io)"
                    ))
                    .with_code("E_MODULE_001")
                    .with_module(self.module.name.clone()),
                );
            }
        }
    }

    fn check_types(&mut self) {
        for t in &self.module.types {
            if !valid_type_ident(&t.name) {
                self.diags.push(Diag::error_at(
                    t.span.clone(),
                    format!(
                        "invalid type name '{}' (types use PascalCase, e.g. ObjectMeta)",
                        t.name
                    ),
                ));
            }
            match &t.kind {
                ast::TypeKind::Record(fields) => {
                    let mut seen = HashSet::new();
                    for (name, te) in fields {
                        if !valid_ident(name) {
                            self.diags.push(Diag::error_at(
                                t.span.clone(),
                                format!("invalid field name '{name}' in type '{}'", t.name),
                            ));
                        }
                        if !seen.insert(name.clone()) {
                            self.diags.push(Diag::error_at(
                                t.span.clone(),
                                format!("duplicate field '{name}' in type '{}'", t.name),
                            ));
                        }
                        self.check_type_expr(te, &t.name);
                    }
                }
                ast::TypeKind::Alias(te) => {
                    self.check_type_expr(te, &t.name);
                }
                ast::TypeKind::Enum(variants) => {
                    let mut seen = HashSet::new();
                    for v in variants {
                        if !valid_ident(v) {
                            self.diags.push(Diag::error_at(
                                t.span.clone(),
                                format!("invalid variant name '{v}' in enum '{}'", t.name),
                            ));
                        }
                        if !seen.insert(v.clone()) {
                            self.diags.push(Diag::error_at(
                                t.span.clone(),
                                format!("duplicate variant '{v}' in enum '{}'", t.name),
                            ));
                        }
                    }
                }
            }
        }
    }

    fn check_type_expr(&mut self, te: &TypeExpr, ctx: &str) {
        match te {
            TypeExpr::Prim(_) => {}
            TypeExpr::Named(n) => {
                let ok = if n.contains('.') {
                    self.external_types.contains_key(n)
                } else {
                    self.types.contains_key(n)
                };
                if !ok {
                    self.diags.push(
                        Diag::error(format!("type '{n}' referenced in '{ctx}' is not defined"))
                            .with_code("E_MODULE_004"),
                    );
                }
            }
            TypeExpr::Result(a, b) => {
                self.check_type_expr(a, ctx);
                self.check_type_expr(b, ctx);
            }
            TypeExpr::Vec(t) => {
                self.check_type_expr(t, ctx);
            }
            TypeExpr::Map(k, v) => {
                self.check_type_expr(k, ctx);
                self.check_type_expr(v, ctx);
            }
        }
    }

    fn check_fns(&mut self) {
        for f in &self.module.fns {
            self.current_fn = Some(f.name.clone());
            if !valid_ident(&f.name) {
                self.diags.push(Diag::error_at(
                    f.span.clone(),
                    format!("invalid fn name '{}'", f.name),
                ));
            }
            let mut seen_params = HashSet::new();
            for (pname, pte) in &f.params {
                if pname == "result" {
                    self.diags.push(Diag::error_at(
                        f.span.clone(),
                        format!("param name '{pname}' is reserved for postconditions"),
                    ));
                }
                if !valid_ident(pname) {
                    self.diags.push(Diag::error_at(
                        f.span.clone(),
                        format!("invalid param name '{pname}' in fn '{}'", f.name),
                    ));
                }
                if !seen_params.insert(pname.clone()) {
                    self.diags.push(
                        Diag::error_at(
                            f.span.clone(),
                            format!("duplicate param '{pname}' in fn '{}'", f.name),
                        )
                        .with_code("E_NAME_002")
                        .with_module(self.module.name.clone()),
                    );
                }
                self.check_type_expr(pte, &f.name);
            }
            self.check_type_expr(&f.returns, &f.name);
            if f.pure && !f.eff.is_empty() {
                self.diags.push(Diag::error_at(
                    f.span.clone(),
                    format!(
                        "fn '{}' is marked (pure) but also declares (eff ...)",
                        f.name
                    ),
                ));
            }
            for eff in &f.eff {
                if !KNOWN_CAPS.contains(&eff.as_str()) {
                    self.diags.push(Diag::error_at(
                        f.span.clone(),
                        format!("unknown capability '{eff}' in fn '{}'", f.name),
                    ));
                }
                if !self.module.caps.contains(eff) {
                    self.diags.push(Diag::error_at(
                        f.span.clone(),
                        format!(
                            "fn '{}' requires capability '{eff}' but module does not declare (cap {eff})",
                            f.name
                        ),
                    ));
                }
            }

            let mut env = Env::new();
            for (pname, pte) in &f.params {
                env.vars.push((pname.clone(), ty_of(pte)));
            }
            env.effects = f.eff.clone();
            env.is_pure = f.pure;
            for e in &f.body {
                let _ = self.type_of(e, &mut env);
            }

            let mut pre_env = Env::new();
            for (pname, pte) in &f.params {
                pre_env.vars.push((pname.clone(), ty_of(pte)));
            }
            for e in &f.pre {
                self.expect_bool(e, &mut pre_env, "precondition");
            }
            for e in &f.inv {
                self.expect_bool(e, &mut pre_env, "invariant");
            }
            let mut post_env = pre_env;
            post_env.result = Some(ty_of(&f.returns));
            for e in &f.post {
                self.expect_bool(e, &mut post_env, "postcondition");
            }
        }
        self.current_fn = None;
    }

    fn check_externs(&mut self) {
        for e in &self.module.exts {
            let has_eff = !e.eff.is_empty();
            if e.pure == has_eff {
                self.diags.push(Diag::error_at(
                    e.span.clone(),
                    format!(
                        "extern '{}' must declare exactly one of (pure) or (eff ...) — raw Rust templates cannot hide side effects",
                        e.name
                    ),
                )
                .with_code("E_EXTERN_002")
                .with_module(self.module.name.clone()));
            }
            if !e.unsafe_ffi {
                self.diags.push(Diag::error_at(
                    e.span.clone(),
                    format!(
                        "extern '{}' embeds raw Rust via (rust ...) — must declare (unsafe) and the module must declare (cap unsafe-ffi)",
                        e.name
                    ),
                )
                .with_code("E_EXTERN_001")
                .with_module(self.module.name.clone()));
            }
            if e.unsafe_ffi && !self.module.caps.iter().any(|c| c == "unsafe-ffi") {
                self.diags.push(Diag::error_at(
                    e.span.clone(),
                    format!(
                        "extern '{}' embeds raw Rust (unsafe) — module must declare (cap unsafe-ffi)",
                        e.name
                    ),
                )
                .with_code("E_EXTERN_003")
                .with_module(self.module.name.clone()));
            }
            if !e.name.contains('.') {
                self.diags.push(
                    Diag::error_at(
                        e.span.clone(),
                        format!(
                            "extern '{}' must be a dotted rust path like crate.fn",
                            e.name
                        ),
                    )
                    .with_code("E_EXTERN_004")
                    .with_module(self.module.name.clone()),
                );
                continue;
            }
            let crate_name = e.name.split('.').next().unwrap_or("");
            if !self.rust_crates.contains(crate_name)
                && !BUILTIN_EXTERN_CRATES.contains(&crate_name)
            {
                self.diags.push(
                    Diag::error_at(
                        e.span.clone(),
                        format!(
                            "extern '{}' requires (use rust \"{}\" ...)",
                            e.name, crate_name
                        ),
                    )
                    .with_code("E_EXTERN_005")
                    .with_module(self.module.name.clone()),
                );
            }
            if self.fns.contains_key(&e.name) {
                self.diags.push(
                    Diag::error_at(
                        e.span.clone(),
                        format!("extern '{}' collides with a local fn", e.name),
                    )
                    .with_code("E_EXTERN_006")
                    .with_module(self.module.name.clone()),
                );
            }
            if e.template.is_empty() {
                self.diags.push(
                    Diag::error_at(
                        e.span.clone(),
                        format!("extern '{}' rust template must not be empty", e.name),
                    )
                    .with_code("E_EXTERN_007")
                    .with_module(self.module.name.clone()),
                );
            }
            for eff in &e.eff {
                if !KNOWN_CAPS.contains(&eff.as_str()) {
                    self.diags.push(Diag::error_at(
                        e.span.clone(),
                        format!("unknown capability '{eff}' in extern '{}'", e.name),
                    ));
                }
                if !self.module.caps.contains(eff) {
                    self.diags.push(Diag::error_at(
                        e.span.clone(),
                        format!(
                            "extern '{}' requires capability '{eff}' but module does not declare (cap {eff})",
                            e.name
                        ),
                    ));
                }
            }
            let mut seen = HashSet::new();
            for (pname, pte) in &e.params {
                if !valid_ident(pname) {
                    self.diags.push(Diag::error_at(
                        e.span.clone(),
                        format!("invalid param name '{pname}' in extern '{}'", e.name),
                    ));
                }
                if !seen.insert(pname.clone()) {
                    self.diags.push(
                        Diag::error_at(
                            e.span.clone(),
                            format!("duplicate param '{pname}' in extern '{}'", e.name),
                        )
                        .with_code("E_NAME_002")
                        .with_module(self.module.name.clone()),
                    );
                }
                self.check_type_expr(pte, &e.name);
            }
            self.check_type_expr(&e.returns, &e.name);
        }
    }

    fn check_exports(&mut self) {
        for e in &self.module.exports {
            if !self.fns.contains_key(e) && !self.types.contains_key(e) {
                self.diags.push(
                    Diag::error(format!(
                        "export '{e}' is not defined in module '{}'",
                        self.module.name
                    ))
                    .with_code("E_MODULE_002")
                    .with_module(self.module.name.clone()),
                );
            }
        }
    }

    fn check_tests(&mut self) {
        for t in &self.module.tests {
            if !valid_ident(&t.name) {
                self.diags.push(Diag::error_at(
                    t.span.clone(),
                    format!("invalid test name '{}'", t.name),
                ));
            }
            let mut env = Env::new();
            self.expect_bool(&t.body, &mut env, "test body");
        }
    }

    fn check_benches(&mut self) {
        for b in &self.module.benches {
            if !valid_ident(&b.name) {
                self.diags.push(Diag::error_at(
                    b.span.clone(),
                    format!("invalid bench name '{}'", b.name),
                ));
            }
            if let Some(ms) = b.ms_budget {
                if ms <= 0 {
                    self.diags.push(Diag::error_at(
                        b.span.clone(),
                        format!("bench '{}' budget (ms {ms}) must be positive", b.name),
                    ));
                }
            }
            let mut env = Env::new();
            for e in &b.setup {
                let _ = self.type_of(e, &mut env);
            }
            let _ = self.type_of(&b.body, &mut env);
        }
    }

    fn expect_bool(&mut self, e: &Expr, env: &mut Env, what: &str) {
        let t = self.type_of(e, env);
        if t != Ty::Prim(Prim::Bool) && t != Ty::Unknown {
            self.diags.push(
                Diag::error_at(
                    e.span(),
                    format!("{what} must be a bool expression (found {})", ty_name(&t)),
                )
                .with_code("E_CONTRACT_001")
                .with_module(self.module.name.clone())
                .with_function(self.current_fn.clone().unwrap_or_default()),
            );
        }
    }

    fn type_of(&mut self, e: &Expr, env: &mut Env) -> Ty {
        match e {
            Expr::Int(_, _) => Ty::Prim(Prim::I64),
            Expr::UInt(_, _) => Ty::Prim(Prim::U64),
            Expr::Float(_, _) => Ty::Prim(Prim::F64),
            Expr::Str(_, _) => Ty::Prim(Prim::String),
            Expr::Bool(_, _) => Ty::Prim(Prim::Bool),
            Expr::Bytes(_, _) => Ty::Prim(Prim::Bytes),
            Expr::Nil(_) => Ty::Prim(Prim::Nil),
            Expr::Ref(name, span) => {
                if name == "result" {
                    match &env.result {
                        Some(t) => t.clone(),
                        None => {
                            self.diags.push(Diag::error_at(
                                span.clone(),
                                "'result' can only be used in a postcondition",
                            ));
                            Ty::Unknown
                        }
                    }
                } else {
                    match env.get(name) {
                        Some(t) => t,
                        None => {
                            self.diags.push(
                                Diag::error_at(span.clone(), format!("unknown reference '{name}'"))
                                    .with_code("E_NAME_001")
                                    .with_module(self.module.name.clone())
                                    .with_function(self.current_fn.clone().unwrap_or_default()),
                            );
                            Ty::Unknown
                        }
                    }
                }
            }
            Expr::Call(name, args, span) => self.type_call(name, args, span, env),
            Expr::Bin(op, a, b, span) => {
                let ta = self.type_of(a, env);
                let tb = self.type_of(b, env);
                match op {
                    BinOp::And | BinOp::Or => {
                        self.expect_ty(
                            ta,
                            &Ty::Prim(Prim::Bool),
                            span,
                            "logical operator requires bool operands",
                        );
                        self.expect_ty(
                            tb,
                            &Ty::Prim(Prim::Bool),
                            span,
                            "logical operator requires bool operands",
                        );
                        Ty::Prim(Prim::Bool)
                    }
                    BinOp::Eq | BinOp::Ne => {
                        self.unify(ta, tb, span, "comparison operands");
                        Ty::Prim(Prim::Bool)
                    }
                    BinOp::Lt | BinOp::Le | BinOp::Gt | BinOp::Ge => {
                        let t = self.unify(ta, tb, span, "comparison operands");
                        if !is_numeric(&t) && t != Ty::Unknown {
                            self.diags.push(
                                Diag::error_at(
                                    span.clone(),
                                    "ordering comparison requires numeric operands",
                                )
                                .with_code("E_TYPE_001")
                                .with_module(self.module.name.clone())
                                .with_function(self.current_fn.clone().unwrap_or_default()),
                            );
                        }
                        Ty::Prim(Prim::Bool)
                    }
                    BinOp::Add | BinOp::Sub | BinOp::Mul | BinOp::Div => {
                        let t = self.unify(ta, tb, span, "arithmetic operands");
                        if !is_numeric(&t) && t != Ty::Unknown {
                            self.diags.push(
                                Diag::error_at(
                                    span.clone(),
                                    "arithmetic requires numeric operands",
                                )
                                .with_code("E_TYPE_001")
                                .with_module(self.module.name.clone())
                                .with_function(self.current_fn.clone().unwrap_or_default()),
                            );
                        }
                        t
                    }
                    BinOp::Mod => {
                        let t = self.unify(ta, tb, span, "modulo operands");
                        if !is_integer(&t) && t != Ty::Unknown {
                            self.diags.push(
                                Diag::error_at(span.clone(), "modulo requires integer operands")
                                    .with_code("E_TYPE_001")
                                    .with_module(self.module.name.clone())
                                    .with_function(self.current_fn.clone().unwrap_or_default()),
                            );
                        }
                        t
                    }
                }
            }
            Expr::Not(x, span) => {
                let tx = self.type_of(x, env);
                self.expect_ty(
                    tx,
                    &Ty::Prim(Prim::Bool),
                    span,
                    "not requires a bool operand",
                );
                Ty::Prim(Prim::Bool)
            }
            Expr::If(c, t, e2, span) => {
                let tc = self.type_of(c, env);
                self.expect_ty(tc, &Ty::Prim(Prim::Bool), span, "if condition must be bool");
                let tt = self.type_of(t, env);
                let te = self.type_of(e2, env);
                self.unify(tt, te, span, "if branches")
            }
            Expr::Let(name, declared, value, body, span) => {
                if name == "result" {
                    self.diags.push(Diag::error_at(
                        span.clone(),
                        "binding name 'result' is reserved for postconditions",
                    ));
                }
                if !valid_ident(name) {
                    self.diags.push(Diag::error_at(
                        span.clone(),
                        format!("invalid binding name '{name}'"),
                    ));
                }
                let tv = self.type_of(value, env);
                let td = declared.as_ref().map(ty_of).unwrap_or(Ty::Unknown);
                let t = self.unify(tv, td, span, "let binding");
                env.vars.push((name.clone(), t.clone()));
                let r = self.type_of(body, env);
                env.vars.pop();
                r
            }
            Expr::Block(exprs, _) => {
                let mut last = Ty::Unknown;
                for x in exprs {
                    last = self.type_of(x, env);
                }
                last
            }
            Expr::VecLit(t, elems, span) => {
                let et = ty_of(t);
                for e in elems {
                    let te = self.type_of(e, env);
                    self.unify(et.clone(), te, span, "vec element type");
                }
                Ty::Vec(Box::new(et))
            }
            Expr::Len(v, span) => {
                let tv = self.type_of(v, env);
                match &tv {
                    Ty::Vec(_) | Ty::Map(..) | Ty::Prim(Prim::Bytes) | Ty::Prim(Prim::String) => {
                        Ty::Prim(Prim::I64)
                    }
                    Ty::Unknown => Ty::Unknown,
                    _ => {
                        self.diags.push(Diag::error_at(
                            span.clone(),
                            "len requires a vec, map, string or bytes value",
                        ));
                        Ty::Unknown
                    }
                }
            }
            Expr::Get(v, i, span) => {
                let tv = self.type_of(v, env);
                let ti = self.type_of(i, env);
                if !is_integer(&ti) && ti != Ty::Unknown {
                    self.diags
                        .push(Diag::error_at(span.clone(), "get index must be an integer"));
                }
                match tv {
                    Ty::Vec(t) => *t,
                    Ty::Prim(Prim::Bytes) => Ty::Prim(Prim::U8),
                    Ty::Unknown => Ty::Unknown,
                    _ => {
                        self.diags.push(Diag::error_at(
                            span.clone(),
                            "get requires a vec or bytes value",
                        ));
                        Ty::Unknown
                    }
                }
            }
            Expr::Append(v, x, span) => {
                let tv = self.type_of(v, env);
                match tv {
                    Ty::Vec(t) => {
                        let tx = self.type_of(x, env);
                        let t2 = self.unify((*t).clone(), tx, span, "append value type");
                        Ty::Vec(Box::new(t2))
                    }
                    Ty::Unknown => {
                        let _ = self.type_of(x, env);
                        Ty::Unknown
                    }
                    _ => {
                        self.diags
                            .push(Diag::error_at(span.clone(), "append requires a vec value"));
                        Ty::Unknown
                    }
                }
            }
            Expr::As(t, x, span) => {
                let _ = self.type_of(x, env);
                let _ = span;
                ty_of(t)
            }
            Expr::Fold(idx, lo, hi, acc_name, acc_ty, init, body, span) => {
                if acc_name == "result" {
                    self.diags.push(Diag::error_at(
                        span.clone(),
                        "accumulator name 'result' is reserved for postconditions",
                    ));
                }
                let tlo = self.type_of(lo, env);
                let thi = self.type_of(hi, env);
                for (t, what) in [(&tlo, "fold lower bound"), (&thi, "fold upper bound")] {
                    if !is_numeric(t) && *t != Ty::Unknown {
                        self.diags.push(Diag::error_at(
                            span.clone(),
                            format!("{what} must be numeric"),
                        ));
                    }
                }
                let ti = self.type_of(init, env);
                let ta = ty_of(acc_ty);
                let t = self.unify(ti, ta, span, "fold accumulator");
                env.vars.push((idx.clone(), Ty::Prim(Prim::I64)));
                env.vars.push((acc_name.clone(), t.clone()));
                let tb = self.type_of(body, env);
                env.vars.pop();
                env.vars.pop();
                self.unify(t, tb, span, "fold body")
            }
            Expr::Variant(enum_name, vname, span) => match self.types.get(enum_name) {
                Some(td) => match &td.kind {
                    ast::TypeKind::Enum(variants) if variants.contains(vname) => {
                        Ty::Named(enum_name.clone())
                    }
                    ast::TypeKind::Enum(_) => {
                        self.diags.push(Diag::error_at(
                            span.clone(),
                            format!("unknown variant '{vname}' in enum '{enum_name}'"),
                        ));
                        Ty::Unknown
                    }
                    _ => {
                        self.diags.push(Diag::error_at(
                            span.clone(),
                            format!("'{enum_name}' is not an enum type"),
                        ));
                        Ty::Unknown
                    }
                },
                None => {
                    self.diags.push(Diag::error_at(
                        span.clone(),
                        format!("unknown enum type '{enum_name}'"),
                    ));
                    Ty::Unknown
                }
            },
            Expr::Match(enum_name, value, cases, span) => {
                let tv = self.type_of(value, env);
                let expected = Ty::Named(enum_name.clone());
                if tv != expected && tv != Ty::Unknown {
                    self.diags.push(Diag::error_at(
                        span.clone(),
                        format!(
                            "match value must be of type '{enum_name}' (found {})",
                            ty_name(&tv)
                        ),
                    ));
                }
                match self.types.get(enum_name) {
                    Some(td) => match &td.kind {
                        ast::TypeKind::Enum(variants) => {
                            let mut covered = HashSet::new();
                            let mut wildcard = false;
                            let mut result = Ty::Unknown;
                            for (vname, body) in cases {
                                if vname == "_" {
                                    wildcard = true;
                                } else if !variants.contains(vname) {
                                    self.diags.push(Diag::error_at(
                                        span.clone(),
                                        format!("unknown variant '{vname}' in enum '{enum_name}'"),
                                    ));
                                } else if !covered.insert(vname.clone()) {
                                    self.diags.push(Diag::error_at(
                                        span.clone(),
                                        format!("duplicate case for variant '{vname}'"),
                                    ));
                                }
                                let tb = self.type_of(body, env);
                                result = self.unify(result, tb, span, "match arms");
                            }
                            if !wildcard {
                                for v in variants {
                                    if !covered.contains(v) {
                                        self.diags.push(Diag::error_at(
                                            span.clone(),
                                            format!(
                                                "match on '{enum_name}' is not exhaustive: missing variant '{v}'"
                                            ),
                                        ));
                                    }
                                }
                            }
                            result
                        }
                        _ => {
                            self.diags.push(Diag::error_at(
                                span.clone(),
                                format!("'{enum_name}' is not an enum type"),
                            ));
                            Ty::Unknown
                        }
                    },
                    None => {
                        self.diags.push(Diag::error_at(
                            span.clone(),
                            format!("unknown enum type '{enum_name}'"),
                        ));
                        Ty::Unknown
                    }
                }
            }
            Expr::MapLit(kt, vt, entries, span) => {
                let key_ty = ty_of(kt);
                let val_ty = ty_of(vt);
                if !is_hashable_key(&key_ty) && key_ty != Ty::Unknown {
                    self.diags.push(Diag::error_at(
                        span.clone(),
                        format!(
                            "map key type {} is not hashable (use int/uint/string/bytes)",
                            ty_name(&key_ty)
                        ),
                    ));
                }
                for (k, v) in entries {
                    let tk = self.type_of(k, env);
                    self.unify(key_ty.clone(), tk, span, "map key type");
                    let tv = self.type_of(v, env);
                    self.unify(val_ty.clone(), tv, span, "map value type");
                }
                Ty::Map(Box::new(key_ty), Box::new(val_ty))
            }
            Expr::Set(m, k, v, span) => {
                let tm = self.type_of(m, env);
                match &tm {
                    Ty::Map(kt, vt) => {
                        let tk = self.type_of(k, env);
                        self.unify((**kt).clone(), tk, span, "map key type");
                        let tv = self.type_of(v, env);
                        self.unify((**vt).clone(), tv, span, "map value type");
                        tm
                    }
                    Ty::Unknown => {
                        let _ = self.type_of(k, env);
                        let _ = self.type_of(v, env);
                        Ty::Unknown
                    }
                    _ => {
                        self.diags
                            .push(Diag::error_at(span.clone(), "set requires a map value"));
                        Ty::Unknown
                    }
                }
            }
            Expr::Lookup(m, k, span) => {
                let tm = self.type_of(m, env);
                match &tm {
                    Ty::Map(kt, vt) => {
                        let tk = self.type_of(k, env);
                        self.unify((**kt).clone(), tk, span, "map key type");
                        Ty::Result(Box::new((**vt).clone()), Box::new(Ty::Prim(Prim::Nil)))
                    }
                    Ty::Unknown => {
                        let _ = self.type_of(k, env);
                        Ty::Unknown
                    }
                    _ => {
                        self.diags
                            .push(Diag::error_at(span.clone(), "lookup requires a map value"));
                        Ty::Unknown
                    }
                }
            }
            Expr::Contains(m, k, span) => {
                let tm = self.type_of(m, env);
                match &tm {
                    Ty::Map(kt, _) => {
                        let tk = self.type_of(k, env);
                        self.unify((**kt).clone(), tk, span, "map key type");
                        Ty::Prim(Prim::Bool)
                    }
                    Ty::Unknown => {
                        let _ = self.type_of(k, env);
                        Ty::Unknown
                    }
                    _ => {
                        self.diags.push(Diag::error_at(
                            span.clone(),
                            "contains requires a map value",
                        ));
                        Ty::Unknown
                    }
                }
            }
            Expr::Remove(m, k, span) => {
                let tm = self.type_of(m, env);
                match &tm {
                    Ty::Map(kt, _) => {
                        let tk = self.type_of(k, env);
                        self.unify((**kt).clone(), tk, span, "map key type");
                        tm
                    }
                    Ty::Unknown => {
                        let _ = self.type_of(k, env);
                        Ty::Unknown
                    }
                    _ => {
                        self.diags
                            .push(Diag::error_at(span.clone(), "remove requires a map value"));
                        Ty::Unknown
                    }
                }
            }
            Expr::Keys(m, span) => {
                let tm = self.type_of(m, env);
                match &tm {
                    Ty::Map(kt, _) => Ty::Vec(Box::new((**kt).clone())),
                    Ty::Unknown => Ty::Unknown,
                    _ => {
                        self.diags
                            .push(Diag::error_at(span.clone(), "keys requires a map value"));
                        Ty::Unknown
                    }
                }
            }
            Expr::Unwrap(x, span) => {
                let tx = self.type_of(x, env);
                match tx {
                    Ty::Result(t, _) => *t,
                    Ty::Unknown => Ty::Unknown,
                    _ => {
                        self.diags.push(Diag::error_at(
                            span.clone(),
                            "unwrap requires a result-typed value",
                        ));
                        Ty::Unknown
                    }
                }
            }
            Expr::ErrValue(x, span) => {
                let tx = self.type_of(x, env);
                match tx {
                    Ty::Result(_, e) => *e,
                    Ty::Unknown => Ty::Unknown,
                    _ => {
                        self.diags.push(Diag::error_at(
                            span.clone(),
                            "err-value requires a result-typed value",
                        ));
                        Ty::Unknown
                    }
                }
            }
            Expr::Slice(v, s, e, span) => {
                let tv = self.type_of(v, env);
                let ts = self.type_of(s, env);
                let te = self.type_of(e, env);
                for (t, what) in [(&ts, "slice start"), (&te, "slice end")] {
                    if !is_integer(t) && *t != Ty::Unknown {
                        self.diags.push(Diag::error_at(
                            span.clone(),
                            format!("{what} must be an integer"),
                        ));
                    }
                }
                match tv {
                    Ty::Vec(t) => Ty::Vec(t),
                    Ty::Prim(Prim::Bytes) => Ty::Prim(Prim::Bytes),
                    Ty::Unknown => Ty::Unknown,
                    _ => {
                        self.diags.push(Diag::error_at(
                            span.clone(),
                            "slice requires a vec or bytes value",
                        ));
                        Ty::Unknown
                    }
                }
            }
            Expr::Split(s, sep, span) => {
                let ts = self.type_of(s, env);
                self.expect_ty(ts, &Ty::Prim(Prim::String), span, "split requires a string");
                let tp = self.type_of(sep, env);
                self.expect_ty(
                    tp,
                    &Ty::Prim(Prim::String),
                    span,
                    "split separator must be a string",
                );
                Ty::Vec(Box::new(Ty::Prim(Prim::String)))
            }
            Expr::Concat(a, b, span) => {
                let ta = self.type_of(a, env);
                self.expect_ty(ta, &Ty::Prim(Prim::String), span, "concat requires strings");
                let tb = self.type_of(b, env);
                self.expect_ty(tb, &Ty::Prim(Prim::String), span, "concat requires strings");
                Ty::Prim(Prim::String)
            }
            Expr::ToString(x, span) => {
                let tx = self.type_of(x, env);
                match &tx {
                    Ty::Prim(
                        Prim::U8
                        | Prim::U16
                        | Prim::U32
                        | Prim::U64
                        | Prim::I8
                        | Prim::I16
                        | Prim::I32
                        | Prim::I64
                        | Prim::F32
                        | Prim::F64
                        | Prim::Bool
                        | Prim::String,
                    ) => {}
                    Ty::Unknown => {}
                    _ => {
                        self.diags.push(Diag::error_at(
                            span.clone(),
                            "to-string requires a number, bool or string",
                        ));
                    }
                }
                Ty::Prim(Prim::String)
            }
            Expr::ParseInt(x, span) => {
                let tx = self.type_of(x, env);
                self.expect_ty(
                    tx,
                    &Ty::Prim(Prim::String),
                    span,
                    "parse-int requires a string",
                );
                Ty::Result(
                    Box::new(Ty::Prim(Prim::I64)),
                    Box::new(Ty::Prim(Prim::String)),
                )
            }
            Expr::ToBytes(x, span) => {
                let tx = self.type_of(x, env);
                self.expect_ty(
                    tx,
                    &Ty::Prim(Prim::String),
                    span,
                    "to-bytes requires a string",
                );
                Ty::Prim(Prim::Bytes)
            }
            Expr::IsOk(x, span) => {
                let tx = self.type_of(x, env);
                match &tx {
                    Ty::Result(..) | Ty::Unknown => {}
                    _ => {
                        self.diags.push(Diag::error_at(
                            span.clone(),
                            "is-ok requires a result-typed value",
                        ));
                    }
                }
                Ty::Prim(Prim::Bool)
            }
            Expr::Join(v, sep, span) => {
                let tv = self.type_of(v, env);
                match &tv {
                    Ty::Vec(t) => {
                        if **t != Ty::Prim(Prim::String) && **t != Ty::Unknown {
                            self.diags.push(Diag::error_at(
                                span.clone(),
                                "join requires a vec of strings",
                            ));
                        }
                    }
                    Ty::Unknown => {}
                    _ => {
                        self.diags.push(Diag::error_at(
                            span.clone(),
                            "join requires a vec of strings",
                        ));
                    }
                }
                let ts = self.type_of(sep, env);
                self.expect_ty(
                    ts,
                    &Ty::Prim(Prim::String),
                    span,
                    "join separator must be a string",
                );
                Ty::Prim(Prim::String)
            }
            Expr::StripPrefix(s, p, span) => {
                let ts = self.type_of(s, env);
                self.expect_ty(
                    ts,
                    &Ty::Prim(Prim::String),
                    span,
                    "strip-prefix requires strings",
                );
                let tp = self.type_of(p, env);
                self.expect_ty(
                    tp,
                    &Ty::Prim(Prim::String),
                    span,
                    "strip-prefix prefix must be a string",
                );
                Ty::Prim(Prim::String)
            }
            Expr::Before(s, sep, span) => {
                let ts = self.type_of(s, env);
                self.expect_ty(ts, &Ty::Prim(Prim::String), span, "before requires strings");
                let tp = self.type_of(sep, env);
                self.expect_ty(
                    tp,
                    &Ty::Prim(Prim::String),
                    span,
                    "before separator must be a string",
                );
                Ty::Prim(Prim::String)
            }
            Expr::EndsWith(s, suf, span) => {
                let ts = self.type_of(s, env);
                self.expect_ty(
                    ts,
                    &Ty::Prim(Prim::String),
                    span,
                    "ends-with requires strings",
                );
                let tp = self.type_of(suf, env);
                self.expect_ty(
                    tp,
                    &Ty::Prim(Prim::String),
                    span,
                    "ends-with suffix must be a string",
                );
                Ty::Prim(Prim::Bool)
            }
            Expr::Sort(v, span) => {
                let tv = self.type_of(v, env);
                match &tv {
                    Ty::Vec(t) => {
                        if **t != Ty::Prim(Prim::String) && **t != Ty::Unknown {
                            self.diags.push(Diag::error_at(
                                span.clone(),
                                "sort requires a vec of strings",
                            ));
                        }
                    }
                    Ty::Unknown => {}
                    _ => {
                        self.diags.push(Diag::error_at(
                            span.clone(),
                            "sort requires a vec of strings",
                        ));
                    }
                }
                tv
            }
            Expr::UrlDecode(x, span) => {
                let tx = self.type_of(x, env);
                self.expect_ty(
                    tx,
                    &Ty::Prim(Prim::String),
                    span,
                    "url-decode requires a string",
                );
                Ty::Prim(Prim::String)
            }
            Expr::ToHex(x, span) => {
                let tx = self.type_of(x, env);
                self.expect_ty(tx, &Ty::Prim(Prim::Bytes), span, "to-hex requires bytes");
                Ty::Prim(Prim::String)
            }
            Expr::CtEq(a, b, span) => {
                let ta = self.type_of(a, env);
                self.expect_ty(ta, &Ty::Prim(Prim::String), span, "ct-eq requires strings");
                let tb = self.type_of(b, env);
                self.expect_ty(tb, &Ty::Prim(Prim::String), span, "ct-eq requires strings");
                Ty::Prim(Prim::Bool)
            }
            Expr::Loop(acc_name, acc_ty, init, inv, cond, body, span) => {
                if acc_name == "result" {
                    self.diags.push(Diag::error_at(
                        span.clone(),
                        "loop accumulator name 'result' is reserved for postconditions",
                    ));
                }
                let ti = self.type_of(init, env);
                let ta = ty_of(acc_ty);
                let t = self.unify(ti, ta, span, "loop accumulator");
                env.vars.push((acc_name.clone(), t.clone()));
                if let Some(inv_expr) = inv {
                    let ti = self.type_of(inv_expr, env);
                    self.expect_ty(
                        ti,
                        &Ty::Prim(Prim::Bool),
                        span,
                        "loop invariant must be bool",
                    );
                }
                let tc = self.type_of(cond, env);
                self.expect_ty(
                    tc,
                    &Ty::Prim(Prim::Bool),
                    span,
                    "loop condition must be bool",
                );
                let tb = self.type_of(body, env);
                env.vars.pop();
                self.unify(t, tb, span, "loop body")
            }
            Expr::Record(name, fields, span) => {
                let kind: Option<ast::TypeKind> = if name.contains('.') {
                    self.external_types.get(name).map(|e| e.kind.clone())
                } else {
                    self.types.get(name).map(|t| t.kind.clone())
                };
                match kind {
                    Some(ast::TypeKind::Record(defs)) => {
                        let def_map: HashMap<&str, &TypeExpr> =
                            defs.iter().map(|(n, t)| (n.as_str(), t)).collect();
                        let mut seen = HashSet::new();
                        for (fname, fval) in fields {
                            if !seen.insert(fname.clone()) {
                                self.diags.push(
                                    Diag::error_at(
                                        span.clone(),
                                        format!("duplicate field '{fname}' in record '{name}'"),
                                    )
                                    .with_code("E_TYPE_002")
                                    .with_module(self.module.name.clone())
                                    .with_function(self.current_fn.clone().unwrap_or_default()),
                                );
                            }
                            match def_map.get(fname.as_str()) {
                                Some(fte) => {
                                    let tf = ty_of(fte);
                                    let tv = self.type_of(fval, env);
                                    self.unify(tf, tv, span, format!("field '{fname}' type"));
                                }
                                None => {
                                    self.diags.push(
                                        Diag::error_at(
                                            span.clone(),
                                            format!("unknown field '{fname}' in record '{name}'"),
                                        )
                                        .with_code("E_NAME_003")
                                        .with_module(self.module.name.clone())
                                        .with_function(self.current_fn.clone().unwrap_or_default()),
                                    );
                                }
                            }
                        }
                        for (n, _) in defs {
                            if !seen.contains(&n) {
                                self.diags.push(
                                    Diag::error_at(
                                        span.clone(),
                                        format!("missing field '{n}' in record '{name}'"),
                                    )
                                    .with_code("E_NAME_003")
                                    .with_module(self.module.name.clone())
                                    .with_function(self.current_fn.clone().unwrap_or_default()),
                                );
                            }
                        }
                        Ty::Named(name.clone())
                    }
                    Some(_) => {
                        self.diags.push(Diag::error_at(
                            span.clone(),
                            format!("'{name}' is not a record type and cannot be constructed"),
                        ));
                        Ty::Unknown
                    }
                    None => {
                        self.diags.push(Diag::error_at(
                            span.clone(),
                            format!("unknown record type '{name}'"),
                        ));
                        Ty::Unknown
                    }
                }
            }
            Expr::Field(x, fname, span) => {
                let tx = self.type_of(x, env);
                match tx {
                    Ty::Named(n) => {
                        let kind = if n.contains('.') {
                            self.external_types.get(&n).map(|e| &e.kind)
                        } else {
                            self.types.get(&n).map(|t| &t.kind)
                        };
                        match kind {
                            Some(ast::TypeKind::Record(defs)) => {
                                match defs.iter().find(|(dn, _)| dn == fname) {
                                    Some((_, fte)) => ty_of(fte),
                                    None => {
                                        self.diags.push(
                                            Diag::error_at(
                                                span.clone(),
                                                format!("unknown field '{fname}' on record '{n}'"),
                                            )
                                            .with_code("E_NAME_003")
                                            .with_module(self.module.name.clone())
                                            .with_function(
                                                self.current_fn.clone().unwrap_or_default(),
                                            ),
                                        );
                                        Ty::Unknown
                                    }
                                }
                            }
                            Some(_) => {
                                self.diags.push(Diag::error_at(
                                    span.clone(),
                                    "field access requires a record type",
                                ));
                                Ty::Unknown
                            }
                            None => {
                                self.diags.push(Diag::error_at(
                                    span.clone(),
                                    format!("unknown type '{n}'"),
                                ));
                                Ty::Unknown
                            }
                        }
                    }
                    Ty::Unknown => Ty::Unknown,
                    _ => {
                        self.diags.push(Diag::error_at(
                            span.clone(),
                            "field access requires a record type",
                        ));
                        Ty::Unknown
                    }
                }
            }
            Expr::Raise(x, span) => {
                let _ = self.type_of(x, env);
                let _ = span;
                Ty::Unknown
            }
            Expr::Try(x, name, body, span) => {
                if name == "result" {
                    self.diags.push(Diag::error_at(
                        span.clone(),
                        "catch name 'result' is reserved for postconditions",
                    ));
                }
                let tx = self.type_of(x, env);
                match &tx {
                    Ty::Result(ok_ty, err_ty) => {
                        env.vars.push((name.clone(), (**err_ty).clone()));
                        let r = self.type_of(body, env);
                        env.vars.pop();
                        self.unify((**ok_ty).clone(), r, span, "try/catch result")
                    }
                    Ty::Unknown => Ty::Unknown,
                    _ => {
                        self.diags.push(Diag::error_at(
                            span.clone(),
                            "try requires a result-typed expression",
                        ));
                        Ty::Unknown
                    }
                }
            }
            Expr::Ok(x, _) => Ty::Result(Box::new(self.type_of(x, env)), Box::new(Ty::Unknown)),
            Expr::Err(x, _) => Ty::Result(Box::new(Ty::Unknown), Box::new(self.type_of(x, env))),
        }
    }

    fn type_call(&mut self, name: &str, args: &[Expr], span: &Span, env: &mut Env) -> Ty {
        if name == "io.print" {
            self.require_effects(&["io".to_string()], span, name, env);
            if args.len() != 1 {
                self.diags.push(Diag::error_at(
                    span.clone(),
                    "io.print takes exactly 1 argument",
                ));
            } else {
                let _ = self.type_of(&args[0], env);
            }
            return Ty::Prim(Prim::Nil);
        }
        if name == "io.print_debug" {
            self.require_effects(&["io".to_string()], span, name, env);
            if args.len() != 1 {
                self.diags.push(Diag::error_at(
                    span.clone(),
                    "io.print_debug takes exactly 1 argument",
                ));
            } else {
                let _ = self.type_of(&args[0], env);
            }
            return Ty::Prim(Prim::Nil);
        }
        if name == "sys.now_ms" {
            self.require_effects(&["clock".to_string()], span, name, env);
            if !args.is_empty() {
                self.diags.push(Diag::error_at(
                    span.clone(),
                    "sys.now_ms takes no arguments",
                ));
            }
            return Ty::Prim(Prim::I64);
        }
        if name == "len" {
            if args.len() != 1 {
                self.diags
                    .push(Diag::error_at(span.clone(), "len takes exactly 1 argument"));
                return Ty::Unknown;
            }
            let tv = self.type_of(&args[0], env);
            return match &tv {
                Ty::Vec(_) | Ty::Map(..) | Ty::Prim(Prim::Bytes) | Ty::Prim(Prim::String) => {
                    Ty::Prim(Prim::I64)
                }
                Ty::Unknown => Ty::Unknown,
                _ => {
                    self.diags.push(Diag::error_at(
                        span.clone(),
                        "len requires a vec, map, string or bytes value",
                    ));
                    Ty::Unknown
                }
            };
        }
        if name == "set" {
            if args.len() != 3 {
                self.diags.push(Diag::error_at(
                    span.clone(),
                    "set takes exactly 3 arguments",
                ));
                return Ty::Unknown;
            }
            let tm = self.type_of(&args[0], env);
            return match &tm {
                Ty::Map(kt, vt) => {
                    let tk = self.type_of(&args[1], env);
                    self.unify((**kt).clone(), tk, span, "map key type");
                    let tv = self.type_of(&args[2], env);
                    self.unify((**vt).clone(), tv, span, "map value type");
                    tm
                }
                Ty::Unknown => {
                    let _ = self.type_of(&args[1], env);
                    let _ = self.type_of(&args[2], env);
                    Ty::Unknown
                }
                _ => {
                    self.diags
                        .push(Diag::error_at(span.clone(), "set requires a map value"));
                    Ty::Unknown
                }
            };
        }
        if name == "lookup" {
            if args.len() != 2 {
                self.diags.push(Diag::error_at(
                    span.clone(),
                    "lookup takes exactly 2 arguments",
                ));
                return Ty::Unknown;
            }
            let tm = self.type_of(&args[0], env);
            return match &tm {
                Ty::Map(kt, vt) => {
                    let tk = self.type_of(&args[1], env);
                    self.unify((**kt).clone(), tk, span, "map key type");
                    Ty::Result(Box::new((**vt).clone()), Box::new(Ty::Prim(Prim::Nil)))
                }
                Ty::Unknown => {
                    let _ = self.type_of(&args[1], env);
                    Ty::Unknown
                }
                _ => {
                    self.diags
                        .push(Diag::error_at(span.clone(), "lookup requires a map value"));
                    Ty::Unknown
                }
            };
        }
        if name == "contains" {
            if args.len() != 2 {
                self.diags.push(Diag::error_at(
                    span.clone(),
                    "contains takes exactly 2 arguments",
                ));
                return Ty::Unknown;
            }
            let tm = self.type_of(&args[0], env);
            return match &tm {
                Ty::Map(kt, _) => {
                    let tk = self.type_of(&args[1], env);
                    self.unify((**kt).clone(), tk, span, "map key type");
                    Ty::Prim(Prim::Bool)
                }
                Ty::Unknown => {
                    let _ = self.type_of(&args[1], env);
                    Ty::Unknown
                }
                _ => {
                    self.diags.push(Diag::error_at(
                        span.clone(),
                        "contains requires a map value",
                    ));
                    Ty::Unknown
                }
            };
        }
        if name == "remove" {
            if args.len() != 2 {
                self.diags.push(Diag::error_at(
                    span.clone(),
                    "remove takes exactly 2 arguments",
                ));
                return Ty::Unknown;
            }
            let tm = self.type_of(&args[0], env);
            return match &tm {
                Ty::Map(kt, _) => {
                    let tk = self.type_of(&args[1], env);
                    self.unify((**kt).clone(), tk, span, "map key type");
                    tm
                }
                Ty::Unknown => {
                    let _ = self.type_of(&args[1], env);
                    Ty::Unknown
                }
                _ => {
                    self.diags
                        .push(Diag::error_at(span.clone(), "remove requires a map value"));
                    Ty::Unknown
                }
            };
        }
        if name == "keys" {
            if args.len() != 1 {
                self.diags.push(Diag::error_at(
                    span.clone(),
                    "keys takes exactly 1 argument",
                ));
                return Ty::Unknown;
            }
            let tm = self.type_of(&args[0], env);
            return match &tm {
                Ty::Map(kt, _) => Ty::Vec(Box::new((**kt).clone())),
                Ty::Unknown => Ty::Unknown,
                _ => {
                    self.diags
                        .push(Diag::error_at(span.clone(), "keys requires a map value"));
                    Ty::Unknown
                }
            };
        }
        if name == "unwrap" {
            if args.len() != 1 {
                self.diags.push(Diag::error_at(
                    span.clone(),
                    "unwrap takes exactly 1 argument",
                ));
                return Ty::Unknown;
            }
            let tx = self.type_of(&args[0], env);
            return match tx {
                Ty::Result(t, _) => *t,
                Ty::Unknown => Ty::Unknown,
                _ => {
                    self.diags.push(Diag::error_at(
                        span.clone(),
                        "unwrap requires a result-typed value",
                    ));
                    Ty::Unknown
                }
            };
        }
        if name == "slice" {
            if args.len() != 3 {
                self.diags.push(Diag::error_at(
                    span.clone(),
                    "slice takes exactly 3 arguments",
                ));
                return Ty::Unknown;
            }
            let tv = self.type_of(&args[0], env);
            let ts = self.type_of(&args[1], env);
            let te = self.type_of(&args[2], env);
            for (t, what) in [(&ts, "slice start"), (&te, "slice end")] {
                if !is_integer(t) && *t != Ty::Unknown {
                    self.diags.push(Diag::error_at(
                        span.clone(),
                        format!("{what} must be an integer"),
                    ));
                }
            }
            return match tv {
                Ty::Vec(t) => Ty::Vec(t),
                Ty::Prim(Prim::Bytes) => Ty::Prim(Prim::Bytes),
                Ty::Unknown => Ty::Unknown,
                _ => {
                    self.diags.push(Diag::error_at(
                        span.clone(),
                        "slice requires a vec or bytes value",
                    ));
                    Ty::Unknown
                }
            };
        }
        if name == "split" {
            if args.len() != 2 {
                self.diags.push(Diag::error_at(
                    span.clone(),
                    "split takes exactly 2 arguments",
                ));
                return Ty::Unknown;
            }
            let ts = self.type_of(&args[0], env);
            self.expect_ty(ts, &Ty::Prim(Prim::String), span, "split requires a string");
            let tp = self.type_of(&args[1], env);
            self.expect_ty(
                tp,
                &Ty::Prim(Prim::String),
                span,
                "split separator must be a string",
            );
            return Ty::Vec(Box::new(Ty::Prim(Prim::String)));
        }
        if name == "concat" {
            if args.len() != 2 {
                self.diags.push(Diag::error_at(
                    span.clone(),
                    "concat takes exactly 2 arguments",
                ));
                return Ty::Unknown;
            }
            let ta = self.type_of(&args[0], env);
            self.expect_ty(ta, &Ty::Prim(Prim::String), span, "concat requires strings");
            let tb = self.type_of(&args[1], env);
            self.expect_ty(tb, &Ty::Prim(Prim::String), span, "concat requires strings");
            return Ty::Prim(Prim::String);
        }
        if name == "to-string" {
            if args.len() != 1 {
                self.diags.push(Diag::error_at(
                    span.clone(),
                    "to-string takes exactly 1 argument",
                ));
                return Ty::Unknown;
            }
            let tx = self.type_of(&args[0], env);
            let printable = matches!(
                &tx,
                Ty::Prim(
                    Prim::U8
                        | Prim::U16
                        | Prim::U32
                        | Prim::U64
                        | Prim::I8
                        | Prim::I16
                        | Prim::I32
                        | Prim::I64
                        | Prim::F32
                        | Prim::F64
                        | Prim::Bool
                        | Prim::String,
                ) | Ty::Unknown
            );
            if !printable {
                self.diags.push(Diag::error_at(
                    span.clone(),
                    "to-string requires a number, bool or string",
                ));
            }
            return Ty::Prim(Prim::String);
        }
        if name == "to-bytes" {
            if args.len() != 1 {
                self.diags.push(Diag::error_at(
                    span.clone(),
                    "to-bytes takes exactly 1 argument",
                ));
                return Ty::Unknown;
            }
            let tx = self.type_of(&args[0], env);
            self.expect_ty(
                tx,
                &Ty::Prim(Prim::String),
                span,
                "to-bytes requires a string",
            );
            return Ty::Prim(Prim::Bytes);
        }
        if name == "is-ok" {
            if args.len() != 1 {
                self.diags.push(Diag::error_at(
                    span.clone(),
                    "is-ok takes exactly 1 argument",
                ));
                return Ty::Unknown;
            }
            let tx = self.type_of(&args[0], env);
            match &tx {
                Ty::Result(..) | Ty::Unknown => {}
                _ => {
                    self.diags.push(Diag::error_at(
                        span.clone(),
                        "is-ok requires a result-typed value",
                    ));
                }
            }
            return Ty::Prim(Prim::Bool);
        }
        if name == "join" {
            if args.len() != 2 {
                self.diags.push(Diag::error_at(
                    span.clone(),
                    "join takes exactly 2 arguments",
                ));
                return Ty::Unknown;
            }
            let tv = self.type_of(&args[0], env);
            match &tv {
                Ty::Vec(t) => {
                    if **t != Ty::Prim(Prim::String) && **t != Ty::Unknown {
                        self.diags.push(Diag::error_at(
                            span.clone(),
                            "join requires a vec of strings",
                        ));
                    }
                }
                Ty::Unknown => {}
                _ => {
                    self.diags.push(Diag::error_at(
                        span.clone(),
                        "join requires a vec of strings",
                    ));
                }
            }
            let ts = self.type_of(&args[1], env);
            self.expect_ty(
                ts,
                &Ty::Prim(Prim::String),
                span,
                "join separator must be a string",
            );
            return Ty::Prim(Prim::String);
        }
        if name == "strip-prefix" {
            if args.len() != 2 {
                self.diags.push(Diag::error_at(
                    span.clone(),
                    "strip-prefix takes exactly 2 arguments",
                ));
                return Ty::Unknown;
            }
            let ts = self.type_of(&args[0], env);
            self.expect_ty(
                ts,
                &Ty::Prim(Prim::String),
                span,
                "strip-prefix requires strings",
            );
            let tp = self.type_of(&args[1], env);
            self.expect_ty(
                tp,
                &Ty::Prim(Prim::String),
                span,
                "strip-prefix prefix must be a string",
            );
            return Ty::Prim(Prim::String);
        }
        if name == "before" {
            if args.len() != 2 {
                self.diags.push(Diag::error_at(
                    span.clone(),
                    "before takes exactly 2 arguments",
                ));
                return Ty::Unknown;
            }
            let ts = self.type_of(&args[0], env);
            self.expect_ty(ts, &Ty::Prim(Prim::String), span, "before requires strings");
            let tp = self.type_of(&args[1], env);
            self.expect_ty(
                tp,
                &Ty::Prim(Prim::String),
                span,
                "before separator must be a string",
            );
            return Ty::Prim(Prim::String);
        }
        if name == "ends-with" {
            if args.len() != 2 {
                self.diags.push(Diag::error_at(
                    span.clone(),
                    "ends-with takes exactly 2 arguments",
                ));
                return Ty::Unknown;
            }
            let ts = self.type_of(&args[0], env);
            self.expect_ty(
                ts,
                &Ty::Prim(Prim::String),
                span,
                "ends-with requires strings",
            );
            let tp = self.type_of(&args[1], env);
            self.expect_ty(
                tp,
                &Ty::Prim(Prim::String),
                span,
                "ends-with suffix must be a string",
            );
            return Ty::Prim(Prim::Bool);
        }
        if name == "sort" {
            if args.len() != 1 {
                self.diags.push(Diag::error_at(
                    span.clone(),
                    "sort takes exactly 1 argument",
                ));
                return Ty::Unknown;
            }
            let tv = self.type_of(&args[0], env);
            match &tv {
                Ty::Vec(t) => {
                    if **t != Ty::Prim(Prim::String) && **t != Ty::Unknown {
                        self.diags.push(Diag::error_at(
                            span.clone(),
                            "sort requires a vec of strings",
                        ));
                    }
                }
                Ty::Unknown => {}
                _ => {
                    self.diags.push(Diag::error_at(
                        span.clone(),
                        "sort requires a vec of strings",
                    ));
                }
            }
            return tv;
        }
        if name == "url-decode" {
            if args.len() != 1 {
                self.diags.push(Diag::error_at(
                    span.clone(),
                    "url-decode takes exactly 1 argument",
                ));
                return Ty::Unknown;
            }
            let tx = self.type_of(&args[0], env);
            self.expect_ty(
                tx,
                &Ty::Prim(Prim::String),
                span,
                "url-decode requires a string",
            );
            return Ty::Prim(Prim::String);
        }
        if name == "to-hex" {
            if args.len() != 1 {
                self.diags.push(Diag::error_at(
                    span.clone(),
                    "to-hex takes exactly 1 argument",
                ));
                return Ty::Unknown;
            }
            let tx = self.type_of(&args[0], env);
            self.expect_ty(tx, &Ty::Prim(Prim::Bytes), span, "to-hex requires bytes");
            return Ty::Prim(Prim::String);
        }
        if name == "ct-eq" {
            if args.len() != 2 {
                self.diags.push(Diag::error_at(
                    span.clone(),
                    "ct-eq takes exactly 2 arguments",
                ));
                return Ty::Unknown;
            }
            let ta = self.type_of(&args[0], env);
            self.expect_ty(ta, &Ty::Prim(Prim::String), span, "ct-eq requires strings");
            let tb = self.type_of(&args[1], env);
            self.expect_ty(tb, &Ty::Prim(Prim::String), span, "ct-eq requires strings");
            return Ty::Prim(Prim::Bool);
        }
        if name == "get" {
            if args.len() != 2 {
                self.diags.push(Diag::error_at(
                    span.clone(),
                    "get takes exactly 2 arguments",
                ));
                return Ty::Unknown;
            }
            let tv = self.type_of(&args[0], env);
            let ti = self.type_of(&args[1], env);
            if !is_integer(&ti) && ti != Ty::Unknown {
                self.diags
                    .push(Diag::error_at(span.clone(), "get index must be an integer"));
            }
            return match tv {
                Ty::Vec(t) => *t,
                Ty::Prim(Prim::Bytes) => Ty::Prim(Prim::U8),
                Ty::Unknown => Ty::Unknown,
                _ => {
                    self.diags.push(Diag::error_at(
                        span.clone(),
                        "get requires a vec or bytes value",
                    ));
                    Ty::Unknown
                }
            };
        }
        if name == "append" {
            if args.len() != 2 {
                self.diags.push(Diag::error_at(
                    span.clone(),
                    "append takes exactly 2 arguments",
                ));
                return Ty::Unknown;
            }
            let tv = self.type_of(&args[0], env);
            return match tv {
                Ty::Vec(t) => {
                    let tx = self.type_of(&args[1], env);
                    let t2 = self.unify((*t).clone(), tx, span, "append value type");
                    Ty::Vec(Box::new(t2))
                }
                Ty::Unknown => {
                    let _ = self.type_of(&args[1], env);
                    Ty::Unknown
                }
                _ => {
                    self.diags
                        .push(Diag::error_at(span.clone(), "append requires a vec value"));
                    Ty::Unknown
                }
            };
        }
        if let Some(ext) = self.external_fns.get(name).cloned() {
            self.require_effects(&ext.eff, span, name, env);
            if ext.params.len() != args.len() {
                self.diags.push(
                    Diag::error_at(
                        span.clone(),
                        format!(
                            "external fn '{name}' expects {} argument(s), got {}",
                            ext.params.len(),
                            args.len()
                        ),
                    )
                    .with_code("E_CALL_003"),
                );
            } else {
                for (pt, arg) in ext.params.iter().zip(args) {
                    let at = self.type_of(arg, env);
                    self.unify(
                        ty_of(pt),
                        at,
                        span,
                        format!("argument type mismatch for '{name}'"),
                    );
                }
            }
            return ty_of(&ext.returns);
        }
        if let Some(e) = self.exts.get(name).copied() {
            self.require_effects(&e.eff, span, name, env);
            if e.params.len() != args.len() {
                self.diags.push(
                    Diag::error_at(
                        span.clone(),
                        format!(
                            "extern '{name}' expects {} argument(s), got {}",
                            e.params.len(),
                            args.len()
                        ),
                    )
                    .with_code("E_CALL_003")
                    .with_module(self.module.name.clone())
                    .with_function(self.current_fn.clone().unwrap_or_default()),
                );
            } else {
                for ((_, pte), arg) in e.params.iter().zip(args) {
                    let pt = ty_of(pte);
                    let at = self.type_of(arg, env);
                    self.unify(
                        pt,
                        at,
                        span,
                        format!("argument type mismatch for extern '{name}'"),
                    );
                }
            }
            return ty_of(&e.returns);
        }
        if let Some(f) = self.fns.get(name).copied() {
            self.require_effects(&f.eff, span, name, env);
            if f.params.len() != args.len() {
                self.diags.push(
                    Diag::error_at(
                        span.clone(),
                        format!(
                            "fn '{name}' expects {} argument(s), got {}",
                            f.params.len(),
                            args.len()
                        ),
                    )
                    .with_code("E_CALL_003")
                    .with_module(self.module.name.clone())
                    .with_function(self.current_fn.clone().unwrap_or_default()),
                );
            } else {
                for ((_, pte), arg) in f.params.iter().zip(args) {
                    let pt = ty_of(pte);
                    let at = self.type_of(arg, env);
                    self.unify(pt, at, span, format!("argument type mismatch for '{name}'"));
                }
            }
            return ty_of(&f.returns);
        }
        if name.contains('.') {
            self.diags.push(
                Diag::error_at(
                    span.clone(),
                    format!("rust function '{name}' must be declared via (extern ...)"),
                )
                .with_code("E_CALL_002")
                .with_module(self.module.name.clone())
                .with_function(self.current_fn.clone().unwrap_or_default()),
            );
            return Ty::Unknown;
        }
        self.diags.push(
            Diag::error_at(span.clone(), format!("unknown function '{name}'"))
                .with_code("E_CALL_001")
                .with_module(self.module.name.clone())
                .with_function(self.current_fn.clone().unwrap_or_default()),
        );
        Ty::Unknown
    }

    fn require_effects(&mut self, effects: &[String], span: &Span, callee: &str, env: &Env) {
        if effects.is_empty() {
            return;
        }
        if env.is_pure {
            let mut d = Diag::error_at(
                span.clone(),
                format!(
                    "pure function cannot call effectful '{callee}' (requires {})",
                    effects.join(", ")
                ),
            )
            .with_code("E_EFFECT_002");
            if let Some(f) = &self.current_fn {
                d = d.with_repair(Repair::new("remove_pure").target(f.clone()));
            }
            d = d
                .with_module(self.module.name.clone())
                .with_function(self.current_fn.clone().unwrap_or_default());
            self.diags.push(d);
            return;
        }
        let missing: Vec<&String> = effects
            .iter()
            .filter(|e| !env.effects.contains(e))
            .collect();
        if !missing.is_empty() {
            let m: Vec<String> = missing.iter().map(|s| s.to_string()).collect();
            let mut d = Diag::error_at(
                span.clone(),
                format!(
                    "calling '{callee}' requires effect(s) {} not declared on this function",
                    m.join(", ")
                ),
            )
            .with_code("E_EFFECT_001");
            if let Some(f) = &self.current_fn {
                d = d.with_repair(
                    Repair::new("add_effect")
                        .target(f.clone())
                        .value(m.join(",")),
                );
            }
            d = d
                .with_module(self.module.name.clone())
                .with_function(self.current_fn.clone().unwrap_or_default());
            self.diags.push(d);
        }
    }

    fn finalize(mut self) -> Vec<Diag> {
        let module_name = self.module.name.clone();
        for d in &mut self.diags {
            if d.module.is_none() {
                d.module = Some(module_name.clone());
            }
            if d.function.is_none() {
                d.function = self.current_fn.clone();
            }
            if d.affected_modules.is_empty() {
                d.affected_modules.push(module_name.clone());
            }
        }
        self.diags
    }

    fn expect_ty(&mut self, got: Ty, want: &Ty, span: &Span, msg: &str) {
        if got != *want && got != Ty::Unknown {
            self.diags.push(
                Diag::error_at(span.clone(), format!("{msg} (found {})", ty_name(&got)))
                    .with_code("E_TYPE_001")
                    .with_module(self.module.name.clone())
                    .with_function(self.current_fn.clone().unwrap_or_default()),
            );
        }
    }

    fn unify(&mut self, a: Ty, b: Ty, span: &Span, what: impl Into<String>) -> Ty {
        let what = what.into();
        match (a, b) {
            (Ty::Unknown, t) => t,
            (t, Ty::Unknown) => t,
            (Ty::Result(a1, a2), Ty::Result(b1, b2)) => {
                let t1 = self.unify(*a1, *b1, span, what.clone());
                let t2 = self.unify(*a2, *b2, span, what.clone());
                Ty::Result(Box::new(t1), Box::new(t2))
            }
            (Ty::Vec(a1), Ty::Vec(b1)) => {
                Ty::Vec(Box::new(self.unify(*a1, *b1, span, what.clone())))
            }
            (Ty::Map(ak, av), Ty::Map(bk, bv)) => Ty::Map(
                Box::new(self.unify(*ak, *bk, span, what.clone())),
                Box::new(self.unify(*av, *bv, span, what.clone())),
            ),
            (x, y) if x == y => x,
            (x, y) => {
                let mut d = Diag::error_at(
                    span.clone(),
                    format!(
                        "{}: type mismatch ({} vs {})",
                        what,
                        ty_name(&x),
                        ty_name(&y)
                    ),
                )
                .with_code("E_TYPE_001");
                d.expected.push(ty_name(&x));
                d.actual.push(ty_name(&y));
                d = d
                    .with_module(self.module.name.clone())
                    .with_function(self.current_fn.clone().unwrap_or_default());
                self.diags.push(d);
                Ty::Unknown
            }
        }
    }
}
