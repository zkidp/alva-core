#[derive(Clone, Debug, PartialEq)]
pub struct Span {
    pub line: u32,
    pub col: u32,
}

// ---------------------------------------------------------------------------
// Resource limits
//
// These bound adversarial or accidentally huge inputs so the recursive
// parser/checker cannot be driven into unbounded stack or memory use.
// Defaults can be overridden via ALVA_MAX_* environment variables, which also
// lets the golden tests exercise each limit with tiny fixtures.
// ---------------------------------------------------------------------------

pub const DEFAULT_MAX_AST_DEPTH: usize = 512;
pub const DEFAULT_MAX_AST_NODES: usize = 100_000;
pub const DEFAULT_MAX_SOURCE_BYTES: usize = 8 * 1024 * 1024;
pub const DEFAULT_MAX_LITERAL_BYTES: usize = 256 * 1024;
pub const DEFAULT_MAX_ATOM_BYTES: usize = 4096;

#[derive(Clone, Debug)]
pub struct Limits {
    pub max_depth: usize,
    pub max_nodes: usize,
    pub max_source_bytes: usize,
    pub max_literal_bytes: usize,
    pub max_atom_bytes: usize,
}

impl Default for Limits {
    fn default() -> Self {
        Limits {
            max_depth: DEFAULT_MAX_AST_DEPTH,
            max_nodes: DEFAULT_MAX_AST_NODES,
            max_source_bytes: DEFAULT_MAX_SOURCE_BYTES,
            max_literal_bytes: DEFAULT_MAX_LITERAL_BYTES,
            max_atom_bytes: DEFAULT_MAX_ATOM_BYTES,
        }
    }
}

impl Limits {
    /// Read limits from ALVA_MAX_* environment variables (invalid values fall
    /// back to the defaults).
    pub fn from_env() -> Self {
        let mut l = Limits::default();
        if let Ok(v) = std::env::var("ALVA_MAX_AST_DEPTH") {
            if let Ok(n) = v.parse() {
                l.max_depth = n;
            }
        }
        if let Ok(v) = std::env::var("ALVA_MAX_AST_NODES") {
            if let Ok(n) = v.parse() {
                l.max_nodes = n;
            }
        }
        if let Ok(v) = std::env::var("ALVA_MAX_SOURCE_BYTES") {
            if let Ok(n) = v.parse() {
                l.max_source_bytes = n;
            }
        }
        if let Ok(v) = std::env::var("ALVA_MAX_LITERAL_BYTES") {
            if let Ok(n) = v.parse() {
                l.max_literal_bytes = n;
            }
        }
        if let Ok(v) = std::env::var("ALVA_MAX_ATOM_BYTES") {
            if let Ok(n) = v.parse() {
                l.max_atom_bytes = n;
            }
        }
        l
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum ParseError {
    Depth {
        line: u32,
        col: u32,
        limit: usize,
    },
    Nodes {
        line: u32,
        col: u32,
        limit: usize,
    },
    SourceBytes {
        bytes: usize,
        limit: usize,
    },
    LiteralBytes {
        line: u32,
        col: u32,
        bytes: usize,
        limit: usize,
    },
    AtomBytes {
        line: u32,
        col: u32,
        bytes: usize,
        limit: usize,
    },
    UnterminatedString {
        line: u32,
        col: u32,
    },
    UnclosedList {
        line: u32,
        col: u32,
    },
    UnexpectedClose {
        line: u32,
        col: u32,
    },
    EmptyAtom {
        line: u32,
        col: u32,
    },
    UnexpectedEof {
        line: u32,
        col: u32,
    },
    TrailingInput {
        line: u32,
        col: u32,
    },
}

impl ParseError {
    /// Stable diagnostic code (public contract; do not renumber).
    pub fn code(&self) -> &'static str {
        match self {
            ParseError::Depth { .. } => "E_PARSE_002",
            ParseError::Nodes { .. } => "E_PARSE_003",
            ParseError::SourceBytes { .. } => "E_PARSE_004",
            ParseError::LiteralBytes { .. } => "E_PARSE_005",
            ParseError::AtomBytes { .. } => "E_PARSE_006",
            _ => "E_PARSE_001",
        }
    }

    pub fn span(&self) -> Span {
        match self {
            ParseError::Depth { line, col, .. }
            | ParseError::Nodes { line, col, .. }
            | ParseError::LiteralBytes { line, col, .. }
            | ParseError::AtomBytes { line, col, .. }
            | ParseError::UnterminatedString { line, col }
            | ParseError::UnclosedList { line, col }
            | ParseError::UnexpectedClose { line, col }
            | ParseError::EmptyAtom { line, col }
            | ParseError::UnexpectedEof { line, col }
            | ParseError::TrailingInput { line, col } => Span {
                line: *line,
                col: *col,
            },
            ParseError::SourceBytes { .. } => Span { line: 1, col: 1 },
        }
    }

    pub fn message(&self) -> String {
        match self {
            ParseError::Depth { limit, .. } => {
                format!("maximum AST nesting depth {limit} exceeded")
            }
            ParseError::Nodes { limit, .. } => {
                format!("maximum AST node count {limit} exceeded")
            }
            ParseError::SourceBytes { bytes, limit } => {
                format!("source is {bytes} bytes, exceeding limit of {limit} bytes")
            }
            ParseError::LiteralBytes { bytes, limit, .. } => {
                format!("string literal is {bytes} bytes, exceeding limit of {limit} bytes")
            }
            ParseError::AtomBytes { bytes, limit, .. } => {
                format!("atom is {bytes} bytes, exceeding limit of {limit} bytes")
            }
            ParseError::UnterminatedString { line, col } => {
                format!("unterminated string at line {line} col {col}")
            }
            ParseError::UnclosedList { line, col } => {
                format!("unclosed '(' opened at line {line} col {col}")
            }
            ParseError::UnexpectedClose { line, col } => {
                format!("unexpected ')' at line {line} col {col}")
            }
            ParseError::EmptyAtom { line, col } => {
                format!("empty atom at line {line} col {col}")
            }
            ParseError::UnexpectedEof { line, col } => {
                format!("unexpected end of input at line {line} col {col}")
            }
            ParseError::TrailingInput { line, col } => {
                format!("unexpected trailing input at line {line} col {col}")
            }
        }
    }
}

impl std::fmt::Display for ParseError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.message())
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum Atom {
    Sym(String),
    Str(String),
}

