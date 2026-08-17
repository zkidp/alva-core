//! Capability catalog (pre-RFC mechanical probe).
//!
//! COMPILER-OWNED single source of truth for the language's builtin
//! operations and binary operators. Everything here is declared by the
//! compiler (not derived from historical agent sessions) and is meta-checked
//! against the actual AIR tag / binop implementations in air.rs and ast.rs
//! (`catalog_matches_implementation`, run in tests).
//!
//! Boundaries (locked 2026-08-18):
//!   - positive knowledge: canonical name + aliases + category;
//!   - negative knowledge: NOT_SUPPORTED + supported_alternatives; synonyms
//!     ONLY where the compiler declares them (never fuzzy/string-similarity);
//!   - no applicability reasoning (C3 has zero evidence);
//!   - capability discovery stays separate from entity navigation.

/// Category of a capability.
#[derive(Clone, Copy, PartialEq, Eq)]
pub enum CapCategory {
    Builtin,
    Operator,
}

impl CapCategory {
    pub fn as_str(&self) -> &'static str {
        match self {
            CapCategory::Builtin => "builtin",
            CapCategory::Operator => "operator",
        }
    }
}

pub struct Capability {
    pub canonical: &'static str,
    pub category: CapCategory,
    /// Display aliases the compiler accepts (e.g. to-string / to_string /
    /// tostring all address the same builtin).
    pub aliases: &'static [&'static str],
    /// Arity hint for documentation (unary / binary / ternary / variadic).
    pub arity: &'static str,
}

/// Compiler-declared known synonyms. ONLY explicit declarations; never
/// inferred from string similarity. `sorted` is declared as a synonym of
/// `sort` (language-design choice), `&&`/`||` as synonyms of `and`/`or`.
pub static SYNONYMS: &[(&str, &str)] = &[("sorted", "sort"), ("&&", "and"), ("||", "or")];

/// Canonical builtin operations implemented by the compiler (mirrors the AIR
/// expr tags in air.rs; the meta-test enforces exact correspondence).
pub static BUILTINS: &[Capability] = &[
    Capability {
        canonical: "len",
        category: CapCategory::Builtin,
        aliases: &[],
        arity: "unary",
    },
    Capability {
        canonical: "get",
        category: CapCategory::Builtin,
        aliases: &[],
        arity: "binary",
    },
    Capability {
        canonical: "append",
        category: CapCategory::Builtin,
        aliases: &[],
        arity: "binary",
    },
    Capability {
        canonical: "lookup",
        category: CapCategory::Builtin,
        aliases: &[],
        arity: "binary",
    },
    Capability {
        canonical: "contains",
        category: CapCategory::Builtin,
        aliases: &["has"],
        arity: "binary",
    },
    Capability {
        canonical: "any",
        category: CapCategory::Builtin,
        aliases: &[],
        arity: "binary",
    },
    Capability {
        canonical: "all",
        category: CapCategory::Builtin,
        aliases: &[],
        arity: "binary",
    },
    Capability {
        canonical: "find",
        category: CapCategory::Builtin,
        aliases: &[],
        arity: "binary",
    },
    Capability {
        canonical: "remove",
        category: CapCategory::Builtin,
        aliases: &[],
        arity: "binary",
    },
    Capability {
        canonical: "keys",
        category: CapCategory::Builtin,
        aliases: &[],
        arity: "unary",
    },
    Capability {
        canonical: "split",
        category: CapCategory::Builtin,
        aliases: &[],
        arity: "binary",
    },
    Capability {
        canonical: "concat",
        category: CapCategory::Builtin,
        aliases: &[],
        arity: "binary",
    },
    Capability {
        canonical: "to-string",
        category: CapCategory::Builtin,
        aliases: &["tostring", "to_string"],
        arity: "unary",
    },
    Capability {
        canonical: "parse-int",
        category: CapCategory::Builtin,
        aliases: &["parseint", "parse_int"],
        arity: "unary",
    },
    Capability {
        canonical: "to-bytes",
        category: CapCategory::Builtin,
        aliases: &["tobytes", "to_bytes"],
        arity: "unary",
    },
    Capability {
        canonical: "is-ok",
        category: CapCategory::Builtin,
        aliases: &["isok", "is_ok"],
        arity: "unary",
    },
    Capability {
        canonical: "join",
        category: CapCategory::Builtin,
        aliases: &[],
        arity: "binary",
    },
    Capability {
        canonical: "strip-prefix",
        category: CapCategory::Builtin,
        aliases: &["stripprefix", "strip_prefix"],
        arity: "binary",
    },
    Capability {
        canonical: "before",
        category: CapCategory::Builtin,
        aliases: &[],
        arity: "binary",
    },
    Capability {
        canonical: "ends-with",
        category: CapCategory::Builtin,
        aliases: &["endswith", "ends_with"],
        arity: "binary",
    },
    Capability {
        canonical: "sort",
        category: CapCategory::Builtin,
        aliases: &[],
        arity: "unary",
    },
    Capability {
        canonical: "url-decode",
        category: CapCategory::Builtin,
        aliases: &["urldecode", "url_decode"],
        arity: "unary",
    },
    Capability {
        canonical: "to-hex",
        category: CapCategory::Builtin,
        aliases: &["tohex", "to_hex"],
        arity: "unary",
    },
    Capability {
        canonical: "ct-eq",
        category: CapCategory::Builtin,
        aliases: &["cteq", "ct_eq"],
        arity: "binary",
    },
    Capability {
        canonical: "unwrap",
        category: CapCategory::Builtin,
        aliases: &[],
        arity: "unary",
    },
    Capability {
        canonical: "err-value",
        category: CapCategory::Builtin,
        aliases: &["errvalue", "err_value"],
        arity: "unary",
    },
    Capability {
        canonical: "slice",
        category: CapCategory::Builtin,
        aliases: &[],
        arity: "ternary",
    },
    Capability {
        canonical: "not",
        category: CapCategory::Builtin,
        aliases: &[],
        arity: "unary",
    },
];

