use crate::ast::{self, BinOp, Expr, TypeExpr, TypeKind};
use crate::s_expr::{Atom, Limits, Node, Span};
use std::fmt::Write;

const ALIASES: &[(&str, &str)] = &[
    ("is_ok", "is-ok"),
    ("to_bytes", "to-bytes"),
    ("err_value", "err-value"),
    ("parse_int", "parse-int"),
    ("to_string", "to-string"),
    ("strip_prefix", "strip-prefix"),
    ("ends_with", "ends-with"),
    ("url_decode", "url-decode"),
    ("to_hex", "to-hex"),
    ("ct_eq", "ct-eq"),
];

const COMPACT_PARSE_ERROR: &str = "E_AEP_COMPACT_PARSE";

fn canonical(name: &str) -> &str {
    ALIASES
        .iter()
        .find(|(short, _)| *short == name)
        .map_or(name, |(_, long)| long)
}

fn ident(name: &str) -> String {
    if name.split('.').all(|part| {
        part.starts_with(|c: char| c.is_ascii_alphabetic() || c == '_')
            && part.chars().all(|c| c.is_ascii_alphanumeric() || c == '_')
    }) && !matches!(
        name,
        "true"
            | "false"
            | "nil"
            | "if"
            | "let"
            | "block"
            | "do"
            | "loop"
            | "for"
            | "match"
            | "raise"
            | "return"
            | "while"
            | "mut"
    ) {
        name.to_owned()
    } else {
        format!("`{}`", escape(name).replace('`', "\\`"))
    }
}

fn escape(s: &str) -> String {
    s.replace('\\', "\\\\")
        .replace('"', "\\\"")
        .replace('\n', "\\n")
        .replace('\r', "\\r")
        .replace('\t', "\\t")
}

fn string(s: &str) -> String {
    format!("\"{}\"", escape(s))
}

fn called(name: &str) -> String {
    for (short, long) in ALIASES {
        if name == *long {
            return (*short).into();
        }
        if name == *short {
            return format!("`{name}`");
        }
    }
    if matches!(name, "ok" | "err" | "float_bits" | "not") {
        return format!("`{name}`");
    }
    ident(name)
}

pub fn qualify_colliding_aliases(text: &str, local_functions: &[&str]) -> String {
    // Operate on lexer spans so aliases inside strings or quoted names never
    // change. Work from right to left to keep the byte offsets valid.
    let Ok(tokens) = lex(text, &Limits::default()) else {
        return text.to_owned();
    };
    let mut out = text.to_owned();
    let lines: Vec<_> = std::iter::once(0)
        .chain(text.match_indices('\n').map(|(i, _)| i + 1))
        .collect();
    for pair in tokens.windows(2).rev() {
        let (Token::Word(name, false), span) = &pair[0] else {
            continue;
        };
        if !matches!(pair[1].0, Token::Punct("("))
            || !local_functions.contains(&name.as_str())
            || canonical(name) == name
        {
            continue;
        }
        let row = &text[lines[span.line as usize - 1]..];
        let byte = lines[span.line as usize - 1]
            + row.char_indices().nth(span.col as usize - 1).unwrap().0;
        if text[..byte].ends_with(['@', '.']) {
            continue;
        }
        out.replace_range(byte..byte + name.len(), &format!("`{}`", canonical(name)));
    }
    out
}

fn op(op: BinOp) -> (&'static str, u8) {
    match op {
        BinOp::Or => ("||", 2),
        BinOp::And => ("&&", 3),
        BinOp::Eq => ("==", 4),
        BinOp::Ne => ("!=", 4),
        BinOp::Lt => ("<", 4),
        BinOp::Le => ("<=", 4),
        BinOp::Gt => (">", 4),
        BinOp::Ge => (">=", 4),
        BinOp::Add => ("+", 5),
        BinOp::Sub => ("-", 5),
        BinOp::Mul => ("*", 6),
        BinOp::Div => ("/", 6),
        BinOp::Mod => ("%", 6),
    }
}

pub fn ty(t: &TypeExpr) -> String {
    match t {
        TypeExpr::Prim(p) => ast::prim_name(p).into(),
        TypeExpr::Named(n) if primitive(n) || matches!(n.as_str(), "vec" | "map" | "result") => {
            format!("`{n}`")
        }
        TypeExpr::Named(n) => ident(n),
        TypeExpr::Vec(t) => format!("vec<{}>", ty(t)),
        TypeExpr::Map(k, v) => format!("map<{}, {}>", ty(k), ty(v)),
        TypeExpr::Result(ok, err) => format!("result<{}, {}>", ty(ok), ty(err)),
    }
}

fn primitive(n: &str) -> bool {
    matches!(
        n,
        "i8" | "i16"
            | "i32"
            | "i64"
            | "u8"
            | "u16"
            | "u32"
            | "u64"
            | "f32"
            | "f64"
            | "string"
            | "bytes"
            | "bool"
            | "nil"
    )
}

fn fields(fields: &[(String, Expr)]) -> String {
    fields
        .iter()
        .map(|(n, v)| format!("{}: {}", ident(n), expression(v, 0)))
        .collect::<Vec<_>>()
        .join(", ")
}

fn args(xs: &[Expr]) -> String {
    xs.iter()
        .map(|e| expression(e, 0))
        .collect::<Vec<_>>()
        .join(", ")
}

fn section(e: &Expr) -> String {
    let content = match e {
        Expr::Block(xs, _) if xs.len() >= 2 && !xs.iter().any(|x| matches!(x, Expr::Let(..))) => {
            sequence(xs)
        }
        _ => tail(e),
    };
    format!("{{ {content} }}")
}

fn tail(e: &Expr) -> String {
    if let Expr::Let(n, t, value, body, _) = e {
        return format!(
            "let {}{} = {}; {}",
            ident(n),
            annotation(t.as_ref()),
            expression(value, 0),
            tail(body)
        );
    }
    match e {
        Expr::Block(xs, _) if xs.len() >= 2 && !xs.iter().any(|x| matches!(x, Expr::Let(..))) => {
            sequence(xs)
        }
        _ => expression(e, 0),
    }
}

