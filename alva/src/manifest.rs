use crate::ast::{self, BinOp, Expr, Module, TypeExpr};
use crate::diag::json_escape;
use sha2::{Digest, Sha256};

// 模块接口清单 v2：
//   - signature_hash   只含参数类型/返回类型/effects（参数名不属于公开接口，调用是位置式）
//   - contract_hash    pre/post/inv 的语义序列化（排除 span/注释/格式，参数按位置规范化）
//   - documentation_hash（预留，当前为空文档的稳定哈希）
//   - interface_hash   排序后的导出签名 + 三个子哈希的 SHA-256
// 全部使用 SHA-256，跨平台/版本稳定。

pub fn generate(module: &Module) -> String {
    let mut lines: Vec<String> = Vec::new();
    let mut exports: Vec<String> = Vec::new();

    for f in &module.fns {
        if !module.exports.contains(&f.name) {
            continue;
        }
        let sig = semantic_signature(f);
        let signature_hash = sha256(&sig);
        let contract = semantic_contracts(f);
        let contract_hash = sha256(&contract);
        let documentation_hash = sha256("");
        lines.push(format!(
            "fn {} sig={} contract={} doc={}",
            f.name, signature_hash, contract_hash, documentation_hash
        ));
        exports.push(format!(
            "\"{}\":{{\"kind\":\"fn\",\"params\":[{}],\"returns\":\"{}\",\"effects\":[{}],\"signature_hash\":\"{}\",\"contract_hash\":\"{}\",\"documentation_hash\":\"{}\"}}",
            json_escape(&f.name),
            f.params
                .iter()
                .map(|(_, t)| format!("\"{}\"", json_escape(&semantic_type(t))))
                .collect::<Vec<_>>()
                .join(","),
            json_escape(&semantic_type(&f.returns)),
            sorted(&f.eff)
                .iter()
                .map(|e| format!("\"{}\"", json_escape(e)))
                .collect::<Vec<_>>()
                .join(","),
            signature_hash,
            contract_hash,
            documentation_hash
        ));
    }
    for t in &module.types {
        if !module.exports.contains(&t.name) {
            continue;
        }
        let def = semantic_type_def(t);
        let def_hash = sha256(&def);
        lines.push(format!("type {} = {}", t.name, def_hash));
        exports.push(format!(
            "\"{}\":{{\"kind\":\"type\",\"signature_hash\":\"{}\",\"def\":\"{}\"}}",
            json_escape(&t.name),
            def_hash,
            json_escape(&def)
        ));
    }

    lines.sort();
    let interface_hash = sha256(&lines.join("\n"));
    format!(
        "{{\"module\":\"{}\",\"interface_hash\":\"{}\",\"deps\":[{}],\"exports\":{{{}}}}}",
        json_escape(&module.name),
        interface_hash,
        module
            .deps
            .iter()
            .map(|(n, _)| format!("\"{}\"", json_escape(n)))
            .collect::<Vec<_>>()
            .join(","),
        exports.join(",")
    )
}

fn semantic_signature(f: &ast::FnDef) -> String {
    let param_types: Vec<String> = f.params.iter().map(|(_, t)| semantic_type(t)).collect();
    format!(
        "fn {} ({}) -> {} eff=[{}]",
        f.name,
        param_types.join(", "),
        semantic_type(&f.returns),
        sorted(&f.eff).join(",")
    )
}

fn semantic_contracts(f: &ast::FnDef) -> String {
    // 参数名规范化为 $0,$1,...；let 绑定按出现顺序规范化为 $l<n>
    let mut ctx = SemCtx::new();
    for (i, (name, _)) in f.params.iter().enumerate() {
        ctx = ctx.bind(name, &format!("${i}"));
    }
    let mut lc = 0usize;
    let mut parts = Vec::new();
    for e in &f.pre {
        parts.push(format!("pre({})", semantic_expr(e, &ctx, &mut lc)));
    }
    for e in &f.post {
        parts.push(format!("post({})", semantic_expr(e, &ctx, &mut lc)));
    }
    for e in &f.inv {
        parts.push(format!("inv({})", semantic_expr(e, &ctx, &mut lc)));
    }
    parts.join(" ")
}

