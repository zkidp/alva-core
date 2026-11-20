//! Project symbol locations derived from the compiler's parsed AST.
use crate::ast::{Expr, Module, TypeExpr, TypeKind};
use crate::project::LoadedModule;
use crate::s_expr::Span;
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};

pub fn index(modules: &[LoadedModule], paths: &BTreeMap<String, String>) -> Value {
    let mut definitions = Vec::new();
    for loaded in modules {
        let m = &loaded.module;
        for (kind, name, span) in m
            .fns
            .iter()
            .map(|f| ("function", &f.name, &f.span))
            .chain(m.exts.iter().map(|f| ("extern", &f.name, &f.span)))
            .chain(m.types.iter().map(|t| ("type", &t.name, &t.span)))
        {
            definitions.push(json!({
                "symbol": format!("{}.{}", m.name, name), "kind": kind,
                "module": m.name, "path": paths[&m.name], "line": span.line, "column": span.col
            }));
        }
    }
    let symbols = definitions
        .iter()
        .map(|d| d["symbol"].as_str().unwrap().to_owned())
        .collect();
    let mut references = Vec::new();
    for loaded in modules {
        let m = &loaded.module;
        let mut collector = Collector {
            module: m,
            path: &paths[&m.name],
            symbols: &symbols,
            references: &mut references,
            owner: m.name.clone(),
        };
        for f in &m.fns {
            collector.owner = format!("{}.{}", m.name, f.name);
            for (_, ty) in &f.params {
                collector.ty(ty, &f.span);
            }
            collector.ty(&f.returns, &f.span);
            for e in f.body.iter().chain(&f.pre).chain(&f.post).chain(&f.inv) {
                collector.expr(e);
            }
        }
        for f in &m.exts {
            collector.owner = format!("{}.{}", m.name, f.name);
            for (_, ty) in &f.params {
                collector.ty(ty, &f.span);
            }
            collector.ty(&f.returns, &f.span);
        }
        for t in &m.types {
            collector.owner = format!("{}.{}", m.name, t.name);
            match &t.kind {
                TypeKind::Alias(ty) => collector.ty(ty, &t.span),
                TypeKind::Record(fields) => {
                    for (_, ty) in fields {
                        collector.ty(ty, &t.span);
                    }
                }
                TypeKind::Enum(_) => {}
            }
        }
        for t in &m.tests {
            collector.owner = format!("{}.test:{}", m.name, t.name);
            collector.expr(&t.body);
        }
        for b in &m.benches {
            collector.owner = format!("{}.bench:{}", m.name, b.name);
            for e in b.setup.iter().chain(std::iter::once(&b.body)) {
                collector.expr(e);
            }
        }
    }
    json!({"definitions": definitions, "references": references})
}

struct Collector<'a> {
    module: &'a Module,
    path: &'a str,
    symbols: &'a BTreeSet<String>,
    references: &'a mut Vec<Value>,
    owner: String,
}