fn annotation(t: Option<&TypeExpr>) -> String {
    t.map_or_else(String::new, |t| format!(": {}", ty(t)))
}

fn sequence(xs: &[Expr]) -> String {
    let Some((last, prefix)) = xs.split_last() else {
        return String::new();
    };
    let mut out = prefix.iter().map(|e| expression(e, 0)).collect::<Vec<_>>();
    out.push(if matches!(last, Expr::Let(..)) {
        tail(last)
    } else {
        expression(last, 0)
    });
    out.join("; ")
}

pub fn body(xs: &[Expr]) -> String {
    format!("{{ {} }}", sequence(xs))
}

fn expression(e: &Expr, min: u8) -> String {
    use Expr::{Err as ErrExpr, Ok as OkExpr, *};
    let show = |e| expression(e, 0);
    let binary =
        |name, a: &Expr, b: &Expr| format!("@{name}({}, {})", expression(a, 0), expression(b, 0));
    let unary = |name, a: &Expr| format!("@{name}({})", expression(a, 0));
    let (text, priority) = match e {
        Int(v, _) => (v.to_string(), 10),
        UInt(v, _) => (format!("{v}u"), 10),
        Float(v, _) => (
            if v.is_finite() {
                format!("{v:?}")
            } else {
                format!("float_bits(\"{:016x}\")", v.to_bits())
            },
            10,
        ),
        Str(v, _) => (string(v), 10),
        Bool(v, _) => (v.to_string(), 10),
        Bytes(v, _) => (
            format!(
                "0x\"{}\"",
                v.iter().map(|b| format!("{b:02x}")).collect::<String>()
            ),
            10,
        ),
        Nil(_) => ("nil".into(), 10),
        Ref(n, _) => (
            if n.contains('.') {
                format!("`{}`", escape(n).replace('`', "\\`"))
            } else {
                ident(n)
            },
            10,
        ),
        Call(n, xs, _) => (format!("{}({})", called(n), args(xs)), 10),
        Bin(operator, a, b, _) => {
            let (symbol, p) = op(*operator);
            (
                format!(
                    "{} {symbol} {}",
                    expression(a, p + u8::from(p == 4)),
                    expression(b, p + 1)
                ),
                p,
            )
        }
        Not(x, _) => (format!("!{}", expression(x, 8)), 8),
        If(c, t, f, _) => (
            format!(
                "if {} {} else {}",
                before_brace(c),
                section(t),
                if matches!(f.as_ref(), If(..)) {
                    show(f)
                } else {
                    section(f)
                }
            ),
            0,
        ),
        Let(..) => (format!("do {{ {} }}", tail(e)), 10),
        Block(xs, _) => (
            format!(
                "block {{ {} }}",
                xs.iter().map(show).collect::<Vec<_>>().join("; ")
            ),
            10,
        ),
        VecLit(t, xs, _) => (format!("vec<{}>[{}]", ty(t), args(xs)), 10),
        MapLit(k, v, xs, _) => (
            format!(
                "map<{}, {}>{{{}}}",
                ty(k),
                ty(v),
                xs.iter()
                    .map(|(k, v)| format!("{}: {}", show(k), show(v)))
                    .collect::<Vec<_>>()
                    .join(", ")
            ),
            10,
        ),
        As(t, x, _) => (format!("{} as {}", expression(x, 7), ty(t)), 7),
        Fold(i, lo, hi, n, t, init, b, _) => (
            format!(
                "for {} in range({}, {}) with {}: {} = {} {}",
                ident(i),
                show(lo),
                show(hi),
                ident(n),
                ty(t),
                before_brace(init),
                section(b)
            ),
            0,
        ),
        Variant(t, n, _) => (format!("{}::{}", ident(t), ident(n)), 10),
        Match(t, x, cases, _) => (
            format!(
                "match {} {} {{ {} }}",
                ident(t),
                before_brace(x),
                cases
                    .iter()
                    .map(|(n, v)| format!("{} => {}", ident(n), show(v)))
                    .collect::<Vec<_>>()
                    .join(", ")
            ),
            0,
        ),
        Loop(n, t, init, inv, cond, b, _) => (
            format!(
                "loop with {}: {} = {}{} while {} {}",
                ident(n),
                ty(t),
                show(init),
                inv.as_ref()
                    .map_or_else(String::new, |e| format!(" inv {}", show(e))),
                before_brace(cond),
                section(b)
            ),
            0,
        ),
        Any(n, c, p, _) | All(n, c, p, _) | Find(n, c, p, _) => {
            let kind = match e {
                Any(..) => "any",
                All(..) => "all",
                _ => "find",
            };
            (
                format!("{kind} {} in {} {}", ident(n), before_brace(c), section(p)),
                0,
            )
        }
        Record(n, fs, _) => (format!("{} {{ {} }}", ident(n), fields(fs)), 10),
        RecordUpdate(n, base, fs, _) => (
            format!(
                "{} {{ ..{}{} }}",
                ident(n),
                show(base),
                if fs.is_empty() {
                    String::new()
                } else {
                    format!(", {}", fields(fs))
                }
            ),
            10,
        ),
        Field(x, n, _) => (
            format!(
                "{}.{}",
                if matches!(x.as_ref(), Ref(..) | Field(..) | Call(..) | Try(..)) {
                    expression(x, 9)
                } else {
                    format!("({})", show(x))
                },
                ident(n)
            ),
            9,
        ),
        Raise(x, _) => (format!("raise {}", show(x)), 0),
        Try(x, n, h, _)
            if n == "e"
                && matches!(h.as_ref(), Raise(v, _) if matches!(v.as_ref(), Ref(r, _) if r == n)) =>
        {
            (format!("{}?", expression(x, 9)), 9)
        }
        Try(x, n, h, _) => (
            format!("{} catch {} {}", expression(x, 2), ident(n), section(h)),
            1,
        ),
        OkExpr(x, _) => (format!("ok({})", show(x)), 10),
        ErrExpr(x, _) => (format!("err({})", show(x)), 10),
        Len(x, _) => (unary("len", x), 10),
        Keys(x, _) => (unary("keys", x), 10),
        Unwrap(x, _) => (unary("unwrap", x), 10),
        ErrValue(x, _) => (unary("err_value", x), 10),
        ToString(x, _) => (unary("to_string", x), 10),
        ParseInt(x, _) => (unary("parse_int", x), 10),
        ToBytes(x, _) => (unary("to_bytes", x), 10),
        IsOk(x, _) => (unary("is_ok", x), 10),
        Sort(x, _) => (unary("sort", x), 10),
        UrlDecode(x, _) => (unary("url_decode", x), 10),
        ToHex(x, _) => (unary("to_hex", x), 10),
        Get(a, b, _) => (binary("get", a, b), 10),
        Append(a, b, _) => (binary("append", a, b), 10),
        Lookup(a, b, _) => (binary("lookup", a, b), 10),
        Contains(a, b, _) => (binary("map_contains", a, b), 10),
        VecContains(a, b, _) => (binary("contains", a, b), 10),
        Remove(a, b, _) => (binary("remove", a, b), 10),
        Split(a, b, _) => (binary("split", a, b), 10),
        Concat(a, b, _) => (binary("concat", a, b), 10),
        Join(a, b, _) => (binary("join", a, b), 10),
        StripPrefix(a, b, _) => (binary("strip_prefix", a, b), 10),
        Before(a, b, _) => (binary("before", a, b), 10),
        EndsWith(a, b, _) => (binary("ends_with", a, b), 10),
        CtEq(a, b, _) => (binary("ct_eq", a, b), 10),
        Slice(a, b, c, _) => (format!("@slice({}, {}, {})", show(a), show(b), show(c)), 10),
        Set(a, b, c, _) => (format!("@set({}, {}, {})", show(a), show(b), show(c)), 10),
    };
    if priority < min {
        format!("({text})")
    } else {
        text
    }
}

