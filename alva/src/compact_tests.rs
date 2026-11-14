use super::*;
use crate::air::{air_from_module, air_to_module, expr_to_air, AirGraph};
use std::path::Path;

fn revision(expr: &Expr) -> String {
    expr_to_air(&mut AirGraph::new(), expr)
}

fn assert_expression(e: &Expr) -> String {
    let text = body(std::slice::from_ref(e));
    let restored =
        parse_body(&text, &Limits::default()).unwrap_or_else(|err| panic!("{err}\n{text}"));
    assert_eq!(restored.len(), 1, "{text}");
    assert_eq!(
        revision(e),
        revision(&restored[0]),
        "{text}\n{e:?}\n{restored:?}"
    );
    assert_eq!(text, body(&restored));
    text
}

fn corpus_files(root: &Path, files: &mut Vec<std::path::PathBuf>) {
    for entry in std::fs::read_dir(root).unwrap() {
        let path = entry.unwrap().path();
        if path.is_dir() {
            if !matches!(
                path.file_name().and_then(|s| s.to_str()),
                Some("target" | "out" | "alva-air" | ".git")
            ) {
                corpus_files(&path, files);
            }
        } else if path.extension().is_some_and(|s| s == "alva") {
            files.push(path);
        }
    }
}

#[test]
fn compact_corpus_preserves_module_and_function_revisions() {
    let mut files = Vec::new();
    for folder in ["../examples", "examples", "../tests"] {
        corpus_files(Path::new(folder), &mut files);
    }
    files.sort();
    let limits = Limits::default();
    let mut failures = vec![];
    let mut counts = [0; 7];
    for path in &files {
        let original = std::fs::read_to_string(path).unwrap();
        let Ok(tree) = crate::s_expr::parse_with_limits(&original, &limits) else {
            continue;
        };
        let Ok(ast) = ast::from_tree(&tree) else {
            continue;
        };
        let before = air_from_module(&ast);
        // Render the AIR-projected AST, exactly as the maintenance read path does.
        let ast = air_to_module(&before, &before.module_entities[0]).unwrap();
        let text = module(&ast);
        let restored = match parse_module(&text, &limits) {
            Ok(restored) => restored,
            Err(error) => {
                let line = text
                    .lines()
                    .nth(error.span.line.saturating_sub(1) as usize)
                    .unwrap_or("");
                failures.push(format!("{}: {error}\n{line}", path.display()));
                continue;
            }
        };
        let after = air_from_module(&restored);
        if before.semantic_hash() != after.semantic_hash()
            || before.heads != after.heads
            || text != module(&restored)
        {
            failures.push(format!(
                "{}: revision or canonical text changed; affected heads: {:?}",
                path.display(),
                before
                    .heads
                    .iter()
                    .filter(|(k, v)| after.heads.get(*k) != Some(*v))
                    .map(|(k, _)| k)
                    .take(6)
                    .collect::<Vec<_>>()
            ));
        }
        counts[0] += 1;
        counts[1] += ast.fns.len();
        counts[2] += text.matches("block {").count();
        counts[3] += text.matches("do {").count();
        counts[4] += before.nodes.values().filter(|n| n.kind == "call"
            && matches!(n.fields.get("name"), Some(crate::air::Value::Str(name)) if has_dedicated_form(name))).count();
        counts[5] += before
            .nodes
            .values()
            .filter(|n| {
                matches!(
                    n.kind.as_str(),
                    "len"
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
                        | "slice"
                        | "set"
                )
            })
            .count();
    }
    counts[6] = files.len();
    println!("modules/functions/block/do/call-encoding/dedicated-encoding/files: {counts:?}");
    assert!(
        failures.is_empty(),
        "{}/{} failures\n{}",
        failures.len(),
        files.len(),
        failures.join("\n")
    );
}

fn has_dedicated_form(name: &str) -> bool {
    matches!(
        name,
        "len"
            | "keys"
            | "unwrap"
            | "err-value"
            | "to-string"
            | "parse-int"
            | "to-bytes"
            | "is-ok"
            | "sort"
            | "url-decode"
            | "to-hex"
            | "get"
            | "append"
            | "lookup"
            | "contains"
            | "remove"
            | "split"
            | "concat"
            | "join"
            | "strip-prefix"
            | "before"
            | "ends-with"
            | "ct-eq"
            | "slice"
            | "set"
    )
}