#[derive(Clone, Debug)]
pub enum Node {
    List(Vec<Node>, Span),
    Atom(Atom, Span),
}

impl Node {
    pub fn span(&self) -> Span {
        match self {
            Node::List(_, s) => s.clone(),
            Node::Atom(_, s) => s.clone(),
        }
    }
}

pub fn parse_with_limits(text: &str, limits: &Limits) -> Result<Node, ParseError> {
    if text.len() > limits.max_source_bytes {
        return Err(ParseError::SourceBytes {
            bytes: text.len(),
            limit: limits.max_source_bytes,
        });
    }
    let mut p = Parser {
        chars: text.chars().collect(),
        pos: 0,
        line: 1,
        col: 1,
        limits: limits.clone(),
        nodes: 0,
    };
    let node = p.parse_node(1)?;
    p.skip_ws();
    if p.pos < p.chars.len() {
        return Err(ParseError::TrailingInput {
            line: p.line,
            col: p.col,
        });
    }
    Ok(node)
}

struct Parser {
    chars: Vec<char>,
    pos: usize,
    line: u32,
    col: u32,
    limits: Limits,
    nodes: usize,
}

impl Parser {
    fn peek(&self) -> Option<char> {
        self.chars.get(self.pos).copied()
    }

    fn bump(&mut self) -> Option<char> {
        let c = self.chars.get(self.pos).copied();
        if let Some(c) = c {
            self.pos += 1;
            if c == '\n' {
                self.line += 1;
                self.col = 1;
            } else {
                self.col += 1;
            }
        }
        c
    }

    fn skip_ws(&mut self) {
        loop {
            while let Some(c) = self.peek() {
                if c.is_whitespace() {
                    self.bump();
                } else {
                    break;
                }
            }
            if self.peek() == Some(';') {
                while let Some(c) = self.peek() {
                    if c == '\n' {
                        break;
                    }
                    self.bump();
                }
            } else {
                break;
            }
        }
    }