// Braces introducing a control body cannot also introduce a record literal.
fn before_brace(e: &Expr) -> String {
    fn needs_group(e: &Expr) -> bool {
        match e {
            Expr::Record(..)
            | Expr::RecordUpdate(..)
            | Expr::If(..)
            | Expr::Match(..)
            | Expr::Loop(..)
            | Expr::Fold(..) => true,
            Expr::Bin(_, a, b, _) => needs_group(a) || needs_group(b),
            Expr::Not(x, _)
            | Expr::As(_, x, _)
            | Expr::Field(x, _, _)
            | Expr::Raise(x, _)
            | Expr::Try(x, _, _, _) => needs_group(x),
            _ => false,
        }
    }
    if needs_group(e) {
        format!("({})", expression(e, 0))
    } else {
        expression(e, 0)
    }
}

fn signature(
    name: &str,
    params: &[(String, TypeExpr)],
    returns: &TypeExpr,
    pure: bool,
    eff: &[String],
) -> String {
    let params = params
        .iter()
        .map(|(n, t)| format!("{}: {}", ident(n), ty(t)))
        .collect::<Vec<_>>()
        .join(", ");
    let mut out = format!("fn {}({params}) -> {}", ident(name), ty(returns));
    if pure {
        out.push_str(" pure");
    }
    if !eff.is_empty() {
        write!(
            out,
            " eff {}",
            eff.iter().map(|n| ident(n)).collect::<Vec<_>>().join(", ")
        )
        .unwrap();
    }
    out
}

pub fn declaration(f: &ast::FnDef) -> String {
    let mut out = signature(&f.name, &f.params, &f.returns, f.pure, &f.eff);
    for (kind, expressions) in [("pre", &f.pre), ("post", &f.post), ("inv", &f.inv)] {
        for e in expressions {
            write!(out, "\n  {kind} {}", before_brace(e)).unwrap();
        }
    }
    out
}

pub fn type_decl(t: &ast::TypeDef) -> String {
    let value = match &t.kind {
        TypeKind::Alias(t) => ty(t),
        TypeKind::Enum(v) => format!(
            "enum {{ {} }}",
            v.iter().map(|n| ident(n)).collect::<Vec<_>>().join(", ")
        ),
        TypeKind::Record(fields) => format!(
            "record {{ {} }}",
            fields
                .iter()
                .map(|(n, t)| format!("{}: {}", ident(n), ty(t)))
                .collect::<Vec<_>>()
                .join(", ")
        ),
    };
    format!("type {} = {value}", ident(&t.name))
}

#[cfg(test)]
pub fn module(m: &ast::Module) -> String {
    let mut out = format!(
        "module {} version {};\n",
        ident(&m.name),
        string(&m.version)
    );
    for (kind, deps) in [("dep", &m.deps), ("rust_dep", &m.rust_deps)] {
        for (n, v) in deps {
            writeln!(out, "{kind} {} {};", ident(n), string(v)).unwrap();
        }
    }
    for (kind, items) in [("cap", &m.caps), ("export", &m.exports)] {
        if !items.is_empty() {
            writeln!(
                out,
                "{kind} {};",
                items
                    .iter()
                    .map(|n| ident(n))
                    .collect::<Vec<_>>()
                    .join(", ")
            )
            .unwrap();
        }
    }
    for t in &m.types {
        writeln!(out, "{};", type_decl(t)).unwrap();
    }
    for f in &m.fns {
        writeln!(out, "{} {}", declaration(f), body(&f.body)).unwrap();
    }
    for f in &m.exts {
        writeln!(
            out,
            "extern {}{} = {};",
            signature(&f.name, &f.params, &f.returns, f.pure, &f.eff),
            if f.unsafe_ffi { " unsafe" } else { "" },
            string(&f.template)
        )
        .unwrap();
    }
    for t in &m.tests {
        writeln!(out, "test {} {}", ident(&t.name), section(&t.body)).unwrap();
    }
    for b in &m.benches {
        writeln!(
            out,
            "bench {}{} setup {} {}",
            ident(&b.name),
            b.ms_budget
                .map_or_else(String::new, |n| format!(" budget {n}")),
            body(&b.setup),
            section(&b.body)
        )
        .unwrap();
    }
    out
}
#[derive(Clone, Debug)]
enum Token {
    Word(String, bool),
    Text(String),
    Number(String),
    Punct(&'static str),
    End,
}

#[derive(Clone, Debug)]
pub struct Error {
    pub span: Span,
    pub message: String,
}

impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "line {} col {}: {}",
            self.span.line, self.span.col, self.message
        )
    }
}

