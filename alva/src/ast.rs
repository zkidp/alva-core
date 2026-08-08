use crate::diag::Diag;
use crate::s_expr::{Atom, Node, Span};

pub struct Module {
    pub name: String,
    pub version: String,
    pub rust_deps: Vec<(String, String)>,
    pub deps: Vec<(String, String)>,
    pub caps: Vec<String>,
    pub exports: Vec<String>,
    pub types: Vec<TypeDef>,
    pub fns: Vec<FnDef>,
    pub exts: Vec<ExternDef>,
    pub tests: Vec<TestDef>,
    pub benches: Vec<BenchDef>,
}

#[derive(Clone, Debug, PartialEq)]
pub enum Prim {
    U8,
    U16,
    U32,
    U64,
    I8,
    I16,
    I32,
    I64,
    F32,
    F64,
    Bool,
    String,
    Bytes,
    Nil,
}

pub fn prim_name(p: &Prim) -> &'static str {
    match p {
        Prim::U8 => "u8",
        Prim::U16 => "u16",
        Prim::U32 => "u32",
        Prim::U64 => "u64",
        Prim::I8 => "i8",
        Prim::I16 => "i16",
        Prim::I32 => "i32",
        Prim::I64 => "i64",
        Prim::F32 => "f32",
        Prim::F64 => "f64",
        Prim::Bool => "bool",
        Prim::String => "string",
        Prim::Bytes => "bytes",
        Prim::Nil => "nil",
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum TypeExpr {
    Prim(Prim),
    Named(String),
    Vec(Box<TypeExpr>),
    Map(Box<TypeExpr>, Box<TypeExpr>),
    Result(Box<TypeExpr>, Box<TypeExpr>),
}

#[derive(Clone, Debug)]
pub enum TypeKind {
    Record(Vec<(String, TypeExpr)>),
    Enum(Vec<String>),
    Alias(TypeExpr),
}

#[derive(Clone, Debug)]
pub struct TypeDef {
    pub name: String,
    pub kind: TypeKind,
    pub span: Span,
}

#[derive(Clone, Debug)]
pub struct FnDef {
    pub name: String,
    pub params: Vec<(String, TypeExpr)>,
    pub returns: TypeExpr,
    pub pre: Vec<Expr>,
    pub post: Vec<Expr>,
    pub inv: Vec<Expr>,
    pub pure: bool,
    pub eff: Vec<String>,
    pub body: Vec<Expr>,
    pub span: Span,
}

#[derive(Clone, Debug)]
pub struct ExternDef {
    pub name: String,
    pub params: Vec<(String, TypeExpr)>,
    pub returns: TypeExpr,
    pub eff: Vec<String>,
    pub pure: bool,
    pub unsafe_ffi: bool,
    pub template: String,
    pub span: Span,
}

#[derive(Clone, Debug)]
pub struct TestDef {
    pub name: String,
    pub body: Expr,
    pub span: Span,
}

#[derive(Clone, Debug)]
pub struct BenchDef {
    pub name: String,
    pub ms_budget: Option<i64>,
    pub setup: Vec<Expr>,
    pub body: Expr,
    pub span: Span,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum BinOp {
    Add,
    Sub,
    Mul,
    Div,
    Mod,
    Eq,
    Ne,
    Lt,
    Le,
    Gt,
    Ge,
    And,
    Or,
}

#[derive(Clone, Debug)]
pub enum Expr {
    Int(i64, Span),
    UInt(u64, Span),
    Float(f64, Span),
    Str(String, Span),
    Bool(bool, Span),
    Bytes(Vec<u8>, Span),
    Nil(Span),
    Ref(String, Span),
    Call(String, Vec<Expr>, Span),
    Bin(BinOp, Box<Expr>, Box<Expr>, Span),
    Not(Box<Expr>, Span),
    If(Box<Expr>, Box<Expr>, Box<Expr>, Span),
    Let(String, Option<TypeExpr>, Box<Expr>, Box<Expr>, Span),
    Block(Vec<Expr>, Span),
    VecLit(TypeExpr, Vec<Expr>, Span),
    Len(Box<Expr>, Span),
    Get(Box<Expr>, Box<Expr>, Span),
    Append(Box<Expr>, Box<Expr>, Span),
    As(TypeExpr, Box<Expr>, Span),
    Fold(
        String,
        Box<Expr>,
        Box<Expr>,
        String,
        TypeExpr,
        Box<Expr>,
        Box<Expr>,
        Span,
    ),
    Variant(String, String, Span),
    Match(String, Box<Expr>, Vec<(String, Expr)>, Span),
    MapLit(TypeExpr, TypeExpr, Vec<(Expr, Expr)>, Span),
    Set(Box<Expr>, Box<Expr>, Box<Expr>, Span),
    Lookup(Box<Expr>, Box<Expr>, Span),
    Contains(Box<Expr>, Box<Expr>, Span),
    Remove(Box<Expr>, Box<Expr>, Span),
    Keys(Box<Expr>, Span),
    Unwrap(Box<Expr>, Span),
    ErrValue(Box<Expr>, Span),
    Slice(Box<Expr>, Box<Expr>, Box<Expr>, Span),
    Split(Box<Expr>, Box<Expr>, Span),
    Concat(Box<Expr>, Box<Expr>, Span),
    ToString(Box<Expr>, Span),
    ParseInt(Box<Expr>, Span),
    ToBytes(Box<Expr>, Span),
    IsOk(Box<Expr>, Span),
    Join(Box<Expr>, Box<Expr>, Span),
    StripPrefix(Box<Expr>, Box<Expr>, Span),
    Before(Box<Expr>, Box<Expr>, Span),
    EndsWith(Box<Expr>, Box<Expr>, Span),
    Sort(Box<Expr>, Span),
    UrlDecode(Box<Expr>, Span),
    ToHex(Box<Expr>, Span),
    CtEq(Box<Expr>, Box<Expr>, Span),
    Loop(
        String,
        TypeExpr,
        Box<Expr>,
        Option<Box<Expr>>,
        Box<Expr>,
        Box<Expr>,
        Span,
    ),
    Record(String, Vec<(String, Expr)>, Span),
    Field(Box<Expr>, String, Span),
    Raise(Box<Expr>, Span),
    Try(Box<Expr>, String, Box<Expr>, Span),
    Ok(Box<Expr>, Span),
    Err(Box<Expr>, Span),
}

impl Expr {
    pub fn span(&self) -> Span {
        match self {
            Expr::Int(_, s)
            | Expr::UInt(_, s)
            | Expr::Float(_, s)
            | Expr::Str(_, s)
            | Expr::Bool(_, s)
            | Expr::Bytes(_, s)
            | Expr::Nil(s)
            | Expr::Ref(_, s)
            | Expr::Call(_, _, s)
            | Expr::Bin(_, _, _, s)
            | Expr::Not(_, s)
            | Expr::If(_, _, _, s)
            | Expr::Let(_, _, _, _, s)
            | Expr::Block(_, s)
            | Expr::VecLit(_, _, s)
            | Expr::Len(_, s)
            | Expr::Get(_, _, s)
            | Expr::Append(_, _, s)
            | Expr::As(_, _, s)
            | Expr::Fold(_, _, _, _, _, _, _, s)
            | Expr::Variant(_, _, s)
            | Expr::Match(_, _, _, s)
            | Expr::MapLit(_, _, _, s)
            | Expr::Set(_, _, _, s)
            | Expr::Lookup(_, _, s)
            | Expr::Contains(_, _, s)
            | Expr::Remove(_, _, s)
            | Expr::Keys(_, s)
            | Expr::Unwrap(_, s)
            | Expr::ErrValue(_, s)
            | Expr::Slice(_, _, _, s)
            | Expr::Split(_, _, s)
            | Expr::Concat(_, _, s)
            | Expr::ToString(_, s)
            | Expr::ParseInt(_, s)
            | Expr::ToBytes(_, s)
            | Expr::IsOk(_, s)
            | Expr::Join(_, _, s)
            | Expr::StripPrefix(_, _, s)
            | Expr::Before(_, _, s)
            | Expr::EndsWith(_, _, s)
            | Expr::Sort(_, s)
            | Expr::UrlDecode(_, s)
            | Expr::ToHex(_, s)
            | Expr::CtEq(_, _, s)
            | Expr::Loop(_, _, _, _, _, _, s)
            | Expr::Record(_, _, s)
            | Expr::Field(_, _, s)
            | Expr::Raise(_, s)
            | Expr::Try(_, _, _, s)
            | Expr::Ok(_, s)
            | Expr::Err(_, s) => s.clone(),
        }
    }
}

pub fn from_tree(root: &Node) -> Result<Module, Vec<Diag>> {
    let mut diags = Vec::new();
    let items = match root {
        Node::List(items, _) => items,
        _ => {
            return Err(vec![Diag::error(
                "top-level node must be a (module ...) list",
            )]);
        }
    };
    let is_module = matches!(
        items.first(),
        Some(Node::Atom(Atom::Sym(s), _)) if s == "module"
    );
    if !is_module {
        return Err(vec![Diag::error_at(
            root.span(),
            "top-level node must be (module ...)",
        )]);
    }

    let mut m = Module {
        name: String::new(),
        version: String::new(),
        rust_deps: Vec::new(),
        deps: Vec::new(),
        caps: Vec::new(),
        exports: Vec::new(),
        types: Vec::new(),
        fns: Vec::new(),
        exts: Vec::new(),
        tests: Vec::new(),
        benches: Vec::new(),
    };

    for item in &items[1..] {
        let tag = match first_sym(item) {
            Some(t) => t.to_string(),
            None => {
                diags.push(Diag::error_at(
                    item.span(),
                    "expected a tagged node like (name ...)",
                ));
                continue;
            }
        };
        match tag.as_str() {
            "name" => match list_str(item, 1) {
                Some(s) => m.name = s,
                None => diags.push(Diag::error_at(
                    item.span(),
                    "(name ...) requires a string argument",
                )),
            },
            "version" => match list_str(item, 1) {
                Some(s) => m.version = s,
                None => diags.push(Diag::error_at(
                    item.span(),
                    "(version ...) requires a string argument",
                )),
            },
            "use" => match parse_use(item) {
                Ok(d) => m.rust_deps.push(d),
                Err(d) => diags.extend(d),
            },
            "dep" => match list_str2(item) {
                Some((a, b)) => m.deps.push((a, b)),
                None => diags.push(Diag::error_at(
                    item.span(),
                    "(dep name version) requires two strings",
                )),
            },
            "cap" => match list_syms(item) {
                Some(v) => m.caps = v,
                None => diags.push(Diag::error_at(
                    item.span(),
                    "(cap ...) requires symbol arguments",
                )),
            },
            "export" => match list_syms(item) {
                Some(v) => m.exports = v,
                None => diags.push(Diag::error_at(
                    item.span(),
                    "(export ...) requires symbol arguments",
                )),
            },
            "type" => match parse_type_def(item) {
                Ok(t) => m.types.push(t),
                Err(d) => diags.extend(d),
            },
            "fn" => match parse_fn_def(item) {
                Ok(f) => m.fns.push(f),
                Err(d) => diags.extend(d),
            },
            "extern" => match parse_extern(item) {
                Ok(e) => m.exts.push(e),
                Err(d) => diags.extend(d),
            },
            "test" => match parse_test_def(item) {
                Ok(t) => m.tests.push(t),
                Err(d) => diags.extend(d),
            },
            "bench" => match parse_bench_def(item) {
                Ok(b) => m.benches.push(b),
                Err(d) => diags.extend(d),
            },
            other => diags.push(Diag::error_at(
                item.span(),
                format!("unknown module member '{other}'"),
            )),
        }
    }

    if m.name.is_empty() {
        diags.push(Diag::error("module requires (name \"...\")"));
    }
    if m.version.is_empty() {
        diags.push(Diag::error("module requires (version \"...\")"));
    }

    if diags.iter().any(|d| d.severity == "error") {
        Err(diags)
    } else {
        Ok(m)
    }
}

fn first_sym(n: &Node) -> Option<&str> {
    if let Node::List(items, _) = n {
        if let Some(Node::Atom(Atom::Sym(s), _)) = items.first() {
            return Some(s);
        }
    }
    None
}

fn list_items(n: &Node) -> &[Node] {
    match n {
        Node::List(items, _) => items,
        _ => &[],
    }
}

fn sym_text(n: &Node) -> Option<&str> {
    match n {
        Node::Atom(Atom::Sym(s), _) => Some(s),
        _ => None,
    }
}

fn list_str(n: &Node, idx: usize) -> Option<String> {
    match list_items(n).get(idx) {
        Some(Node::Atom(Atom::Str(s), _)) => Some(s.clone()),
        _ => None,
    }
}

fn list_str2(n: &Node) -> Option<(String, String)> {
    let items = list_items(n);
    match (items.get(1), items.get(2)) {
        (Some(Node::Atom(Atom::Str(a), _)), Some(Node::Atom(Atom::Str(b), _))) => {
            Some((a.clone(), b.clone()))
        }
        _ => None,
    }
}

fn list_syms(n: &Node) -> Option<Vec<String>> {
    let items = list_items(n);
    if items.is_empty() {
        return None;
    }
    let mut out = Vec::new();
    for it in &items[1..] {
        match it {
            Node::Atom(Atom::Sym(s), _) => out.push(s.clone()),
            _ => return None,
        }
    }
    Some(out)
}

fn parse_use(n: &Node) -> Result<(String, String), Vec<Diag>> {
    let items = list_items(n);
    let rust_ok = matches!(
        items.get(1),
        Some(Node::Atom(Atom::Sym(s), _)) if s == "rust"
    );
    if !rust_ok {
        return Err(vec![Diag::error_at(
            n.span(),
            "(use rust crate version) expected",
        )]);
    }
    match (items.get(2), items.get(3)) {
        (Some(Node::Atom(Atom::Str(a), _)), Some(Node::Atom(Atom::Str(b), _))) => {
            Ok((a.clone(), b.clone()))
        }
        _ => Err(vec![Diag::error_at(
            n.span(),
            "(use rust crate version) requires two strings",
        )]),
    }
}

fn parse_type_def(n: &Node) -> Result<TypeDef, Vec<Diag>> {
    let items = list_items(n);
    if items.len() != 3 {
        return Err(vec![Diag::error_at(
            n.span(),
            "(type name (record ...)) expected",
        )]);
    }
    let name = match &items[1] {
        Node::Atom(Atom::Sym(s), _) => s.clone(),
        _ => {
            return Err(vec![Diag::error_at(
                items[1].span(),
                "type name must be a symbol",
            )])
        }
    };
    let body = &items[2];
    match first_sym(body) {
        Some("record") => {
            let mut fields = Vec::new();
            let mut diags = Vec::new();
            for f in &list_items(body)[1..] {
                match parse_field(f) {
                    Ok(fld) => fields.push(fld),
                    Err(d) => diags.extend(d),
                }
            }
            if diags.is_empty() {
                Ok(TypeDef {
                    name,
                    kind: TypeKind::Record(fields),
                    span: n.span(),
                })
            } else {
                Err(diags)
            }
        }
        Some("alias") => {
            let t = match list_items(body).get(1) {
                Some(t) => t,
                None => {
                    return Err(vec![Diag::error_at(
                        body.span(),
                        "(alias type-expr) requires an argument",
                    )])
                }
            };
            let te = parse_type_expr(t)?;
            Ok(TypeDef {
                name,
                kind: TypeKind::Alias(te),
                span: n.span(),
            })
        }
        Some("enum") => {
            let mut variants = Vec::new();
            let mut diags = Vec::new();
            for v in &list_items(body)[1..] {
                let vi = list_items(v);
                if vi.len() != 2 || first_sym(v) != Some("variant") {
                    diags.push(Diag::error_at(v.span(), "(variant name) expected"));
                    continue;
                }
                match sym_text(&vi[1]) {
                    Some(s) => variants.push(s.to_string()),
                    None => diags.push(Diag::error_at(
                        vi[1].span(),
                        "variant name must be a symbol",
                    )),
                }
            }
            if variants.is_empty() {
                diags.push(Diag::error_at(
                    body.span(),
                    "enum requires at least one variant",
                ));
            }
            if diags.is_empty() {
                Ok(TypeDef {
                    name,
                    kind: TypeKind::Enum(variants),
                    span: n.span(),
                })
            } else {
                Err(diags)
            }
        }
        _ => Err(vec![Diag::error_at(
            body.span(),
            "type body must be (record ...), (enum ...) or (alias ...)",
        )]),
    }
}

fn parse_field(n: &Node) -> Result<(String, TypeExpr), Vec<Diag>> {
    let items = list_items(n);
    if items.len() != 3 || first_sym(n) != Some("field") {
        return Err(vec![Diag::error_at(
            n.span(),
            "(field name type-expr) expected",
        )]);
    }
    let name = match &items[1] {
        Node::Atom(Atom::Sym(s), _) => s.clone(),
        _ => {
            return Err(vec![Diag::error_at(
                items[1].span(),
                "field name must be a symbol",
            )])
        }
    };
    let te = parse_type_expr(&items[2])?;
    Ok((name, te))
}

fn parse_type_expr(n: &Node) -> Result<TypeExpr, Vec<Diag>> {
    match n {
        Node::Atom(Atom::Sym(s), _) => Ok(TypeExpr::Named(s.clone())),
        Node::Atom(Atom::Str(_), _) => {
            Err(vec![Diag::error_at(n.span(), "type name must be a symbol")])
        }
        Node::List(items, span) => match first_sym(n) {
            Some("prim") => {
                let p = match items.get(1).and_then(sym_text) {
                    Some("u8") => Prim::U8,
                    Some("u16") => Prim::U16,
                    Some("u32") => Prim::U32,
                    Some("u64") => Prim::U64,
                    Some("i8") => Prim::I8,
                    Some("i16") => Prim::I16,
                    Some("i32") => Prim::I32,
                    Some("i64") => Prim::I64,
                    Some("f32") => Prim::F32,
                    Some("f64") => Prim::F64,
                    Some("bool") => Prim::Bool,
                    Some("string") => Prim::String,
                    Some("bytes") => Prim::Bytes,
                    Some("nil") => Prim::Nil,
                    _ => return Err(vec![Diag::error_at(n.span(), "unknown primitive type")]),
                };
                Ok(TypeExpr::Prim(p))
            }
            Some("result") => {
                if items.len() != 3 {
                    return Err(vec![Diag::error_at(
                        n.span(),
                        "(result ok-type err-type) expected",
                    )]);
                }
                let a = parse_type_expr(&items[1])?;
                let b = parse_type_expr(&items[2])?;
                Ok(TypeExpr::Result(Box::new(a), Box::new(b)))
            }
            Some("vec") => {
                if items.len() != 2 {
                    return Err(vec![Diag::error_at(n.span(), "(vec type-expr) expected")]);
                }
                let t = parse_type_expr(&items[1])?;
                Ok(TypeExpr::Vec(Box::new(t)))
            }
            Some("map") => {
                if items.len() != 3 {
                    return Err(vec![Diag::error_at(
                        n.span(),
                        "(map key-type value-type) expected",
                    )]);
                }
                let k = parse_type_expr(&items[1])?;
                let v = parse_type_expr(&items[2])?;
                Ok(TypeExpr::Map(Box::new(k), Box::new(v)))
            }
            _ => Err(vec![Diag::error_at(
                span.clone(),
                "expected (prim ...), (vec ...), (map ...), (result ...) or a type name",
            )]),
        },
    }
}

fn parse_fn_def(n: &Node) -> Result<FnDef, Vec<Diag>> {
    let items = list_items(n);
    if items.len() < 2 {
        return Err(vec![Diag::error_at(n.span(), "(fn name ...) expected")]);
    }
    let name = match &items[1] {
        Node::Atom(Atom::Sym(s), _) => s.clone(),
        _ => {
            return Err(vec![Diag::error_at(
                items[1].span(),
                "fn name must be a symbol",
            )])
        }
    };
    let mut f = FnDef {
        name,
        params: Vec::new(),
        returns: TypeExpr::Prim(Prim::Nil),
        pre: Vec::new(),
        post: Vec::new(),
        inv: Vec::new(),
        pure: false,
        eff: Vec::new(),
        body: Vec::new(),
        span: n.span(),
    };
    let mut diags = Vec::new();
    let mut has_returns = false;

    for item in &items[2..] {
        match first_sym(item) {
            Some("params") => match parse_params(item) {
                Ok(p) => f.params = p,
                Err(d) => diags.extend(d),
            },
            Some("returns") => {
                let t = match list_items(item).get(1) {
                    Some(t) => t,
                    None => {
                        diags.push(Diag::error_at(
                            item.span(),
                            "(returns type-expr) requires an argument",
                        ));
                        continue;
                    }
                };
                match parse_type_expr(t) {
                    Ok(te) => {
                        f.returns = te;
                        has_returns = true;
                    }
                    Err(d) => diags.extend(d),
                }
            }
            Some("pre") => match parse_contract_expr(item) {
                Ok(e) => f.pre.push(e),
                Err(d) => diags.extend(d),
            },
            Some("post") => match parse_contract_expr(item) {
                Ok(e) => f.post.push(e),
                Err(d) => diags.extend(d),
            },
            Some("inv") => match parse_contract_expr(item) {
                Ok(e) => f.inv.push(e),
                Err(d) => diags.extend(d),
            },
            Some("pure") => f.pure = true,
            Some("eff") => match list_syms(item) {
                Some(v) => f.eff = v,
                None => diags.push(Diag::error_at(
                    item.span(),
                    "(eff ...) requires symbol arguments",
                )),
            },
            Some("body") => match parse_body(item) {
                Ok(b) => f.body = b,
                Err(d) => diags.extend(d),
            },
            other => diags.push(Diag::error_at(
                item.span(),
                format!("unknown fn member '{other:?}'"),
            )),
        }
    }

    if !has_returns {
        diags.push(Diag::error_at(
            n.span(),
            format!("fn '{}' requires (returns type-expr)", f.name),
        ));
    }
    if f.body.is_empty() {
        diags.push(Diag::error_at(
            n.span(),
            format!(
                "fn '{}' requires a (body ...) with at least one expression",
                f.name
            ),
        ));
    }

    if diags.iter().any(|d| d.severity == "error") {
        Err(diags)
    } else {
        Ok(f)
    }
}

fn parse_extern(n: &Node) -> Result<ExternDef, Vec<Diag>> {
    let items = list_items(n);
    let name = match items.get(1) {
        Some(Node::Atom(Atom::Sym(s), _)) => s.clone(),
        _ => {
            return Err(vec![Diag::error_at(
                n.span(),
                "(extern name (params ...) (returns ...) (rust \"template\")) expected",
            )])
        }
    };
    let mut params = Vec::new();
    let mut returns = None;
    let mut eff = Vec::new();
    let mut pure = false;
    let mut unsafe_ffi = false;
    let mut template = None;
    let mut diags = Vec::new();
    for item in &items[2..] {
        match first_sym(item) {
            Some("params") => match parse_params(item) {
                Ok(p) => params = p,
                Err(d) => diags.extend(d),
            },
            Some("returns") => match list_items(item).get(1) {
                Some(t) => match parse_type_expr(t) {
                    Ok(te) => returns = Some(te),
                    Err(d) => diags.extend(d),
                },
                None => diags.push(Diag::error_at(
                    item.span(),
                    "(returns type-expr) requires an argument",
                )),
            },
            Some("rust") => match list_str(item, 1) {
                Some(s) => template = Some(s),
                None => diags.push(Diag::error_at(
                    item.span(),
                    "(rust \"template\") requires a string",
                )),
            },
            Some("eff") => match list_syms(item) {
                Some(v) => eff = v,
                None => diags.push(Diag::error_at(
                    item.span(),
                    "(eff ...) requires symbol arguments",
                )),
            },
            Some("pure") => pure = true,
            Some("unsafe") => unsafe_ffi = true,
            _ => diags.push(Diag::error_at(
                item.span(),
                "unknown extern member (expected params/returns/eff/pure/unsafe/rust)",
            )),
        }
    }
    if returns.is_none() {
        diags.push(Diag::error_at(
            n.span(),
            format!("extern '{name}' requires (returns type-expr)"),
        ));
    }
    if template.is_none() {
        diags.push(Diag::error_at(
            n.span(),
            format!("extern '{name}' requires (rust \"template\")"),
        ));
    }
    if diags.iter().any(|d| d.severity == "error") {
        Err(diags)
    } else {
        Ok(ExternDef {
            name,
            params,
            returns: returns.unwrap(),
            eff,
            pure,
            unsafe_ffi,
            template: template.unwrap(),
            span: n.span(),
        })
    }
}

fn parse_params(n: &Node) -> Result<Vec<(String, TypeExpr)>, Vec<Diag>> {
    let items = list_items(n);
    let mut out = Vec::new();
    let mut diags = Vec::new();
    for p in &items[1..] {
        let pi = list_items(p);
        if pi.len() != 3 || first_sym(p) != Some("param") {
            diags.push(Diag::error_at(p.span(), "(param name type-expr) expected"));
            continue;
        }
        let name = match &pi[1] {
            Node::Atom(Atom::Sym(s), _) => s.clone(),
            _ => {
                diags.push(Diag::error_at(pi[1].span(), "param name must be a symbol"));
                continue;
            }
        };
        match parse_type_expr(&pi[2]) {
            Ok(te) => out.push((name, te)),
            Err(d) => diags.extend(d),
        }
    }
    if diags.iter().any(|d| d.severity == "error") {
        Err(diags)
    } else {
        Ok(out)
    }
}

fn parse_contract_expr(n: &Node) -> Result<Expr, Vec<Diag>> {
    match list_items(n).get(1) {
        Some(e) => parse_expr(e),
        None => Err(vec![Diag::error_at(
            n.span(),
            "contract requires an expression argument",
        )]),
    }
}

fn parse_body(n: &Node) -> Result<Vec<Expr>, Vec<Diag>> {
    let items = list_items(n);
    let mut out = Vec::new();
    let mut diags = Vec::new();
    for e in &items[1..] {
        match parse_expr(e) {
            Ok(x) => out.push(x),
            Err(d) => diags.extend(d),
        }
    }
    if diags.iter().any(|d| d.severity == "error") {
        Err(diags)
    } else {
        Ok(out)
    }
}

fn parse_test_def(n: &Node) -> Result<TestDef, Vec<Diag>> {
    let items = list_items(n);
    let name = match items.get(1) {
        Some(Node::Atom(Atom::Sym(s), _)) => s.clone(),
        _ => {
            return Err(vec![Diag::error_at(
                n.span(),
                "(test name (body expr)) expected",
            )])
        }
    };
    let body_node = match items.get(2) {
        Some(b) if first_sym(b) == Some("body") => match list_items(b).get(1) {
            Some(e) => e,
            None => {
                return Err(vec![Diag::error_at(
                    b.span(),
                    "(body expr) requires an expression",
                )])
            }
        },
        _ => {
            return Err(vec![Diag::error_at(
                n.span(),
                "(test name (body expr)) expected",
            )])
        }
    };
    let body = parse_expr(body_node)?;
    Ok(TestDef {
        name,
        body,
        span: n.span(),
    })
}

fn parse_bench_def(n: &Node) -> Result<BenchDef, Vec<Diag>> {
    let items = list_items(n);
    let name = match items.get(1) {
        Some(Node::Atom(Atom::Sym(s), _)) => s.clone(),
        _ => return Err(vec![Diag::error_at(n.span(), "(bench name ...) expected")]),
    };
    let mut ms_budget = None;
    let mut setup = Vec::new();
    let mut body = None;
    let mut diags = Vec::new();

    for item in &items[2..] {
        match first_sym(item) {
            Some("budget") => {
                for b in &list_items(item)[1..] {
                    match first_sym(b) {
                        Some("ms") => {
                            match list_items(b)
                                .get(1)
                                .and_then(atom_text)
                                .and_then(|s| s.parse::<i64>().ok())
                            {
                                Some(v) => ms_budget = Some(v),
                                None => diags.push(Diag::error_at(
                                    b.span(),
                                    "(ms n) requires a positive integer",
                                )),
                            }
                        }
                        Some("ops") | Some("mem") => {
                            // v0.1 只强制时间预算；ops/mem 预留
                        }
                        _ => diags.push(Diag::error_at(
                            b.span(),
                            "unknown budget item (expected ms/ops/mem)",
                        )),
                    }
                }
            }
            Some("setup") => {
                let mut s = Vec::new();
                for e in &list_items(item)[1..] {
                    match parse_expr(e) {
                        Ok(x) => s.push(x),
                        Err(d) => diags.extend(d),
                    }
                }
                setup = s;
            }
            Some("body") => match list_items(item).get(1) {
                Some(e) => match parse_expr(e) {
                    Ok(x) => body = Some(x),
                    Err(d) => diags.extend(d),
                },
                None => diags.push(Diag::error_at(
                    item.span(),
                    "(body expr) requires an expression",
                )),
            },
            _ => diags.push(Diag::error_at(
                item.span(),
                "unknown bench member (expected budget/setup/body)",
            )),
        }
    }

    if body.is_none() {
        diags.push(Diag::error_at(
            n.span(),
            format!("bench '{name}' requires a (body expr)"),
        ));
    }

    if diags.iter().any(|d| d.severity == "error") {
        Err(diags)
    } else {
        Ok(BenchDef {
            name,
            ms_budget,
            setup,
            body: body.unwrap(),
            span: n.span(),
        })
    }
}

fn binop(tag: &str) -> Option<BinOp> {
    Some(match tag {
        "+" => BinOp::Add,
        "-" => BinOp::Sub,
        "*" => BinOp::Mul,
        "/" => BinOp::Div,
        "mod" => BinOp::Mod,
        "==" => BinOp::Eq,
        "!=" => BinOp::Ne,
        "<" => BinOp::Lt,
        "<=" => BinOp::Le,
        ">" => BinOp::Gt,
        ">=" => BinOp::Ge,
        "and" => BinOp::And,
        "or" => BinOp::Or,
        _ => return None,
    })
}

fn parse_expr(n: &Node) -> Result<Expr, Vec<Diag>> {
    let span = n.span();
    match n {
        Node::Atom(Atom::Sym(s), _) => Err(vec![Diag::error_at(
            span,
            format!("expected an expression, found bare symbol '{s}'"),
        )]),
        Node::Atom(Atom::Str(_), _) => Err(vec![Diag::error_at(
            span,
            "expected an expression, found bare string",
        )]),
        Node::List(items, _) => {
            let tag = match first_sym(n) {
                Some(t) => t,
                None => return Err(vec![Diag::error_at(span, "expected a tagged expression")]),
            };
            match tag {
                "int" => match items
                    .get(1)
                    .and_then(atom_text)
                    .and_then(|s| s.parse::<i64>().ok())
                {
                    Some(v) => Ok(Expr::Int(v, span)),
                    None => Err(vec![Diag::error_at(
                        span,
                        "(int ...) requires an integer literal",
                    )]),
                },
                "uint" => match items
                    .get(1)
                    .and_then(atom_text)
                    .and_then(|s| s.parse::<u64>().ok())
                {
                    Some(v) => Ok(Expr::UInt(v, span)),
                    None => Err(vec![Diag::error_at(
                        span,
                        "(uint ...) requires an unsigned integer literal",
                    )]),
                },
                "float" => match items
                    .get(1)
                    .and_then(atom_text)
                    .and_then(|s| s.parse::<f64>().ok())
                {
                    Some(v) => Ok(Expr::Float(v, span)),
                    None => Err(vec![Diag::error_at(
                        span,
                        "(float ...) requires a float literal",
                    )]),
                },
                "string" => match items.get(1) {
                    Some(Node::Atom(Atom::Str(s), _)) => Ok(Expr::Str(s.clone(), span)),
                    _ => Err(vec![Diag::error_at(
                        span,
                        "(string ...) requires a string literal",
                    )]),
                },
                "bool" => match items.get(1).and_then(atom_text) {
                    Some("true") => Ok(Expr::Bool(true, span)),
                    Some("false") => Ok(Expr::Bool(false, span)),
                    _ => Err(vec![Diag::error_at(
                        span,
                        "(bool ...) requires true or false",
                    )]),
                },
                "bytes" => match items.get(1) {
                    Some(Node::Atom(Atom::Str(s), _)) => match parse_hex(s) {
                        Some(v) => Ok(Expr::Bytes(v, span)),
                        None => Err(vec![Diag::error_at(
                            span,
                            "(bytes ...) requires a hex string",
                        )]),
                    },
                    _ => Err(vec![Diag::error_at(
                        span,
                        "(bytes ...) requires a hex string",
                    )]),
                },
                "nil" => Ok(Expr::Nil(span)),
                "ref" => match items.get(1).and_then(sym_text) {
                    Some(s) => Ok(Expr::Ref(s.to_string(), span)),
                    None => Err(vec![Diag::error_at(span, "(ref name) requires a symbol")]),
                },
                "call" => {
                    let name = match items.get(1).and_then(sym_text) {
                        Some(s) => s.to_string(),
                        None => {
                            return Err(vec![Diag::error_at(
                                span,
                                "(call name args...) requires a function name",
                            )])
                        }
                    };
                    let mut args = Vec::new();
                    let mut diags = Vec::new();
                    for a in &items[2..] {
                        match parse_expr(a) {
                            Ok(x) => args.push(x),
                            Err(d) => diags.extend(d),
                        }
                    }
                    if diags.is_empty() {
                        Ok(Expr::Call(name, args, span))
                    } else {
                        Err(diags)
                    }
                }
                "+" | "-" | "*" | "/" | "mod" | "==" | "!=" | "<" | "<=" | ">" | ">=" | "and"
                | "or" => {
                    if items.len() != 3 {
                        return Err(vec![Diag::error_at(
                            span,
                            format!("({tag} a b) requires exactly two operands"),
                        )]);
                    }
                    let a = parse_expr(&items[1])?;
                    let b = parse_expr(&items[2])?;
                    Ok(Expr::Bin(
                        binop(tag).unwrap(),
                        Box::new(a),
                        Box::new(b),
                        span,
                    ))
                }
                "not" => {
                    let a = match items.get(1) {
                        Some(a) => parse_expr(a)?,
                        None => {
                            return Err(vec![Diag::error_at(
                                span,
                                "(not expr) requires one operand",
                            )])
                        }
                    };
                    Ok(Expr::Not(Box::new(a), span))
                }
                "if" => {
                    if items.len() != 4 {
                        return Err(vec![Diag::error_at(
                            span,
                            "(if cond then else) requires three operands",
                        )]);
                    }
                    let c = parse_expr(&items[1])?;
                    let t = parse_expr(&items[2])?;
                    let e = parse_expr(&items[3])?;
                    Ok(Expr::If(Box::new(c), Box::new(t), Box::new(e), span))
                }
                "let" => {
                    let name = match items.get(1).and_then(sym_text) {
                        Some(s) => s.to_string(),
                        None => {
                            return Err(vec![Diag::error_at(
                                span,
                                "(let name ...) requires a symbol name",
                            )])
                        }
                    };
                    if items.len() == 5 {
                        match parse_type_expr(&items[2]) {
                            Ok(t) => {
                                let v = parse_expr(&items[3])?;
                                let b = parse_expr(&items[4])?;
                                Ok(Expr::Let(name, Some(t), Box::new(v), Box::new(b), span))
                            }
                            Err(_) => Err(vec![Diag::error_at(
                                span,
                                "(let name value body) takes a single body expression; wrap multiple statements in (block ...)",
                            )]),
                        }
                    } else if items.len() == 4 {
                        let v = parse_expr(&items[2])?;
                        let b = parse_expr(&items[3])?;
                        Ok(Expr::Let(name, None, Box::new(v), Box::new(b), span))
                    } else {
                        Err(vec![Diag::error_at(
                            span,
                            "(let name [type] value body) expected; wrap multiple statements in (block ...)",
                        )])
                    }
                }
                "block" => {
                    let mut exprs = Vec::new();
                    let mut diags = Vec::new();
                    for e in &items[1..] {
                        match parse_expr(e) {
                            Ok(x) => exprs.push(x),
                            Err(d) => diags.extend(d),
                        }
                    }
                    if exprs.is_empty() {
                        return Err(vec![Diag::error_at(
                            span,
                            "(block ...) requires at least one expression",
                        )]);
                    }
                    if diags.is_empty() {
                        Ok(Expr::Block(exprs, span))
                    } else {
                        Err(diags)
                    }
                }
                "vec" => {
                    let t = match items.get(1) {
                        Some(t) => parse_type_expr(t)?,
                        None => {
                            return Err(vec![Diag::error_at(
                                span,
                                "(vec type-expr elements...) requires an element type",
                            )])
                        }
                    };
                    let mut elems = Vec::new();
                    let mut diags = Vec::new();
                    for e in &items[2..] {
                        match parse_expr(e) {
                            Ok(x) => elems.push(x),
                            Err(d) => diags.extend(d),
                        }
                    }
                    if diags.is_empty() {
                        Ok(Expr::VecLit(t, elems, span))
                    } else {
                        Err(diags)
                    }
                }
                "len" => {
                    let v = match items.get(1) {
                        Some(v) => parse_expr(v)?,
                        None => {
                            return Err(vec![Diag::error_at(
                                span,
                                "(len vec-expr) requires an argument",
                            )])
                        }
                    };
                    Ok(Expr::Len(Box::new(v), span))
                }
                "get" => {
                    if items.len() != 3 {
                        return Err(vec![Diag::error_at(span, "(get vec-expr index) expected")]);
                    }
                    let v = parse_expr(&items[1])?;
                    let i = parse_expr(&items[2])?;
                    Ok(Expr::Get(Box::new(v), Box::new(i), span))
                }
                "append" => {
                    if items.len() != 3 {
                        return Err(vec![Diag::error_at(
                            span,
                            "(append vec-expr value) expected",
                        )]);
                    }
                    let v = parse_expr(&items[1])?;
                    let x = parse_expr(&items[2])?;
                    Ok(Expr::Append(Box::new(v), Box::new(x), span))
                }
                "as" => {
                    if items.len() != 3 {
                        return Err(vec![Diag::error_at(span, "(as type-expr expr) expected")]);
                    }
                    let t = parse_type_expr(&items[1])?;
                    let x = parse_expr(&items[2])?;
                    Ok(Expr::As(t, Box::new(x), span))
                }
                "fold" => {
                    if items.len() != 5 {
                        return Err(vec![Diag::error_at(
                            span,
                            "(fold idx (range lo hi) (acc name type init) body) expected",
                        )]);
                    }
                    let idx = match sym_text(&items[1]) {
                        Some(s) => s.to_string(),
                        None => {
                            return Err(vec![Diag::error_at(
                                items[1].span(),
                                "fold index must be a symbol",
                            )])
                        }
                    };
                    let range = &items[2];
                    if first_sym(range) != Some("range") {
                        return Err(vec![Diag::error_at(range.span(), "(range lo hi) expected")]);
                    }
                    let ri = list_items(range);
                    if ri.len() != 3 {
                        return Err(vec![Diag::error_at(
                            range.span(),
                            "(range lo hi) requires two bounds",
                        )]);
                    }
                    let lo = parse_expr(&ri[1])?;
                    let hi = parse_expr(&ri[2])?;
                    let acc = &items[3];
                    if first_sym(acc) != Some("acc") {
                        return Err(vec![Diag::error_at(
                            acc.span(),
                            "(acc name type init) expected",
                        )]);
                    }
                    let ai = list_items(acc);
                    if ai.len() != 4 {
                        return Err(vec![Diag::error_at(
                            acc.span(),
                            "(acc name type init) requires 3 arguments",
                        )]);
                    }
                    let acc_name = match sym_text(&ai[1]) {
                        Some(s) => s.to_string(),
                        None => {
                            return Err(vec![Diag::error_at(
                                ai[1].span(),
                                "accumulator name must be a symbol",
                            )])
                        }
                    };
                    let acc_ty = parse_type_expr(&ai[2])?;
                    let init = parse_expr(&ai[3])?;
                    let body = parse_expr(&items[4])?;
                    Ok(Expr::Fold(
                        idx,
                        Box::new(lo),
                        Box::new(hi),
                        acc_name,
                        acc_ty,
                        Box::new(init),
                        Box::new(body),
                        span,
                    ))
                }
                "variant" => {
                    if items.len() != 3 {
                        return Err(vec![Diag::error_at(
                            span,
                            "(variant TypeName variant-name) expected",
                        )]);
                    }
                    let ty_name = match sym_text(&items[1]) {
                        Some(s) => s.to_string(),
                        None => {
                            return Err(vec![Diag::error_at(
                                items[1].span(),
                                "enum type name must be a symbol",
                            )])
                        }
                    };
                    let vname = match sym_text(&items[2]) {
                        Some(s) => s.to_string(),
                        None => {
                            return Err(vec![Diag::error_at(
                                items[2].span(),
                                "variant name must be a symbol",
                            )])
                        }
                    };
                    Ok(Expr::Variant(ty_name, vname, span))
                }
                "match" => {
                    if items.len() < 4 {
                        return Err(vec![Diag::error_at(
                            span,
                            "(match TypeName expr (case variant body)...) expected",
                        )]);
                    }
                    let ty_name = match sym_text(&items[1]) {
                        Some(s) => s.to_string(),
                        None => {
                            return Err(vec![Diag::error_at(
                                items[1].span(),
                                "match type name must be a symbol",
                            )])
                        }
                    };
                    let value = parse_expr(&items[2])?;
                    let mut cases = Vec::new();
                    let mut diags = Vec::new();
                    for c in &items[3..] {
                        let ci = list_items(c);
                        if ci.len() != 3 || first_sym(c) != Some("case") {
                            diags.push(Diag::error_at(c.span(), "(case variant body) expected"));
                            continue;
                        }
                        let vname = match sym_text(&ci[1]) {
                            Some(s) => s.to_string(),
                            None => {
                                diags.push(Diag::error_at(
                                    ci[1].span(),
                                    "case variant must be a symbol",
                                ));
                                continue;
                            }
                        };
                        match parse_expr(&ci[2]) {
                            Ok(b) => cases.push((vname, b)),
                            Err(d) => diags.extend(d),
                        }
                    }
                    if diags.is_empty() {
                        Ok(Expr::Match(ty_name, Box::new(value), cases, span))
                    } else {
                        Err(diags)
                    }
                }
                "map" => {
                    if items.len() < 3 {
                        return Err(vec![Diag::error_at(
                            span,
                            "(map key-type value-type (k v)*) expected",
                        )]);
                    }
                    let kt = parse_type_expr(&items[1])?;
                    let vt = parse_type_expr(&items[2])?;
                    let mut entries = Vec::new();
                    let mut diags = Vec::new();
                    for e in &items[3..] {
                        let ei = list_items(e);
                        if ei.len() != 2 {
                            diags.push(Diag::error_at(e.span(), "map entry must be (key value)"));
                            continue;
                        }
                        let k = parse_expr(&ei[0])?;
                        let v = parse_expr(&ei[1])?;
                        entries.push((k, v));
                    }
                    if diags.is_empty() {
                        Ok(Expr::MapLit(kt, vt, entries, span))
                    } else {
                        Err(diags)
                    }
                }
                "set" => {
                    if items.len() != 4 {
                        return Err(vec![Diag::error_at(span, "(set map key value) expected")]);
                    }
                    let m = parse_expr(&items[1])?;
                    let k = parse_expr(&items[2])?;
                    let v = parse_expr(&items[3])?;
                    Ok(Expr::Set(Box::new(m), Box::new(k), Box::new(v), span))
                }
                "lookup" => {
                    if items.len() != 3 {
                        return Err(vec![Diag::error_at(span, "(lookup map key) expected")]);
                    }
                    let m = parse_expr(&items[1])?;
                    let k = parse_expr(&items[2])?;
                    Ok(Expr::Lookup(Box::new(m), Box::new(k), span))
                }
                "contains" => {
                    if items.len() != 3 {
                        return Err(vec![Diag::error_at(span, "(contains map key) expected")]);
                    }
                    let m = parse_expr(&items[1])?;
                    let k = parse_expr(&items[2])?;
                    Ok(Expr::Contains(Box::new(m), Box::new(k), span))
                }
                "remove" => {
                    if items.len() != 3 {
                        return Err(vec![Diag::error_at(span, "(remove map key) expected")]);
                    }
                    let m = parse_expr(&items[1])?;
                    let k = parse_expr(&items[2])?;
                    Ok(Expr::Remove(Box::new(m), Box::new(k), span))
                }
                "keys" => {
                    let m = match items.get(1) {
                        Some(m) => parse_expr(m)?,
                        None => {
                            return Err(vec![Diag::error_at(
                                span,
                                "(keys map) requires an argument",
                            )])
                        }
                    };
                    Ok(Expr::Keys(Box::new(m), span))
                }
                "unwrap" => {
                    let x = match items.get(1) {
                        Some(x) => parse_expr(x)?,
                        None => {
                            return Err(vec![Diag::error_at(
                                span,
                                "(unwrap result-expr) requires an argument",
                            )])
                        }
                    };
                    Ok(Expr::Unwrap(Box::new(x), span))
                }
                "err-value" => {
                    let x = match items.get(1) {
                        Some(x) => parse_expr(x)?,
                        None => {
                            return Err(vec![Diag::error_at(
                                span,
                                "(err-value result-expr) requires an argument",
                            )])
                        }
                    };
                    Ok(Expr::ErrValue(Box::new(x), span))
                }
                "slice" => {
                    if items.len() != 4 {
                        return Err(vec![Diag::error_at(
                            span,
                            "(slice vec-expr start end) expected",
                        )]);
                    }
                    let v = parse_expr(&items[1])?;
                    let s = parse_expr(&items[2])?;
                    let e = parse_expr(&items[3])?;
                    Ok(Expr::Slice(Box::new(v), Box::new(s), Box::new(e), span))
                }
                "split" => {
                    if items.len() != 3 {
                        return Err(vec![Diag::error_at(span, "(split string sep) expected")]);
                    }
                    let s = parse_expr(&items[1])?;
                    let sep = parse_expr(&items[2])?;
                    Ok(Expr::Split(Box::new(s), Box::new(sep), span))
                }
                "concat" => {
                    if items.len() != 3 {
                        return Err(vec![Diag::error_at(span, "(concat a b) expected")]);
                    }
                    let a = parse_expr(&items[1])?;
                    let b = parse_expr(&items[2])?;
                    Ok(Expr::Concat(Box::new(a), Box::new(b), span))
                }
                "to-string" => {
                    let x = match items.get(1) {
                        Some(x) => parse_expr(x)?,
                        None => {
                            return Err(vec![Diag::error_at(
                                span,
                                "(to-string expr) requires an argument",
                            )])
                        }
                    };
                    Ok(Expr::ToString(Box::new(x), span))
                }
                "parse-int" => {
                    let x = match items.get(1) {
                        Some(x) => parse_expr(x)?,
                        None => {
                            return Err(vec![Diag::error_at(
                                span,
                                "(parse-int string) requires an argument",
                            )])
                        }
                    };
                    Ok(Expr::ParseInt(Box::new(x), span))
                }
                "to-bytes" => {
                    let x = match items.get(1) {
                        Some(x) => parse_expr(x)?,
                        None => {
                            return Err(vec![Diag::error_at(
                                span,
                                "(to-bytes string) requires an argument",
                            )])
                        }
                    };
                    Ok(Expr::ToBytes(Box::new(x), span))
                }
                "is-ok" => {
                    let x = match items.get(1) {
                        Some(x) => parse_expr(x)?,
                        None => {
                            return Err(vec![Diag::error_at(
                                span,
                                "(is-ok result-expr) requires an argument",
                            )])
                        }
                    };
                    Ok(Expr::IsOk(Box::new(x), span))
                }
                "join" => {
                    if items.len() != 3 {
                        return Err(vec![Diag::error_at(
                            span,
                            "(join vec-of-strings sep) expected",
                        )]);
                    }
                    let v = parse_expr(&items[1])?;
                    let sep = parse_expr(&items[2])?;
                    Ok(Expr::Join(Box::new(v), Box::new(sep), span))
                }
                "strip-prefix" => {
                    if items.len() != 3 {
                        return Err(vec![Diag::error_at(
                            span,
                            "(strip-prefix s prefix) expected",
                        )]);
                    }
                    let s = parse_expr(&items[1])?;
                    let p = parse_expr(&items[2])?;
                    Ok(Expr::StripPrefix(Box::new(s), Box::new(p), span))
                }
                "before" => {
                    if items.len() != 3 {
                        return Err(vec![Diag::error_at(span, "(before s sep) expected")]);
                    }
                    let s = parse_expr(&items[1])?;
                    let sep = parse_expr(&items[2])?;
                    Ok(Expr::Before(Box::new(s), Box::new(sep), span))
                }
                "ends-with" => {
                    if items.len() != 3 {
                        return Err(vec![Diag::error_at(span, "(ends-with s suffix) expected")]);
                    }
                    let s = parse_expr(&items[1])?;
                    let suf = parse_expr(&items[2])?;
                    Ok(Expr::EndsWith(Box::new(s), Box::new(suf), span))
                }
                "sort" => {
                    let v = match items.get(1) {
                        Some(v) => parse_expr(v)?,
                        None => {
                            return Err(vec![Diag::error_at(
                                span,
                                "(sort vec-of-strings) requires an argument",
                            )])
                        }
                    };
                    Ok(Expr::Sort(Box::new(v), span))
                }
                "url-decode" => {
                    let x = match items.get(1) {
                        Some(x) => parse_expr(x)?,
                        None => {
                            return Err(vec![Diag::error_at(
                                span,
                                "(url-decode string) requires an argument",
                            )])
                        }
                    };
                    Ok(Expr::UrlDecode(Box::new(x), span))
                }
                "to-hex" => {
                    let x = match items.get(1) {
                        Some(x) => parse_expr(x)?,
                        None => {
                            return Err(vec![Diag::error_at(
                                span,
                                "(to-hex bytes) requires an argument",
                            )])
                        }
                    };
                    Ok(Expr::ToHex(Box::new(x), span))
                }
                "ct-eq" => {
                    if items.len() != 3 {
                        return Err(vec![Diag::error_at(span, "(ct-eq a b) expected")]);
                    }
                    let a = parse_expr(&items[1])?;
                    let b = parse_expr(&items[2])?;
                    Ok(Expr::CtEq(Box::new(a), Box::new(b), span))
                }
                "loop" => {
                    if items.len() != 4 && items.len() != 5 {
                        return Err(vec![Diag::error_at(
                            span,
                            "(loop (acc name type init) [(inv expr)] cond body) expected",
                        )]);
                    }
                    let acc = &items[1];
                    if first_sym(acc) != Some("acc") {
                        return Err(vec![Diag::error_at(
                            acc.span(),
                            "(acc name type init) expected",
                        )]);
                    }
                    let ai = list_items(acc);
                    if ai.len() != 4 {
                        return Err(vec![Diag::error_at(
                            acc.span(),
                            "(acc name type init) requires 3 arguments",
                        )]);
                    }
                    let acc_name = match sym_text(&ai[1]) {
                        Some(s) => s.to_string(),
                        None => {
                            return Err(vec![Diag::error_at(
                                ai[1].span(),
                                "accumulator name must be a symbol",
                            )])
                        }
                    };
                    let acc_ty = parse_type_expr(&ai[2])?;
                    let init = parse_expr(&ai[3])?;
                    let (inv, cond, body) = if items.len() == 5 {
                        if first_sym(&items[2]) != Some("inv") {
                            return Err(vec![Diag::error_at(
                                items[2].span(),
                                "(inv expr) expected as the loop invariant",
                            )]);
                        }
                        let inv_node = match list_items(&items[2]).get(1) {
                            Some(e) => e,
                            None => {
                                return Err(vec![Diag::error_at(
                                    items[2].span(),
                                    "(inv expr) requires an expression",
                                )])
                            }
                        };
                        (
                            Some(Box::new(parse_expr(inv_node)?)),
                            parse_expr(&items[3])?,
                            parse_expr(&items[4])?,
                        )
                    } else {
                        (None, parse_expr(&items[2])?, parse_expr(&items[3])?)
                    };
                    Ok(Expr::Loop(
                        acc_name,
                        acc_ty,
                        Box::new(init),
                        inv,
                        Box::new(cond),
                        Box::new(body),
                        span,
                    ))
                }
                "record" => {
                    let name = match items.get(1).and_then(sym_text) {
                        Some(s) => s.to_string(),
                        None => {
                            return Err(vec![Diag::error_at(
                                span,
                                "(record Name (field value)...) requires a type name",
                            )])
                        }
                    };
                    let mut fields = Vec::new();
                    let mut diags = Vec::new();
                    for f in &items[2..] {
                        let fi = list_items(f);
                        if fi.len() != 2 {
                            diags.push(Diag::error_at(
                                f.span(),
                                "record field must be (name value)",
                            ));
                            continue;
                        }
                        let fname = match sym_text(&fi[0]) {
                            Some(s) => s.to_string(),
                            None => {
                                diags.push(Diag::error_at(
                                    fi[0].span(),
                                    "field name must be a symbol",
                                ));
                                continue;
                            }
                        };
                        match parse_expr(&fi[1]) {
                            Ok(v) => fields.push((fname, v)),
                            Err(d) => diags.extend(d),
                        }
                    }
                    if diags.is_empty() {
                        Ok(Expr::Record(name, fields, span))
                    } else {
                        Err(diags)
                    }
                }
                "field" => {
                    if items.len() != 3 {
                        return Err(vec![Diag::error_at(span, "(field expr name) expected")]);
                    }
                    let x = parse_expr(&items[1])?;
                    let name = match &items[2] {
                        Node::Atom(Atom::Sym(s), _) => s.clone(),
                        Node::Atom(Atom::Str(s), _) => s.clone(),
                        _ => {
                            return Err(vec![Diag::error_at(
                                span,
                                "field name must be a symbol or string",
                            )])
                        }
                    };
                    Ok(Expr::Field(Box::new(x), name, span))
                }
                "raise" => {
                    let a = match items.get(1) {
                        Some(a) => parse_expr(a)?,
                        None => {
                            return Err(vec![Diag::error_at(
                                span,
                                "(raise expr) requires an argument",
                            )])
                        }
                    };
                    Ok(Expr::Raise(Box::new(a), span))
                }
                "try" => {
                    if items.len() != 3 {
                        return Err(vec![Diag::error_at(
                            span,
                            "(try expr (catch name body)) expected",
                        )]);
                    }
                    let x = parse_expr(&items[1])?;
                    let catch = &items[2];
                    if first_sym(catch) != Some("catch") {
                        return Err(vec![Diag::error_at(
                            catch.span(),
                            "(catch name body) expected",
                        )]);
                    }
                    let ci = list_items(catch);
                    if ci.len() != 3 {
                        return Err(vec![Diag::error_at(
                            catch.span(),
                            "(catch name body) expected",
                        )]);
                    }
                    let cname = match sym_text(&ci[1]) {
                        Some(s) => s.to_string(),
                        None => {
                            return Err(vec![Diag::error_at(
                                ci[1].span(),
                                "catch name must be a symbol",
                            )])
                        }
                    };
                    let cbody = parse_expr(&ci[2])?;
                    Ok(Expr::Try(Box::new(x), cname, Box::new(cbody), span))
                }
                "ok" => {
                    let a = match items.get(1) {
                        Some(a) => parse_expr(a)?,
                        None => {
                            return Err(vec![Diag::error_at(
                                span,
                                "(ok expr) requires an argument",
                            )])
                        }
                    };
                    Ok(Expr::Ok(Box::new(a), span))
                }
                "err" => {
                    let a = match items.get(1) {
                        Some(a) => parse_expr(a)?,
                        None => {
                            return Err(vec![Diag::error_at(
                                span,
                                "(err expr) requires an argument",
                            )])
                        }
                    };
                    Ok(Expr::Err(Box::new(a), span))
                }
                other => Err(vec![Diag::error_at(
                    span,
                    format!("unknown expression tag '{other}'"),
                )]),
            }
        }
    }
}

fn atom_text(n: &Node) -> Option<&str> {
    match n {
        Node::Atom(Atom::Sym(s), _) => Some(s),
        Node::Atom(Atom::Str(s), _) => Some(s),
        _ => None,
    }
}

fn parse_hex(s: &str) -> Option<Vec<u8>> {
    let s = s.trim();
    if !s.len().is_multiple_of(2) {
        return None;
    }
    let b = s.as_bytes();
    let mut out = Vec::with_capacity(b.len() / 2);
    for i in (0..b.len()).step_by(2) {
        let hi = hex_val(b[i])?;
        let lo = hex_val(b[i + 1])?;
        out.push((hi << 4) | lo);
    }
    Some(out)
}

fn hex_val(c: u8) -> Option<u8> {
    match c {
        b'0'..=b'9' => Some(c - b'0'),
        b'a'..=b'f' => Some(c - b'a' + 10),
        b'A'..=b'F' => Some(c - b'A' + 10),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::s_expr;

    #[test]
    fn debug_from_tree_hello() {
        let src = std::fs::read_to_string("examples/hello.alva").unwrap();
        let tree = s_expr::parse_with_limits(&src, &s_expr::Limits::default()).unwrap();
        match from_tree(&tree) {
            Ok(m) => assert_eq!(m.name, "hello"),
            Err(ds) => {
                panic!("from_tree failed: {:?}", ds);
            }
        }
    }
}