#[test]
fn compact_variants_and_random_ast_round_trip() {
    let t = TypeExpr::Prim(ast::Prim::I64);
    let span = Span { line: 1, col: 1 };
    let source = r#"{ 42; 42u; -0.0; "text"; true; 0x"ff"; nil; x; f(x);
        (x + y) * z; !x; if c { x } else { y }; do { let x: i64 = y; x }; block { x };
        vec<i64>[x]; @len(xs); @get(xs, i); @append(xs, x); x as i64;
        for i in range(0, len(xs)) with out: i64 = 0 { out + i };
        State::ready; match State x { ready => 1, _ => 0 }; map<string, i64>{"x": 1};
        @set(map, k, v); @lookup(map, k); @map_contains(map, k); @contains(xs, x);
        any e in xs { e }; all e in xs { e }; find e in xs { e }; @remove(map, k); @keys(map);
        @unwrap(x); @err_value(x); @slice(xs, 0, 1); @split(s, sep); @concat(s, t);
        @to_string(x); @parse_int(x); @to_bytes(s); @is_ok(x); @join(xs, sep);
        @strip_prefix(s, p); @before(s, p); @ends_with(s, p); @sort(xs); @url_decode(s); @to_hex(xs); @ct_eq(x, y);
        loop with n: i64 = 0 inv n >= 0 while n < 3 { n + 1 };
        T { name: n }; T { ..base, name: n }; base.name; raise e; f(x)?; f(x) catch err { err }; ok(x); err(x)
    }"#;
    let seeds = parse_body(source, &Limits::default()).unwrap();
    assert_eq!(seeds.len(), 58);
    for e in &seeds {
        assert_expression(e);
    }

    fn random(state: &mut u64) -> usize {
        *state = state.wrapping_mul(6364136223846793005).wrapping_add(1);
        (*state >> 32) as usize
    }
    let mut state = 0xc0de;
    for _ in 0..10_000 {
        let mut e = seeds[random(&mut state) % seeds.len()].clone();
        for _ in 0..(random(&mut state) % 5) {
            let other = seeds[random(&mut state) % seeds.len()].clone();
            e = match random(&mut state) % 9 {
                0 => Expr::Bin(BinOp::Add, Box::new(e), Box::new(other), span.clone()),
                1 => Expr::Bin(BinOp::Eq, Box::new(e), Box::new(other), span.clone()),
                2 => Expr::Let(
                    "value".into(),
                    Some(t.clone()),
                    Box::new(e),
                    Box::new(other),
                    span.clone(),
                ),
                3 => Expr::Block(vec![e, other], span.clone()),
                4 => Expr::Call("engine.store.read".into(), vec![e, other], span.clone()),
                5 => Expr::If(
                    Box::new(e),
                    Box::new(other),
                    Box::new(Expr::Nil(span.clone())),
                    span.clone(),
                ),
                6 => Expr::Field(Box::new(e), "field".into(), span.clone()),
                7 => Expr::Not(Box::new(e), span.clone()),
                _ => Expr::Try(Box::new(e), "err".into(), Box::new(other), span.clone()),
            };
        }
        assert_expression(&e);
    }
}

#[test]
fn diagnostics_point_to_rejected_syntax() {
    for (input, example) in [
        ("|x| x", "any x in xs"),
        ("(xs).iter()", "len(xs)"),
        ("let mut x = 0; x", "let x = value; x"),
        ("&x", "f(x)"),
        ("return x", "{ x }"),
        ("while x { y }", "loop with i: i64"),
        ("for x in xs { x }", "for i in range"),
        ("match x { _ => 1 }", "match State state"),
        ("if c { x }", "if c { x } else { y }"),
        ("a < b < c", "a < b && b < c"),
    ] {
        let text = format!("{{\n  {input}\n}}");
        let error = parse_body(&text, &Limits::default()).unwrap_err();
        assert_eq!(error.code(), "E_AEP_COMPACT_PARSE");
        assert!(error.message.contains(example), "{error}");
        assert_eq!(error.span.line, 2, "{input}: {error}");
        assert!(error.span.col >= 3);
    }
}

#[test]
fn compact_builtin_alias_collision_requires_an_explicit_name() {
    let input = "{ is_ok(x); `is_ok`(x); @is_ok(x); m.is_ok(x) }";
    let limits = Limits::default();
    let names = ["is_ok"];
    let original = parse_body(input, &limits).unwrap();
    assert!(parse_body_with_functions(input, &limits, &names)
        .unwrap_err()
        .message
        .contains("names both"));
    let projected = qualify_colliding_aliases(input, &names);
    assert_eq!(
        projected,
        "{ `is-ok`(x); `is_ok`(x); @is_ok(x); m.is_ok(x) }"
    );
    let restored = parse_body_with_functions(&projected, &limits, &names).unwrap();
    assert_eq!(
        original.iter().map(revision).collect::<Vec<_>>(),
        restored.iter().map(revision).collect::<Vec<_>>()
    );
}