/// Canonical binary operators implemented by the compiler (mirrors
/// ast::binop()); `&&`/`||` are NOT implemented (declared synonyms only).
pub static OPERATORS: &[Capability] = &[
    Capability {
        canonical: "+",
        category: CapCategory::Operator,
        aliases: &[],
        arity: "binary",
    },
    Capability {
        canonical: "-",
        category: CapCategory::Operator,
        aliases: &[],
        arity: "binary",
    },
    Capability {
        canonical: "*",
        category: CapCategory::Operator,
        aliases: &[],
        arity: "binary",
    },
    Capability {
        canonical: "/",
        category: CapCategory::Operator,
        aliases: &[],
        arity: "binary",
    },
    Capability {
        canonical: "mod",
        category: CapCategory::Operator,
        aliases: &["%"],
        arity: "binary",
    },
    Capability {
        canonical: "==",
        category: CapCategory::Operator,
        aliases: &[],
        arity: "binary",
    },
    Capability {
        canonical: "!=",
        category: CapCategory::Operator,
        aliases: &[],
        arity: "binary",
    },
    Capability {
        canonical: "<",
        category: CapCategory::Operator,
        aliases: &[],
        arity: "binary",
    },
    Capability {
        canonical: "<=",
        category: CapCategory::Operator,
        aliases: &[],
        arity: "binary",
    },
    Capability {
        canonical: ">",
        category: CapCategory::Operator,
        aliases: &[],
        arity: "binary",
    },
    Capability {
        canonical: ">=",
        category: CapCategory::Operator,
        aliases: &[],
        arity: "binary",
    },
    Capability {
        canonical: "and",
        category: CapCategory::Operator,
        aliases: &[],
        arity: "binary",
    },
    Capability {
        canonical: "or",
        category: CapCategory::Operator,
        aliases: &[],
        arity: "binary",
    },
];

pub enum CapabilityOutcome {
    /// name (canonical or declared alias/synonym) -> canonical capability.
    Canonical(&'static Capability),
    /// name is NOT a supported capability; declared alternatives only.
    Unsupported {
        supported_alternatives: Vec<&'static str>,
    },
}

fn find_cap(name: &str) -> Option<&'static Capability> {
    BUILTINS
        .iter()
        .chain(OPERATORS.iter())
        .find(|c| c.canonical == name || c.aliases.contains(&name))
}

