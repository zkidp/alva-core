//! Tests exercise declaration occurrences, not just detached node construction.
use super::*;

fn graph(module: &str, names: &[&str]) -> AirGraph {
    let functions: String = names
        .iter()
        .map(|name| {
            format!(
                "(fn {name} (params (param x (prim i64))) (returns (prim i64)) (pure) \
         (pre (>= (ref x) (int 0))) (body (+ (ref x) (int 1))))"
            )
        })
        .collect();
    let text = format!("(module (name \"{module}\") (version \"1\") {functions})");
    let tree = crate::s_expr::parse_with_limits(&text, &crate::s_expr::Limits::default()).unwrap();
    air_from_module(&ast::from_tree(&tree).unwrap())
}

fn body(g: &AirGraph, entity: &str) -> String {
    g.resolve(entity).unwrap().slots["body"][0].clone()
}

fn assert_rejected(s: &mut EditSession, target: &str, expected: &str, text: &str, code: &str) {
    let before = graph_to_bytes(&s.graph);
    let bindings = s.bindings.clone();
    let errors = s.errors.clone();
    let error = match s.replace_function_body(target, expected, text) {
        Err(error) => error,
        Ok(_) => panic!("expected rejection: {target} {text}"),
    };
    assert!(error.contains(code), "{error}");
    assert_eq!(before, graph_to_bytes(&s.graph));
    assert_eq!(bindings, s.bindings);
    assert_eq!(errors, s.errors);
}

#[test]
fn shared_body_is_copied_and_function_metadata_is_preserved() {
    let original = graph("demo", &["a", "b"]);
    let old = body(&original, "module:demo/fn:a");
    assert_eq!(old, body(&original, "module:demo/fn:b"));
    let mut s = EditSession::begin(original.clone(), "base".into());
    assert!(s.check().is_empty());
    let (function, new_body) = s
        .replace_function_body("demo.a", &old, "(body (+ (ref x) (int 2)))")
        .unwrap();
    assert_ne!(old, new_body);
    assert_eq!(body(&s.graph, "module:demo/fn:a"), new_body);
    assert_eq!(s.graph.heads["module:demo/fn:a"], function);
    assert_eq!(
        s.graph.heads["module:demo/fn:b"],
        original.heads["module:demo/fn:b"]
    );
    for (rev, node) in &original.nodes {
        let kept = &s.graph.nodes[rev];
        assert_eq!(node.fields, kept.fields);
        assert_eq!(node.slots, kept.slots);
        assert_eq!(node.entity, kept.entity);
    }
    let before = original.resolve("module:demo/fn:a").unwrap();
    let after = s.graph.resolve("module:demo/fn:a").unwrap();
    assert_eq!(before.fields, after.fields);
    for (slot, children) in &before.slots {
        if slot != "body" {
            assert_eq!(children, &after.slots[slot]);
        }
    }
    assert!(s.check().is_empty());
    let bytes = graph_to_bytes(&s.graph);
    let fresh = graph_from_bytes(&bytes).unwrap();
    assert!(fresh.verify().is_empty());
    assert_eq!(body(&fresh, "module:demo/fn:a"), new_body);
    assert_eq!(body(&fresh, "module:demo/fn:b"), old);
    assert_eq!(bytes, graph_to_bytes(&fresh));
}

#[test]
fn shared_entire_function_across_modules_keeps_other_occurrence() {
    let mut original = graph("left", &["f"]);
    let right = graph("right", &["f"]);
    assert_eq!(
        original.heads["module:left/fn:f"],
        right.heads["module:right/fn:f"]
    );
    original.nodes.extend(right.nodes);
    original.heads.extend(right.heads);
    original.module_entities.extend(right.module_entities);
    let old = body(&original, "module:left/fn:f");
    let mut s = EditSession::begin(original.clone(), "base".into());
    assert!(s.check().is_empty());
    s.replace_function_body("left.f", &old, "(body (int 42))")
        .unwrap();
    assert_ne!(
        s.graph.heads["module:left/fn:f"],
        original.heads["module:left/fn:f"]
    );
    for entity in ["module:right", "module:right/fn:f"] {
        assert_eq!(s.graph.heads[entity], original.heads[entity]);
    }
    assert_eq!(body(&s.graph, "module:right/fn:f"), old);
    assert!(s.check().is_empty());
}