impl Error {
    pub fn code(&self) -> &'static str {
        COMPACT_PARSE_ERROR
    }
}

fn lex(text: &str, limits: &Limits) -> Result<Vec<(Token, Span)>, Error> {
    let mut tail = text;
    let mut span = Span { line: 1, col: 1 };
    let mut tokens = Vec::new();
    let error = |span: &Span, message: &str| Error {
        span: span.clone(),
        message: message.into(),
    };
    if text.len() > limits.max_source_bytes {
        return Err(error(&span, "compact source byte limit exceeded"));
    }
    while !tail.is_empty() {
        let start = span.clone();
        let first = tail.chars().next().unwrap();
        let mut size = first.len_utf8();
        let token = if first.is_whitespace() {
            None
        } else if tail.starts_with("//") {
            size = tail.find('\n').unwrap_or(tail.len());
            None
        } else if matches!(first, '"' | '`') {
            let mut value = String::new();
            let mut closed = false;
            let mut chars = tail[size..].chars();
            while let Some(c) = chars.next() {
                size += c.len_utf8();
                if c == first {
                    closed = true;
                    break;
                }
                if c == '\\' {
                    let Some(escaped) = chars.next() else { break };
                    size += escaped.len_utf8();
                    match escaped {
                        'n' => value.push('\n'),
                        'r' => value.push('\r'),
                        't' => value.push('\t'),
                        '"' | '`' | '\\' => value.push(escaped),
                        c => {
                            value.push('\\');
                            value.push(c);
                        }
                    }
                } else {
                    value.push(c);
                }
                let limit = if first == '"' {
                    limits.max_literal_bytes
                } else {
                    limits.max_atom_bytes
                };
                if value.len() > limit {
                    return Err(error(
                        &start,
                        "compact literal or identifier limit exceeded",
                    ));
                }
            }
            if !closed {
                return Err(error(&start, "unclosed string or quoted identifier"));
            }
            Some(if first == '"' {
                Token::Text(value)
            } else {
                Token::Word(value, true)
            })
        } else if first.is_ascii_digit() && !tail.starts_with("0x\"") {
            let bytes = tail.as_bytes();
            while bytes.get(size).is_some_and(u8::is_ascii_digit) {
                size += 1;
            }
            if bytes.get(size) == Some(&b'.') && bytes.get(size + 1).is_some_and(u8::is_ascii_digit)
            {
                size += 1;
                while bytes.get(size).is_some_and(u8::is_ascii_digit) {
                    size += 1;
                }
            }
            if matches!(bytes.get(size), Some(b'e' | b'E')) {
                size += 1;
                if matches!(bytes.get(size), Some(b'-' | b'+')) {
                    size += 1;
                }
                while bytes.get(size).is_some_and(u8::is_ascii_digit) {
                    size += 1;
                }
            }
            if matches!(bytes.get(size), Some(b'u' | b'f')) {
                size += 1;
            }
            Some(Token::Number(tail[..size].into()))
        } else if tail.starts_with("0x\"") {
            size = 2;
            Some(Token::Punct("0x"))
        } else if first.is_ascii_alphabetic() || first == '_' {
            while tail
                .as_bytes()
                .get(size)
                .is_some_and(|b| b.is_ascii_alphanumeric() || *b == b'_')
            {
                size += 1;
            }
            Some(Token::Word(tail[..size].into(), false))
        } else {
            const PUNCT: &[&str] = &[
                "::", "->", "=>", "..", "==", "!=", "<=", ">=", "&&", "||", "(", ")", "{", "}",
                "[", "]", ",", ";", ":", ".", "?", "@", "=", "!", "<", ">", "+", "-", "*", "/",
                "%", "&", "|",
            ];
            let Some(p) = PUNCT.iter().find(|p| tail.starts_with(**p)) else {
                return Err(error(&start, "unknown compact character"));
            };
            size = p.len();
            Some(Token::Punct(p))
        };
        if let Some(token) = token {
            if size > limits.max_atom_bytes
                && matches!(token, Token::Word(_, false) | Token::Number(_))
            {
                return Err(error(&start, "compact identifier limit exceeded"));
            }
            tokens.push((token, start));
            if tokens.len() > limits.max_nodes.saturating_mul(5) {
                return Err(error(&span, "compact token limit exceeded"));
            }
        }
        for c in tail[..size].chars() {
            if c == '\n' {
                span.line += 1;
                span.col = 1;
            } else {
                span.col += 1;
            }
        }
        tail = &tail[size..];
    }
    tokens.push((Token::End, span));
    Ok(tokens)
}

struct Parser<'a> {
    tokens: Vec<(Token, Span)>,
    i: usize,
    depth: usize,
    nodes: usize,
    limits: &'a Limits,
    local_functions: &'a [&'a str],
}