#[derive(Clone)]
struct SemCtx {
    vars: Vec<(String, String)>,
}

impl SemCtx {
    fn new() -> Self {
        SemCtx { vars: Vec::new() }
    }

    fn bind(&self, name: &str, canon: &str) -> Self {
        let mut c = self.clone();
        c.vars.push((name.to_string(), canon.to_string()));
        c
    }

    fn get(&self, name: &str) -> String {
        self.vars
            .iter()
            .rev()
            .find(|(n, _)| n == name)
            .map(|(_, c)| c.clone())
            .unwrap_or_else(|| format!("ref:{name}"))
    }
}

fn se(e: &Expr, ctx: &SemCtx, lc: &mut usize) -> String {
    semantic_expr(e, ctx, lc)
}

// 语义序列化：排除 span、注释、格式；名称按作用域规范化
fn semantic_expr(e: &Expr, ctx: &SemCtx, lc: &mut usize) -> String {
    match e {
        Expr::Int(v, _) => format!("int({v})"),
        Expr::UInt(v, _) => format!("uint({v})"),
        Expr::Float(v, _) => format!("float({v})"),
        Expr::Str(s, _) => format!("str({})", json_escape(s)),
        Expr::Bool(b, _) => format!("bool({b})"),
        Expr::Bytes(v, _) => format!(
            "bytes({})",
            v.iter().map(|x| format!("{x:02x}")).collect::<String>()
        ),
        Expr::Nil(_) => "nil".to_string(),
        Expr::Ref(n, _) => ctx.get(n),
        Expr::Call(n, args, _) => format!(
            "call({n} {})",
            args.iter()
                .map(|a| se(a, ctx, lc))
                .collect::<Vec<_>>()
                .join(" ")
        ),
        Expr::Bin(op, a, b, _) => format!(
            "bin({} {} {})",
            binop_name(op),
            se(a, ctx, lc),
            se(b, ctx, lc)
        ),
        Expr::Not(x, _) => format!("not({})", se(x, ctx, lc)),
        Expr::If(c, t, e2, _) => format!(
            "if({} {} {})",
            se(c, ctx, lc),
            se(t, ctx, lc),
            se(e2, ctx, lc)
        ),
        Expr::Let(n, t, v, b, _) => {
            let cid = *lc;
            *lc += 1;
            let c2 = ctx.bind(n, &format!("$l{cid}"));
            format!(
                "let({cid} {} {} {})",
                t.as_ref()
                    .map(semantic_type)
                    .unwrap_or_else(|| "-".to_string()),
                se(v, ctx, lc),
                se(b, &c2, lc)
            )
        }
        Expr::Block(es, _) => format!(
            "block({})",
            es.iter()
                .map(|x| se(x, ctx, lc))
                .collect::<Vec<_>>()
                .join(" ")
        ),
        Expr::VecLit(t, es, _) => format!(
            "vec({} {})",
            semantic_type(t),
            es.iter()
                .map(|x| se(x, ctx, lc))
                .collect::<Vec<_>>()
                .join(" ")
        ),
        Expr::Len(v, _) => format!("len({})", se(v, ctx, lc)),
        Expr::Get(v, i, _) => format!("get({} {})", se(v, ctx, lc), se(i, ctx, lc)),
        Expr::Append(v, x, _) => format!("append({} {})", se(v, ctx, lc), se(x, ctx, lc)),
        Expr::As(t, x, _) => format!("as({} {})", semantic_type(t), se(x, ctx, lc)),
        Expr::Fold(idx, lo, hi, acc, at, init, body, _) => {
            // capture-safe alpha 归一化：每个 binder 取唯一 id（与 let $l{cid}
            // 同一纪律），嵌套 fold 不再共享固定 $i/$a 而互相遮蔽碰撞。
            let cid = *lc;
            *lc += 1;
            let c2 = ctx
                .bind(idx, &format!("$i{cid}"))
                .bind(acc, &format!("$a{cid}"));
            format!(
                "fold({} {} {} {} {})",
                se(lo, ctx, lc),
                se(hi, ctx, lc),
                semantic_type(at),
                se(init, ctx, lc),
                se(body, &c2, lc)
            )
        }
        Expr::Loop(acc, at, init, inv, cond, body, _) => {
            let cid = *lc;
            *lc += 1;
            let c2 = ctx.bind(acc, &format!("$a{cid}"));
            format!(
                "loop({} {} {} {} {})",
                semantic_type(at),
                se(init, ctx, lc),
                inv.as_deref()
                    .map(|x| se(x, &c2, lc))
                    .unwrap_or_else(|| "-".to_string()),
                se(cond, &c2, lc),
                se(body, &c2, lc)
            )
        }
        Expr::Variant(tn, vn, _) => format!("variant({tn}.{vn})"),
        Expr::Match(tn, v, cases, _) => format!(
            "match({tn} {} {})",
            se(v, ctx, lc),
            cases
                .iter()
                .map(|(c, b)| format!("{c}:{}", se(b, ctx, lc)))
                .collect::<Vec<_>>()
                .join(" ")
        ),
        Expr::MapLit(k, v, entries, _) => format!(
            "map({} {} {})",
            semantic_type(k),
            semantic_type(v),
            entries
                .iter()
                .map(|(a, b)| format!("{}:{}", se(a, ctx, lc), se(b, ctx, lc)))
                .collect::<Vec<_>>()
                .join(" ")
        ),
        Expr::Set(m, k, v, _) => format!(
            "set({} {} {})",
            se(m, ctx, lc),
            se(k, ctx, lc),
            se(v, ctx, lc)
        ),
        Expr::Lookup(m, k, _) => format!("lookup({} {})", se(m, ctx, lc), se(k, ctx, lc)),
        Expr::Contains(m, k, _) => format!("contains({} {})", se(m, ctx, lc), se(k, ctx, lc)),
        Expr::VecContains(v, x, _) => {
            format!("veccontains({} {})", se(v, ctx, lc), se(x, ctx, lc))
        }
        Expr::Any(ev, c, p, _) => {
            // capture-safe alpha 归一化：唯一 lexical binder，避免嵌套
            // any/all/find 的内外层 elem_var 都归一成 $e 而碰撞。
            let cid = *lc;
            *lc += 1;
            let canon = format!("$e{cid}");
            let c2 = ctx.bind(ev, &canon);
            format!("any({canon} {} {})", se(c, ctx, lc), se(p, &c2, lc))
        }
        Expr::All(ev, c, p, _) => {
            let cid = *lc;
            *lc += 1;
            let canon = format!("$e{cid}");
            let c2 = ctx.bind(ev, &canon);
            format!("all({canon} {} {})", se(c, ctx, lc), se(p, &c2, lc))
        }
        Expr::Find(ev, c, p, _) => {
            let cid = *lc;
            *lc += 1;
            let canon = format!("$e{cid}");
            let c2 = ctx.bind(ev, &canon);
            format!("find({canon} {} {})", se(c, ctx, lc), se(p, &c2, lc))
        }
        Expr::Remove(m, k, _) => format!("remove({} {})", se(m, ctx, lc), se(k, ctx, lc)),
        Expr::Keys(m, _) => format!("keys({})", se(m, ctx, lc)),
        Expr::Unwrap(x, _) => format!("unwrap({})", se(x, ctx, lc)),
        Expr::ErrValue(x, _) => format!("errvalue({})", se(x, ctx, lc)),
        Expr::Slice(v, s, e2, _) => format!(
            "slice({} {} {})",
            se(v, ctx, lc),
            se(s, ctx, lc),
            se(e2, ctx, lc)
        ),
        Expr::Split(s, sep, _) => format!("split({} {})", se(s, ctx, lc), se(sep, ctx, lc)),
        Expr::Concat(a, b, _) => format!("concat({} {})", se(a, ctx, lc), se(b, ctx, lc)),
        Expr::ToString(x, _) => format!("tostring({})", se(x, ctx, lc)),
        Expr::ParseInt(x, _) => format!("parseint({})", se(x, ctx, lc)),
        Expr::ToBytes(x, _) => format!("tobytes({})", se(x, ctx, lc)),
        Expr::IsOk(x, _) => format!("isok({})", se(x, ctx, lc)),
        Expr::Join(v, sep, _) => format!("join({} {})", se(v, ctx, lc), se(sep, ctx, lc)),
        Expr::StripPrefix(s, p, _) => format!("stripprefix({} {})", se(s, ctx, lc), se(p, ctx, lc)),
        Expr::Before(s, sep, _) => format!("before({} {})", se(s, ctx, lc), se(sep, ctx, lc)),
        Expr::EndsWith(s, suf, _) => format!("endswith({} {})", se(s, ctx, lc), se(suf, ctx, lc)),
        Expr::Sort(v, _) => format!("sort({})", se(v, ctx, lc)),
        Expr::UrlDecode(x, _) => format!("urldecode({})", se(x, ctx, lc)),
        Expr::ToHex(x, _) => format!("tohex({})", se(x, ctx, lc)),
        Expr::CtEq(a, b, _) => format!("cteq({} {})", se(a, ctx, lc), se(b, ctx, lc)),
        Expr::Record(name, fields, _) => format!(
            "record({name} {})",
            fields
                .iter()
                .map(|(n, v)| format!("{n}:{}", se(v, ctx, lc)))
                .collect::<Vec<_>>()
                .join(" ")
        ),
        Expr::RecordUpdate(name, base, fields, _) => format!(
            "record_update({name} {} {})",
            se(base, ctx, lc),
            fields
                .iter()
                .map(|(n, v)| format!("{n}:{}", se(v, ctx, lc)))
                .collect::<Vec<_>>()
                .join(" ")
        ),
        Expr::Field(x, n, _) => format!("field({} {n})", se(x, ctx, lc)),
        Expr::Raise(x, _) => format!("raise({})", se(x, ctx, lc)),
        Expr::Try(x, _n, b, _) => format!("try({} {})", se(x, ctx, lc), se(b, ctx, lc)),
        Expr::Ok(x, _) => format!("ok({})", se(x, ctx, lc)),
        Expr::Err(x, _) => format!("err({})", se(x, ctx, lc)),
    }
}