#[test]
fn invalid_or_stale_edits_are_atomic_and_next_valid_edit_works() {
    let mut s = EditSession::begin(graph("demo", &["a", "b"]), "base".into());
    let old = body(&s.graph, "module:demo/fn:a");
    s.errors.push("earlier diagnostic".into());
    s.bindings.insert("scope".into(), BTreeMap::new());
    for (target, expected, text, code) in [
        (
            "a",
            old.as_str(),
            "(body (int 2))",
            "QUALIFIED_FUNCTION_REQUIRED",
        ),
        (
            "demo.a",
            &old[..12],
            "(body (int 2))",
            "EXACT_BODY_REVISION_REQUIRED",
        ),
        (
            "demo.missing",
            old.as_str(),
            "(body (int 2))",
            "FUNCTION_NOT_FOUND",
        ),
        ("demo.a", old.as_str(), "(fn a)", "BODY_PARSE"),
        (
            "demo.a",
            old.as_str(),
            "(body (int 2)) (body (int 3))",
            "BODY_PARSE",
        ),
        ("demo.a", old.as_str(), "(body (", "BODY_PARSE"),
        (
            "demo.a",
            old.as_str(),
            "(body (string \"wrong return\"))",
            "BODY_CHECK",
        ),
        ("demo.a", old.as_str(), "(body)", "BODY_PARSE"),
        (
            "demo.a",
            old.as_str(),
            "(body (+ (string \"wrong type\") (int 1)))",
            "BODY_CHECK",
        ),
        ("demo.a", old.as_str(), "(body (ref unknown))", "BODY_CHECK"),
        (
            "demo.a",
            old.as_str(),
            "(body (call io.print (int 1)) (int 2))",
            "BODY_CHECK",
        ),
    ] {
        assert_rejected(&mut s, target, expected, text, code);
    }
    assert_rejected(
        &mut s,
        "demo.a",
        &old,
        &" ".repeat(65537),
        "BODY_SOURCE_LIMIT",
    );
    let (_, current) = s
        .replace_function_body("demo.a", &old, "(body (int 2))")
        .unwrap();
    assert_rejected(
        &mut s,
        "demo.a",
        &old,
        "(body (int 3))",
        "STALE_BODY_REVISION",
    );
    s.replace_function_body("demo.a", &current, "(body (int 3))")
        .unwrap();
    let other = body(&s.graph, "module:demo/fn:b");
    let target = body(&s.graph, "module:demo/fn:a");
    s.replace_function_body("demo.b", &other, "(body (int 4))")
        .unwrap();
    assert_eq!(target, body(&s.graph, "module:demo/fn:a"));
    let bytes = graph_to_bytes(&s.graph);
    s.replace_function_body("demo.a", &target, "(body (int 3))")
        .unwrap();
    assert_eq!(bytes, graph_to_bytes(&s.graph));
}

#[test]
fn ambiguous_declaration_path_is_rejected() {
    let mut s = EditSession::begin(graph("demo", &["a", "a"]), "base".into());
    let old = body(&s.graph, "module:demo/fn:a");
    assert_rejected(
        &mut s,
        "demo.a",
        &old,
        "(body (int 2))",
        "AMBIGUOUS_FUNCTION",
    );
}

#[test]
fn result_and_vector_return_inference_and_source_projection_round_trip() {
    for (returns, original, replacement) in [
        (
            "(result (prim i64) (prim string))",
            "(ok (int 1))",
            "(err (string \"error\"))",
        ),
        (
            "(vec (prim i64))",
            "(vec (prim i64) (int 1))",
            "(vec (prim i64) (int 2))",
        ),
        (
            "(prim string)",
            "(string \"quote\\\" slash\\\\\")",
            "(string \"other\")",
        ),
    ] {
        let source = format!(
            "(module (name \"demo\") (version \"1\") (fn a \
            (params) (returns {returns}) (pure) (body {original})))"
        );
        let tree =
            crate::s_expr::parse_with_limits(&source, &crate::s_expr::Limits::default()).unwrap();
        let mut s = EditSession::begin(
            air_from_module(&ast::from_tree(&tree).unwrap()),
            "base".into(),
        );
        let (_, revision, fragment, _) = s.read_function("demo.a").unwrap();
        let before = graph_to_bytes(&s.graph);
        s.replace_function_body("demo.a", &revision, &fragment)
            .unwrap();
        assert_eq!(before, graph_to_bytes(&s.graph));
        s.replace_function_body("demo.a", &revision, &format!("(body {replacement})"))
            .unwrap();
    }
}