impl<'a> Parser<'a> {
    fn new(text: &str, limits: &'a Limits) -> Result<Self, Error> {
        Ok(Self {
            tokens: lex(text, limits)?,
            i: 0,
            depth: 0,
            nodes: 0,
            limits,
            local_functions: &[],
        })
    }
    fn span(&self) -> Span {
        self.tokens[self.i].1.clone()
    }
    fn peek(&self) -> &Token {
        &self.tokens[self.i].0
    }
    fn at(&self, value: &str) -> bool {
        match self.peek() {
            Token::Punct(p) => *p == value,
            Token::Word(w, false) => w == value,
            _ => false,
        }
    }
    fn take(&mut self) -> Token {
        let token = self.peek().clone();
        if !matches!(token, Token::End) {
            self.i += 1;
        }
        token
    }
    fn error(&self, message: impl Into<String>) -> Error {
        Error {
            span: self.span(),
            message: message.into(),
        }
    }
    fn eat(&mut self, token: &str) -> bool {
        if !self.at(token) {
            return false;
        }
        self.take();
        true
    }
    fn need(&mut self, token: &str) -> Result<(), Error> {
        if self.eat(token) {
            Ok(())
        } else {
            Err(self.error(format!("expected '{token}'")))
        }
    }
    fn word(&mut self) -> Result<(String, bool), Error> {
        if let Token::Word(word, quoted) = self.peek() {
            let value = (word.clone(), *quoted);
            self.take();
            Ok(value)
        } else {
            Err(self.error("expected an identifier"))
        }
    }
    fn name(&mut self) -> Result<String, Error> {
        self.word().map(|(name, _)| name)
    }
    fn path(&mut self) -> Result<(String, bool), Error> {
        let (mut name, quoted) = self.word()?;
        if !quoted {
            while self.eat(".") {
                name.push('.');
                name.push_str(&self.name()?);
            }
        }
        Ok((name, quoted))
    }
    fn text(&mut self) -> Result<String, Error> {
        if let Token::Text(text) = self.peek() {
            let value = text.clone();
            self.take();
            Ok(value)
        } else {
            Err(self.error("expected a string"))
        }
    }
    fn nested<T>(&mut self, parse: impl FnOnce(&mut Self) -> Result<T, Error>) -> Result<T, Error> {
        self.depth += 1;
        self.nodes += 1;
        // Preserve the compiler's stack budget even when an environment raises
        // the legacy S-expression nesting limit.
        if self.depth > self.limits.max_depth.min(512) || self.nodes > self.limits.max_nodes {
            return Err(self.error("compact AST resource limit exceeded"));
        }
        let result = parse(self);
        self.depth -= 1;
        result
    }
    fn list<T>(
        &mut self,
        end: &str,
        sep: &str,
        mut item: impl FnMut(&mut Self) -> Result<T, Error>,
    ) -> Result<Vec<T>, Error> {
        let mut values = Vec::new();
        while !self.eat(end) {
            values.push(item(self)?);
            if self.eat(end) {
                break;
            }
            self.need(sep)?;
        }
        Ok(values)
    }
    fn ty(&mut self) -> Result<TypeExpr, Error> {
        self.nested(|p| {
            let span = p.span();
            let (name, quoted) = p.path()?;
            if !quoted && matches!(name.as_str(), "vec" | "map" | "result") && p.eat("<") {
                let a = Box::new(p.ty()?);
                if name == "vec" {
                    p.need(">")?;
                    return Ok(TypeExpr::Vec(a));
                }
                p.need(",")?;
                let b = Box::new(p.ty()?);
                p.need(">")?;
                return Ok(if name == "map" {
                    TypeExpr::Map(a, b)
                } else {
                    TypeExpr::Result(a, b)
                });
            }
            if !quoted && primitive(&name) {
                return ast::parse_type_expr(&node("prim", vec![symbol(name, &span)], &span))
                    .map_err(|_| Error {
                        span,
                        message: "invalid primitive type".into(),
                    });
            }
            Ok(TypeExpr::Named(name))
        })
    }
    fn body(&mut self) -> Result<Vec<Expr>, Error> {
        self.need("{")?;
        self.body_tail()
    }
    fn body_tail(&mut self) -> Result<Vec<Expr>, Error> {
        let mut xs = Vec::new();
        while !self.eat("}") {
            if self.at("let") {
                xs.push(self.nested(Self::binding)?);
                return Ok(xs);
            }
            xs.push(self.expr(0, true)?);
            if self.eat("}") {
                break;
            }
            self.need(";")?;
        }
        Ok(xs)
    }
    fn section(&mut self) -> Result<Expr, Error> {
        let span = self.span();
        let xs = self.body()?;
        Ok(denote(xs, span))
    }
    fn binding(&mut self) -> Result<Expr, Error> {
        let span = self.span();
        self.need("let")?;
        if self.at("mut") {
            return Err(self.error("ALVA bindings are immutable. Write let x = value; x"));
        }
        let name = self.name()?;
        let t = if self.eat(":") {
            Some(self.ty()?)
        } else {
            None
        };
        self.need("=")?;
        let value = self.expr(0, true)?;
        self.need(";")?;
        let xs = self.body_tail()?;
        if xs.is_empty() {
            return Err(self.error("a let requires a result expression, as in let x = value; x"));
        }
        Ok(Expr::Let(
            name,
            t,
            Box::new(value),
            Box::new(denote(xs, span.clone())),
            span,
        ))
    }
    fn expr(&mut self, min: u8, records: bool) -> Result<Expr, Error> {
        self.nested(|p| p.expression(min, records))
    }
    fn expression(&mut self, min: u8, records: bool) -> Result<Expr, Error> {
        let mut left = self.atom(records)?;
        let mut comparison = false;
        let mut chain = 0;
        loop {
            chain += 1;
            if chain > self.limits.max_depth.min(512) {
                return Err(self.error("compact expression chain limit exceeded"));
            }
            let span = self.span();
            if min <= 9 && self.eat(".") {
                let name = self.name()?;
                if self.at("(") {
                    return Err(
                        self.error("ALVA has no methods. Write len(xs) or module.function(xs)")
                    );
                }
                left = Expr::Field(Box::new(left), name, span);
            } else if min <= 9 && self.eat("?") {
                let handler =
                    Expr::Raise(Box::new(Expr::Ref("e".into(), span.clone())), span.clone());
                left = Expr::Try(Box::new(left), "e".into(), Box::new(handler), span);
            } else if min <= 7 && self.eat("as") {
                left = Expr::As(self.ty()?, Box::new(left), span);
            } else if min <= 1 && self.eat("catch") {
                let name = self.name()?;
                left = Expr::Try(Box::new(left), name, Box::new(self.section()?), span);
            } else if let Some((operator, priority)) = self.operator().filter(|(_, p)| *p >= min) {
                if priority == 4 && comparison {
                    return Err(self.error("comparisons do not chain. Write a < b && b < c"));
                }
                comparison |= priority == 4;
                self.take();
                let right = self.expr(priority + 1, records)?;
                left = Expr::Bin(operator, Box::new(left), Box::new(right), span);
            } else {
                return Ok(left);
            }
        }
    }
    fn operator(&self) -> Option<(BinOp, u8)> {
        let symbol = match self.peek() {
            Token::Punct(s) => *s,
            Token::Word(w, false) => w.as_str(),
            _ => return None,
        };
        let op = match symbol {
            "+" => BinOp::Add,
            "-" => BinOp::Sub,
            "*" => BinOp::Mul,
            "/" => BinOp::Div,
            "%" | "mod" => BinOp::Mod,
            "==" => BinOp::Eq,
            "!=" => BinOp::Ne,
            "<" => BinOp::Lt,
            "<=" => BinOp::Le,
            ">" => BinOp::Gt,
            ">=" => BinOp::Ge,
            "&&" | "and" => BinOp::And,
            "||" | "or" => BinOp::Or,
            _ => return None,
        };
        Some((op, crate::compact::op(op).1))
    }
    fn atom(&mut self, records: bool) -> Result<Expr, Error> {
        let span = self.span();
        if self.eat("(") {
            let e = self.expr(0, true)?;
            self.need(")")?;
            return Ok(e);
        }
        if self.eat("!") || self.eat("not") {
            return Ok(Expr::Not(Box::new(self.expr(8, records)?), span));
        }
        if self.eat("0x") {
            let data = self.text()?;
            if data.len() % 2 != 0 || !data.bytes().all(|c| c.is_ascii_hexdigit()) {
                return Err(Error {
                    span,
                    message: "expected hexadecimal bytes as 0x\"deadbeef\"".into(),
                });
            }
            let bytes = (0..data.len())
                .step_by(2)
                .map(|i| u8::from_str_radix(&data[i..i + 2], 16).unwrap())
                .collect();
            return Ok(Expr::Bytes(bytes, span));
        }
        if self.at("-") || matches!(self.peek(), Token::Number(_)) {
            let minus = if self.eat("-") { "-" } else { "" };
            if let Token::Number(n) = self.take() {
                let n = format!("{minus}{n}");
                if let Some(n) = n.strip_suffix('u') {
                    return n
                        .parse()
                        .map(|n| Expr::UInt(n, span.clone()))
                        .map_err(|_| Error {
                            span,
                            message: "invalid unsigned integer".into(),
                        });
                }
                if n.contains(['.', 'e', 'E']) || n.ends_with('f') {
                    return n
                        .trim_end_matches('f')
                        .parse()
                        .map(|n| Expr::Float(n, span.clone()))
                        .map_err(|_| Error {
                            span,
                            message: "invalid float".into(),
                        });
                }
                return n
                    .parse()
                    .map(|n| Expr::Int(n, span.clone()))
                    .map_err(|_| Error {
                        span,
                        message: "invalid integer".into(),
                    });
            }
            return Err(Error {
                span,
                message: "write a signed literal such as -1 or use 0 - x".into(),
            });
        }
        if let Token::Text(s) = self.peek() {
            let value = s.clone();
            self.take();
            return Ok(Expr::Str(value, span));
        }
        let diagnostic = match self.peek() {
            Token::Punct("|" | "||") => Some("ALVA has no closures. Write any x in xs { x > 0 }"),
            Token::Punct("&") => Some("ALVA has no references. Write f(x)"),
            Token::Word(w, false) if w == "return" => Some("ALVA returns the final expression. Write { x }"),
            Token::Word(w, false) if w == "while" => Some("ALVA loops require an accumulator. Write loop with i: i64 = 0 while i < 4 { i + 1 }"),
            _ => None,
        };
        if let Some(message) = diagnostic {
            return Err(self.error(message));
        }
        if self.eat("if") {
            let cond = self.expr(0, false)?;
            let yes = self.section()?;
            if !self.eat("else") {
                return Err(Error {
                    span,
                    message: "if requires else. Write if c { x } else { y }".into(),
                });
            }
            let no = if self.at("if") {
                self.expr(0, records)?
            } else {
                self.section()?
            };
            return Ok(Expr::If(Box::new(cond), Box::new(yes), Box::new(no), span));
        }
        if self.eat("block") {
            self.need("{")?;
            return Ok(Expr::Block(self.list("}", ";", |p| p.expr(0, true))?, span));
        }
        if self.eat("do") {
            return self.section();
        }
        if self.eat("raise") {
            return Ok(Expr::Raise(Box::new(self.expr(0, records)?), span));
        }
        if self.eat("for") {
            return self.fold(span);
        }
        if self.eat("loop") {
            return self.loop_expr(span);
        }
        if self.eat("match") {
            return self.match_expr(span);
        }
        let dedicated = self.eat("@");
        let start = self.i;
        let (name, quoted) = self.path()?;
        if !quoted
            && matches!(name.as_str(), "any" | "all" | "find")
            && matches!(self.tokens.get(self.i + 1), Some((Token::Word(w, false), _)) if w == "in")
        {
            let var = self.name()?;
            self.need("in")?;
            let collection = Box::new(self.expr(0, false)?);
            let predicate = Box::new(self.section()?);
            return Ok(match name.as_str() {
                "any" => Expr::Any(var, collection, predicate, span),
                "all" => Expr::All(var, collection, predicate, span),
                _ => Expr::Find(var, collection, predicate, span),
            });
        }
        if !quoted && matches!(name.as_str(), "vec" | "map") && self.at("<") {
            // '<' is also an operator; enter the typed-literal grammar only
            // when a complete type argument list is immediately followed by its delimiter.
            let save = self.i;
            self.take();
            if let Ok(key) = self.ty() {
                if name == "vec" && self.eat(">") && self.eat("[") {
                    let items = self.list("]", ",", |p| p.expr(0, true))?;
                    return Ok(Expr::VecLit(key, items, span));
                }
                if name == "map" && self.eat(",") {
                    let value = self.ty()?;
                    self.need(">")?;
                    self.need("{")?;
                    let pairs = self.list("}", ",", |p| {
                        let key = p.expr(0, true)?;
                        p.need(":")?;
                        Ok((key, p.expr(0, true)?))
                    })?;
                    return Ok(Expr::MapLit(key, value, pairs, span));
                }
            }
            self.i = save;
        }
        if self.eat("::") {
            return Ok(Expr::Variant(name, self.name()?, span));
        }
        if self.eat("(") {
            let values = self.list(")", ",", |p| p.expr(0, true))?;
            if dedicated {
                return builtin(&name, values, span);
            }
            if !quoted {
                if canonical(&name) != name && self.local_functions.contains(&name.as_str()) {
                    return Err(Error {
                        span,
                        message: format!(
                            "'{name}' names both a local function and builtin alias. Use `{name}`(...) for the local function or `{}`(...) for the builtin",
                            canonical(&name)
                        ),
                    });
                }
                if matches!(name.as_str(), "ok" | "err") {
                    return builtin(&name, values, span);
                }
                if name == "float_bits" {
                    if let [Expr::Str(bits, _)] = values.as_slice() {
                        if let Ok(bits) = u64::from_str_radix(bits, 16) {
                            return Ok(Expr::Float(f64::from_bits(bits), span));
                        }
                    }
                    return Err(Error {
                        span,
                        message: "write float_bits(\"7ff8000000000000\")".into(),
                    });
                }
            }
            return Ok(Expr::Call(
                if quoted {
                    name
                } else {
                    canonical(&name).to_owned()
                },
                values,
                span,
            ));
        }
        if dedicated {
            return Err(self.error("expected a dedicated builtin call, such as @len(xs)"));
        }
        if records && self.eat("{") {
            let base = if self.eat("..") {
                Some(Box::new(self.expr(0, true)?))
            } else {
                None
            };
            let fields = if base.is_some() && self.eat("}") {
                Vec::new()
            } else {
                if base.is_some() {
                    self.need(",")?;
                }
                self.list("}", ",", |p| {
                    let name = p.name()?;
                    p.need(":")?;
                    Ok((name, p.expr(0, true)?))
                })?
            };
            return Ok(match base {
                Some(base) => Expr::RecordUpdate(name, base, fields, span),
                None => Expr::Record(name, fields, span),
            });
        }
        if !quoted && name.contains('.') {
            self.i = start;
            return Ok(Expr::Ref(self.name()?, span));
        }
        Ok(match (name.as_str(), quoted) {
            ("nil", false) => Expr::Nil(span),
            ("true" | "false", false) => Expr::Bool(name == "true", span),
            _ => Expr::Ref(name, span),
        })
    }
    fn accumulator(&mut self) -> Result<(String, TypeExpr, Box<Expr>), Error> {
        self.need("with")?;
        let name = self.name()?;
        self.need(":")?;
        let ty = self.ty()?;
        self.need("=")?;
        let init = Box::new(self.expr(0, false)?);
        Ok((name, ty, init))
    }
    fn fold(&mut self, span: Span) -> Result<Expr, Error> {
        let idx = self.name()?;
        self.need("in")?;
        if !self.eat("range") {
            return Err(self.error("ALVA for requires range and an accumulator. Write for i in range(0, len(xs)) with n: i64 = 0 { n + 1 }"));
        }
        self.need("(")?;
        let lo = Box::new(self.expr(0, true)?);
        self.need(",")?;
        let hi = Box::new(self.expr(0, true)?);
        self.need(")")?;
        let (n, t, init) = self.accumulator()?;
        Ok(Expr::Fold(
            idx,
            lo,
            hi,
            n,
            t,
            init,
            Box::new(self.section()?),
            span,
        ))
    }
    fn loop_expr(&mut self, span: Span) -> Result<Expr, Error> {
        let (n, t, init) = self.accumulator()?;
        let inv = if self.eat("inv") {
            Some(Box::new(self.expr(0, false)?))
        } else {
            None
        };
        self.need("while")?;
        let cond = Box::new(self.expr(0, false)?);
        Ok(Expr::Loop(
            n,
            t,
            init,
            inv,
            cond,
            Box::new(self.section()?),
            span,
        ))
    }
    fn match_expr(&mut self, span: Span) -> Result<Expr, Error> {
        let (t, _) = self.path()?;
        if self.at("{") {
            return Err(self.error("match requires an enum type and value. Write match State state { ready => true, _ => false }"));
        }
        let scrutinee = Box::new(self.expr(0, false)?);
        self.need("{")?;
        let cases = self.list("}", ",", |p| {
            let variant = p.name()?;
            p.need("=>")?;
            Ok((
                variant,
                if p.at("{") {
                    p.section()?
                } else {
                    p.expr(0, true)?
                },
            ))
        })?;
        if cases.is_empty() {
            return Err(self.error("match requires an arm"));
        }
        Ok(Expr::Match(t, scrutinee, cases, span))
    }
}