fn binop_name(op: &BinOp) -> &'static str {
    match op {
        BinOp::Add => "+",
        BinOp::Sub => "-",
        BinOp::Mul => "*",
        BinOp::Div => "/",
        BinOp::Mod => "%",
        BinOp::Eq => "==",
        BinOp::Ne => "!=",
        BinOp::Lt => "<",
        BinOp::Le => "<=",
        BinOp::Gt => ">",
        BinOp::Ge => ">=",
        BinOp::And => "and",
        BinOp::Or => "or",
    }
}

fn sorted(v: &[String]) -> Vec<String> {
    let mut x: Vec<String> = v.to_vec();
    x.sort();
    x
}

fn semantic_type(te: &TypeExpr) -> String {
    match te {
        TypeExpr::Prim(p) => ast::prim_name(p).to_string(),
        TypeExpr::Named(n) => n.clone(),
        TypeExpr::Vec(t) => format!("vec<{}>", semantic_type(t)),
        TypeExpr::Map(k, v) => format!("map<{}, {}>", semantic_type(k), semantic_type(v)),
        TypeExpr::Result(a, b) => format!("result<{}, {}>", semantic_type(a), semantic_type(b)),
    }
}

fn semantic_type_def(t: &ast::TypeDef) -> String {
    match &t.kind {
        ast::TypeKind::Record(fields) => format!(
            "record{{{}}}",
            fields
                .iter()
                .map(|(n, te)| format!("{n}:{}", semantic_type(te)))
                .collect::<Vec<_>>()
                .join(",")
        ),
        ast::TypeKind::Enum(vs) => format!("enum{{{}}}", sorted(vs).join(",")),
        ast::TypeKind::Alias(te) => format!("alias({})", semantic_type(te)),
    }
}

fn sha256(data: &str) -> String {
    let mut h = Sha256::new();
    h.update(data.as_bytes());
    h.finalize()
        .iter()
        .map(|b| format!("{b:02x}"))
        .collect::<String>()
}