    fn bump_node(&mut self) -> Result<(), ParseError> {
        self.nodes += 1;
        if self.nodes > self.limits.max_nodes {
            return Err(ParseError::Nodes {
                line: self.line,
                col: self.col,
                limit: self.limits.max_nodes,
            });
        }
        Ok(())
    }

    fn parse_node(&mut self, depth: usize) -> Result<Node, ParseError> {
        if depth > self.limits.max_depth {
            return Err(ParseError::Depth {
                line: self.line,
                col: self.col,
                limit: self.limits.max_depth,
            });
        }
        self.skip_ws();
        let (line, col) = (self.line, self.col);
        match self.peek() {
            Some('(') => {
                self.bump();
                let mut items = Vec::new();
                loop {
                    self.skip_ws();
                    match self.peek() {
                        Some(')') => {
                            self.bump();
                            break;
                        }
                        Some(_) => items.push(self.parse_node(depth + 1)?),
                        None => return Err(ParseError::UnclosedList { line, col }),
                    }
                }
                self.bump_node()?;
                Ok(Node::List(items, Span { line, col }))
            }
            Some('"') => {
                self.bump();
                let mut s = String::new();
                loop {
                    match self.bump() {
                        Some('"') => break,
                        Some('\\') => match self.bump() {
                            Some('n') => s.push('\n'),
                            Some('t') => s.push('\t'),
                            Some('r') => s.push('\r'),
                            Some('"') => s.push('"'),
                            Some('\\') => s.push('\\'),
                            Some(c) => {
                                s.push('\\');
                                s.push(c);
                            }
                            None => return Err(ParseError::UnterminatedString { line, col }),
                        },
                        Some(c) => s.push(c),
                        None => return Err(ParseError::UnterminatedString { line, col }),
                    }
                    if s.len() > self.limits.max_literal_bytes {
                        return Err(ParseError::LiteralBytes {
                            line,
                            col,
                            bytes: s.len(),
                            limit: self.limits.max_literal_bytes,
                        });
                    }
                }
                self.bump_node()?;
                Ok(Node::Atom(Atom::Str(s), Span { line, col }))
            }
            Some(')') => Err(ParseError::UnexpectedClose { line, col }),
            Some(_) => {
                let mut s = String::new();
                while let Some(c) = self.peek() {
                    if c.is_whitespace() || c == '(' || c == ')' || c == ';' {
                        break;
                    }
                    s.push(c);
                    self.bump();
                }
                if s.is_empty() {
                    return Err(ParseError::EmptyAtom { line, col });
                }
                if s.len() > self.limits.max_atom_bytes {
                    return Err(ParseError::AtomBytes {
                        line,
                        col,
                        bytes: s.len(),
                        limit: self.limits.max_atom_bytes,
                    });
                }
                self.bump_node()?;
                Ok(Node::Atom(Atom::Sym(s), Span { line, col }))
            }
            None => Err(ParseError::UnexpectedEof { line, col }),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn debug_parse_example() {
        let src = std::fs::read_to_string("examples/hello.alva").unwrap();
        match parse_with_limits(&src, &Limits::default()) {
            Ok(Node::List(items, _)) => {
                assert!(matches!(
                    items.first(),
                    Some(Node::Atom(Atom::Sym(s), _)) if s == "module"
                ));
            }
            Ok(_) => panic!("root is not a list"),
            Err(e) => panic!("parse error: {e}"),
        }
    }

    #[test]
    fn depth_boundary_default() {
        let limits = Limits::default();
        // 511 open parens: the innermost atom sits at depth 512 == max_depth.
        let ok_src = format!("{}x{}", "(".repeat(511), ")".repeat(511));
        assert!(
            parse_with_limits(&ok_src, &limits).is_ok(),
            "input at the depth limit must parse"
        );
        // 512 open parens: the atom sits at depth 513 > max_depth -> E_PARSE_002.
        let bad_src = format!("{}x{}", "(".repeat(512), ")".repeat(512));
        match parse_with_limits(&bad_src, &limits) {
            Err(e) if e.code() == "E_PARSE_002" => {}
            other => panic!("expected E_PARSE_002 at depth limit+1, got {other:?}"),
        }
    }
}