fn denote(mut xs: Vec<Expr>, span: Span) -> Expr {
    if xs.len() == 1 {
        xs.pop().unwrap()
    } else {
        Expr::Block(xs, span)
    }
}

fn symbol(s: String, span: &Span) -> Node {
    Node::Atom(Atom::Sym(s), span.clone())
}

fn node(tag: &str, children: Vec<Node>, span: &Span) -> Node {
    Node::List(
        std::iter::once(symbol(tag.to_owned(), span))
            .chain(children)
            .collect(),
        span.clone(),
    )
}

fn builtin(name: &str, xs: Vec<Expr>, span: Span) -> Result<Expr, Error> {
    use Expr::{Err as ErrExpr, Ok as OkExpr, *};
    type BinaryBuiltin = fn(Box<Expr>, Box<Expr>, Span) -> Expr;
    let unary: Option<fn(Box<Expr>, Span) -> Expr> = match name {
        "len" => Some(Len),
        "keys" => Some(Keys),
        "unwrap" => Some(Unwrap),
        "err_value" => Some(ErrValue),
        "to_string" => Some(ToString),
        "parse_int" => Some(ParseInt),
        "to_bytes" => Some(ToBytes),
        "is_ok" => Some(IsOk),
        "sort" => Some(Sort),
        "url_decode" => Some(UrlDecode),
        "to_hex" => Some(ToHex),
        "ok" => Some(OkExpr),
        "err" => Some(ErrExpr),
        _ => None,
    };
    let binary: Option<BinaryBuiltin> = match name {
        "get" => Some(Get),
        "append" => Some(Append),
        "lookup" => Some(Lookup),
        "map_contains" => Some(Contains),
        "contains" => Some(VecContains),
        "remove" => Some(Remove),
        "split" => Some(Split),
        "concat" => Some(Concat),
        "join" => Some(Join),
        "strip_prefix" => Some(StripPrefix),
        "before" => Some(Before),
        "ends_with" => Some(EndsWith),
        "ct_eq" => Some(CtEq),
        _ => None,
    };
    let error = || Error {
        span: span.clone(),
        message: format!("unknown dedicated builtin or incorrect argument count for {name}"),
    };
    let mut args = xs.into_iter().map(Box::new);
    let result = match args.len() {
        1 => unary.map(|f| f(args.next().unwrap(), span.clone())),
        2 => binary.map(|f| f(args.next().unwrap(), args.next().unwrap(), span.clone())),
        3 if matches!(name, "slice" | "set") => {
            let f = if name == "slice" { Slice } else { Set };
            Some(f(
                args.next().unwrap(),
                args.next().unwrap(),
                args.next().unwrap(),
                span.clone(),
            ))
        }
        _ => None,
    };
    result.ok_or_else(error)
}