/// Deterministic capability resolution: canonical name / declared alias /
/// declared synonym -> canonical; anything else -> NOT_SUPPORTED with ONLY
/// compiler-declared alternatives (never fuzzy).
pub fn resolve_capability(name: &str) -> CapabilityOutcome {
    if let Some(c) = find_cap(name) {
        return CapabilityOutcome::Canonical(c);
    }
    if let Some((_, canonical)) = SYNONYMS.iter().find(|(s, _)| *s == name) {
        if let Some(c) = find_cap(canonical) {
            return CapabilityOutcome::Canonical(c);
        }
    }
    CapabilityOutcome::Unsupported {
        supported_alternatives: Vec::new(),
    }
}

pub fn list_capabilities(category: Option<CapCategory>) -> Vec<&'static Capability> {
    BUILTINS
        .iter()
        .chain(OPERATORS.iter())
        .filter(|c| category.is_none_or(|cat| c.category == cat))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Ground truth of what the compiler actually implements (from air.rs
    /// expr tags and ast.rs binop()). The catalog MUST match exactly.
    const IMPLEMENTED_BUILTINS: &[&str] = &[
        "len",
        "get",
        "append",
        "lookup",
        "contains",
        "any",
        "all",
        "find",
        "remove",
        "keys",
        "split",
        "concat",
        "to-string",
        "parse-int",
        "to-bytes",
        "is-ok",
        "join",
        "strip-prefix",
        "before",
        "ends-with",
        "sort",
        "url-decode",
        "to-hex",
        "ct-eq",
        "unwrap",
        "err-value",
        "slice",
        "not",
    ];
    const IMPLEMENTED_OPERATORS: &[&str] = &[
        "+", "-", "*", "/", "mod", "==", "!=", "<", "<=", ">", ">=", "and", "or",
    ];

    #[test]
    fn catalog_matches_implementation() {
        let cataloged_builtins: Vec<&str> = BUILTINS.iter().map(|c| c.canonical).collect();
        let mut a = cataloged_builtins.clone();
        a.sort_unstable();
        let mut b = IMPLEMENTED_BUILTINS.to_vec();
        b.sort_unstable();
        assert_eq!(a, b, "builtin catalog drifted from implementation");

        let cataloged_ops: Vec<&str> = OPERATORS.iter().map(|c| c.canonical).collect();
        let mut a = cataloged_ops.clone();
        a.sort_unstable();
        let mut b = IMPLEMENTED_OPERATORS.to_vec();
        b.sort_unstable();
        assert_eq!(a, b, "operator catalog drifted from implementation");

        // every declared synonym maps to a real capability
        for (syn, canonical) in SYNONYMS {
            assert!(
                find_cap(canonical).is_some(),
                "synonym target {canonical} missing"
            );
            match resolve_capability(syn) {
                CapabilityOutcome::Canonical(c) => assert_eq!(c.canonical, *canonical),
                _ => panic!("synonym {syn} did not resolve"),
            }
        }
    }

    #[test]
    fn negative_knowledge_is_deterministic() {
        match resolve_capability("removefunction") {
            CapabilityOutcome::Unsupported {
                supported_alternatives,
            } => {
                assert!(supported_alternatives.is_empty());
            }
            _ => panic!("removefunction must be unsupported"),
        }
        match resolve_capability("filter") {
            CapabilityOutcome::Unsupported { .. } => {}
            _ => panic!("filter must be unsupported"),
        }
        // declared synonym resolves canonically
        match resolve_capability("sorted") {
            CapabilityOutcome::Canonical(c) => assert_eq!(c.canonical, "sort"),
            _ => panic!("sorted must resolve to sort"),
        }
        match resolve_capability("&&") {
            CapabilityOutcome::Canonical(c) => assert_eq!(c.canonical, "and"),
            _ => panic!("&& must resolve to and"),
        }
    }
}