impl Collector<'_> {
    fn name(&mut self, name: &str, span: &Span, kind: &str) {
        let local = format!("{}.{}", self.module.name, name);
        let qualified = if self.symbols.contains(&local) {
            local.as_str()
        } else {
            name
        };
        if self.symbols.contains(qualified) {
            self.references.push(json!({
                "symbol": qualified, "kind": kind, "owner": self.owner, "path": self.path,
                "line": span.line, "column": span.col
            }));
        }
    }

    fn ty(&mut self, ty: &TypeExpr, span: &Span) {
        match ty {
            TypeExpr::Named(name) => self.name(name, span, "type"),
            TypeExpr::Vec(ty) => self.ty(ty, span),
            TypeExpr::Map(a, b) | TypeExpr::Result(a, b) => {
                self.ty(a, span);
                self.ty(b, span);
            }
            TypeExpr::Prim(_) => {}
        }
    }

    fn expr(&mut self, expr: &Expr) {
        use Expr::*;
        let span = expr.span();
        match expr {
            Call(name, args, _) => {
                self.name(name, &span, "function");
                for arg in args {
                    self.expr(arg);
                }
            }
            Variant(ty, _, _) => self.name(ty, &span, "type"),
            Match(ty, value, arms, _) => {
                self.name(ty, &span, "type");
                self.expr(value);
                for (_, body) in arms {
                    self.expr(body);
                }
            }
            Record(ty, fields, _) => {
                self.name(ty, &span, "type");
                for (_, value) in fields {
                    self.expr(value);
                }
            }
            RecordUpdate(ty, base, fields, _) => {
                self.name(ty, &span, "type");
                self.expr(base);
                for (_, value) in fields {
                    self.expr(value);
                }
            }
            Let(_, ty, value, body, _) => {
                if let Some(ty) = ty {
                    self.ty(ty, &span);
                }
                self.expr(value);
                self.expr(body);
            }
            Fold(_, start, end, _, ty, init, body, _) => {
                self.ty(ty, &span);
                for e in [start, end, init, body] {
                    self.expr(e);
                }
            }
            Loop(_, ty, init, condition, body, next, _) => {
                self.ty(ty, &span);
                for e in [init, body, next] {
                    self.expr(e);
                }
                if let Some(condition) = condition {
                    self.expr(condition);
                }
            }
            VecLit(ty, values, _) => {
                self.ty(ty, &span);
                for value in values {
                    self.expr(value);
                }
            }
            MapLit(key, value, pairs, _) => {
                self.ty(key, &span);
                self.ty(value, &span);
                for (key, value) in pairs {
                    self.expr(key);
                    self.expr(value);
                }
            }
            As(ty, value, _) => {
                self.ty(ty, &span);
                self.expr(value);
            }
            Block(values, _) => {
                for value in values {
                    self.expr(value);
                }
            }
            If(a, b, c, _) | Set(a, b, c, _) | Slice(a, b, c, _) => {
                for value in [a, b, c] {
                    self.expr(value);
                }
            }
            Bin(_, a, b, _)
            | Get(a, b, _)
            | Append(a, b, _)
            | Lookup(a, b, _)
            | Contains(a, b, _)
            | VecContains(a, b, _)
            | Remove(a, b, _)
            | Split(a, b, _)
            | Concat(a, b, _)
            | Join(a, b, _)
            | StripPrefix(a, b, _)
            | Before(a, b, _)
            | EndsWith(a, b, _)
            | CtEq(a, b, _)
            | Any(_, a, b, _)
            | All(_, a, b, _)
            | Find(_, a, b, _)
            | Try(a, _, b, _) => {
                self.expr(a);
                self.expr(b);
            }
            Not(value, _)
            | Len(value, _)
            | Keys(value, _)
            | Unwrap(value, _)
            | ErrValue(value, _)
            | ToString(value, _)
            | ParseInt(value, _)
            | ToBytes(value, _)
            | IsOk(value, _)
            | Sort(value, _)
            | UrlDecode(value, _)
            | ToHex(value, _)
            | Field(value, _, _)
            | Raise(value, _)
            | Ok(value, _)
            | Err(value, _) => self.expr(value),
            Int(..) | UInt(..) | Float(..) | Str(..) | Bool(..) | Bytes(..) | Nil(..) | Ref(..) => {
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::air::{air_from_module, graph_to_bytes, EditSession};
    use crate::compact::parse_module;
    use crate::s_expr::Limits;

    #[test]
    fn navigation_resolves_local_and_qualified_calls_and_ignores_strings() {
        let sources = [
            ("alpha", "module alpha version \"1\"; export Shared, value; type Shared = record { x: i64 }; fn value(x: Shared) -> i64 pure { x.x }"),
            ("beta", "module beta version \"1\"; dep alpha \"1\"; fn value() -> i64 pure { 0 } fn use_it() -> i64 pure { let fake = \"alpha.value\"; value() + alpha.value(alpha.Shared { x: 1 }) }"),
        ];
        let modules: Vec<_> = sources
            .iter()
            .map(|(name, source)| LoadedModule {
                name: name.to_string(),
                module: parse_module(source, &Limits::default()).unwrap(),
            })
            .collect();
        let paths = sources
            .iter()
            .map(|(name, _)| (name.to_string(), format!("{name}.alva")))
            .collect();
        let result = index(&modules, &paths);
        let references = result["references"].as_array().unwrap();
        assert_eq!(
            references
                .iter()
                .filter(|r| r["symbol"] == "alpha.value")
                .count(),
            1
        );
        assert_eq!(
            references
                .iter()
                .filter(|r| r["symbol"] == "beta.value")
                .count(),
            1
        );
        assert_eq!(
            references
                .iter()
                .filter(|r| r["symbol"] == "alpha.Shared")
                .count(),
            2
        );
    }

    #[test]
    fn module_batches_reject_conflicting_or_misnamed_edits_atomically() {
        let source = "module alpha version \"1\"; fn value() -> i64 pure { 0 }";
        let module = parse_module(source, &Limits::default()).unwrap();
        let graph = air_from_module(&module);
        let before = graph_to_bytes(&graph);
        let mut session = EditSession::begin(graph, String::new());
        let allowed = vec!["alpha".to_string()];
        let replacement = ("module".into(), "alpha".into(), source.into());
        assert!(session
            .stage_declarations(
                &allowed,
                vec![
                    replacement.clone(),
                    ("body".into(), "alpha.value".into(), "{ 2 }".into())
                ]
            )
            .is_err());
        assert_eq!(graph_to_bytes(&session.graph), before);
        assert!(session
            .stage_declarations(
                &allowed,
                vec![(
                    "module".into(),
                    "alpha".into(),
                    source.replace("alpha", "beta")
                )]
            )
            .is_err());
        assert_eq!(graph_to_bytes(&session.graph), before);
        session
            .stage_declarations(
                &allowed,
                vec![(
                    "module".into(),
                    "alpha".into(),
                    source.replace("{ 0 }", "{ 1 }"),
                )],
            )
            .unwrap();
        assert_ne!(graph_to_bytes(&session.graph), before);
    }

    #[test]
    fn source_cast_nodes_remain_valid_during_unrelated_declaration_edits() {
        let source = "module alpha version \"1\"; fn cast_value() -> i64 pure { 1u as i64 } fn other() -> i64 pure { 0 }";
        let module = parse_module(source, &Limits::default()).unwrap();
        let graph = air_from_module(&module);
        assert!(crate::air::validate_graph(&graph).is_empty());
        let mut session = EditSession::begin(graph, String::new());
        session
            .stage_declarations(
                &["alpha".to_string()],
                vec![("body".into(), "alpha.other".into(), "{ 2 }".into())],
            )
            .unwrap();
        assert!(session.check().is_empty());
    }
}