#[cfg(test)]
pub fn parse_body(text: &str, limits: &Limits) -> Result<Vec<Expr>, Error> {
    parse_body_with_functions(text, limits, &[])
}

pub fn parse_body_with_functions(
    text: &str,
    limits: &Limits,
    local_functions: &[&str],
) -> Result<Vec<Expr>, Error> {
    let mut parser = Parser::new(text, limits)?;
    parser.local_functions = local_functions;
    let body = parser.body()?;
    if body.is_empty() {
        return Err(parser.error("body requires a result expression"));
    }
    if !matches!(parser.peek(), Token::End) {
        return Err(parser.error("unexpected input after function body"));
    }
    Ok(body)
}
#[cfg(test)]
impl Parser<'_> {
    fn params(&mut self) -> Result<Vec<(String, TypeExpr)>, Error> {
        self.need("(")?;
        self.list(")", ",", |p| {
            let name = p.name()?;
            p.need(":")?;
            Ok((name, p.ty()?))
        })
    }

    fn effects(&mut self) -> Result<(bool, Vec<String>), Error> {
        let pure = self.eat("pure");
        let mut eff = Vec::new();
        if self.eat("eff") {
            eff.push(self.name()?);
            while self.eat(",") {
                eff.push(self.name()?);
            }
        }
        Ok((pure, eff))
    }

    fn type_decl(&mut self, span: Span) -> Result<ast::TypeDef, Error> {
        let name = self.name()?;
        self.need("=")?;
        let kind = if self.eat("enum") {
            self.need("{")?;
            TypeKind::Enum(self.list("}", ",", Parser::name)?)
        } else if self.eat("record") {
            self.need("{")?;
            TypeKind::Record(self.list("}", ",", |p| {
                let name = p.name()?;
                p.need(":")?;
                Ok((name, p.ty()?))
            })?)
        } else {
            TypeKind::Alias(self.ty()?)
        };
        self.need(";")?;
        Ok(ast::TypeDef { name, kind, span })
    }

    fn module(&mut self) -> Result<ast::Module, Error> {
        self.need("module")?;
        let (name, _) = self.path()?;
        self.need("version")?;
        let version = self.text()?;
        self.need(";")?;
        let mut module = ast::Module {
            name,
            version,
            rust_deps: vec![],
            deps: vec![],
            caps: vec![],
            exports: vec![],
            types: vec![],
            fns: vec![],
            exts: vec![],
            tests: vec![],
            benches: vec![],
        };
        while !matches!(self.peek(), Token::End) {
            let span = self.span();
            let kind = self.name()?;
            match kind.as_str() {
                "dep" | "rust_dep" => {
                    let (name, _) = self.path()?;
                    let version = self.text()?;
                    self.need(";")?;
                    let deps = if kind == "dep" {
                        &mut module.deps
                    } else {
                        &mut module.rust_deps
                    };
                    deps.push((name, version));
                }
                "cap" => module.caps.extend(self.list(";", ",", Parser::name)?),
                "export" => module.exports.extend(self.list(";", ",", Parser::name)?),
                "type" => module.types.push(self.type_decl(span)?),
                "fn" | "extern" => {
                    if kind == "extern" {
                        self.need("fn")?;
                    }
                    let (name, _) = self.path()?;
                    let params = self.params()?;
                    self.need("->")?;
                    let returns = self.ty()?;
                    let (pure, eff) = self.effects()?;
                    if kind == "extern" {
                        let unsafe_ffi = self.eat("unsafe");
                        self.need("=")?;
                        let template = self.text()?;
                        self.need(";")?;
                        module.exts.push(ast::ExternDef {
                            name,
                            params,
                            returns,
                            eff,
                            pure,
                            unsafe_ffi,
                            template,
                            span,
                        });
                    } else {
                        let mut f = ast::FnDef {
                            name,
                            params,
                            returns,
                            pre: vec![],
                            post: vec![],
                            inv: vec![],
                            pure,
                            eff,
                            body: vec![],
                            span,
                        };
                        loop {
                            let list = if self.eat("pre") {
                                &mut f.pre
                            } else if self.eat("post") {
                                &mut f.post
                            } else if self.eat("inv") {
                                &mut f.inv
                            } else {
                                break;
                            };
                            list.push(self.expr(0, false)?);
                        }
                        f.body = self.body()?;
                        module.fns.push(f);
                    }
                }
                "test" => module.tests.push(ast::TestDef {
                    name: self.name()?,
                    body: self.section()?,
                    span,
                }),
                "bench" => {
                    let name = self.name()?;
                    let ms_budget = if self.eat("budget") {
                        if let Expr::Int(n, _) = self.atom(false)? {
                            Some(n)
                        } else {
                            return Err(self.error("expected integral millisecond budget"));
                        }
                    } else {
                        None
                    };
                    self.need("setup")?;
                    let setup = self.body()?;
                    let body = self.section()?;
                    module.benches.push(ast::BenchDef {
                        name,
                        ms_budget,
                        setup,
                        body,
                        span,
                    });
                }
                _ => {
                    return Err(Error {
                        span,
                        message: format!("unknown declaration {kind}"),
                    })
                }
            }
        }
        Ok(module)
    }
}

#[cfg(test)]
pub fn parse_module(text: &str, limits: &Limits) -> Result<ast::Module, Error> {
    Parser::new(text, limits)?.module()
}

#[cfg(test)]
#[path = "compact_tests.rs"]
mod tests;
