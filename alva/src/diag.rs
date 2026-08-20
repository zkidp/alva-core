use crate::s_expr::Span;

#[derive(Clone, Debug)]
pub struct Repair {
    pub kind: String,
    pub target: Option<String>,
    pub value: Option<String>,
}

impl Repair {
    pub fn new(kind: impl Into<String>) -> Self {
        Repair {
            kind: kind.into(),
            target: None,
            value: None,
        }
    }

    pub fn target(mut self, t: impl Into<String>) -> Self {
        self.target = Some(t.into());
        self
    }

    pub fn value(mut self, v: impl Into<String>) -> Self {
        self.value = Some(v.into());
        self
    }

    pub fn to_json(&self) -> String {
        let mut parts = vec![format!("\"kind\":\"{}\"", json_escape(&self.kind))];
        if let Some(t) = &self.target {
            parts.push(format!("\"target\":\"{}\"", json_escape(t)));
        }
        if let Some(v) = &self.value {
            parts.push(format!("\"value\":\"{}\"", json_escape(v)));
        }
        format!("{{{}}}", parts.join(","))
    }
}

#[derive(Clone, Debug)]
pub struct Diag {
    pub severity: &'static str,
    pub code: String,
    pub message: String,
    pub span: Option<Span>,
    pub module: Option<String>,
    pub function: Option<String>,
    pub expected: Vec<String>,
    pub actual: Vec<String>,
    pub caused_by: Vec<String>,
    pub affected_modules: Vec<String>,
    pub repairs: Vec<Repair>,
}

impl Diag {
    pub fn error(message: impl Into<String>) -> Self {
        Diag {
            severity: "error",
            code: "E_DIAG".to_string(),
            message: message.into(),
            span: None,
            module: None,
            function: None,
            expected: Vec::new(),
            actual: Vec::new(),
            caused_by: Vec::new(),
            affected_modules: Vec::new(),
            repairs: Vec::new(),
        }
    }

    pub fn error_at(span: Span, message: impl Into<String>) -> Self {
        Diag {
            severity: "error",
            code: "E_DIAG".to_string(),
            message: message.into(),
            span: Some(span),
            module: None,
            function: None,
            expected: Vec::new(),
            actual: Vec::new(),
            caused_by: Vec::new(),
            affected_modules: Vec::new(),
            repairs: Vec::new(),
        }
    }

    pub fn warn(message: impl Into<String>) -> Self {
        Diag {
            severity: "warning",
            code: "W_DIAG".to_string(),
            message: message.into(),
            span: None,
            module: None,
            function: None,
            expected: Vec::new(),
            actual: Vec::new(),
            caused_by: Vec::new(),
            affected_modules: Vec::new(),
            repairs: Vec::new(),
        }
    }

    #[allow(dead_code)]
    pub fn warn_at(span: Span, message: impl Into<String>) -> Self {
        Diag {
            severity: "warning",
            code: "W_DIAG".to_string(),
            message: message.into(),
            span: Some(span),
            module: None,
            function: None,
            expected: Vec::new(),
            actual: Vec::new(),
            caused_by: Vec::new(),
            affected_modules: Vec::new(),
            repairs: Vec::new(),
        }
    }

    pub fn with_code(mut self, code: impl Into<String>) -> Self {
        self.code = code.into();
        self
    }

    pub fn with_repair(mut self, repair: Repair) -> Self {
        self.repairs.push(repair);
        self
    }

    pub fn with_module(mut self, m: impl Into<String>) -> Self {
        self.module = Some(m.into());
        self
    }

    pub fn with_function(mut self, f: impl Into<String>) -> Self {
        self.function = Some(f.into());
        self
    }

    pub fn render(&self) -> String {
        match &self.span {
            Some(s) => format!(
                "{}:{}: {}: {}: {}",
                s.line, s.col, self.severity, self.code, self.message
            ),
            None => format!("{}: {}: {}", self.severity, self.code, self.message),
        }
    }

    pub fn to_json(&self) -> String {
        let mut parts = vec![
            "\"schema_version\":\"1\"".to_string(),
            format!("\"code\":\"{}\"", json_escape(&self.code)),
            format!("\"severity\":\"{}\"", self.severity),
        ];
        if let Some(m) = &self.module {
            parts.push(format!("\"module\":\"{}\"", json_escape(m)));
        }
        if let Some(f) = &self.function {
            parts.push(format!("\"function\":\"{}\"", json_escape(f)));
        }
        if let Some(s) = &self.span {
            parts.push(format!(
                "\"span\":{{\"start\":{{\"line\":{},\"column\":{}}},\"end\":{{\"line\":{},\"column\":{}}}}}",
                s.line, s.col, s.line, s.col
            ));
        }
        parts.push(format!("\"message\":\"{}\"", json_escape(&self.message)));
        parts.push(format!(
            "\"expected\":[{}]",
            self.expected
                .iter()
                .map(|x| format!("\"{}\"", json_escape(x)))
                .collect::<Vec<_>>()
                .join(",")
        ));
        parts.push(format!(
            "\"actual\":[{}]",
            self.actual
                .iter()
                .map(|x| format!("\"{}\"", json_escape(x)))
                .collect::<Vec<_>>()
                .join(",")
        ));
        parts.push(format!(
            "\"caused_by\":[{}]",
            self.caused_by
                .iter()
                .map(|x| format!("\"{}\"", json_escape(x)))
                .collect::<Vec<_>>()
                .join(",")
        ));
        parts.push(format!(
            "\"affected_modules\":[{}]",
            self.affected_modules
                .iter()
                .map(|x| format!("\"{}\"", json_escape(x)))
                .collect::<Vec<_>>()
                .join(",")
        ));
        parts.push(format!(
            "\"repairs\":[{}]",
            self.repairs
                .iter()
                .map(|r| r.to_json())
                .collect::<Vec<_>>()
                .join(",")
        ));
        format!("{{{}}}", parts.join(","))
    }
}

pub fn json_escape(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out
}
