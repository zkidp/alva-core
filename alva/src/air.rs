//! AIR — Alva Intermediate Representation.
//!
//! The authoritative representation of an alva program is a typed program
//! graph (a Merkle DAG), NOT hand-written S-expression text:
//!
//! - every node has a stable content-addressed id (SHA-256 of its canonical
//!   encoding), independent of line/column/indentation/comments;
//! - node ids are Merkle: a node's id covers its own kind/fields and the ids
//!   of its named child slots, so unrelated edits never change ids;
//! - fields are typed values; slots are named child collections;
//! - `.alva` text is only an import format and a generated read-only
//!   projection; the AEP edit protocol operates on this graph.
//!
//! Deterministic serialization: the on-disk `.air` format is a length-prefixed
//! binary encoding (canonical ordering), and a deterministic JSON debug view is
//! produced on demand.

use crate::ast;
use crate::diag::json_escape;
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

pub const AIR_MAGIC: &[u8] = b"ALVA-AIR-1\n";

// AIR input hardening limits (adversarial files must fail cleanly).
pub const MAX_AIR_BYTES: usize = 64 * 1024 * 1024;
pub const MAX_AIR_NODES: usize = 1_000_000;
pub const MAX_AIR_STR_BYTES: usize = 16 * 1024 * 1024;
pub const MAX_AIR_FIELDS: usize = 256;
pub const MAX_AIR_SLOTS: usize = 256;
pub const MAX_AIR_DEPTH: usize = 4096;

// ---------------------------------------------------------------------------
// Values
// ---------------------------------------------------------------------------

#[derive(Clone, Debug, PartialEq)]
pub enum Value {
    Str(String),
    Int(i64),
    UInt(u64),
    Float(f64),
    Bool(bool),
    Bytes(Vec<u8>),
    Names(Vec<String>),
}

impl Value {
    fn tag(&self) -> u8 {
        match self {
            Value::Str(_) => 0x01,
            Value::Int(_) => 0x02,
            Value::UInt(_) => 0x03,
            Value::Float(_) => 0x04,
            Value::Bool(_) => 0x05,
            Value::Bytes(_) => 0x06,
            Value::Names(_) => 0x07,
        }
    }
}

// ---------------------------------------------------------------------------
// Nodes and graph
// ---------------------------------------------------------------------------

#[derive(Clone, Debug)]
pub struct AirNode {
    /// Merkle content hash of this node revision (kind + fields + child slot
    /// revision ids). Changes when the node's own content or any descendant
    /// changes. Edits produce new revisions; old revisions are retained
    /// (immutable history).
    pub revision: String,
    /// Stable, content-independent identity for named entities
    /// (e.g. "module:store.model", "module:store.model/fn:put_object").
    /// Anonymous expression nodes have an empty entity and are addressed by
    /// their revision only.
    pub entity: String,
    pub kind: String,
    pub fields: BTreeMap<String, Value>,
    pub slots: BTreeMap<String, Vec<String>>,
}

#[derive(Clone, Debug, Default)]
pub struct AirGraph {
    /// revision -> node (all historical revisions; content-addressed).
    pub nodes: BTreeMap<String, AirNode>,
    /// entity id -> current head revision.
    pub heads: BTreeMap<String, String>,
    /// module entity ids in project order.
    pub module_entities: Vec<String>,
}

/// Direct work performed by the current full-root revision rebuild. These
/// counters are execution measurements, not a claim of incremental behavior.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct RebuildStats {
    pub root_modules: usize,
    pub node_visits: usize,
    pub unique_nodes_visited: usize,
    pub rewritten_nodes: usize,
}

impl AirGraph {
    pub fn new() -> Self {
        AirGraph::default()
    }

    /// Compute the Merkle revision for a node's content.
    pub fn compute_revision(
        &self,
        kind: &str,
        fields: &BTreeMap<String, Value>,
        slots: &BTreeMap<String, Vec<String>>,
    ) -> String {
        let canonical = canonical_node(kind, fields, slots);
        hex(&Sha256::digest(&canonical))
    }

    /// Insert an immutable node revision (dedup by content). Returns the revision.
    pub fn add(
        &mut self,
        kind: &str,
        entity: &str,
        fields: BTreeMap<String, Value>,
        slots: BTreeMap<String, Vec<String>>,
    ) -> String {
        let revision = self.compute_revision(kind, &fields, &slots);
        if !self.nodes.contains_key(&revision) {
            self.nodes.insert(
                revision.clone(),
                AirNode {
                    revision: revision.clone(),
                    entity: entity.to_string(),
                    kind: kind.to_string(),
                    fields,
                    slots,
                },
            );
        }
        if !entity.is_empty() {
            self.heads.insert(entity.to_string(), revision.clone());
        }
        revision
    }

    /// Resolve a handle (entity id or revision) to a node.
    pub fn resolve(&self, handle: &str) -> Option<&AirNode> {
        if let Some(head) = self.heads.get(handle) {
            return self.nodes.get(head);
        }
        if handle.len() >= 6 {
            let mut hit: Option<&str> = None;
            for k in self.nodes.keys() {
                if k.starts_with(handle) {
                    if hit.is_some() {
                        return None; // ambiguous
                    }
                    hit = Some(k.as_str());
                }
            }
            if let Some(h) = hit {
                return self.nodes.get(h);
            }
        }
        self.nodes.get(handle)
    }

    /// Resolve a handle to its current head revision (entity) or itself.
    pub fn resolve_rev(&self, handle: &str) -> Option<String> {
        if let Some(head) = self.heads.get(handle) {
            return Some(head.clone());
        }
        if self.nodes.contains_key(handle) {
            return Some(handle.to_string());
        }
        // AEP 0.7: unambiguous prefix of a node revision (agents often pass
        // the short id shown in views).
        if handle.len() >= 6 {
            let mut hit: Option<String> = None;
            for k in self.nodes.keys() {
                if k.starts_with(handle) {
                    if hit.is_some() {
                        return None; // ambiguous
                    }
                    hit = Some(k.clone());
                }
            }
            if let Some(h) = hit {
                return Some(h);
            }
        }
        None
    }

    /// Whether a revision is reachable from any module head.
    pub fn is_reachable(&self, rev: &str) -> bool {
        let mut stack: Vec<String> = self.heads.values().cloned().collect();
        let mut seen = std::collections::HashSet::new();
        let mut guard = 0usize;
        while let Some(cur) = stack.pop() {
            if !seen.insert(cur.clone()) {
                continue;
            }
            if cur == rev {
                return true;
            }
            guard += 1;
            if guard > 1_000_000 {
                break;
            }
            if let Some(n) = self.nodes.get(&cur) {
                for children in n.slots.values() {
                    for c in children {
                        stack.push(c.clone());
                    }
                }
            }
        }
        false
    }

    pub fn get(&self, revision: &str) -> Option<&AirNode> {
        self.nodes.get(revision)
    }

    /// Project revision: hash of the ordered module head revisions.
    pub fn semantic_hash(&self) -> String {
        let mut buf = Vec::new();
        for m in &self.module_entities {
            if let Some(head) = self.heads.get(m) {
                buf.extend_from_slice(&id_bytes(head));
            }
        }
        hex(&Sha256::digest(&buf))
    }

    /// Immutable path-copy: recompute revisions bottom-up from the module heads
    /// after any structural edit. Content addressing keeps unchanged subtrees
    /// at identical revisions; only the edited node and its ancestors receive
    /// new revisions. Heads are updated for every named entity along the way.
    #[allow(dead_code)] // compatibility helper used by graph-level regressions
    pub fn rebuild_revisions(&mut self) {
        let _ = self.rebuild_revisions_with_stats();
    }

    /// Current measured implementation: walk every module root and recursively
    /// rebuild its reachable descendants. The returned counters make this
    /// baseline explicit before affected-subgraph optimization is attempted.
    pub fn rebuild_revisions_with_stats(&mut self) -> RebuildStats {
        let mut stats = RebuildStats::default();
        let mut unique = std::collections::BTreeSet::new();
        if !detect_cycles(self).is_empty() {
            return stats; // never recurse on a cyclic graph
        }
        let modules: Vec<String> = self.module_entities.clone();
        for m in modules {
            if let Some(head) = self.heads.get(&m).cloned() {
                stats.root_modules += 1;
                let new_rev = self.recompute_revision_measured(&head, &mut stats, &mut unique);
                self.heads.insert(m, new_rev);
            }
        }
        stats.unique_nodes_visited = unique.len();
        stats
    }

    fn recompute_revision_measured(
        &mut self,
        rev: &str,
        stats: &mut RebuildStats,
        unique: &mut std::collections::BTreeSet<String>,
    ) -> String {
        stats.node_visits += 1;
        unique.insert(rev.to_string());
        let Some(node) = self.nodes.get(rev).cloned() else {
            return rev.to_string();
        };
        let mut slots = node.slots.clone();
        for children in slots.values_mut() {
            for c in children.iter_mut() {
                let new_c = self.recompute_revision_measured(c, stats, unique);
                if &new_c != c {
                    *c = new_c;
                }
            }
        }
        let new_rev = self.compute_revision(&node.kind, &node.fields, &slots);
        let mut n = node;
        n.revision = new_rev.clone();
        n.slots = slots;
        if new_rev != rev {
            stats.rewritten_nodes += 1;
        }
        self.nodes.insert(new_rev.clone(), n);
        // content addressing: one revision may be shared by several entities
        // (e.g. identical params in different functions); move ALL heads that
        // pointed at the old revision to the new one.
        for (entity, head) in self.heads.clone() {
            if head == rev {
                self.heads.insert(entity, new_rev.clone());
            }
        }
        new_rev
    }

    /// Full integrity verification: every revision matches its content hash,
    /// every slot reference resolves, every entity head resolves, and every
    /// module entity has a head. Only revisions REACHABLE from the module
    /// heads are part of the current program and are checked (older revisions
    /// may exist in the session history).
    pub fn verify(&self) -> Vec<String> {
        let mut problems = Vec::new();
        for rev in self.reachable() {
            let Some(n) = self.nodes.get(&rev) else {
                problems.push(format!("E_AIR_DANGLING_CHILD: parent_rev={rev}"));
                continue;
            };
            let expect = self.compute_revision(&n.kind, &n.fields, &n.slots);
            if expect != rev {
                problems.push(format!("revision mismatch: {rev} (kind {})", n.kind));
            }
            for (slot, children) in &n.slots {
                for c in children {
                    if !self.nodes.contains_key(c) {
                        problems.push(format!(
                            "E_AIR_DANGLING_CHILD: parent_rev={rev} parent_entity={} slot={slot} child={c}",
                            n.entity
                        ));
                    }
                }
            }
        }
        for (entity, head) in &self.heads {
            if !self.nodes.contains_key(head) {
                problems.push(format!("head {entity} points at missing revision {head}"));
            }
        }
        for m in &self.module_entities {
            if !self.heads.contains_key(m) {
                problems.push(format!("module entity {m} has no head"));
            }
        }
        problems
    }

    /// Revisions reachable from the module heads (the current program).
    pub fn reachable(&self) -> std::collections::BTreeSet<String> {
        let mut out: std::collections::BTreeSet<String> = self
            .nodes
            .iter()
            .filter(|(_, n)| n.kind == "hole")
            .map(|(r, _)| r.clone())
            .collect();
        let mut stack: Vec<String> = self
            .module_entities
            .iter()
            .filter_map(|m| self.heads.get(m).cloned())
            .collect();
        while let Some(rev) = stack.pop() {
            if !out.insert(rev.clone()) {
                continue;
            }
            if let Some(n) = self.nodes.get(&rev) {
                for children in n.slots.values() {
                    for c in children {
                        stack.push(c.clone());
                    }
                }
            }
        }
        out
    }
}

/// Iterative white/gray/black DFS cycle detection over the reachable graph.
/// Returns cycle descriptions like "a -> b -> a". Shared DAGs (diamonds) are
/// not misreported. Safe on large graphs (no recursion).
pub fn detect_cycles(g: &AirGraph) -> Vec<String> {
    let mut state: BTreeMap<String, u8> = BTreeMap::new();
    let mut cycles = Vec::new();
    let roots: Vec<String> = g
        .module_entities
        .iter()
        .filter_map(|m| g.heads.get(m).cloned())
        .collect();
    let mut ri = 0;
    while ri < roots.len() {
        let root = roots[ri].clone();
        ri += 1;
        if state.get(&root) == Some(&2) {
            continue;
        }
        let mut stack: Vec<(String, usize)> = vec![(root.clone(), 0)];
        let mut path = vec![root.clone()];
        state.insert(root.clone(), 1);
        while let Some((node, idx)) = stack.last() {
            let node = node.clone();
            let children: Vec<String> = g
                .get(&node)
                .map(|n| n.slots.values().flatten().cloned().collect())
                .unwrap_or_default();
            if *idx >= children.len() {
                state.insert(node.clone(), 2);
                stack.pop();
                path.pop();
                continue;
            }
            let child = children[*idx].clone();
            let new_idx = *idx + 1;
            if let Some((_, idx_slot)) = stack.last_mut() {
                *idx_slot = new_idx;
            }
            match state.get(&child).copied() {
                Some(2) => {}
                Some(1) => {
                    let pos = path.iter().position(|p| p == &child).unwrap_or(0);
                    let mut s = path[pos..].join(" -> ");
                    s.push_str(&format!(" -> {child}"));
                    cycles.push(s);
                    // mark black so the same cycle is not reported repeatedly
                    state.insert(child.clone(), 2);
                }
                _ => {
                    state.insert(child.clone(), 1);
                    path.push(child.clone());
                    stack.push((child.clone(), 0));
                }
            }
        }
    }
    cycles
}

/// Iterative depth of the reachable graph (number of nodes on the longest
/// root-to-leaf path). Returns Err on cycles or when MAX_AIR_DEPTH is exceeded.
pub fn graph_depth(g: &AirGraph) -> Result<usize, String> {
    if !detect_cycles(g).is_empty() {
        return Err("E_AIR_CYCLE: cycle detected".to_string());
    }
    let mut depth: BTreeMap<String, usize> = BTreeMap::new();
    let mut order: Vec<String> = g
        .module_entities
        .iter()
        .filter_map(|m| g.heads.get(m).cloned())
        .collect();
    let mut i = 0;
    while i < order.len() {
        let node = order[i].clone();
        i += 1;
        let d = depth.get(&node).copied().unwrap_or(1);
        if d > MAX_AIR_DEPTH {
            return Err(format!("E_AIR_DEPTH: graph depth exceeds {MAX_AIR_DEPTH}"));
        }
        if let Some(n) = g.get(&node) {
            for children in n.slots.values() {
                for c in children {
                    let nd = d + 1;
                    let prev = depth.entry(c.clone()).or_insert(0);
                    if nd > *prev {
                        *prev = nd;
                        order.push(c.clone());
                    }
                }
            }
        }
    }
    Ok(depth.values().copied().max().unwrap_or(0))
}

// ---------------------------------------------------------------------------
// Canonical binary encoding (deterministic; used both for hashing and the
// on-disk .air format)
// ---------------------------------------------------------------------------

fn w_u8(out: &mut Vec<u8>, v: u8) {
    out.push(v);
}

fn w_u32(out: &mut Vec<u8>, v: u32) {
    out.extend_from_slice(&v.to_le_bytes());
}

fn w_u64(out: &mut Vec<u8>, v: u64) {
    out.extend_from_slice(&v.to_le_bytes());
}

fn w_i64(out: &mut Vec<u8>, v: i64) {
    out.extend_from_slice(&v.to_le_bytes());
}

fn w_str(out: &mut Vec<u8>, s: &str) {
    let b = s.as_bytes();
    w_u32(out, b.len() as u32);
    out.extend_from_slice(b);
}

fn w_value(out: &mut Vec<u8>, v: &Value) {
    w_u8(out, v.tag());
    match v {
        Value::Str(s) => w_str(out, s),
        Value::Int(i) => w_i64(out, *i),
        Value::UInt(u) => w_u64(out, *u),
        Value::Float(f) => out.extend_from_slice(&f.to_bits().to_le_bytes()),
        Value::Bool(b) => w_u8(out, if *b { 1 } else { 0 }),
        Value::Bytes(b) => {
            w_u32(out, b.len() as u32);
            out.extend_from_slice(b);
        }
        Value::Names(ns) => {
            w_u32(out, ns.len() as u32);
            for n in ns {
                w_str(out, n);
            }
        }
    }
}

fn canonical_node(
    kind: &str,
    fields: &BTreeMap<String, Value>,
    slots: &BTreeMap<String, Vec<String>>,
) -> Vec<u8> {
    let mut out = Vec::new();
    out.extend_from_slice(b"ALVANODE1");
    w_str(&mut out, kind);
    w_u32(&mut out, fields.len() as u32);
    for (k, v) in fields {
        w_str(&mut out, k);
        w_value(&mut out, v);
    }
    w_u32(&mut out, slots.len() as u32);
    for (name, children) in slots {
        w_str(&mut out, name);
        w_u32(&mut out, children.len() as u32);
        for c in children {
            out.extend_from_slice(&id_bytes(c));
        }
    }
    out
}

/// Public access to the deterministic canonical encoding (used by verify).
pub fn canonical_encoding(
    kind: &str,
    fields: &BTreeMap<String, Value>,
    slots: &BTreeMap<String, Vec<String>>,
) -> Vec<u8> {
    canonical_node(kind, fields, slots)
}

pub fn id_bytes(id: &str) -> [u8; 32] {
    let mut out = [0u8; 32];
    for (i, b) in id.as_bytes().chunks(2).take(32).enumerate() {
        if b.len() == 2 {
            if let Ok(v) = u8::from_str_radix(std::str::from_utf8(b).unwrap_or("00"), 16) {
                out[i] = v;
            }
        }
    }
    out
}

pub fn hex(bytes: &[u8]) -> String {
    let mut s = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        s.push_str(&format!("{b:02x}"));
    }
    s
}

// ---------------------------------------------------------------------------
// On-disk serialization
// ---------------------------------------------------------------------------

pub fn graph_to_bytes(g: &AirGraph) -> Vec<u8> {
    let mut out = Vec::new();
    out.extend_from_slice(AIR_MAGIC);
    let reachable = g.reachable();
    w_u32(&mut out, reachable.len() as u32);
    for rev in &reachable {
        let n = &g.nodes[rev];
        out.extend_from_slice(&id_bytes(&n.revision));
        w_str(&mut out, &n.entity);
        out.extend_from_slice(&canonical_node(&n.kind, &n.fields, &n.slots));
    }
    w_u32(&mut out, g.heads.len() as u32);
    for (entity, head) in &g.heads {
        w_str(&mut out, entity);
        out.extend_from_slice(&id_bytes(head));
    }
    w_u32(&mut out, g.module_entities.len() as u32);
    for m in &g.module_entities {
        w_str(&mut out, m);
    }
    out
}

pub fn graph_from_bytes(data: &[u8]) -> Result<AirGraph, String> {
    if !data.starts_with(AIR_MAGIC) {
        return Err("not an AIR file".to_string());
    }
    if data.len() > MAX_AIR_BYTES {
        return Err(format!(
            "E_AIR_INPUT: file too large ({} bytes, limit {MAX_AIR_BYTES})",
            data.len()
        ));
    }
    let mut pos = AIR_MAGIC.len();
    let read_u32 = |pos: &mut usize| -> Result<u32, String> {
        if *pos + 4 > data.len() {
            return Err("truncated AIR".to_string());
        }
        let mut b = [0u8; 4];
        b.copy_from_slice(&data[*pos..*pos + 4]);
        let v = u32::from_le_bytes(b);
        *pos += 4;
        Ok(v)
    };
    let read_str = |pos: &mut usize| -> Result<String, String> {
        let len = read_u32(pos)? as usize;
        if len > MAX_AIR_STR_BYTES {
            return Err(format!(
                "E_AIR_INPUT: string too large ({len} bytes, limit {MAX_AIR_STR_BYTES})"
            ));
        }
        if *pos + len > data.len() {
            return Err("truncated AIR string".to_string());
        }
        let s = String::from_utf8(data[*pos..*pos + len].to_vec())
            .map_err(|_| "E_AIR_INPUT: invalid UTF-8".to_string())?;
        *pos += len;
        Ok(s)
    };
    let count = read_u32(&mut pos)? as usize;
    if count > MAX_AIR_NODES {
        return Err(format!(
            "E_AIR_INPUT: too many nodes ({count}, limit {MAX_AIR_NODES})"
        ));
    }
    let mut g = AirGraph::new();
    for _ in 0..count {
        if pos + 32 > data.len() {
            return Err("truncated AIR node id".to_string());
        }
        let id = hex(&data[pos..pos + 32]);
        pos += 32;
        if g.nodes.contains_key(&id) {
            return Err(format!("E_AIR_INPUT: duplicate revision {id}"));
        }
        let entity = read_str(&mut pos)?;
        if !entity.is_empty() && g.heads.contains_key(&entity) {
            return Err(format!("E_AIR_INPUT: duplicate entity {entity}"));
        }
        if data[pos..].starts_with(b"ALVANODE1") {
            pos += "ALVANODE1".len();
        }
        let kind = read_str(&mut pos)?;
        let nfields = read_u32(&mut pos)? as usize;
        if nfields > MAX_AIR_FIELDS {
            return Err(format!(
                "E_AIR_INPUT: too many fields ({nfields}, limit {MAX_AIR_FIELDS})"
            ));
        }
        let mut fields = BTreeMap::new();
        for _ in 0..nfields {
            let k = read_str(&mut pos)?;
            if pos >= data.len() {
                return Err("truncated AIR value".to_string());
            }
            let tag = data[pos];
            pos += 1;
            let v = match tag {
                0x01 => Value::Str(read_str(&mut pos)?),
                0x02 => {
                    if pos + 8 > data.len() {
                        return Err("truncated AIR int".to_string());
                    }
                    let mut b = [0u8; 8];
                    b.copy_from_slice(&data[pos..pos + 8]);
                    let x = i64::from_le_bytes(b);
                    pos += 8;
                    Value::Int(x)
                }
                0x03 => {
                    if pos + 8 > data.len() {
                        return Err("truncated AIR uint".to_string());
                    }
                    let mut b = [0u8; 8];
                    b.copy_from_slice(&data[pos..pos + 8]);
                    let x = u64::from_le_bytes(b);
                    pos += 8;
                    Value::UInt(x)
                }
                0x04 => {
                    if pos + 8 > data.len() {
                        return Err("truncated AIR float".to_string());
                    }
                    let mut b = [0u8; 8];
                    b.copy_from_slice(&data[pos..pos + 8]);
                    let x = f64::from_bits(u64::from_le_bytes(b));
                    pos += 8;
                    Value::Float(x)
                }
                0x05 => {
                    let b = data[pos] != 0;
                    pos += 1;
                    Value::Bool(b)
                }
                0x06 => {
                    let len = read_u32(&mut pos)? as usize;
                    if len > MAX_AIR_STR_BYTES {
                        return Err(format!(
                            "E_AIR_INPUT: bytes too large ({len} bytes, limit {MAX_AIR_STR_BYTES})"
                        ));
                    }
                    if pos + len > data.len() {
                        return Err("truncated AIR bytes".to_string());
                    }
                    let b = data[pos..pos + len].to_vec();
                    pos += len;
                    Value::Bytes(b)
                }
                0x07 => {
                    let n = read_u32(&mut pos)? as usize;
                    let mut ns = Vec::with_capacity(n);
                    for _ in 0..n {
                        ns.push(read_str(&mut pos)?);
                    }
                    Value::Names(ns)
                }
                _ => return Err(format!("unknown AIR value tag {tag}")),
            };
            fields.insert(k, v);
        }
        let nslots = read_u32(&mut pos)? as usize;
        if nslots > MAX_AIR_SLOTS {
            return Err(format!(
                "E_AIR_INPUT: too many slots ({nslots}, limit {MAX_AIR_SLOTS})"
            ));
        }
        let mut slots = BTreeMap::new();
        for _ in 0..nslots {
            let name = read_str(&mut pos)?;
            let n = read_u32(&mut pos)? as usize;
            let mut children = Vec::with_capacity(n);
            for _ in 0..n {
                if pos + 32 > data.len() {
                    return Err("truncated AIR slot child".to_string());
                }
                children.push(hex(&data[pos..pos + 32]));
                pos += 32;
            }
            slots.insert(name, children);
        }
        g.nodes.insert(
            id.clone(),
            AirNode {
                revision: id,
                entity,
                kind,
                fields,
                slots,
            },
        );
    }
    let nheads = read_u32(&mut pos)? as usize;
    for _ in 0..nheads {
        let entity = read_str(&mut pos)?;
        if g.heads.contains_key(&entity) {
            return Err(format!("E_AIR_INPUT: duplicate head entity {entity}"));
        }
        if pos + 32 > data.len() {
            return Err("truncated AIR head".to_string());
        }
        g.heads.insert(entity, hex(&data[pos..pos + 32]));
        pos += 32;
    }
    let nmods = read_u32(&mut pos)? as usize;
    for _ in 0..nmods {
        let m = read_str(&mut pos)?;
        if g.module_entities.contains(&m) {
            return Err(format!("E_AIR_INPUT: duplicate module entity {m}"));
        }
        g.module_entities.push(m);
    }
    if pos != data.len() {
        return Err("E_AIR_INPUT: trailing garbage after AIR data".to_string());
    }
    // structural safety: cycles and depth are rejected before any consumer
    // (air_to_ast / rebuild) recurses over the graph.
    let cycles = detect_cycles(&g);
    if !cycles.is_empty() {
        return Err(format!("E_AIR_CYCLE: {}", cycles[0]));
    }
    graph_depth(&g)?;
    Ok(g)
}

// ---------------------------------------------------------------------------
// Authoritative project store: generation + atomic CURRENT pointer
// ---------------------------------------------------------------------------

pub const AIR_STORE_DIR: &str = "alva-air";

/// Cross-process exclusive lock for the authoritative store (lock-directory
/// mutex; atomic on both POSIX and Windows). Stale locks (older than 120s)
/// are broken so a crashed committer cannot wedge the store.
pub struct StoreLock {
    dir: PathBuf,
}

impl Drop for StoreLock {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir(&self.dir);
    }
}

pub fn acquire_store_lock(store: &Path) -> Result<StoreLock, String> {
    let lock = store.join("lock");
    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(60);
    loop {
        match std::fs::create_dir(&lock) {
            Ok(()) => return Ok(StoreLock { dir: lock }),
            Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => {
                if let Ok(meta) = std::fs::metadata(&lock) {
                    if let Ok(modified) = meta.modified() {
                        if modified.elapsed().unwrap_or_default()
                            > std::time::Duration::from_secs(120)
                        {
                            let _ = std::fs::remove_dir_all(&lock);
                            continue;
                        }
                    }
                }
                if std::time::Instant::now() > deadline {
                    return Err("E_AEP_LOCK_TIMEOUT: could not acquire store lock".to_string());
                }
                std::thread::sleep(std::time::Duration::from_millis(40));
            }
            Err(e) => return Err(e.to_string()),
        }
    }
}

fn fsync_dir(path: &Path) -> Result<(), String> {
    #[cfg(windows)]
    {
        use std::os::windows::ffi::OsStrExt;
        use std::ptr;
        const FILE_FLAG_BACKUP_SEMANTICS: u32 = 0x0200_0000;
        const GENERIC_WRITE: u32 = 0x4000_0000;
        const OPEN_EXISTING: u32 = 3;
        const INVALID_HANDLE_VALUE: isize = -1;
        #[link(name = "kernel32")]
        extern "system" {
            fn CreateFileW(
                lp_file_name: *const u16,
                dw_desired_access: u32,
                dw_share_mode: u32,
                lp_security_attributes: *mut std::ffi::c_void,
                dw_creation_disposition: u32,
                dw_flags_and_attributes: u32,
                h_template_file: *mut std::ffi::c_void,
            ) -> isize;
            fn FlushFileBuffers(h_file: isize) -> i32;
            fn CloseHandle(h_object: isize) -> i32;
        }
        let wide: Vec<u16> = path
            .as_os_str()
            .encode_wide()
            .chain(std::iter::once(0))
            .collect();
        let handle = unsafe {
            CreateFileW(
                wide.as_ptr(),
                GENERIC_WRITE,
                0,
                ptr::null_mut(),
                OPEN_EXISTING,
                FILE_FLAG_BACKUP_SEMANTICS,
                ptr::null_mut(),
            )
        };
        if handle == INVALID_HANDLE_VALUE {
            return Err(format!(
                "open dir {}: {}",
                path.display(),
                std::io::Error::last_os_error()
            ));
        }
        let ok = unsafe { FlushFileBuffers(handle) };
        unsafe { CloseHandle(handle) };
        if ok == 0 {
            return Err(format!(
                "flush dir {}: {}",
                path.display(),
                std::io::Error::last_os_error()
            ));
        }
        Ok(())
    }
    #[cfg(not(windows))]
    {
        std::fs::File::open(path)
            .and_then(|f| f.sync_all())
            .map_err(|e| format!("fsync dir {}: {e}", path.display()))
    }
}

/// Write the graph as a new generation and atomically advance the CURRENT
/// pointer, under the cross-process store lock. Returns the new generation.
pub fn write_authoritative(
    project_dir: &Path,
    g: &AirGraph,
    expected_base: Option<&str>,
) -> Result<u64, String> {
    let store = project_dir.join(AIR_STORE_DIR);
    std::fs::create_dir_all(&store).map_err(|e| e.to_string())?;
    let _lock = acquire_store_lock(&store)?;
    // inside the lock: re-read CURRENT, verify the base revision, then allocate
    // the generation (no TOCTOU between concurrent committers)
    let current_path = store.join("current");
    if let Some(base) = expected_base {
        if let Ok(current_text) = std::fs::read_to_string(&current_path) {
            let mut lines = current_text.lines();
            let _gen = lines.next();
            let cur_rev = lines.next().unwrap_or("").trim();
            if !cur_rev.is_empty() && cur_rev != base {
                return Err(format!(
                    "E_AEP_CONFLICT: authoritative revision {cur_rev} != base {base}"
                ));
            }
        }
    }
    let gen = read_generation(&current_path).unwrap_or(0) + 1;
    let data = graph_to_bytes(g);
    let gen_path = store.join(format!("gen-{gen}.air"));
    let tmp = store.join(format!("gen-{gen}.air.tmp"));
    {
        use std::io::Write;
        let mut f = std::fs::File::create(&tmp).map_err(|e| e.to_string())?;
        f.write_all(&data).map_err(|e| e.to_string())?;
        f.sync_all().map_err(|e| e.to_string())?;
    }
    std::fs::rename(&tmp, &gen_path).map_err(|e| e.to_string())?;
    fsync_dir(&store).map_err(|e| e.to_string())?;
    let rev = g.semantic_hash();
    let current_tmp = store.join("current.tmp");
    {
        use std::io::Write;
        let mut f = std::fs::File::create(&current_tmp).map_err(|e| e.to_string())?;
        f.write_all(format!("{gen}\n{rev}\n").as_bytes())
            .map_err(|e| e.to_string())?;
        f.sync_all().map_err(|e| e.to_string())?;
    }
    std::fs::rename(&current_tmp, &current_path).map_err(|e| e.to_string())?;
    fsync_dir(&store).map_err(|e| e.to_string())?;
    Ok(gen)
}

fn read_generation(current_path: &Path) -> Option<u64> {
    let text = std::fs::read_to_string(current_path).ok()?;
    text.lines().next()?.trim().parse().ok()
}

/// Load the authoritative graph: read CURRENT -> load the generation file.
pub fn load_authoritative(project_dir: &Path) -> Result<AirGraph, String> {
    let store = project_dir.join(AIR_STORE_DIR);
    let current_path = store.join("current");
    let text = std::fs::read_to_string(&current_path)
        .map_err(|e| format!("no authoritative store at {}: {e}", store.display()))?;
    let mut lines = text.lines();
    let gen = lines.next().ok_or("empty CURRENT")?.trim();
    let revision = lines.next().unwrap_or("").trim();
    let gen_path = store.join(format!("gen-{gen}.air"));
    let data =
        std::fs::read(&gen_path).map_err(|e| format!("cannot read generation {gen}: {e}"))?;
    let g = graph_from_bytes(&data)?;
    if !g.verify().is_empty() {
        return Err("authoritative AIR failed verification".to_string());
    }
    if !revision.is_empty() && g.semantic_hash() != revision {
        return Err("authoritative CURRENT revision does not match generation".to_string());
    }
    Ok(g)
}

// ---------------------------------------------------------------------------
// Type expression helpers
// ---------------------------------------------------------------------------

pub fn type_expr_to_air(g: &mut AirGraph, te: &ast::TypeExpr) -> String {
    match te {
        ast::TypeExpr::Prim(p) => {
            let mut f = BTreeMap::new();
            f.insert("shape".to_string(), Value::Str("prim".to_string()));
            f.insert(
                "name".to_string(),
                Value::Str(ast::prim_name(p).to_string()),
            );
            g.add("type_expr", "", f, BTreeMap::new())
        }
        ast::TypeExpr::Named(n) => {
            let mut f = BTreeMap::new();
            f.insert("shape".to_string(), Value::Str("named".to_string()));
            f.insert("name".to_string(), Value::Str(n.clone()));
            g.add("type_expr", "", f, BTreeMap::new())
        }
        ast::TypeExpr::Vec(t) => {
            let mut f = BTreeMap::new();
            f.insert("shape".to_string(), Value::Str("vec".to_string()));
            let mut s = BTreeMap::new();
            s.insert("inner".to_string(), vec![type_expr_to_air(g, t)]);
            g.add("type_expr", "", f, s)
        }
        ast::TypeExpr::Map(k, v) => {
            let mut f = BTreeMap::new();
            f.insert("shape".to_string(), Value::Str("map".to_string()));
            let mut s = BTreeMap::new();
            s.insert("key".to_string(), vec![type_expr_to_air(g, k)]);
            s.insert("value".to_string(), vec![type_expr_to_air(g, v)]);
            g.add("type_expr", "", f, s)
        }
        ast::TypeExpr::Result(a, b) => {
            let mut f = BTreeMap::new();
            f.insert("shape".to_string(), Value::Str("result".to_string()));
            let mut s = BTreeMap::new();
            s.insert("ok".to_string(), vec![type_expr_to_air(g, a)]);
            s.insert("err".to_string(), vec![type_expr_to_air(g, b)]);
            g.add("type_expr", "", f, s)
        }
    }
}

// ---------------------------------------------------------------------------
// AST -> AIR
// ---------------------------------------------------------------------------

fn lit(g: &mut AirGraph, kind: &str, value: Value) -> String {
    let mut f = BTreeMap::new();
    f.insert("value".to_string(), value);
    g.add(kind, "", f, BTreeMap::new())
}

fn expr_to_air(g: &mut AirGraph, e: &ast::Expr) -> String {
    match e {
        ast::Expr::Int(v, _) => lit(g, "literal", Value::Int(*v)),
        ast::Expr::UInt(v, _) => lit(g, "literal", Value::UInt(*v)),
        ast::Expr::Float(v, _) => lit(g, "literal", Value::Float(*v)),
        ast::Expr::Str(s, _) => lit(g, "literal", Value::Str(s.clone())),
        ast::Expr::Bool(b, _) => lit(g, "literal", Value::Bool(*b)),
        ast::Expr::Bytes(b, _) => lit(g, "literal", Value::Bytes(b.clone())),
        ast::Expr::Nil(_) => lit(g, "literal", Value::Str("nil".to_string())),
        ast::Expr::Ref(n, _) => {
            let mut f = BTreeMap::new();
            f.insert("name".to_string(), Value::Str(n.clone()));
            g.add("ref", "", f, BTreeMap::new())
        }
        ast::Expr::Call(name, args, _) => {
            let mut f = BTreeMap::new();
            f.insert("name".to_string(), Value::Str(name.clone()));
            let mut s = BTreeMap::new();
            s.insert(
                "args".to_string(),
                args.iter().map(|a| expr_to_air(g, a)).collect(),
            );
            g.add("call", "", f, s)
        }
        ast::Expr::Bin(op, a, b, _) => {
            let mut f = BTreeMap::new();
            f.insert("op".to_string(), Value::Str(binop_name(*op).to_string()));
            let mut s = BTreeMap::new();
            s.insert("left".to_string(), vec![expr_to_air(g, a)]);
            s.insert("right".to_string(), vec![expr_to_air(g, b)]);
            g.add("binary", "", f, s)
        }
        ast::Expr::Not(x, _) => unary(g, "not", x),
        ast::Expr::If(c, t, e2, _) => {
            let mut s = BTreeMap::new();
            s.insert("cond".to_string(), vec![expr_to_air(g, c)]);
            s.insert("then".to_string(), vec![expr_to_air(g, t)]);
            s.insert("else".to_string(), vec![expr_to_air(g, e2)]);
            g.add("if", "", BTreeMap::new(), s)
        }
        ast::Expr::Let(name, ty, value, body, _) => {
            let mut f = BTreeMap::new();
            f.insert("name".to_string(), Value::Str(name.clone()));
            let mut s = BTreeMap::new();
            if let Some(t) = ty {
                s.insert("type".to_string(), vec![type_expr_to_air(g, t)]);
            }
            s.insert("value".to_string(), vec![expr_to_air(g, value)]);
            s.insert("body".to_string(), vec![expr_to_air(g, body)]);
            g.add("binding", "", f, s)
        }
        ast::Expr::Block(stmts, _) => {
            let mut s = BTreeMap::new();
            s.insert(
                "steps".to_string(),
                stmts.iter().map(|x| expr_to_air(g, x)).collect(),
            );
            g.add("block", "", BTreeMap::new(), s)
        }
        ast::Expr::VecLit(t, items, _) => {
            let mut s = BTreeMap::new();
            s.insert("elem_type".to_string(), vec![type_expr_to_air(g, t)]);
            s.insert(
                "items".to_string(),
                items.iter().map(|x| expr_to_air(g, x)).collect(),
            );
            g.add("veclit", "", BTreeMap::new(), s)
        }
        ast::Expr::Len(x, _) => unary(g, "len", x),
        ast::Expr::Get(v, i, _) => binary(g, "get", v, i),
        ast::Expr::Append(v, x, _) => binary(g, "append", v, x),
        ast::Expr::As(t, x, _) => {
            let mut f = BTreeMap::new();
            f.insert("cast".to_string(), Value::Bool(true));
            let mut s = BTreeMap::new();
            s.insert("type".to_string(), vec![type_expr_to_air(g, t)]);
            s.insert("value".to_string(), vec![expr_to_air(g, x)]);
            g.add("as", "", f, s)
        }
        ast::Expr::Fold(idx, init, over, acc_name, acc_ty, acc_init, body, _) => {
            let mut f = BTreeMap::new();
            f.insert("index".to_string(), Value::Str(idx.clone()));
            f.insert("acc_name".to_string(), Value::Str(acc_name.clone()));
            let mut s = BTreeMap::new();
            s.insert("range_start".to_string(), vec![expr_to_air(g, init)]);
            s.insert("range_end".to_string(), vec![expr_to_air(g, over)]);
            s.insert("acc_type".to_string(), vec![type_expr_to_air(g, acc_ty)]);
            s.insert("acc_init".to_string(), vec![expr_to_air(g, acc_init)]);
            s.insert("body".to_string(), vec![expr_to_air(g, body)]);
            g.add("fold", "", f, s)
        }
        ast::Expr::Variant(ty, vname, _) => {
            let mut f = BTreeMap::new();
            f.insert("type".to_string(), Value::Str(ty.clone()));
            f.insert("variant".to_string(), Value::Str(vname.clone()));
            g.add("variant", "", f, BTreeMap::new())
        }
        ast::Expr::Match(ty, scrutinee, cases, _) => {
            let mut f = BTreeMap::new();
            f.insert("type".to_string(), Value::Str(ty.clone()));
            let mut s = BTreeMap::new();
            s.insert("scrutinee".to_string(), vec![expr_to_air(g, scrutinee)]);
            s.insert(
                "cases".to_string(),
                cases
                    .iter()
                    .map(|(v, e)| {
                        let mut cf = BTreeMap::new();
                        cf.insert("variant".to_string(), Value::Str(v.clone()));
                        let mut cs = BTreeMap::new();
                        cs.insert("body".to_string(), vec![expr_to_air(g, e)]);
                        g.add("case", "", cf, cs)
                    })
                    .collect(),
            );
            g.add("match", "", f, s)
        }
        ast::Expr::MapLit(kt, vt, pairs, _) => {
            let mut s = BTreeMap::new();
            s.insert("key_type".to_string(), vec![type_expr_to_air(g, kt)]);
            s.insert("value_type".to_string(), vec![type_expr_to_air(g, vt)]);
            s.insert(
                "pairs".to_string(),
                pairs
                    .iter()
                    .map(|(k, v)| {
                        let mut ps = BTreeMap::new();
                        ps.insert("key".to_string(), vec![expr_to_air(g, k)]);
                        ps.insert("value".to_string(), vec![expr_to_air(g, v)]);
                        g.add("pair", "", BTreeMap::new(), ps)
                    })
                    .collect(),
            );
            g.add("maplit", "", BTreeMap::new(), s)
        }
        ast::Expr::Set(m, k, v, _) => ternary(g, "set", m, k, v),
        ast::Expr::Lookup(m, k, _) => binary(g, "lookup", m, k),
        ast::Expr::Contains(m, k, _) => binary(g, "contains", m, k),
        ast::Expr::VecContains(v, x, _) => binary(g, "veccontains", v, x),
        ast::Expr::Any(ev, c, p, _) => {
            let mut f = BTreeMap::new();
            f.insert("elem_var".to_string(), Value::Str(ev.clone()));
            let mut s = BTreeMap::new();
            s.insert("collection".to_string(), vec![expr_to_air(g, c)]);
            s.insert("predicate".to_string(), vec![expr_to_air(g, p)]);
            g.add("any", "", f, s)
        }
        ast::Expr::All(ev, c, p, _) => {
            let mut f = BTreeMap::new();
            f.insert("elem_var".to_string(), Value::Str(ev.clone()));
            let mut s = BTreeMap::new();
            s.insert("collection".to_string(), vec![expr_to_air(g, c)]);
            s.insert("predicate".to_string(), vec![expr_to_air(g, p)]);
            g.add("all", "", f, s)
        }
        ast::Expr::Find(ev, c, p, _) => {
            let mut f = BTreeMap::new();
            f.insert("elem_var".to_string(), Value::Str(ev.clone()));
            let mut s = BTreeMap::new();
            s.insert("collection".to_string(), vec![expr_to_air(g, c)]);
            s.insert("predicate".to_string(), vec![expr_to_air(g, p)]);
            g.add("find", "", f, s)
        }
        ast::Expr::Remove(m, k, _) => binary(g, "remove", m, k),
        ast::Expr::Keys(m, _) => unary(g, "keys", m),
        ast::Expr::Unwrap(x, _) => unary(g, "unwrap", x),
        ast::Expr::ErrValue(x, _) => unary(g, "errvalue", x),
        ast::Expr::Slice(v, s, e2, _) => {
            let mut sl = BTreeMap::new();
            sl.insert("value".to_string(), vec![expr_to_air(g, v)]);
            sl.insert("start".to_string(), vec![expr_to_air(g, s)]);
            sl.insert("end".to_string(), vec![expr_to_air(g, e2)]);
            g.add("slice", "", BTreeMap::new(), sl)
        }
        ast::Expr::Split(a, b, _) => binary(g, "split", a, b),
        ast::Expr::Concat(a, b, _) => binary(g, "concat", a, b),
        ast::Expr::ToString(x, _) => unary(g, "tostring", x),
        ast::Expr::ParseInt(x, _) => unary(g, "parseint", x),
        ast::Expr::ToBytes(x, _) => unary(g, "tobytes", x),
        ast::Expr::IsOk(x, _) => unary(g, "isok", x),
        ast::Expr::Join(a, b, _) => binary(g, "join", a, b),
        ast::Expr::StripPrefix(a, b, _) => binary(g, "stripprefix", a, b),
        ast::Expr::Before(a, b, _) => binary(g, "before", a, b),
        ast::Expr::EndsWith(a, b, _) => binary(g, "endswith", a, b),
        ast::Expr::Sort(x, _) => unary(g, "sort", x),
        ast::Expr::UrlDecode(x, _) => unary(g, "urldecode", x),
        ast::Expr::ToHex(x, _) => unary(g, "tohex", x),
        ast::Expr::CtEq(a, b, _) => binary(g, "cteq", a, b),
        ast::Expr::Loop(acc_name, acc_ty, init, inv, cond, body, _) => {
            let mut f = BTreeMap::new();
            f.insert("acc_name".to_string(), Value::Str(acc_name.clone()));
            let mut s = BTreeMap::new();
            s.insert("acc_type".to_string(), vec![type_expr_to_air(g, acc_ty)]);
            s.insert("init".to_string(), vec![expr_to_air(g, init)]);
            if let Some(i) = inv {
                s.insert("inv".to_string(), vec![expr_to_air(g, i)]);
            }
            s.insert("cond".to_string(), vec![expr_to_air(g, cond)]);
            s.insert("body".to_string(), vec![expr_to_air(g, body)]);
            g.add("loop", "", f, s)
        }
        ast::Expr::Record(ty, fields, _) => {
            let mut f = BTreeMap::new();
            f.insert("type".to_string(), Value::Str(ty.clone()));
            let mut s = BTreeMap::new();
            s.insert(
                "fields".to_string(),
                fields
                    .iter()
                    .map(|(n, v)| {
                        let mut ff = BTreeMap::new();
                        ff.insert("name".to_string(), Value::Str(n.clone()));
                        let mut fs = BTreeMap::new();
                        fs.insert("value".to_string(), vec![expr_to_air(g, v)]);
                        g.add("record_field", "", ff, fs)
                    })
                    .collect(),
            );
            g.add("record", "", f, s)
        }
        ast::Expr::RecordUpdate(ty, base, updates, _) => {
            let mut f = BTreeMap::new();
            f.insert("type".to_string(), Value::Str(ty.clone()));
            let mut s = BTreeMap::new();
            s.insert("base".to_string(), vec![expr_to_air(g, base)]);
            s.insert(
                "updates".to_string(),
                updates
                    .iter()
                    .map(|(n, v)| {
                        let mut ff = BTreeMap::new();
                        ff.insert("name".to_string(), Value::Str(n.clone()));
                        let mut fs = BTreeMap::new();
                        fs.insert("value".to_string(), vec![expr_to_air(g, v)]);
                        g.add("update_field", "", ff, fs)
                    })
                    .collect(),
            );
            g.add("record_update", "", f, s)
        }
        ast::Expr::Field(x, name, _) => {
            let mut f = BTreeMap::new();
            f.insert("name".to_string(), Value::Str(name.clone()));
            let mut s = BTreeMap::new();
            s.insert("value".to_string(), vec![expr_to_air(g, x)]);
            g.add("field", "", f, s)
        }
        ast::Expr::Raise(x, _) => {
            let mut s = BTreeMap::new();
            s.insert("value".to_string(), vec![expr_to_air(g, x)]);
            g.add("raise", "", BTreeMap::new(), s)
        }
        ast::Expr::Try(x, name, body, _) => {
            let mut f = BTreeMap::new();
            f.insert("catch_name".to_string(), Value::Str(name.clone()));
            let mut s = BTreeMap::new();
            s.insert("value".to_string(), vec![expr_to_air(g, x)]);
            s.insert("catch".to_string(), vec![expr_to_air(g, body)]);
            g.add("try", "", f, s)
        }
        ast::Expr::Ok(x, _) => {
            let mut s = BTreeMap::new();
            s.insert("value".to_string(), vec![expr_to_air(g, x)]);
            g.add("ok", "", BTreeMap::new(), s)
        }
        ast::Expr::Err(x, _) => {
            let mut s = BTreeMap::new();
            s.insert("value".to_string(), vec![expr_to_air(g, x)]);
            g.add("err", "", BTreeMap::new(), s)
        }
    }
}

fn unary(g: &mut AirGraph, tag: &str, x: &ast::Expr) -> String {
    let mut s = BTreeMap::new();
    s.insert("value".to_string(), vec![expr_to_air(g, x)]);
    g.add(tag, "", BTreeMap::new(), s)
}

fn binary(g: &mut AirGraph, tag: &str, a: &ast::Expr, b: &ast::Expr) -> String {
    let mut s = BTreeMap::new();
    s.insert("left".to_string(), vec![expr_to_air(g, a)]);
    s.insert("right".to_string(), vec![expr_to_air(g, b)]);
    g.add(tag, "", BTreeMap::new(), s)
}

fn ternary(g: &mut AirGraph, tag: &str, a: &ast::Expr, b: &ast::Expr, c: &ast::Expr) -> String {
    let mut s = BTreeMap::new();
    s.insert("a".to_string(), vec![expr_to_air(g, a)]);
    s.insert("b".to_string(), vec![expr_to_air(g, b)]);
    s.insert("c".to_string(), vec![expr_to_air(g, c)]);
    g.add(tag, "", BTreeMap::new(), s)
}

fn binop_name(op: ast::BinOp) -> &'static str {
    match op {
        ast::BinOp::Add => "+",
        ast::BinOp::Sub => "-",
        ast::BinOp::Mul => "*",
        ast::BinOp::Div => "/",
        ast::BinOp::Mod => "mod",
        ast::BinOp::Eq => "==",
        ast::BinOp::Ne => "!=",
        ast::BinOp::Lt => "<",
        ast::BinOp::Le => "<=",
        ast::BinOp::Gt => ">",
        ast::BinOp::Ge => ">=",
        ast::BinOp::And => "and",
        ast::BinOp::Or => "or",
    }
}

pub fn air_from_module(module: &ast::Module) -> AirGraph {
    let mut g = AirGraph::new();
    let module_entity = format!("module:{}", module.name);
    let mut module_fields = BTreeMap::new();
    module_fields.insert("name".to_string(), Value::Str(module.name.clone()));
    module_fields.insert("version".to_string(), Value::Str(module.version.clone()));
    module_fields.insert("caps".to_string(), Value::Names(module.caps.clone()));
    module_fields.insert("exports".to_string(), Value::Names(module.exports.clone()));
    module_fields.insert(
        "rust_deps".to_string(),
        Value::Names(
            module
                .rust_deps
                .iter()
                .map(|(c, v)| format!("{c}@{v}"))
                .collect(),
        ),
    );
    module_fields.insert(
        "deps".to_string(),
        Value::Names(
            module
                .deps
                .iter()
                .map(|(n, v)| format!("{n}@{v}"))
                .collect(),
        ),
    );
    let mut module_slots = BTreeMap::new();
    module_slots.insert(
        "types".to_string(),
        module
            .types
            .iter()
            .map(|t| type_to_air(&mut g, &module_entity, t))
            .collect(),
    );
    module_slots.insert(
        "functions".to_string(),
        module
            .fns
            .iter()
            .map(|f| fn_to_air(&mut g, &module_entity, f))
            .collect(),
    );
    module_slots.insert(
        "externs".to_string(),
        module
            .exts
            .iter()
            .map(|e| extern_to_air(&mut g, &module_entity, e))
            .collect(),
    );
    module_slots.insert(
        "tests".to_string(),
        module
            .tests
            .iter()
            .map(|t| {
                let mut f = BTreeMap::new();
                f.insert("name".to_string(), Value::Str(t.name.clone()));
                let mut s = BTreeMap::new();
                s.insert("body".to_string(), vec![expr_to_air(&mut g, &t.body)]);
                g.add("test", &format!("{module_entity}/test:{}", t.name), f, s)
            })
            .collect(),
    );
    module_slots.insert(
        "benches".to_string(),
        module
            .benches
            .iter()
            .map(|b| {
                let mut f = BTreeMap::new();
                f.insert("name".to_string(), Value::Str(b.name.clone()));
                if let Some(ms) = b.ms_budget {
                    f.insert("ms_budget".to_string(), Value::Int(ms));
                }
                let mut s = BTreeMap::new();
                s.insert(
                    "setup".to_string(),
                    b.setup.iter().map(|e| expr_to_air(&mut g, e)).collect(),
                );
                s.insert("body".to_string(), vec![expr_to_air(&mut g, &b.body)]);
                g.add("bench", &format!("{module_entity}/bench:{}", b.name), f, s)
            })
            .collect(),
    );
    let _root = g.add("module", &module_entity, module_fields, module_slots);
    g.module_entities.push(module_entity);
    g
}

fn type_to_air(g: &mut AirGraph, module_entity: &str, t: &ast::TypeDef) -> String {
    let mut f = BTreeMap::new();
    f.insert("name".to_string(), Value::Str(t.name.clone()));
    let entity = format!("{module_entity}/type:{}", t.name);
    let mut s = BTreeMap::new();
    match &t.kind {
        ast::TypeKind::Record(fields) => {
            f.insert("kind".to_string(), Value::Str("record".to_string()));
            s.insert(
                "fields".to_string(),
                fields
                    .iter()
                    .map(|(n, te)| {
                        let mut ff = BTreeMap::new();
                        ff.insert("name".to_string(), Value::Str(n.clone()));
                        let mut fs = BTreeMap::new();
                        fs.insert("type".to_string(), vec![type_expr_to_air(g, te)]);
                        g.add("type_field", &format!("{entity}/field:{}", n), ff, fs)
                    })
                    .collect(),
            );
        }
        ast::TypeKind::Enum(variants) => {
            f.insert("kind".to_string(), Value::Str("enum".to_string()));
            f.insert("variants".to_string(), Value::Names(variants.clone()));
        }
        ast::TypeKind::Alias(te) => {
            f.insert("kind".to_string(), Value::Str("alias".to_string()));
            s.insert("alias".to_string(), vec![type_expr_to_air(g, te)]);
        }
    }
    g.add("type", &entity, f, s)
}

fn fn_to_air(g: &mut AirGraph, module_entity: &str, f: &ast::FnDef) -> String {
    let entity = format!("{module_entity}/fn:{}", f.name);
    let mut fields = BTreeMap::new();
    fields.insert("name".to_string(), Value::Str(f.name.clone()));
    fields.insert("pure".to_string(), Value::Bool(f.pure));
    fields.insert("eff".to_string(), Value::Names(f.eff.clone()));
    let mut slots = BTreeMap::new();
    slots.insert(
        "params".to_string(),
        f.params
            .iter()
            .map(|(n, te)| {
                let mut pf = BTreeMap::new();
                pf.insert("name".to_string(), Value::Str(n.clone()));
                let mut ps = BTreeMap::new();
                ps.insert("type".to_string(), vec![type_expr_to_air(g, te)]);
                g.add("param", &format!("{entity}/param:{}", n), pf, ps)
            })
            .collect(),
    );
    slots.insert("returns".to_string(), vec![type_expr_to_air(g, &f.returns)]);
    slots.insert(
        "pre".to_string(),
        f.pre.iter().map(|e| contract_to_air(g, "pre", e)).collect(),
    );
    slots.insert(
        "post".to_string(),
        f.post
            .iter()
            .map(|e| contract_to_air(g, "post", e))
            .collect(),
    );
    slots.insert(
        "inv".to_string(),
        f.inv.iter().map(|e| contract_to_air(g, "inv", e)).collect(),
    );
    slots.insert(
        "body".to_string(),
        vec![{
            let mut s = BTreeMap::new();
            s.insert(
                "steps".to_string(),
                f.body.iter().map(|e| expr_to_air(g, e)).collect(),
            );
            g.add("block", "", BTreeMap::new(), s)
        }],
    );
    g.add("function", &entity, fields, slots)
}

fn contract_to_air(g: &mut AirGraph, kind: &str, e: &ast::Expr) -> String {
    let mut s = BTreeMap::new();
    s.insert("expr".to_string(), vec![expr_to_air(g, e)]);
    g.add(
        "contract",
        "",
        BTreeMap::from([("kind".to_string(), Value::Str(kind.to_string()))]),
        s,
    )
}

fn extern_to_air(g: &mut AirGraph, module_entity: &str, e: &ast::ExternDef) -> String {
    let entity = format!("{module_entity}/extern:{}", e.name);
    let mut fields = BTreeMap::new();
    fields.insert("name".to_string(), Value::Str(e.name.clone()));
    fields.insert("pure".to_string(), Value::Bool(e.pure));
    fields.insert("unsafe".to_string(), Value::Bool(e.unsafe_ffi));
    fields.insert("eff".to_string(), Value::Names(e.eff.clone()));
    fields.insert("template".to_string(), Value::Str(e.template.clone()));
    let mut slots = BTreeMap::new();
    slots.insert(
        "params".to_string(),
        e.params
            .iter()
            .map(|(n, te)| {
                let mut pf = BTreeMap::new();
                pf.insert("name".to_string(), Value::Str(n.clone()));
                let mut ps = BTreeMap::new();
                ps.insert("type".to_string(), vec![type_expr_to_air(g, te)]);
                g.add("param", &format!("{entity}/param:{}", n), pf, ps)
            })
            .collect(),
    );
    slots.insert("returns".to_string(), vec![type_expr_to_air(g, &e.returns)]);
    g.add("extern", &entity, fields, slots)
}

// ---------------------------------------------------------------------------
// AIR -> canonical S-expression projection (read-only)
// ---------------------------------------------------------------------------

fn type_air_to_sexpr(g: &AirGraph, id: &str) -> String {
    let n = match g.get(id) {
        Some(n) => n,
        None => return format!("?type:{id}"),
    };
    let shape = field_str(n, "shape");
    match shape.as_str() {
        "prim" => format!("(prim {})", field_str(n, "name")),
        "named" => field_str(n, "name"),
        "vec" => format!("(vec {})", type_child_str(g, n, "inner")),
        "map" => format!(
            "(map {} {})",
            type_child_str(g, n, "key"),
            type_child_str(g, n, "value")
        ),
        "result" => format!(
            "(result {} {})",
            type_child_str(g, n, "ok"),
            type_child_str(g, n, "err")
        ),
        _ => "?type".to_string(),
    }
}

fn type_child_str(g: &AirGraph, n: &AirNode, slot: &str) -> String {
    match n.slots.get(slot).and_then(|c| c.first()) {
        Some(id) => type_air_to_sexpr(g, id),
        None => String::new(),
    }
}

fn expr_air_to_sexpr(g: &AirGraph, id: &str) -> String {
    let n = match g.get(id) {
        Some(n) => n,
        None => return format!("?expr:{id}"),
    };
    let tag = n.kind.as_str();
    match tag {
        "literal" => {
            let v = n
                .fields
                .get("value")
                .cloned()
                .unwrap_or(Value::Str("nil".to_string()));
            match v {
                Value::Str(s) if s == "nil" => "(nil)".to_string(),
                Value::Str(s) => format!("(string {})", quote(&s)),
                Value::Int(i) => format!("(int {i})"),
                Value::UInt(u) => format!("(uint {u})"),
                Value::Float(x) => format!("(float {x})"),
                Value::Bool(b) => format!("(bool {b})"),
                Value::Bytes(b) => format!(
                    "(bytes {})",
                    b.iter().map(|x| format!("{x:02x}")).collect::<String>()
                ),
                Value::Names(_) => "(nil)".to_string(),
            }
        }
        "ref" => format!("(ref {})", field_str(n, "name")),
        "call" => {
            let args = slot_children(g, n, "args");
            format!(
                "(call {} {})",
                field_str(n, "name"),
                args.iter()
                    .map(|c| expr_air_to_sexpr(g, c))
                    .collect::<Vec<_>>()
                    .join(" ")
            )
        }
        "binary" => format!(
            "({} {} {})",
            field_str(n, "op"),
            expr_air_to_sexpr(g, &n.slots["left"][0]),
            expr_air_to_sexpr(g, &n.slots["right"][0])
        ),
        "not" => format!("(not {})", unary_child(g, n)),
        "if" => format!(
            "(if {} {} {})",
            child_str(g, n, "cond"),
            child_str(g, n, "then"),
            child_str(g, n, "else")
        ),
        "binding" => {
            let ty = n.slots.get("type").map(|t| t[0].clone());
            let ty_s = match ty {
                Some(t) => format!(" {} ", type_air_to_sexpr(g, &t)),
                None => " ".to_string(),
            };
            format!(
                "(let {}{} {} {})",
                field_str(n, "name"),
                ty_s,
                child_str(g, n, "value"),
                child_str(g, n, "body")
            )
        }
        "block" => {
            let steps = slot_children(g, n, "steps");
            format!(
                "(block {})",
                steps
                    .iter()
                    .map(|c| expr_air_to_sexpr(g, c))
                    .collect::<Vec<_>>()
                    .join(" ")
            )
        }
        "veclit" => format!(
            "(vec {} {})",
            type_child_str(g, n, "elem_type"),
            slot_children(g, n, "items")
                .iter()
                .map(|c| expr_air_to_sexpr(g, c))
                .collect::<Vec<_>>()
                .join(" ")
        ),
        "len" | "keys" | "unwrap" | "errvalue" | "tostring" | "parseint" | "tobytes" | "isok"
        | "sort" | "urldecode" | "tohex" => format!(
            "({} {})",
            tag.replace("tostring", "to-string")
                .replace("parseint", "parse-int")
                .replace("tobytes", "to-bytes")
                .replace("isok", "is-ok")
                .replace("urldecode", "url-decode")
                .replace("tohex", "to-hex")
                .replace("errvalue", "err-value"),
            unary_child(g, n)
        ),
        "get" | "append" | "lookup" | "contains" | "remove" | "split" | "concat" | "join"
        | "stripprefix" | "before" | "endswith" | "cteq" | "veccontains" => {
            // RFC-0003: 裸 (contains ...) 是 vec 元素 contains；AIR tag "contains"
            // 是 map key contains（旧语义），投影必须写成 (call contains m k)
            // 才能被新 parser 读回 map contains，避免 round-trip 语义漂移。
            if tag == "contains" {
                return format!(
                    "(call contains {} {})",
                    child_str(g, n, "left"),
                    child_str(g, n, "right")
                );
            }
            let name = match tag {
                "stripprefix" => "strip-prefix",
                "endswith" => "ends-with",
                "cteq" => "ct-eq",
                "veccontains" => "contains",
                other => other,
            };
            format!(
                "({} {} {})",
                name,
                child_str(g, n, "left"),
                child_str(g, n, "right")
            )
        }
        "any" | "all" | "find" => format!(
            "({} {} {} {})",
            tag,
            field_str(n, "elem_var"),
            child_str(g, n, "collection"),
            child_str(g, n, "predicate")
        ),
        "slice" => format!(
            "(slice {} {} {})",
            child_str(g, n, "value"),
            child_str(g, n, "start"),
            child_str(g, n, "end")
        ),
        "set" => format!(
            "(set {} {} {})",
            child_str(g, n, "a"),
            child_str(g, n, "b"),
            child_str(g, n, "c")
        ),
        "as" => format!(
            "(as {} {})",
            type_child_str(g, n, "type"),
            child_str(g, n, "value")
        ),
        "fold" => format!(
            "(fold {} (range {} {}) (acc {} {} {}) {})",
            field_str(n, "index"),
            child_str(g, n, "range_start"),
            child_str(g, n, "range_end"),
            field_str(n, "acc_name"),
            type_child_str(g, n, "acc_type"),
            child_str(g, n, "acc_init"),
            child_str(g, n, "body")
        ),
        "variant" => format!(
            "(variant {} {})",
            field_str(n, "type"),
            field_str(n, "variant")
        ),
        "match" => {
            let cases = slot_children(g, n, "cases");
            format!(
                "(match {} {} {})",
                field_str(n, "type"),
                child_str(g, n, "scrutinee"),
                cases
                    .iter()
                    .map(|c| {
                        let cn = g.get(c).unwrap();
                        format!(
                            "(case {} {})",
                            field_str(cn, "variant"),
                            expr_air_to_sexpr(g, &cn.slots["body"][0])
                        )
                    })
                    .collect::<Vec<_>>()
                    .join(" ")
            )
        }
        "maplit" => {
            let pairs = slot_children(g, n, "pairs");
            format!(
                "(map {} {} {})",
                type_child_str(g, n, "key_type"),
                type_child_str(g, n, "value_type"),
                pairs
                    .iter()
                    .map(|p| {
                        let pn = g.get(p).unwrap();
                        format!(
                            "(entry {} {})",
                            expr_air_to_sexpr(g, &pn.slots["key"][0]),
                            expr_air_to_sexpr(g, &pn.slots["value"][0])
                        )
                    })
                    .collect::<Vec<_>>()
                    .join(" ")
            )
        }
        "record" => {
            let fields = slot_children(g, n, "fields");
            format!(
                "(record {} {})",
                field_str(n, "type"),
                fields
                    .iter()
                    .map(|f| {
                        let fn_ = g.get(f).unwrap();
                        format!(
                            "({} {})",
                            field_str(fn_, "name"),
                            expr_air_to_sexpr(g, &fn_.slots["value"][0])
                        )
                    })
                    .collect::<Vec<_>>()
                    .join(" ")
            )
        }
        "record_update" => {
            let base = &n.slots["base"][0];
            let updates = slot_children(g, n, "updates");
            format!(
                "(record-update {} {} {})",
                field_str(n, "type"),
                expr_air_to_sexpr(g, base),
                updates
                    .iter()
                    .map(|f| {
                        let fn_ = g.get(f).unwrap();
                        format!(
                            "({} {})",
                            field_str(fn_, "name"),
                            expr_air_to_sexpr(g, &fn_.slots["value"][0])
                        )
                    })
                    .collect::<Vec<_>>()
                    .join(" ")
            )
        }
        "field" => format!(
            "(field {} {})",
            expr_air_to_sexpr(g, &n.slots["value"][0]),
            quote(&field_str(n, "name"))
        ),
        "raise" => format!("(raise {})", child_str(g, n, "value")),
        "try" => format!(
            "(try {} (catch {} {}))",
            child_str(g, n, "value"),
            field_str(n, "catch_name"),
            child_str(g, n, "catch")
        ),
        "ok" => format!("(ok {})", child_str(g, n, "value")),
        "err" => format!("(err {})", child_str(g, n, "value")),
        "loop" => {
            let inv = n.slots.get("inv").map(|i| expr_air_to_sexpr(g, &i[0]));
            match inv {
                Some(i) => format!(
                    "(loop (acc {} {} {}) (inv {}) {} {})",
                    field_str(n, "acc_name"),
                    type_child_str(g, n, "acc_type"),
                    child_str(g, n, "init"),
                    i,
                    child_str(g, n, "cond"),
                    child_str(g, n, "body")
                ),
                None => format!(
                    "(loop (acc {} {} {}) {} {})",
                    field_str(n, "acc_name"),
                    type_child_str(g, n, "acc_type"),
                    child_str(g, n, "init"),
                    child_str(g, n, "cond"),
                    child_str(g, n, "body")
                ),
            }
        }
        "hole" => format!("(hole {})", field_str(n, "hole_id")),
        other => format!("?node:{other}"),
    }
}

fn field_str(n: &AirNode, name: &str) -> String {
    match n.fields.get(name) {
        Some(Value::Str(s)) => s.clone(),
        Some(Value::Int(i)) => i.to_string(),
        Some(Value::UInt(u)) => u.to_string(),
        Some(Value::Float(x)) => x.to_string(),
        Some(Value::Bool(b)) => b.to_string(),
        Some(Value::Names(ns)) => ns.join(" "),
        _ => String::new(),
    }
}

fn child_str(g: &AirGraph, n: &AirNode, slot: &str) -> String {
    match n.slots.get(slot).and_then(|c| c.first()) {
        Some(id) => expr_air_to_sexpr(g, id),
        None => String::new(),
    }
}

fn unary_child(g: &AirGraph, n: &AirNode) -> String {
    child_str(g, n, "value")
}

fn slot_children(_g: &AirGraph, n: &AirNode, slot: &str) -> Vec<String> {
    n.slots.get(slot).cloned().unwrap_or_default()
}

fn quote(s: &str) -> String {
    format!("\"{}\"", s.replace('\\', "\\\\").replace('"', "\\\""))
}

pub fn module_to_sexpr(g: &AirGraph, module_id: &str) -> String {
    let n = match g.get(module_id) {
        Some(n) => n,
        None => return String::new(),
    };
    let mut out = String::new();
    out.push_str("(module\n");
    out.push_str(&format!("  (name \"{}\")\n", field_str(n, "name")));
    out.push_str(&format!("  (version \"{}\")\n", field_str(n, "version")));
    if let Some(Value::Names(deps)) = n.fields.get("deps") {
        for d in deps {
            if let Some((name, ver)) = d.split_once('@') {
                out.push_str(&format!("  (dep \"{name}\" \"{ver}\")\n"));
            }
        }
    }
    if let Some(Value::Names(deps)) = n.fields.get("rust_deps") {
        for d in deps {
            if let Some((name, ver)) = d.split_once('@') {
                out.push_str(&format!("  (use rust \"{name}\" \"{ver}\")\n"));
            }
        }
    }
    if let Some(Value::Names(caps)) = n.fields.get("caps") {
        if !caps.is_empty() {
            out.push_str(&format!("  (cap {})\n", caps.join(" ")));
        }
    }
    if let Some(Value::Names(exports)) = n.fields.get("exports") {
        if !exports.is_empty() {
            out.push_str(&format!("  (export {})\n", exports.join(" ")));
        }
    }
    for slot in ["types", "externs"] {
        if let Some(ids) = n.slots.get(slot) {
            for id in ids {
                out.push_str(&format!("{}\n", node_to_sexpr(g, id)));
            }
        }
    }
    if let Some(ids) = n.slots.get("functions") {
        for id in ids {
            out.push_str(&format!("{}\n", node_to_sexpr(g, id)));
        }
    }
    for slot in ["tests", "benches"] {
        if let Some(ids) = n.slots.get(slot) {
            for id in ids {
                out.push_str(&format!("{}\n", node_to_sexpr(g, id)));
            }
        }
    }
    out.push_str(")\n");
    out
}

fn node_to_sexpr(g: &AirGraph, id: &str) -> String {
    let n = match g.get(id) {
        Some(n) => n,
        None => return String::new(),
    };
    match n.kind.as_str() {
        "type" => {
            let kind = field_str(n, "kind");
            match kind.as_str() {
                "record" => {
                    let fields = slot_children(g, n, "fields");
                    format!(
                        "  (type {} (record\n{}  ))\n",
                        field_str(n, "name"),
                        fields
                            .iter()
                            .map(|f| {
                                let fn_ = g.get(f).unwrap();
                                format!(
                                    "    (field {} {})",
                                    field_str(fn_, "name"),
                                    type_air_to_sexpr(g, &fn_.slots["type"][0])
                                )
                            })
                            .collect::<Vec<_>>()
                            .join("\n")
                    )
                }
                "enum" => format!(
                    "  (type {} (enum {}))\n",
                    field_str(n, "name"),
                    n.fields
                        .get("variants")
                        .map(|v| match v {
                            Value::Names(ns) => ns.join(" "),
                            _ => String::new(),
                        })
                        .unwrap_or_default()
                ),
                "alias" => format!(
                    "  (type {} (alias {}))\n",
                    field_str(n, "name"),
                    child_str(g, n, "alias")
                ),
                _ => String::new(),
            }
        }
        "extern" => {
            let params = slot_children(g, n, "params");
            let mut p = String::new();
            if !params.is_empty() {
                p.push_str("    (params\n");
                for x in params {
                    let pn = g.get(&x).unwrap();
                    p.push_str(&format!(
                        "      (param {} {})\n",
                        field_str(pn, "name"),
                        type_air_to_sexpr(g, &pn.slots["type"][0])
                    ));
                }
                p.push_str("    )\n");
            } else {
                p.push_str("    (params)\n");
            }
            let eff = n
                .fields
                .get("eff")
                .map(|v| match v {
                    Value::Names(ns) => ns.join(" "),
                    _ => String::new(),
                })
                .unwrap_or_default();
            let pure = n
                .fields
                .get("pure")
                .map(|v| v == &Value::Bool(true))
                .unwrap_or(false);
            let unsafe_ = n
                .fields
                .get("unsafe")
                .map(|v| v == &Value::Bool(true))
                .unwrap_or(false);
            let mut body = String::new();
            if pure {
                body.push_str("    (pure)\n");
            } else if !eff.is_empty() {
                body.push_str(&format!("    (eff {eff})\n"));
            }
            if unsafe_ {
                body.push_str("    (unsafe)\n");
            }
            body.push_str(&format!(
                "    (rust \"{}\")\n",
                field_str(n, "template")
                    .replace('\\', "\\\\")
                    .replace('"', "\\\"")
            ));
            format!(
                "  (extern {}\n{}    (returns {})\n{})",
                field_str(n, "name"),
                p,
                type_air_to_sexpr(g, &n.slots["returns"][0]),
                body
            )
        }
        "function" => {
            let params = slot_children(g, n, "params");
            let mut p = String::new();
            if !params.is_empty() {
                p.push_str("    (params\n");
                for x in params {
                    let pn = g.get(&x).unwrap();
                    p.push_str(&format!(
                        "      (param {} {})\n",
                        field_str(pn, "name"),
                        type_air_to_sexpr(g, &pn.slots["type"][0])
                    ));
                }
                p.push_str("    )\n");
            } else {
                p.push_str("    (params)\n");
            }
            let eff = n
                .fields
                .get("eff")
                .map(|v| match v {
                    Value::Names(ns) => ns.join(" "),
                    _ => String::new(),
                })
                .unwrap_or_default();
            let pure = n
                .fields
                .get("pure")
                .map(|v| v == &Value::Bool(true))
                .unwrap_or(false);
            let mut head = format!(
                "  (fn {}\n{}    (returns {})\n",
                field_str(n, "name"),
                p,
                type_air_to_sexpr(g, &n.slots["returns"][0])
            );
            if pure {
                head.push_str("    (pure)\n");
            } else if !eff.is_empty() {
                head.push_str(&format!("    (eff {eff})\n"));
            }
            for slot in ["pre", "post", "inv"] {
                if let Some(ids) = n.slots.get(slot) {
                    for id in ids {
                        let cn = g.get(id).unwrap();
                        head.push_str(&format!(
                            "    ({kind} {})\n",
                            expr_air_to_sexpr(g, &cn.slots["expr"][0]),
                            kind = field_str(cn, "kind")
                        ));
                    }
                }
            }
            // the body slot holds a Block node whose steps are the fn's statements
            let body_steps = n
                .slots
                .get("body")
                .and_then(|b| b.first())
                .and_then(|b| g.get(b))
                .map(|b| b.slots.get("steps").cloned().unwrap_or_default())
                .unwrap_or_default();
            let rendered: Vec<String> =
                body_steps.iter().map(|s| expr_air_to_sexpr(g, s)).collect();
            head.push_str(&format!("    (body {})\n  )\n", rendered.join(" ")));
            head
        }
        "test" => format!(
            "  (test {}\n    (body {}))\n",
            field_str(n, "name"),
            child_str(g, n, "body")
        ),
        "bench" => {
            let budget = n.fields.get("ms_budget").map(|v| match v {
                Value::Int(i) => format!("(budget (ms {i}))"),
                _ => String::new(),
            });
            format!(
                "  (bench {}\n    {}\n    (body {}))\n",
                field_str(n, "name"),
                budget.unwrap_or_default(),
                child_str(g, n, "body")
            )
        }
        _ => String::new(),
    }
}

// ---------------------------------------------------------------------------
// Deterministic JSON debug view
// ---------------------------------------------------------------------------

pub fn graph_to_json(g: &AirGraph, budget: Option<usize>) -> String {
    let mut out = String::from("{\"format\":\"air\",\"roots\":[");
    out.push_str(
        &g.module_entities
            .iter()
            .map(|m| {
                g.heads
                    .get(m)
                    .map(|h| format!("\"{h}\""))
                    .unwrap_or_else(|| "null".to_string())
            })
            .collect::<Vec<_>>()
            .join(","),
    );
    out.push_str("],\"semantic_hash\":\"");
    out.push_str(&g.semantic_hash());
    out.push_str("\",\"nodes\":[");
    for (shown, n) in g.nodes.values().enumerate() {
        if let Some(b) = budget {
            if shown >= b {
                out.push_str(",{\"truncated\":true}");
                break;
            }
        }
        if shown > 0 {
            out.push(',');
        }
        out.push_str(&node_to_json(n));
    }
    out.push_str("]}");
    out
}

fn value_to_json(v: &Value) -> String {
    match v {
        Value::Str(s) => format!("\"{}\"", json_escape(s)),
        Value::Int(i) => i.to_string(),
        Value::UInt(u) => u.to_string(),
        Value::Float(x) => x.to_string(),
        Value::Bool(b) => b.to_string(),
        Value::Bytes(b) => format!(
            "\"{}\"",
            b.iter().map(|x| format!("{x:02x}")).collect::<String>()
        ),
        Value::Names(ns) => format!(
            "[{}]",
            ns.iter()
                .map(|x| format!("\"{}\"", json_escape(x)))
                .collect::<Vec<_>>()
                .join(",")
        ),
    }
}

fn node_to_json(n: &AirNode) -> String {
    let mut out = format!(
        "{{\"revision\":\"{}\",\"entity\":\"{}\",\"kind\":\"{}\",\"fields\":{{",
        n.revision, n.entity, n.kind
    );
    let mut first = true;
    for (k, v) in &n.fields {
        if !first {
            out.push(',');
        }
        first = false;
        out.push_str(&format!("\"{}\":{}", json_escape(k), value_to_json(v)));
    }
    out.push_str("},\"slots\":{");
    first = true;
    for (k, children) in &n.slots {
        if !first {
            out.push(',');
        }
        first = false;
        out.push_str(&format!(
            "\"{}\":[{}]",
            json_escape(k),
            children
                .iter()
                .map(|c| format!("\"{c}\""))
                .collect::<Vec<_>>()
                .join(",")
        ));
    }
    out.push_str("}}");
    out
}

// ---------------------------------------------------------------------------
// Semantic diff
// ---------------------------------------------------------------------------

#[derive(Clone, Debug, Default)]
pub struct DiffReport {
    pub changed_modules: Vec<String>,
    pub changed_functions: Vec<(String, String)>, // (module, function name)
    pub changed_node_ids: Vec<String>,
    pub summary: String,
}

/// RFC-0006: one pending construction node (kind, fields, slots).
pub type NodeSpec = (
    String,
    BTreeMap<String, Value>,
    BTreeMap<String, Vec<String>>,
);

// ---------------------------------------------------------------------------
// Layer A: semantic handle canonicalization (AEP identity resolution hardening)
// ---------------------------------------------------------------------------

/// One canonical named entity from the staged graph (modules, types,
/// functions, externs, tests).
#[derive(Clone, Debug)]
pub struct CanonicalEntity {
    pub entity: String,    // entity id, e.g. "module:m/fn:f"
    pub kind: String,      // module | type | function | extern | test
    pub name: String,      // unqualified
    pub qualified: String, // module.name (module -> module name)
    pub handle: String,    // canonical handle graph.resolve() accepts: entity
                           // id when named, else node revision (anonymous
                           // nodes created mid-transaction, e.g. add_function)
}

/// Strip shell/JSON quoting, `function:`/`module:`/`type:` prefixes and
/// entity-path suffixes (`/body`, `/body:0`, `/body:0/st:0`) so the same
/// semantic entity can be addressed through any deterministic representation.
/// Representation normalization ONLY; never semantic guessing.
pub fn normalize_handle(s: &str) -> String {
    let mut h = s.trim().trim_matches(['\'', '"']).to_string();
    let mut is_entity_path = false;
    if h.starts_with("module:") {
        // keep the entity-path prefix module:X/fn:Y (or /type:Y), dropping any
        // trailing slot path like /body, /body:0, /body:0/st:0.
        for marker in ["/fn:", "/type:"] {
            if let Some(pos) = h.find(marker) {
                let rest = &h[pos + marker.len()..];
                let end = rest.find('/').unwrap_or(rest.len());
                h = format!("{}{}", &h[..pos + marker.len()], &rest[..end]);
                is_entity_path = true;
                break;
            }
        }
    }
    if !is_entity_path {
        for p in ["function:", "module:", "type:"] {
            if let Some(rest) = h.strip_prefix(p) {
                h = rest.to_string();
                break;
            }
        }
    }
    h
}

/// Build the canonical entity index from the CURRENT staged graph. No caches,
/// no external vocabularies: everything derives from the graph itself.
pub fn canonical_entities(g: &AirGraph) -> Vec<CanonicalEntity> {
    let mut out = Vec::new();
    for me in &g.module_entities {
        let Some(mn) = g.resolve(me) else {
            continue;
        };
        let module_name = me.trim_start_matches("module:").to_string();
        out.push(CanonicalEntity {
            entity: me.clone(),
            kind: "module".to_string(),
            name: module_name.clone(),
            qualified: module_name.clone(),
            handle: me.clone(),
        });
        for (slot, kind) in [
            ("types", "type"),
            ("functions", "function"),
            ("externs", "extern"),
            ("tests", "test"),
        ] {
            for id in mn.slots.get(slot).cloned().unwrap_or_default() {
                if let Some(n) = g.get(&id) {
                    let name = n
                        .fields
                        .get("name")
                        .and_then(|v| match v {
                            Value::Str(s) => Some(s.as_str()),
                            _ => None,
                        })
                        .unwrap_or("");
                    if name.is_empty() {
                        continue;
                    }
                    out.push(CanonicalEntity {
                        entity: n.entity.clone(),
                        kind: kind.to_string(),
                        name: name.to_string(),
                        qualified: format!("{module_name}.{name}"),
                        handle: if n.entity.is_empty() {
                            n.revision.clone()
                        } else {
                            n.entity.clone()
                        },
                    });
                }
            }
        }
    }
    out
}

/// Strict canonical resolution outcome.
#[derive(Debug)]
pub enum CanonicalOutcome {
    /// exactly one match of an expected kind -> canonical entity id.
    Resolved(String),
    /// >1 exact match -> candidates (qualified names), never a silent pick.
    Ambiguous(Vec<String>),
    /// entity exists but is NOT of an expected kind (e.g. a module name passed
    /// to inspect_function) -> preserved as a typed mismatch (NAVIGATION).
    WrongKind {
        entity: String,
        kind: String,
        expected: String,
    },
    /// no exact match.
    NotFound,
}

fn classify_canonical(v: Vec<CanonicalEntity>, expected: &[&str]) -> CanonicalOutcome {
    if v.len() > 1 {
        return CanonicalOutcome::Ambiguous(v.iter().map(|e| e.qualified.clone()).collect());
    }
    let e = &v[0];
    if expected.iter().any(|k| *k == "any" || *k == e.kind) {
        CanonicalOutcome::Resolved(e.handle.clone())
    } else {
        CanonicalOutcome::WrongKind {
            entity: e.entity.clone(),
            kind: e.kind.clone(),
            expected: expected.join("|"),
        }
    }
}

/// Resolve `handle` against the CURRENT staged graph with strict 0/1/>1
/// matching. `expected` restricts the target kinds; "any" accepts anything.
pub fn resolve_canonical(g: &AirGraph, handle: &str, expected: &[&str]) -> CanonicalOutcome {
    let h = normalize_handle(handle);
    if h.is_empty() {
        return CanonicalOutcome::NotFound;
    }
    let ents = canonical_entities(g);
    // 1) exact entity id / entity-path
    let id_matches: Vec<CanonicalEntity> = ents.iter().filter(|e| e.entity == h).cloned().collect();
    if !id_matches.is_empty() {
        return classify_canonical(id_matches, expected);
    }
    // 2) revision hash -> owning entity (run-graph identity, cut 2: read the
    // authoritative staged graph, never a maintained cache).
    if let Some(n) = g.nodes.get(&h) {
        if !n.entity.is_empty() {
            let owners: Vec<CanonicalEntity> = ents
                .iter()
                .filter(|e| e.entity == n.entity)
                .cloned()
                .collect();
            if !owners.is_empty() {
                // prefer the owner's canonical handle (entity id when named).
                let mut o = owners;
                if o.len() == 1 && !o[0].entity.is_empty() {
                    o[0].handle = o[0].entity.clone();
                }
                return classify_canonical(o, expected);
            }
        }
    }
    // 3) qualified display name
    let q: Vec<CanonicalEntity> = ents.iter().filter(|e| e.qualified == h).cloned().collect();
    if !q.is_empty() {
        return classify_canonical(q, expected);
    }
    // 4) unqualified name (strict: >1 -> ambiguous)
    let n: Vec<CanonicalEntity> = ents.iter().filter(|e| e.name == h).cloned().collect();
    match n.len() {
        0 => CanonicalOutcome::NotFound,
        _ => classify_canonical(n, expected),
    }
}

fn module_name(g: &AirGraph, module_id: &str) -> String {
    g.get(module_id)
        .map(|n| field_str(n, "name"))
        .unwrap_or_default()
}

fn node_label(g: &AirGraph, id: &str) -> String {
    match g.get(id) {
        Some(n) if n.kind == "function" => format!("function {}", field_str(n, "name")),
        Some(n) if n.kind == "type" => format!("type {}", field_str(n, "name")),
        Some(n) if n.kind == "extern" => format!("extern {}", field_str(n, "name")),
        Some(n) => format!("{} node {:.12}", n.kind, id),
        None => format!("missing {:.12}", id),
    }
}

pub fn diff_graphs(base: &AirGraph, head: &AirGraph) -> DiffReport {
    let mut report = DiffReport::default();
    for m in &base.module_entities {
        let head_root = head.heads.get(m).cloned().unwrap_or_default();
        let root = base.heads.get(m).cloned().unwrap_or_default();
        let bname = module_name(base, &root);
        let hname = module_name(head, &head_root);
        if root != head_root {
            report.changed_modules.push(hname.clone());
            let mut changed_fns = Vec::new();
            let mut changed_nodes = Vec::new();
            diff_node(
                base,
                &root,
                head,
                &head_root,
                &hname,
                &mut changed_fns,
                &mut changed_nodes,
            );
            report.changed_functions.extend(changed_fns);
            report.changed_node_ids.extend(changed_nodes);
        } else {
            let _ = bname;
        }
    }
    let mut s = String::new();
    for m in &report.changed_modules {
        s.push_str(&format!("CHANGED module {m}\n"));
    }
    for (m, f) in &report.changed_functions {
        s.push_str(&format!("CHANGED function {m}.{f}\n"));
    }
    if report.changed_node_ids.is_empty() && report.changed_modules.is_empty() {
        s.push_str("NO CHANGES\n");
    }
    report.summary = s;
    report
}

fn diff_node(
    base: &AirGraph,
    base_id: &str,
    head: &AirGraph,
    head_id: &str,
    module: &str,
    changed_fns: &mut Vec<(String, String)>,
    changed_nodes: &mut Vec<String>,
) {
    if base_id == head_id {
        return;
    }
    let bn = base.get(base_id);
    let hn = head.get(head_id);
    match (bn, hn) {
        (Some(b), Some(h)) => {
            if b.kind == "function" {
                changed_fns.push((module.to_string(), field_str(b, "name")));
            }
            if h.revision != b.revision {
                changed_nodes.push(h.revision.clone());
            }
            // recurse into union of slots to find specific changed children
            let mut slots: Vec<&String> = b.slots.keys().collect();
            for k in h.slots.keys() {
                if !slots.contains(&k) {
                    slots.push(k);
                }
            }
            for slot in slots {
                let bc = b.slots.get(slot).cloned().unwrap_or_default();
                let hc = h.slots.get(slot).cloned().unwrap_or_default();
                let n = bc.len().max(hc.len());
                for i in 0..n {
                    match (bc.get(i), hc.get(i)) {
                        (Some(bi), Some(hi)) => {
                            if bi != hi {
                                diff_node(base, bi, head, hi, module, changed_fns, changed_nodes);
                            }
                        }
                        (None, Some(hi)) => {
                            // added child
                            if let Some(hn) = head.get(hi) {
                                if hn.kind == "function" {
                                    changed_fns.push((module.to_string(), field_str(hn, "name")));
                                }
                            }
                            changed_nodes.push(hi.clone());
                        }
                        (Some(bi), None) => {
                            // removed child
                            if let Some(bn) = base.get(bi) {
                                if bn.kind == "function" {
                                    changed_fns.push((module.to_string(), field_str(bn, "name")));
                                }
                            }
                        }
                        (None, None) => {}
                    }
                }
            }
        }
        _ => {
            changed_nodes.push(head_id.to_string());
        }
    }
}

// ---------------------------------------------------------------------------
// Views (budgeted semantic projections for agents)
// ---------------------------------------------------------------------------

pub fn view_module(g: &AirGraph, module_id: &str, budget: Option<usize>) -> String {
    let n = match g.resolve(module_id) {
        Some(n) => n,
        None => return format!("module not found: {module_id}"),
    };
    let mut out = format!(
        "module {} ({}): deps={} caps={} exports={}\n",
        field_str(n, "name"),
        n.revision,
        match n.fields.get("deps") {
            Some(Value::Names(ns)) => ns.len().to_string(),
            _ => "0".to_string(),
        },
        match n.fields.get("caps") {
            Some(Value::Names(ns)) => ns.join(","),
            _ => String::new(),
        },
        match n.fields.get("exports") {
            Some(Value::Names(ns)) => ns.join(","),
            _ => String::new(),
        },
    );
    let mut used = 0;
    if let Some(ids) = n.slots.get("types") {
        for id in ids {
            if budget.map(|b| used >= b).unwrap_or(false) {
                break;
            }
            let t = g.get(id).unwrap();
            out.push_str(&format!(
                "  type {} ({})\n",
                field_str(t, "name"),
                t.revision
            ));
            used += 1;
        }
    }
    if let Some(ids) = n.slots.get("functions") {
        for id in ids {
            if budget.map(|b| used >= b).unwrap_or(false) {
                break;
            }
            let f = g.get(id).unwrap();
            let params = slot_children(g, f, "params")
                .iter()
                .map(|p| {
                    let pn = g.get(p).unwrap();
                    format!(
                        "{}:{}",
                        field_str(pn, "name"),
                        type_air_to_sexpr(g, &pn.slots["type"][0])
                    )
                })
                .collect::<Vec<_>>()
                .join(", ");
            let ret = type_air_to_sexpr(g, &f.slots["returns"][0]);
            let eff = match f.fields.get("eff") {
                Some(Value::Names(ns)) if !ns.is_empty() => ns.join(","),
                _ => match f.fields.get("pure") {
                    Some(Value::Bool(true)) => "pure".to_string(),
                    _ => "?".to_string(),
                },
            };
            out.push_str(&format!(
                "  fn {}({}) -> {} [{}] ({})\n",
                field_str(f, "name"),
                params,
                ret,
                eff,
                f.revision
            ));
            used += 1;
        }
    }
    out
}

pub fn view_function(g: &AirGraph, function_id: &str) -> String {
    let n = match g.get(function_id) {
        Some(n) => n,
        None => return format!("function not found: {function_id}"),
    };
    let mut out = format!(
        "fn {} -> {} [{}]\n",
        field_str(n, "name"),
        type_child_str(g, n, "returns"),
        match n.fields.get("eff") {
            Some(Value::Names(ns)) if !ns.is_empty() => ns.join(","),
            _ => match n.fields.get("pure") {
                Some(Value::Bool(true)) => "pure".to_string(),
                _ => "?".to_string(),
            },
        }
    );
    for p in slot_children(g, n, "params") {
        let pn = g.get(&p).unwrap();
        out.push_str(&format!(
            "  param {}: {}\n",
            field_str(pn, "name"),
            type_child_str(g, pn, "type")
        ));
    }
    out.push_str(&format!("  revision {}\n", n.revision));
    if let Some(body) = n.slots.get("body").and_then(|b| b.first()) {
        let steps = g
            .get(body)
            .map(|b| b.slots.get("steps").cloned().unwrap_or_default())
            .unwrap_or_default();
        out.push_str(&format!("  body: {} step(s)\n", steps.len()));
        for s in steps {
            out.push_str(&format!("    - {} ({})\n", node_label(g, &s), s));
        }
    }
    out
}

pub fn view_callers(g: &AirGraph, target_id: &str) -> String {
    let mut out = String::new();
    for n in g.nodes.values() {
        if n.kind == "call" {
            if let Some(Value::Str(name)) = n.fields.get("name") {
                if name == target_id {
                    out.push_str(&format!("called by call node {}\n", n.revision));
                }
            }
        }
    }
    if out.is_empty() {
        out.push_str("no callers\n");
    }
    out
}

pub fn view_dependencies(g: &AirGraph, module_id: &str) -> String {
    let n = match g.resolve(module_id) {
        Some(n) => n,
        None => return format!("module not found: {module_id}"),
    };
    let mut out = String::new();
    if let Some(Value::Names(deps)) = n.fields.get("deps") {
        for d in deps {
            out.push_str(&format!("dep {d}\n"));
        }
    }
    if out.is_empty() {
        out.push_str("no deps\n");
    }
    out
}

// ---------------------------------------------------------------------------
// AEP — Alva Edit Protocol (typed, transactional editing)
// ---------------------------------------------------------------------------

#[derive(Clone, Copy, PartialEq)]
enum VKind {
    Str,
    Int,
    Bool,
    Names,
    Any,
}

struct FieldSpec {
    name: &'static str,
    vkind: VKind,
    required: bool,
}

struct SlotSpec {
    name: &'static str,
    allowed: &'static [&'static str], // child kinds; "expr" matches any expression kind
    min: usize,
    max: usize,
}

pub fn is_expr_kind(k: &str) -> bool {
    matches!(
        k,
        "literal"
            | "ref"
            | "call"
            | "binary"
            | "not"
            | "if"
            | "binding"
            | "block"
            | "veclit"
            | "len"
            | "get"
            | "append"
            | "as"
            | "fold"
            | "variant"
            | "match"
            | "maplit"
            | "set"
            | "lookup"
            | "contains"
            | "veccontains"
            | "any"
            | "all"
            | "find"
            | "remove"
            | "keys"
            | "unwrap"
            | "errvalue"
            | "slice"
            | "split"
            | "concat"
            | "tostring"
            | "parseint"
            | "tobytes"
            | "isok"
            | "join"
            | "stripprefix"
            | "before"
            | "endswith"
            | "sort"
            | "urldecode"
            | "tohex"
            | "cteq"
            | "loop"
            | "record"
            | "record_update"
            | "field"
            | "raise"
            | "try"
            | "ok"
            | "err"
            | "hole"
    )
}

fn child_allowed(allowed: &[&str], kind: &str) -> bool {
    allowed
        .iter()
        .any(|a| *a == kind || (*a == "expr" && is_expr_kind(kind)))
}

/// RFC-0006: does the schema for `parent_kind` allow `child_kind` in `slot`?
/// Single source of truth shared by construction validation and recovery.
pub fn slot_allows_kind(parent_kind: &str, slot: &str, child_kind: &str) -> bool {
    let Some((_, _, allowed_slots)) = schema(parent_kind) else {
        return false;
    };
    allowed_slots
        .iter()
        .find(|s| s.name == slot)
        .map(|s| child_allowed(s.allowed, child_kind))
        .unwrap_or(false)
}

/// Per-node-kind schema: (required fields, allowed fields, allowed slots).
/// create_node validates against this so malformed nodes cannot enter the graph.
fn schema(
    kind: &str,
) -> Option<(
    &'static [FieldSpec],
    &'static [FieldSpec],
    &'static [SlotSpec],
)> {
    use VKind::*;
    Some(match kind {
        "module" => (
            &[FieldSpec {
                name: "name",
                vkind: Str,
                required: true,
            }],
            &[
                FieldSpec {
                    name: "version",
                    vkind: Str,
                    required: false,
                },
                FieldSpec {
                    name: "caps",
                    vkind: Names,
                    required: false,
                },
                FieldSpec {
                    name: "exports",
                    vkind: Names,
                    required: false,
                },
                FieldSpec {
                    name: "rust_deps",
                    vkind: Names,
                    required: false,
                },
                FieldSpec {
                    name: "deps",
                    vkind: Names,
                    required: false,
                },
            ],
            &[
                SlotSpec {
                    name: "types",
                    allowed: &["type"],
                    min: 0,
                    max: usize::MAX,
                },
                SlotSpec {
                    name: "functions",
                    allowed: &["function"],
                    min: 0,
                    max: usize::MAX,
                },
                SlotSpec {
                    name: "externs",
                    allowed: &["extern"],
                    min: 0,
                    max: usize::MAX,
                },
                SlotSpec {
                    name: "tests",
                    allowed: &["test"],
                    min: 0,
                    max: usize::MAX,
                },
                SlotSpec {
                    name: "benches",
                    allowed: &["bench"],
                    min: 0,
                    max: usize::MAX,
                },
            ],
        ),
        "type_expr" => (
            &[FieldSpec {
                name: "shape",
                vkind: Str,
                required: true,
            }],
            &[FieldSpec {
                name: "name",
                vkind: Str,
                required: false,
            }],
            &[
                SlotSpec {
                    name: "inner",
                    allowed: &["type_expr"],
                    min: 1,
                    max: 1,
                },
                SlotSpec {
                    name: "key",
                    allowed: &["type_expr"],
                    min: 1,
                    max: 1,
                },
                SlotSpec {
                    name: "value",
                    allowed: &["type_expr"],
                    min: 1,
                    max: 1,
                },
                SlotSpec {
                    name: "ok",
                    allowed: &["type_expr"],
                    min: 1,
                    max: 1,
                },
                SlotSpec {
                    name: "err",
                    allowed: &["type_expr"],
                    min: 1,
                    max: 1,
                },
            ],
        ),
        "type" => (
            &[
                FieldSpec {
                    name: "name",
                    vkind: Str,
                    required: true,
                },
                FieldSpec {
                    name: "kind",
                    vkind: Str,
                    required: true,
                },
            ],
            &[FieldSpec {
                name: "variants",
                vkind: Names,
                required: false,
            }],
            &[
                SlotSpec {
                    name: "fields",
                    allowed: &["type_field"],
                    min: 0,
                    max: usize::MAX,
                },
                SlotSpec {
                    name: "alias",
                    allowed: &["type_expr"],
                    min: 1,
                    max: 1,
                },
            ],
        ),
        "type_field" => (
            &[FieldSpec {
                name: "name",
                vkind: Str,
                required: true,
            }],
            &[],
            &[SlotSpec {
                name: "type",
                allowed: &["type_expr"],
                min: 1,
                max: 1,
            }],
        ),
        "function" => (
            &[FieldSpec {
                name: "name",
                vkind: Str,
                required: true,
            }],
            &[
                FieldSpec {
                    name: "pure",
                    vkind: Bool,
                    required: false,
                },
                FieldSpec {
                    name: "eff",
                    vkind: Names,
                    required: false,
                },
            ],
            &[
                SlotSpec {
                    name: "params",
                    allowed: &["param"],
                    min: 0,
                    max: usize::MAX,
                },
                SlotSpec {
                    name: "returns",
                    allowed: &["type_expr"],
                    min: 1,
                    max: 1,
                },
                SlotSpec {
                    name: "pre",
                    allowed: &["contract"],
                    min: 0,
                    max: usize::MAX,
                },
                SlotSpec {
                    name: "post",
                    allowed: &["contract"],
                    min: 0,
                    max: usize::MAX,
                },
                SlotSpec {
                    name: "inv",
                    allowed: &["contract"],
                    min: 0,
                    max: usize::MAX,
                },
                SlotSpec {
                    name: "body",
                    allowed: &["block"],
                    min: 1,
                    max: 1,
                },
            ],
        ),
        "param" => (
            &[FieldSpec {
                name: "name",
                vkind: Str,
                required: true,
            }],
            &[],
            &[SlotSpec {
                name: "type",
                allowed: &["type_expr"],
                min: 1,
                max: 1,
            }],
        ),
        "extern" => (
            &[FieldSpec {
                name: "name",
                vkind: Str,
                required: true,
            }],
            &[
                FieldSpec {
                    name: "pure",
                    vkind: Bool,
                    required: false,
                },
                FieldSpec {
                    name: "unsafe",
                    vkind: Bool,
                    required: false,
                },
                FieldSpec {
                    name: "eff",
                    vkind: Names,
                    required: false,
                },
                FieldSpec {
                    name: "template",
                    vkind: Str,
                    required: false,
                },
            ],
            &[
                SlotSpec {
                    name: "params",
                    allowed: &["param"],
                    min: 0,
                    max: usize::MAX,
                },
                SlotSpec {
                    name: "returns",
                    allowed: &["type_expr"],
                    min: 1,
                    max: 1,
                },
            ],
        ),
        "test" => (
            &[FieldSpec {
                name: "name",
                vkind: Str,
                required: true,
            }],
            &[],
            &[SlotSpec {
                name: "body",
                allowed: &["expr"],
                min: 1,
                max: 1,
            }],
        ),
        "bench" => (
            &[FieldSpec {
                name: "name",
                vkind: Str,
                required: true,
            }],
            &[FieldSpec {
                name: "ms_budget",
                vkind: Int,
                required: false,
            }],
            &[
                SlotSpec {
                    name: "setup",
                    allowed: &["expr"],
                    min: 0,
                    max: usize::MAX,
                },
                SlotSpec {
                    name: "body",
                    allowed: &["expr"],
                    min: 1,
                    max: 1,
                },
            ],
        ),
        "block" => (
            &[],
            &[],
            &[SlotSpec {
                name: "steps",
                allowed: &["expr"],
                min: 0,
                max: usize::MAX,
            }],
        ),
        "binding" => (
            &[FieldSpec {
                name: "name",
                vkind: Str,
                required: true,
            }],
            &[],
            &[
                SlotSpec {
                    name: "type",
                    allowed: &["type_expr"],
                    min: 0,
                    max: 1,
                },
                SlotSpec {
                    name: "value",
                    allowed: &["expr"],
                    min: 1,
                    max: 1,
                },
                SlotSpec {
                    name: "body",
                    allowed: &["expr"],
                    min: 1,
                    max: 1,
                },
            ],
        ),
        "call" => (
            &[FieldSpec {
                name: "name",
                vkind: Str,
                required: true,
            }],
            &[],
            &[SlotSpec {
                name: "args",
                allowed: &["expr"],
                min: 0,
                max: usize::MAX,
            }],
        ),
        "ref" => (
            &[FieldSpec {
                name: "name",
                vkind: Str,
                required: true,
            }],
            &[],
            &[],
        ),
        "literal" => (
            &[FieldSpec {
                name: "value",
                vkind: Any,
                required: true,
            }],
            &[],
            &[],
        ),
        "if" => (
            &[],
            &[],
            &[
                SlotSpec {
                    name: "cond",
                    allowed: &["expr"],
                    min: 1,
                    max: 1,
                },
                SlotSpec {
                    name: "then",
                    allowed: &["expr"],
                    min: 1,
                    max: 1,
                },
                SlotSpec {
                    name: "else",
                    allowed: &["expr"],
                    min: 1,
                    max: 1,
                },
            ],
        ),
        "binary" => (
            &[FieldSpec {
                name: "op",
                vkind: Str,
                required: true,
            }],
            &[],
            &[
                SlotSpec {
                    name: "left",
                    allowed: &["expr"],
                    min: 1,
                    max: 1,
                },
                SlotSpec {
                    name: "right",
                    allowed: &["expr"],
                    min: 1,
                    max: 1,
                },
            ],
        ),
        "not" | "len" | "keys" | "unwrap" | "errvalue" | "tostring" | "parseint" | "tobytes"
        | "isok" | "sort" | "urldecode" | "tohex" | "raise" => (
            &[],
            &[],
            &[SlotSpec {
                name: "value",
                allowed: &["expr"],
                min: 1,
                max: 1,
            }],
        ),
        "get" | "append" | "lookup" | "contains" | "remove" | "split" | "concat" | "join"
        | "stripprefix" | "before" | "endswith" | "cteq" | "veccontains" => (
            &[],
            &[],
            &[
                SlotSpec {
                    name: "left",
                    allowed: &["expr"],
                    min: 1,
                    max: 1,
                },
                SlotSpec {
                    name: "right",
                    allowed: &["expr"],
                    min: 1,
                    max: 1,
                },
            ],
        ),
        "any" | "all" | "find" => (
            &[FieldSpec {
                name: "elem_var",
                vkind: Str,
                required: true,
            }],
            &[],
            &[
                SlotSpec {
                    name: "collection",
                    allowed: &["expr"],
                    min: 1,
                    max: 1,
                },
                SlotSpec {
                    name: "predicate",
                    allowed: &["expr"],
                    min: 1,
                    max: 1,
                },
            ],
        ),
        "set" => (
            &[],
            &[],
            &[
                SlotSpec {
                    name: "a",
                    allowed: &["expr"],
                    min: 1,
                    max: 1,
                },
                SlotSpec {
                    name: "b",
                    allowed: &["expr"],
                    min: 1,
                    max: 1,
                },
                SlotSpec {
                    name: "c",
                    allowed: &["expr"],
                    min: 1,
                    max: 1,
                },
            ],
        ),
        "slice" => (
            &[],
            &[],
            &[
                SlotSpec {
                    name: "value",
                    allowed: &["expr"],
                    min: 1,
                    max: 1,
                },
                SlotSpec {
                    name: "start",
                    allowed: &["expr"],
                    min: 1,
                    max: 1,
                },
                SlotSpec {
                    name: "end",
                    allowed: &["expr"],
                    min: 1,
                    max: 1,
                },
            ],
        ),
        "as" => (
            &[],
            &[],
            &[
                SlotSpec {
                    name: "type",
                    allowed: &["type_expr"],
                    min: 1,
                    max: 1,
                },
                SlotSpec {
                    name: "value",
                    allowed: &["expr"],
                    min: 1,
                    max: 1,
                },
            ],
        ),
        "fold" => (
            &[
                FieldSpec {
                    name: "index",
                    vkind: Str,
                    required: true,
                },
                FieldSpec {
                    name: "acc_name",
                    vkind: Str,
                    required: true,
                },
            ],
            &[],
            &[
                SlotSpec {
                    name: "range_start",
                    allowed: &["expr"],
                    min: 1,
                    max: 1,
                },
                SlotSpec {
                    name: "range_end",
                    allowed: &["expr"],
                    min: 1,
                    max: 1,
                },
                SlotSpec {
                    name: "acc_type",
                    allowed: &["type_expr"],
                    min: 1,
                    max: 1,
                },
                SlotSpec {
                    name: "acc_init",
                    allowed: &["expr"],
                    min: 1,
                    max: 1,
                },
                SlotSpec {
                    name: "body",
                    allowed: &["expr"],
                    min: 1,
                    max: 1,
                },
            ],
        ),
        "variant" => (
            &[
                FieldSpec {
                    name: "type",
                    vkind: Str,
                    required: true,
                },
                FieldSpec {
                    name: "variant",
                    vkind: Str,
                    required: true,
                },
            ],
            &[],
            &[],
        ),
        "match" => (
            &[FieldSpec {
                name: "type",
                vkind: Str,
                required: true,
            }],
            &[],
            &[
                SlotSpec {
                    name: "scrutinee",
                    allowed: &["expr"],
                    min: 1,
                    max: 1,
                },
                SlotSpec {
                    name: "cases",
                    allowed: &["case"],
                    min: 0,
                    max: usize::MAX,
                },
            ],
        ),
        "case" => (
            &[FieldSpec {
                name: "variant",
                vkind: Str,
                required: true,
            }],
            &[],
            &[SlotSpec {
                name: "body",
                allowed: &["expr"],
                min: 1,
                max: 1,
            }],
        ),
        "maplit" => (
            &[],
            &[],
            &[
                SlotSpec {
                    name: "key_type",
                    allowed: &["type_expr"],
                    min: 1,
                    max: 1,
                },
                SlotSpec {
                    name: "value_type",
                    allowed: &["type_expr"],
                    min: 1,
                    max: 1,
                },
                SlotSpec {
                    name: "pairs",
                    allowed: &["pair"],
                    min: 0,
                    max: usize::MAX,
                },
            ],
        ),
        "pair" => (
            &[],
            &[],
            &[
                SlotSpec {
                    name: "key",
                    allowed: &["expr"],
                    min: 1,
                    max: 1,
                },
                SlotSpec {
                    name: "value",
                    allowed: &["expr"],
                    min: 1,
                    max: 1,
                },
            ],
        ),
        "record" => (
            &[FieldSpec {
                name: "type",
                vkind: Str,
                required: true,
            }],
            &[],
            &[SlotSpec {
                name: "fields",
                allowed: &["record_field"],
                min: 0,
                max: usize::MAX,
            }],
        ),
        "record_update" => (
            &[FieldSpec {
                name: "type",
                vkind: Str,
                required: true,
            }],
            &[],
            &[
                SlotSpec {
                    name: "base",
                    allowed: &["expr"],
                    min: 1,
                    max: 1,
                },
                SlotSpec {
                    name: "updates",
                    allowed: &["update_field"],
                    min: 0,
                    max: usize::MAX,
                },
            ],
        ),
        "update_field" => (
            &[FieldSpec {
                name: "name",
                vkind: Str,
                required: true,
            }],
            &[],
            &[SlotSpec {
                name: "value",
                allowed: &["expr"],
                min: 1,
                max: 1,
            }],
        ),
        "record_field" => (
            &[FieldSpec {
                name: "name",
                vkind: Str,
                required: true,
            }],
            &[],
            &[SlotSpec {
                name: "value",
                allowed: &["expr"],
                min: 1,
                max: 1,
            }],
        ),
        "field" => (
            &[FieldSpec {
                name: "name",
                vkind: Str,
                required: true,
            }],
            &[],
            &[SlotSpec {
                name: "value",
                allowed: &["expr"],
                min: 1,
                max: 1,
            }],
        ),
        "try" => (
            &[FieldSpec {
                name: "catch_name",
                vkind: Str,
                required: true,
            }],
            &[],
            &[
                SlotSpec {
                    name: "value",
                    allowed: &["expr"],
                    min: 1,
                    max: 1,
                },
                SlotSpec {
                    name: "catch",
                    allowed: &["expr"],
                    min: 1,
                    max: 1,
                },
            ],
        ),
        "ok" | "err" => (
            &[],
            &[],
            &[SlotSpec {
                name: "value",
                allowed: &["expr"],
                min: 1,
                max: 1,
            }],
        ),
        "loop" => (
            &[FieldSpec {
                name: "acc_name",
                vkind: Str,
                required: true,
            }],
            &[],
            &[
                SlotSpec {
                    name: "acc_type",
                    allowed: &["type_expr"],
                    min: 1,
                    max: 1,
                },
                SlotSpec {
                    name: "init",
                    allowed: &["expr"],
                    min: 1,
                    max: 1,
                },
                SlotSpec {
                    name: "inv",
                    allowed: &["expr"],
                    min: 0,
                    max: 1,
                },
                SlotSpec {
                    name: "cond",
                    allowed: &["expr"],
                    min: 1,
                    max: 1,
                },
                SlotSpec {
                    name: "body",
                    allowed: &["expr"],
                    min: 1,
                    max: 1,
                },
            ],
        ),
        "veclit" => (
            &[],
            &[],
            &[
                SlotSpec {
                    name: "elem_type",
                    allowed: &["type_expr"],
                    min: 1,
                    max: 1,
                },
                SlotSpec {
                    name: "items",
                    allowed: &["expr"],
                    min: 0,
                    max: usize::MAX,
                },
            ],
        ),
        "contract" => (
            &[FieldSpec {
                name: "kind",
                vkind: Str,
                required: true,
            }],
            &[],
            &[SlotSpec {
                name: "expr",
                allowed: &["expr"],
                min: 1,
                max: 1,
            }],
        ),
        "hole" => (
            &[FieldSpec {
                name: "expected_type",
                vkind: Str,
                required: true,
            }],
            &[
                FieldSpec {
                    name: "hole_id",
                    vkind: Str,
                    required: false,
                },
                FieldSpec {
                    name: "allowed_effects",
                    vkind: Names,
                    required: false,
                },
            ],
            &[],
        ),
        _ => return None,
    })
}

pub fn validate_node(
    kind: &str,
    fields: &BTreeMap<String, Value>,
    slots: &BTreeMap<String, Vec<String>>,
) -> Result<(), String> {
    let (required_fields, allowed_fields, allowed_slots) = match schema(kind) {
        Some(s) => s,
        None => return Err("E_AEP_001: unknown node kind".to_string()),
    };
    for fs in required_fields.iter().chain(allowed_fields.iter()) {
        if fs.required && !fields.contains_key(fs.name) {
            return Err(format!(
                "E_AEP_003: node kind '{kind}' requires field '{}'",
                fs.name
            ));
        }
    }
    for (fname, fval) in fields {
        let spec = required_fields
            .iter()
            .chain(allowed_fields.iter())
            .find(|s| s.name == fname)
            .ok_or_else(|| {
                format!("E_AEP_002: node kind '{kind}' does not allow field '{fname}'")
            })?;
        let ok = matches!(
            (spec.vkind, fval),
            (VKind::Str, Value::Str(_))
                | (VKind::Int, Value::Int(_))
                | (VKind::Bool, Value::Bool(_))
                | (VKind::Names, Value::Names(_))
                | (VKind::Any, _)
        );
        if !ok {
            return Err(format!(
                "E_AEP_004: node kind '{kind}' field '{fname}' has wrong value type"
            ));
        }
    }
    for (sname, children) in slots {
        let spec = allowed_slots
            .iter()
            .find(|s| s.name == sname)
            .ok_or_else(|| {
                format!("E_AEP_005: node kind '{kind}' does not allow slot '{sname}'")
            })?;
        if children.len() < spec.min || children.len() > spec.max {
            return Err(format!(
                "E_AEP_006: node kind '{kind}' slot '{sname}' has {} children (allowed {}..{})",
                children.len(),
                spec.min,
                spec.max
            ));
        }
    }
    Ok(())
}

pub fn validate_graph(g: &AirGraph) -> Vec<String> {
    let mut problems = g.verify();
    for n in g.nodes.values() {
        if let Err(e) = validate_node(&n.kind, &n.fields, &n.slots) {
            problems.push(format!("{}: {e}", n.revision));
        }
        // slot child kind checks (child kinds must match the slot spec)
        if let Some((_, _, allowed_slots)) = schema(&n.kind) {
            for (sname, children) in &n.slots {
                if let Some(spec) = allowed_slots.iter().find(|s| s.name == sname) {
                    for c in children {
                        if let Some(cn) = g.nodes.get(c) {
                            if !child_allowed(spec.allowed, &cn.kind) {
                                problems.push(format!(
                                    "E_AEP_007: node {} slot '{}' child kind '{}' not allowed",
                                    n.revision, sname, cn.kind
                                ));
                            }
                        }
                    }
                }
            }
        }
    }
    problems
}

#[derive(Clone, Debug, Default)]
pub struct EditSession {
    pub graph: AirGraph,
    #[allow(dead_code)] // re-validated against the authoritative store at commit
    pub base_hash: String,
    pub bindings: BTreeMap<String, BTreeMap<String, (String, String)>>, // scope -> (name -> (type, node))
    pub errors: Vec<String>,
    pub last_rebuild_stats: Option<RebuildStats>,
    pub full_check_runs: u64,
}

impl EditSession {
    pub fn begin(graph: AirGraph, base_hash: String) -> Self {
        EditSession {
            graph,
            base_hash,
            bindings: BTreeMap::new(),
            errors: Vec::new(),
            last_rebuild_stats: None,
            full_check_runs: 0,
        }
    }

    /// Atomic mutation: operate on a CLONE (staging graph), then rebuild,
    /// verify, schema-check and cycle-check the candidate; only on full
    /// success is the session graph swapped. Any failure leaves the session
    /// graph untouched.
    fn stage(
        &mut self,
        apply: impl FnOnce(&mut AirGraph) -> Result<(), String>,
    ) -> Result<(), String> {
        let mut candidate = self.graph.clone();
        apply(&mut candidate)?;
        let cycles = detect_cycles(&candidate);
        if !cycles.is_empty() {
            self.errors = vec![format!("E_AIR_CYCLE: {}", cycles[0])];
            return Err(format!("E_AIR_CYCLE: {}", cycles[0]));
        }
        let rebuild_stats = candidate.rebuild_revisions_with_stats();
        let problems = validate_graph(&candidate);
        if !problems.is_empty() {
            self.errors = problems.clone();
            return Err(format!("E_AIR_INVARIANT: {}", problems.join("; ")));
        }
        self.graph = candidate;
        self.last_rebuild_stats = Some(rebuild_stats);
        Ok(())
    }

    /// AEP 0.7: resolve a handle to the CURRENT reachable revision. Accepts
    /// entity ids, exact revisions, and unambiguous prefixes. If the target
    /// is a stale (unreachable) node that still carries an entity, map it to
    /// that entity's current head so the agent never edits a ghost node.
    pub fn resolve_current(&self, handle: &str) -> Result<String, String> {
        let rev = self
            .graph
            .resolve_rev(handle)
            .ok_or_else(|| format!("E_AEP_ENTITY_NOT_FOUND: {handle}"))?;
        if self.graph.is_reachable(&rev) {
            return Ok(rev);
        }
        if let Some(n) = self.graph.get(&rev) {
            // 匿名节点（entity 为空）通常是刚创建、尚未挂载的新节点；
            // 本次操作（如 append_child）即将把它挂进图，因此直接允许。
            if n.entity.is_empty() {
                return Ok(rev);
            }
            // 带 entity 的旧 revision：映射到该实体当前 head（stale->latest）。
            if !n.entity.is_empty() {
                if let Some(head) = self.graph.heads.get(&n.entity) {
                    return Ok(head.clone());
                }
            }
        }
        Err(format!("E_AEP_STALE_REVISION: {handle}"))
    }

    pub fn create_node(
        &mut self,
        kind: &str,
        fields: BTreeMap<String, Value>,
        slots: BTreeMap<String, Vec<String>>,
    ) -> Result<String, String> {
        validate_node(kind, &fields, &slots)?;
        for children in slots.values() {
            for c in children {
                if !self.graph.nodes.contains_key(c) {
                    return Err(format!(
                        "E_AIR_DANGLING_CHILD: create_node child {c} does not exist"
                    ));
                }
            }
        }
        let rev = self.graph.add(kind, "", fields, slots);
        self.stage(|_| Ok(()))?;
        Ok(rev)
    }

    /// RFC-0006: atomic batch construction.
    ///
    /// `construct_expression` validates the ENTIRE request first, then
    /// materializes all nodes in ONE staged commit. A failed construction
    /// MUST NOT create partial AIR nodes or alter the transaction semantic
    /// state (RFC-0006 §6 invariant 7): validation errors return before any
    /// node is inserted, and the single `stage` call swaps the session graph
    /// only on full success.
    ///
    /// `nodes` are (kind, fields, slots) in dependency order (children before
    /// parents); slots may reference revisions of earlier entries in the same
    /// batch (content-addressed, pre-computed). Returns the LAST entry's
    /// revision, which is the constructed expression's main node.
    pub fn create_nodes_atomic(&mut self, nodes: Vec<NodeSpec>) -> Result<String, String> {
        if nodes.is_empty() {
            return Err("E_AEP_CONSTRUCTION_EMPTY_BATCH".to_string());
        }
        // 1) validate every node spec (fields + slot count ranges) BEFORE any
        //    insertion.
        for (kind, fields, slots) in &nodes {
            validate_node(kind, fields, slots)?;
        }
        // 2) pre-compute revisions so batch-internal slot references resolve
        //    deterministically, and so external child references are checked
        //    against the existing graph.
        let mut revs: Vec<String> = Vec::with_capacity(nodes.len());
        for (kind, fields, slots) in &nodes {
            let rev = self.graph.compute_revision(kind, fields, slots);
            revs.push(rev);
        }
        // 3) one staged commit.
        let main_rev = revs
            .last()
            .cloned()
            .ok_or_else(|| "E_AEP_CONSTRUCTION_EMPTY_BATCH".to_string())?;
        self.stage(|g| {
            for (kind, fields, slots) in &nodes {
                g.add(kind, "", fields.clone(), slots.clone());
            }
            Ok(())
        })?;
        Ok(main_rev)
    }

    pub fn create_hole(
        &mut self,
        expected_type: &str,
        allowed_effects: Vec<String>,
    ) -> Result<String, String> {
        let mut f = BTreeMap::new();
        f.insert(
            "hole_id".to_string(),
            Value::Str(format!("h{}", self.graph.nodes.len())),
        );
        f.insert(
            "expected_type".to_string(),
            Value::Str(expected_type.to_string()),
        );
        f.insert("allowed_effects".to_string(), Value::Names(allowed_effects));
        let rev = self.graph.add("hole", "", f, BTreeMap::new());
        self.stage(|_| Ok(()))?;
        Ok(rev)
    }

    /// Replace every slot reference to `target` with `replacement`.
    pub fn replace_node(&mut self, target: &str, replacement: &str) -> Result<String, String> {
        let target_rev = self
            .resolve_current(target)
            .map_err(|e| format!("replace_node: {e}"))?;
        let replacement_rev = self
            .resolve_current(replacement)
            .map_err(|e| format!("replace_node: {e}"))?;
        let tr = target_rev.clone();
        let rr = replacement_rev.clone();
        self.stage(|g| {
            for n in g.nodes.values_mut() {
                for children in n.slots.values_mut() {
                    for c in children.iter_mut() {
                        if *c == tr {
                            *c = rr.clone();
                        }
                    }
                }
            }
            for (entity, head) in g.heads.clone() {
                if head == tr {
                    g.heads.insert(entity, rr.clone());
                }
            }
            Ok(())
        })?;
        Ok(replacement_rev)
    }

    pub fn replace_slot(
        &mut self,
        parent: &str,
        slot: &str,
        child: &str,
    ) -> Result<String, String> {
        let parent_rev = self
            .resolve_current(parent)
            .map_err(|e| format!("replace_slot: {e}"))?;
        let child_rev = self
            .resolve_current(child)
            .map_err(|e| format!("replace_slot: {e}"))?;
        let n = self
            .graph
            .nodes
            .get(&parent_rev)
            .ok_or_else(|| format!("E_AIR_DANGLING_CHILD: unknown parent {parent}"))?;
        let (_, _, allowed_slots) = schema(&n.kind).ok_or("unknown kind")?;
        if !allowed_slots.iter().any(|s| s.name == slot) {
            return Err(format!(
                "replace_slot: node kind '{}' has no slot '{slot}'",
                n.kind
            ));
        }
        let pr = parent_rev.clone();
        let cr = child_rev.clone();
        self.stage(|g| {
            if let Some(n) = g.nodes.get_mut(&pr) {
                n.slots.insert(slot.to_string(), vec![cr.clone()]);
            }
            Ok(())
        })?;
        Ok(self.graph.resolve_rev(&parent_rev).unwrap_or_default())
    }

    pub fn append_child(
        &mut self,
        parent: &str,
        slot: &str,
        child: &str,
    ) -> Result<String, String> {
        let parent_rev = self
            .resolve_current(parent)
            .map_err(|e| format!("append_child: {e}"))?;
        let child_rev = self
            .resolve_current(child)
            .map_err(|e| format!("append_child: {e}"))?;
        let n = self
            .graph
            .nodes
            .get(&parent_rev)
            .ok_or_else(|| format!("E_AIR_DANGLING_CHILD: unknown parent {parent}"))?;
        let (_, _, allowed_slots) = schema(&n.kind).ok_or("unknown kind")?;
        if !allowed_slots.iter().any(|s| s.name == slot) {
            return Err(format!(
                "append_child: node kind '{}' has no slot '{slot}'",
                n.kind
            ));
        }
        let pr = parent_rev.clone();
        let cr = child_rev.clone();
        self.stage(|g| {
            if let Some(n) = g.nodes.get_mut(&pr) {
                n.slots
                    .entry(slot.to_string())
                    .or_default()
                    .push(cr.clone());
            }
            Ok(())
        })?;
        Ok(self.graph.resolve_rev(&parent_rev).unwrap_or_default())
    }

    /// 在 slot 的指定位置插入子节点（供工具做临时挂载校验等）。
    pub fn insert_child(
        &mut self,
        parent: &str,
        slot: &str,
        child: &str,
        index: usize,
    ) -> Result<(), String> {
        let parent_rev = self
            .resolve_current(parent)
            .map_err(|e| format!("insert_child: {e}"))?;
        let child_rev = self
            .resolve_current(child)
            .map_err(|e| format!("insert_child: {e}"))?;
        let pr = parent_rev.clone();
        let cr = child_rev.clone();
        self.stage(|g| {
            if let Some(n) = g.nodes.get_mut(&pr) {
                let v = n.slots.entry(slot.to_string()).or_default();
                let idx = index.min(v.len());
                v.insert(idx, cr.clone());
            }
            Ok(())
        })?;
        Ok(())
    }

    pub fn bind_symbol(
        &mut self,
        scope: &str,
        name: &str,
        type_name: &str,
        value: &str,
    ) -> Result<(), String> {
        let value_rev = self
            .graph
            .resolve_rev(value)
            .ok_or_else(|| format!("bind_symbol: unknown value node {value}"))?;
        self.bindings
            .entry(scope.to_string())
            .or_default()
            .insert(name.to_string(), (type_name.to_string(), value_rev));
        Ok(())
    }

    pub fn rename_symbol(&mut self, symbol: &str, new_name: &str) -> Result<(), String> {
        // 重命名所有引用该符号的节点：ref（局部/参数引用）与 call（调用点，
        // 跨模块调用使用限定名 module.symbol）。
        let targets: Vec<(String, String)> = self
            .graph
            .nodes
            .values()
            .filter(|n| matches!(n.kind.as_str(), "ref" | "call"))
            .filter_map(|n| match n.fields.get("name") {
                Some(Value::Str(name)) if name == symbol => {
                    Some((n.revision.clone(), n.kind.clone()))
                }
                _ => None,
            })
            .collect();
        if targets.is_empty() {
            return Ok(());
        }
        let nn = new_name.to_string();
        self.stage(|g| {
            for (rev, kind) in &targets {
                if let Some(n) = g.nodes.get_mut(rev) {
                    if kind == "call" {
                        let updated = match n.fields.get("name") {
                            Some(Value::Str(name)) if name.contains('.') => {
                                let mut parts: Vec<&str> = name.split('.').collect();
                                if let Some(last) = parts.last_mut() {
                                    *last = nn.rsplit('.').next().unwrap_or(&nn);
                                }
                                parts.join(".")
                            }
                            _ => nn.clone(),
                        };
                        n.fields.insert("name".to_string(), Value::Str(updated));
                    } else {
                        n.fields.insert("name".to_string(), Value::Str(nn.clone()));
                    }
                }
            }
            Ok(())
        })?;
        Ok(())
    }

    /// Immutable field update on a named node (path-copy via staging).
    pub fn set_field(&mut self, handle: &str, field: &str, value: Value) -> Result<String, String> {
        let rev = self
            .resolve_current(handle)
            .map_err(|e| format!("set_field: {e}"))?;
        let kind = self
            .graph
            .get(&rev)
            .map(|n| n.kind.clone())
            .ok_or("set_field: missing node")?;
        let mut fields = self
            .graph
            .get(&rev)
            .map(|n| n.fields.clone())
            .unwrap_or_default();
        let slots = self
            .graph
            .get(&rev)
            .map(|n| n.slots.clone())
            .unwrap_or_default();
        fields.insert(field.to_string(), value.clone());
        validate_node(&kind, &fields, &slots)?;
        let new_revision = self.graph.compute_revision(&kind, &fields, &slots);
        let r = rev.clone();
        self.stage(|g| {
            if let Some(n) = g.nodes.get_mut(&r) {
                n.fields.insert(field.to_string(), value.clone());
            }
            Ok(())
        })?;
        if !self.graph.nodes.contains_key(&new_revision) {
            return Err("set_field: staged revision was not materialized".to_string());
        }
        Ok(new_revision)
    }

    pub fn delete_entity(&mut self, handle: &str) -> Result<(), String> {
        let rev = self
            .resolve_current(handle)
            .map_err(|e| format!("delete_entity: {e}"))?;
        let r = rev.clone();
        let h = handle.to_string();
        self.stage(|g| {
            g.nodes.remove(&r);
            g.heads.retain(|_, hh| hh != &r);
            g.module_entities.retain(|m| m != &h);
            for n in g.nodes.values_mut() {
                for children in n.slots.values_mut() {
                    children.retain(|c| c != &r);
                }
            }
            Ok(())
        })?;
        Ok(())
    }

    pub fn check(&mut self) -> Vec<String> {
        self.full_check_runs += 1;
        let mut all = validate_graph(&self.graph);
        all.extend(
            detect_cycles(&self.graph)
                .into_iter()
                .map(|c| format!("E_AIR_CYCLE: {c}")),
        );
        // 结构检查通过后，再跑完整语义检查（类型/effect/契约，含跨模块
        // 外部符号），确保 check_transaction / commit 在写入前暴露类型错误。
        if all.is_empty() {
            match crate::project::check_graph_semantic(&self.graph) {
                Ok(()) => {}
                Err(ds) => all.extend(ds),
            }
        }
        self.errors = all.clone();
        all
    }

    pub fn diff_vs_base(&self, base: &AirGraph) -> DiffReport {
        diff_graphs(base, &self.graph)
    }
}

// ---------------------------------------------------------------------------
// Typed holes: candidates from the current graph environment
// ---------------------------------------------------------------------------

pub fn hole_constraints(g: &AirGraph, hole_id: &str) -> String {
    let n = match g.get(hole_id) {
        Some(n) => n,
        None => return format!("hole not found: {hole_id}"),
    };
    let mut out = format!(
        "hole {} expected_type={}",
        n.revision,
        field_str(n, "expected_type")
    );
    if let Some(Value::Names(eff)) = n.fields.get("allowed_effects") {
        out.push_str(&format!(" allowed_effects=[{}]", eff.join(",")));
    }
    out
}

/// Build a parent index: child revision -> [(parent revision, slot)].
pub fn parent_index(g: &AirGraph) -> BTreeMap<String, Vec<(String, String)>> {
    let mut index: BTreeMap<String, Vec<(String, String)>> = BTreeMap::new();
    for n in g.nodes.values() {
        for (slot, children) in &n.slots {
            for c in children {
                index
                    .entry(c.clone())
                    .or_default()
                    .push((n.revision.clone(), slot.clone()));
            }
        }
    }
    index
}

/// RFC-0002/AEP-0001: 从模块根出发遍历所有可达表达式节点。
/// 返回 (node_revision, kind, enclosing_function_entity, enclosing_test_entity)
/// 的列表，供 change-impact 查询使用。
pub fn walk_expressions(g: &AirGraph) -> Vec<(String, String, String, String)> {
    let mut out = Vec::new();
    let mut seen = std::collections::HashSet::new();
    let mut stack: Vec<(String, String, String)> = Vec::new(); // (rev, fn_entity, test_entity)
    for me in &g.module_entities {
        let Some(mn) = g.resolve(me) else { continue };
        for fn_id in mn.slots.get("functions").cloned().unwrap_or_default() {
            if let Some(fn_) = g.get(&fn_id) {
                if let Some(b) = fn_.slots.get("body").and_then(|b| b.first()) {
                    stack.push((b.clone(), fn_id.clone(), String::new()));
                }
                for t in fn_.slots.get("returns").cloned().unwrap_or_default() {
                    stack.push((t, fn_id.clone(), String::new()));
                }
                for p in fn_.slots.get("params").cloned().unwrap_or_default() {
                    stack.push((p, fn_id.clone(), String::new()));
                }
            }
        }
        for t_id in mn.slots.get("tests").cloned().unwrap_or_default() {
            if let Some(t_) = g.get(&t_id) {
                if let Some(b) = t_.slots.get("body").and_then(|b| b.first()) {
                    stack.push((b.clone(), String::new(), t_id.clone()));
                }
            }
        }
    }
    while let Some((rev, fn_e, test_e)) = stack.pop() {
        if !seen.insert(rev.clone()) {
            continue;
        }
        let Some(n) = g.get(&rev) else { continue };
        out.push((rev.clone(), n.kind.clone(), fn_e.clone(), test_e.clone()));
        for children in n.slots.values() {
            for c in children {
                stack.push((c.clone(), fn_e.clone(), test_e.clone()));
            }
        }
    }
    out
}

/// Accurate lexical scope for a hole: walk the parent chain from the hole up to
/// the enclosing function. A binding is only visible if the hole lies inside
/// that binding's BODY slot. Returns (enclosing function entity, visible
/// (name, type) pairs in inner-to-outer order).
pub fn lexical_scope(g: &AirGraph, hole_rev: &str) -> (Option<String>, Vec<(String, String)>) {
    let parents = parent_index(g);
    let mut path = Vec::new(); // node revisions from hole up to the root
    let mut cur = hole_rev.to_string();
    let mut guard = 0;
    while let Some((parent_rev, slot)) = parents.get(&cur).and_then(|p| p.first()) {
        path.push((cur.clone(), parent_rev.clone(), slot.clone()));
        cur = parent_rev.clone();
        guard += 1;
        if guard > 100_000 {
            break;
        }
    }
    let mut scope = Vec::new();
    let mut fn_entity = None;
    // path is ordered hole->...->root; walk it from the hole side upward so
    // bindings are collected in inner-to-outer order and the enclosing
    // function (with its params) is reached last.
    for (child_rev, parent_rev, slot) in path.iter() {
        let Some(parent) = g.get(parent_rev) else {
            continue;
        };
        if parent.kind == "function" {
            fn_entity = Some(parent.entity.clone());
            for p in slot_children(g, parent, "params") {
                if let Some(pn) = g.get(&p) {
                    scope.push((field_str(pn, "name"), type_child_str(g, pn, "type")));
                }
            }
            break;
        }
        if parent.kind == "binding" && slot == "body" {
            // the binding's body contains the hole path -> the binding is visible
            scope.push((
                field_str(parent, "name"),
                parent
                    .slots
                    .get("type")
                    .map(|t| type_air_to_sexpr(g, &t[0]))
                    .unwrap_or_else(|| "?".to_string()),
            ));
        }
        if (parent.kind == "fold" || parent.kind == "loop") && slot == "body" {
            // accumulator is visible only inside the loop/fold body
            scope.push((
                field_str(parent, "acc_name"),
                parent
                    .slots
                    .get("acc_type")
                    .map(|t| type_air_to_sexpr(g, &t[0]))
                    .unwrap_or_else(|| "?".to_string()),
            ));
        }
        let _ = child_rev;
    }
    (fn_entity, scope)
}

pub fn hole_candidates(g: &AirGraph, hole_rev: &str) -> Vec<String> {
    let n = match g.get(hole_rev) {
        Some(n) => n,
        None => return Vec::new(),
    };
    let expected = field_str(n, "expected_type");
    let (fn_entity, scope) = lexical_scope(g, hole_rev);
    let mut candidates = Vec::new();
    for (name, ty) in scope {
        if type_satisfies(&ty, &expected) {
            candidates.push(format!("ref {name} : {ty}"));
        }
    }
    for node in g.nodes.values() {
        if node.kind == "function" {
            let ret = type_child_str(g, node, "returns");
            if type_satisfies(&ret, &expected) {
                candidates.push(format!("call {} : {ret}", field_str(node, "name")));
            }
        }
    }
    match expected.as_str() {
        "string" => candidates.push("literal \"\"".to_string()),
        "bool" => candidates.push("literal true".to_string()),
        "i64" => candidates.push("literal 0".to_string()),
        _ => {}
    }
    let _ = fn_entity;
    candidates
}

/// Compare a rendered type (e.g. "(prim string)") against an expected type
/// hint (e.g. "string"); primitives may be written by their short name.
fn type_satisfies(rendered: &str, expected: &str) -> bool {
    if rendered == "?" {
        return true; // unknown/not-yet-inferred types unify with anything
    }
    if rendered == expected {
        return true;
    }
    if let Some(rest) = rendered.strip_prefix("(prim ") {
        if let Some(name) = rest.strip_suffix(')') {
            return name == expected;
        }
    }
    false
}

// ---------------------------------------------------------------------------
// AIR -> AST reconstruction (so check/build/codegen can consume AIR directly;
// .alva is only an import format / read-only projection)
// ---------------------------------------------------------------------------

fn prim_from_name(name: &str) -> Option<ast::Prim> {
    Some(match name {
        "u8" => ast::Prim::U8,
        "u16" => ast::Prim::U16,
        "u32" => ast::Prim::U32,
        "u64" => ast::Prim::U64,
        "i8" => ast::Prim::I8,
        "i16" => ast::Prim::I16,
        "i32" => ast::Prim::I32,
        "i64" => ast::Prim::I64,
        "f32" => ast::Prim::F32,
        "f64" => ast::Prim::F64,
        "bool" => ast::Prim::Bool,
        "string" => ast::Prim::String,
        "bytes" => ast::Prim::Bytes,
        "nil" => ast::Prim::Nil,
        _ => return None,
    })
}

pub fn type_air_to_ast(g: &AirGraph, id: &str) -> Result<ast::TypeExpr, String> {
    let n = g.get(id).ok_or_else(|| format!("missing type node {id}"))?;
    let shape = field_str(n, "shape");
    match shape.as_str() {
        "prim" => {
            let name = field_str(n, "name");
            prim_from_name(&name)
                .map(ast::TypeExpr::Prim)
                .ok_or_else(|| format!("unknown prim {name}"))
        }
        "named" => Ok(ast::TypeExpr::Named(field_str(n, "name"))),
        "vec" => Ok(ast::TypeExpr::Vec(Box::new(type_air_to_ast(
            g,
            n.slots
                .get("inner")
                .and_then(|c| c.first())
                .ok_or("vec missing inner")?,
        )?))),
        "map" => Ok(ast::TypeExpr::Map(
            Box::new(type_air_to_ast(
                g,
                n.slots
                    .get("key")
                    .and_then(|c| c.first())
                    .ok_or("map missing key")?,
            )?),
            Box::new(type_air_to_ast(
                g,
                n.slots
                    .get("value")
                    .and_then(|c| c.first())
                    .ok_or("map missing value")?,
            )?),
        )),
        "result" => Ok(ast::TypeExpr::Result(
            Box::new(type_air_to_ast(
                g,
                n.slots
                    .get("ok")
                    .and_then(|c| c.first())
                    .ok_or("result missing ok")?,
            )?),
            Box::new(type_air_to_ast(
                g,
                n.slots
                    .get("err")
                    .and_then(|c| c.first())
                    .ok_or("result missing err")?,
            )?),
        )),
        _ => Err(format!("unknown type shape {shape}")),
    }
}

fn slot_first(_g: &AirGraph, n: &AirNode, slot: &str) -> Result<String, String> {
    n.slots
        .get(slot)
        .and_then(|c| c.first())
        .cloned()
        .ok_or_else(|| format!("node {} missing slot '{slot}'", n.revision))
}

fn slot_all(_g: &AirGraph, n: &AirNode, slot: &str) -> Vec<String> {
    n.slots.get(slot).cloned().unwrap_or_default()
}

pub fn expr_air_to_ast(g: &AirGraph, id: &str) -> Result<ast::Expr, String> {
    let n = g.get(id).ok_or_else(|| format!("missing expr node {id}"))?;
    let sp = || crate::s_expr::Span { line: 0, col: 0 };
    let tag = n.kind.as_str();
    let unary = |g: &AirGraph, n: &AirNode| -> Result<ast::Expr, String> {
        expr_air_to_ast(g, &slot_first(g, n, "value")?)
    };
    let bin = |g: &AirGraph,
               n: &AirNode,
               ctor: fn(Box<ast::Expr>, Box<ast::Expr>, crate::s_expr::Span) -> ast::Expr|
     -> Result<ast::Expr, String> {
        Ok(ctor(
            Box::new(expr_air_to_ast(g, &slot_first(g, n, "left")?)?),
            Box::new(expr_air_to_ast(g, &slot_first(g, n, "right")?)?),
            sp(),
        ))
    };
    Ok(match tag {
        "literal" => match n
            .fields
            .get("value")
            .cloned()
            .unwrap_or(Value::Str("nil".to_string()))
        {
            Value::Str(s) if s == "nil" => ast::Expr::Nil(sp()),
            Value::Str(s) => ast::Expr::Str(s, sp()),
            Value::Int(i) => ast::Expr::Int(i, sp()),
            Value::UInt(u) => ast::Expr::UInt(u, sp()),
            Value::Float(x) => ast::Expr::Float(x, sp()),
            Value::Bool(b) => ast::Expr::Bool(b, sp()),
            Value::Bytes(b) => ast::Expr::Bytes(b, sp()),
            Value::Names(_) => ast::Expr::Nil(sp()),
        },
        "ref" => ast::Expr::Ref(field_str(n, "name"), sp()),
        "call" => ast::Expr::Call(
            field_str(n, "name"),
            slot_all(g, n, "args")
                .iter()
                .map(|c| expr_air_to_ast(g, c))
                .collect::<Result<Vec<_>, _>>()?,
            sp(),
        ),
        "binary" => {
            let op = match field_str(n, "op").as_str() {
                "+" => ast::BinOp::Add,
                "-" => ast::BinOp::Sub,
                "*" => ast::BinOp::Mul,
                "/" => ast::BinOp::Div,
                "mod" => ast::BinOp::Mod,
                "==" => ast::BinOp::Eq,
                "!=" => ast::BinOp::Ne,
                "<" => ast::BinOp::Lt,
                "<=" => ast::BinOp::Le,
                ">" => ast::BinOp::Gt,
                ">=" => ast::BinOp::Ge,
                "and" => ast::BinOp::And,
                "or" => ast::BinOp::Or,
                other => return Err(format!("unknown binary op {other}")),
            };
            ast::Expr::Bin(
                op,
                Box::new(expr_air_to_ast(g, &slot_first(g, n, "left")?)?),
                Box::new(expr_air_to_ast(g, &slot_first(g, n, "right")?)?),
                sp(),
            )
        }
        "not" => ast::Expr::Not(Box::new(unary(g, n)?), sp()),
        "if" => ast::Expr::If(
            Box::new(expr_air_to_ast(g, &slot_first(g, n, "cond")?)?),
            Box::new(expr_air_to_ast(g, &slot_first(g, n, "then")?)?),
            Box::new(expr_air_to_ast(g, &slot_first(g, n, "else")?)?),
            sp(),
        ),
        "binding" => {
            let ty = n
                .slots
                .get("type")
                .and_then(|c| c.first())
                .map(|t| type_air_to_ast(g, t))
                .transpose()?;
            ast::Expr::Let(
                field_str(n, "name"),
                ty,
                Box::new(expr_air_to_ast(g, &slot_first(g, n, "value")?)?),
                Box::new(expr_air_to_ast(g, &slot_first(g, n, "body")?)?),
                sp(),
            )
        }
        "block" => ast::Expr::Block(
            slot_all(g, n, "steps")
                .iter()
                .map(|c| expr_air_to_ast(g, c))
                .collect::<Result<Vec<_>, _>>()?,
            sp(),
        ),
        "veclit" => ast::Expr::VecLit(
            type_air_to_ast(g, &slot_first(g, n, "elem_type")?)?,
            slot_all(g, n, "items")
                .iter()
                .map(|c| expr_air_to_ast(g, c))
                .collect::<Result<Vec<_>, _>>()?,
            sp(),
        ),
        "len" => ast::Expr::Len(Box::new(unary(g, n)?), sp()),
        "get" => bin(g, n, ast::Expr::Get)?,
        "append" => bin(g, n, ast::Expr::Append)?,
        "as" => ast::Expr::As(
            type_air_to_ast(g, &slot_first(g, n, "type")?)?,
            Box::new(expr_air_to_ast(g, &slot_first(g, n, "value")?)?),
            sp(),
        ),
        "fold" => ast::Expr::Fold(
            field_str(n, "index"),
            Box::new(expr_air_to_ast(g, &slot_first(g, n, "range_start")?)?),
            Box::new(expr_air_to_ast(g, &slot_first(g, n, "range_end")?)?),
            field_str(n, "acc_name"),
            type_air_to_ast(g, &slot_first(g, n, "acc_type")?)?,
            Box::new(expr_air_to_ast(g, &slot_first(g, n, "acc_init")?)?),
            Box::new(expr_air_to_ast(g, &slot_first(g, n, "body")?)?),
            sp(),
        ),
        "variant" => ast::Expr::Variant(field_str(n, "type"), field_str(n, "variant"), sp()),
        "match" => ast::Expr::Match(
            field_str(n, "type"),
            Box::new(expr_air_to_ast(g, &slot_first(g, n, "scrutinee")?)?),
            slot_all(g, n, "cases")
                .iter()
                .map(|c| {
                    let cn = g.get(c).ok_or("missing case")?;
                    Ok((
                        field_str(cn, "variant"),
                        expr_air_to_ast(g, &slot_first(g, cn, "body")?)?,
                    ))
                })
                .collect::<Result<Vec<_>, String>>()?,
            sp(),
        ),
        "maplit" => ast::Expr::MapLit(
            type_air_to_ast(g, &slot_first(g, n, "key_type")?)?,
            type_air_to_ast(g, &slot_first(g, n, "value_type")?)?,
            slot_all(g, n, "pairs")
                .iter()
                .map(|p| {
                    let pn = g.get(p).ok_or("missing pair")?;
                    Ok((
                        expr_air_to_ast(g, &slot_first(g, pn, "key")?)?,
                        expr_air_to_ast(g, &slot_first(g, pn, "value")?)?,
                    ))
                })
                .collect::<Result<Vec<_>, String>>()?,
            sp(),
        ),
        "set" => ast::Expr::Set(
            Box::new(expr_air_to_ast(g, &slot_first(g, n, "a")?)?),
            Box::new(expr_air_to_ast(g, &slot_first(g, n, "b")?)?),
            Box::new(expr_air_to_ast(g, &slot_first(g, n, "c")?)?),
            sp(),
        ),
        "lookup" => bin(g, n, ast::Expr::Lookup)?,
        "contains" => bin(g, n, ast::Expr::Contains)?,
        "veccontains" => bin(g, n, ast::Expr::VecContains)?,
        "any" => ast::Expr::Any(
            field_str(n, "elem_var"),
            Box::new(expr_air_to_ast(g, &slot_first(g, n, "collection")?)?),
            Box::new(expr_air_to_ast(g, &slot_first(g, n, "predicate")?)?),
            sp(),
        ),
        "all" => ast::Expr::All(
            field_str(n, "elem_var"),
            Box::new(expr_air_to_ast(g, &slot_first(g, n, "collection")?)?),
            Box::new(expr_air_to_ast(g, &slot_first(g, n, "predicate")?)?),
            sp(),
        ),
        "find" => ast::Expr::Find(
            field_str(n, "elem_var"),
            Box::new(expr_air_to_ast(g, &slot_first(g, n, "collection")?)?),
            Box::new(expr_air_to_ast(g, &slot_first(g, n, "predicate")?)?),
            sp(),
        ),
        "remove" => bin(g, n, ast::Expr::Remove)?,
        "keys" => ast::Expr::Keys(Box::new(unary(g, n)?), sp()),
        "unwrap" => ast::Expr::Unwrap(Box::new(unary(g, n)?), sp()),
        "errvalue" => ast::Expr::ErrValue(Box::new(unary(g, n)?), sp()),
        "slice" => ast::Expr::Slice(
            Box::new(expr_air_to_ast(g, &slot_first(g, n, "value")?)?),
            Box::new(expr_air_to_ast(g, &slot_first(g, n, "start")?)?),
            Box::new(expr_air_to_ast(g, &slot_first(g, n, "end")?)?),
            sp(),
        ),
        "split" => bin(g, n, ast::Expr::Split)?,
        "concat" => bin(g, n, ast::Expr::Concat)?,
        "tostring" => ast::Expr::ToString(Box::new(unary(g, n)?), sp()),
        "parseint" => ast::Expr::ParseInt(Box::new(unary(g, n)?), sp()),
        "tobytes" => ast::Expr::ToBytes(Box::new(unary(g, n)?), sp()),
        "isok" => ast::Expr::IsOk(Box::new(unary(g, n)?), sp()),
        "join" => bin(g, n, ast::Expr::Join)?,
        "stripprefix" => bin(g, n, ast::Expr::StripPrefix)?,
        "before" => bin(g, n, ast::Expr::Before)?,
        "endswith" => bin(g, n, ast::Expr::EndsWith)?,
        "sort" => ast::Expr::Sort(Box::new(unary(g, n)?), sp()),
        "urldecode" => ast::Expr::UrlDecode(Box::new(unary(g, n)?), sp()),
        "tohex" => ast::Expr::ToHex(Box::new(unary(g, n)?), sp()),
        "cteq" => bin(g, n, ast::Expr::CtEq)?,
        "loop" => {
            let inv = n
                .slots
                .get("inv")
                .and_then(|c| c.first())
                .map(|c| expr_air_to_ast(g, c).map(Box::new))
                .transpose()?;
            ast::Expr::Loop(
                field_str(n, "acc_name"),
                type_air_to_ast(g, &slot_first(g, n, "acc_type")?)?,
                Box::new(expr_air_to_ast(g, &slot_first(g, n, "init")?)?),
                inv,
                Box::new(expr_air_to_ast(g, &slot_first(g, n, "cond")?)?),
                Box::new(expr_air_to_ast(g, &slot_first(g, n, "body")?)?),
                sp(),
            )
        }
        "record" => ast::Expr::Record(
            field_str(n, "type"),
            slot_all(g, n, "fields")
                .iter()
                .map(|f| {
                    let fn_ = g.get(f).ok_or("missing record field")?;
                    Ok((
                        field_str(fn_, "name"),
                        expr_air_to_ast(g, &slot_first(g, fn_, "value")?)?,
                    ))
                })
                .collect::<Result<Vec<_>, String>>()?,
            sp(),
        ),
        "record_update" => ast::Expr::RecordUpdate(
            field_str(n, "type"),
            Box::new(expr_air_to_ast(g, &slot_first(g, n, "base")?)?),
            slot_all(g, n, "updates")
                .iter()
                .map(|f| {
                    let fn_ = g.get(f).ok_or("missing update field")?;
                    Ok((
                        field_str(fn_, "name"),
                        expr_air_to_ast(g, &slot_first(g, fn_, "value")?)?,
                    ))
                })
                .collect::<Result<Vec<_>, String>>()?,
            sp(),
        ),
        "field" => ast::Expr::Field(
            Box::new(expr_air_to_ast(g, &slot_first(g, n, "value")?)?),
            field_str(n, "name"),
            sp(),
        ),
        "raise" => ast::Expr::Raise(Box::new(unary(g, n)?), sp()),
        "try" => ast::Expr::Try(
            Box::new(expr_air_to_ast(g, &slot_first(g, n, "value")?)?),
            field_str(n, "catch_name"),
            Box::new(expr_air_to_ast(g, &slot_first(g, n, "catch")?)?),
            sp(),
        ),
        "ok" => ast::Expr::Ok(Box::new(unary(g, n)?), sp()),
        "err" => ast::Expr::Err(Box::new(unary(g, n)?), sp()),
        other => return Err(format!("cannot reconstruct expr kind {other}")),
    })
}

pub fn air_to_module(g: &AirGraph, module_entity: &str) -> Result<ast::Module, String> {
    let root = g
        .heads
        .get(module_entity)
        .ok_or_else(|| format!("module entity {module_entity} has no head"))?;
    let n = g.get(root).ok_or("missing module node")?;
    let mut module = ast::Module {
        name: field_str(n, "name"),
        version: field_str(n, "version"),
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
    if let Some(Value::Names(ns)) = n.fields.get("deps") {
        for d in ns {
            if let Some((name, ver)) = d.split_once('@') {
                module.deps.push((name.to_string(), ver.to_string()));
            }
        }
    }
    if let Some(Value::Names(ns)) = n.fields.get("rust_deps") {
        for d in ns {
            if let Some((name, ver)) = d.split_once('@') {
                module.rust_deps.push((name.to_string(), ver.to_string()));
            }
        }
    }
    if let Some(Value::Names(ns)) = n.fields.get("caps") {
        module.caps = ns.clone();
    }
    if let Some(Value::Names(ns)) = n.fields.get("exports") {
        module.exports = ns.clone();
    }
    for t in slot_all(g, n, "types") {
        module.types.push(type_air_to_ast_def(g, &t)?);
    }
    for e in slot_all(g, n, "externs") {
        module.exts.push(extern_air_to_ast(g, &e)?);
    }
    for f in slot_all(g, n, "functions") {
        module.fns.push(fn_air_to_ast(g, &f)?);
    }
    for t in slot_all(g, n, "tests") {
        let tn = g.get(&t).ok_or("missing test")?;
        module.tests.push(ast::TestDef {
            name: field_str(tn, "name"),
            body: expr_air_to_ast(g, &slot_first(g, tn, "body")?)?,
            span: crate::s_expr::Span { line: 0, col: 0 },
        });
    }
    for b in slot_all(g, n, "benches") {
        let bn = g.get(&b).ok_or("missing bench")?;
        module.benches.push(ast::BenchDef {
            name: field_str(bn, "name"),
            ms_budget: bn.fields.get("ms_budget").and_then(|v| match v {
                Value::Int(i) => Some(*i),
                _ => None,
            }),
            setup: slot_all(g, bn, "setup")
                .iter()
                .map(|c| expr_air_to_ast(g, c))
                .collect::<Result<Vec<_>, _>>()?,
            body: expr_air_to_ast(g, &slot_first(g, bn, "body")?)?,
            span: crate::s_expr::Span { line: 0, col: 0 },
        });
    }
    Ok(module)
}

fn type_air_to_ast_def(g: &AirGraph, id: &str) -> Result<ast::TypeDef, String> {
    let n = g.get(id).ok_or("missing type")?;
    let span = crate::s_expr::Span { line: 0, col: 0 };
    let kind = match field_str(n, "kind").as_str() {
        "record" => ast::TypeKind::Record(
            slot_all(g, n, "fields")
                .iter()
                .map(|f| {
                    let fn_ = g.get(f).ok_or("missing type field")?;
                    Ok((
                        field_str(fn_, "name"),
                        type_air_to_ast(g, &slot_first(g, fn_, "type")?)?,
                    ))
                })
                .collect::<Result<Vec<_>, String>>()?,
        ),
        "enum" => match n.fields.get("variants") {
            Some(Value::Names(ns)) => ast::TypeKind::Enum(ns.clone()),
            _ => return Err("enum missing variants".to_string()),
        },
        "alias" => ast::TypeKind::Alias(type_air_to_ast(g, &slot_first(g, n, "alias")?)?),
        other => return Err(format!("unknown type kind {other}")),
    };
    Ok(ast::TypeDef {
        name: field_str(n, "name"),
        kind,
        span,
    })
}

fn fn_air_to_ast(g: &AirGraph, id: &str) -> Result<ast::FnDef, String> {
    let n = g.get(id).ok_or("missing function")?;
    let span = crate::s_expr::Span { line: 0, col: 0 };
    let eff = match n.fields.get("eff") {
        Some(Value::Names(ns)) => ns.clone(),
        _ => Vec::new(),
    };
    Ok(ast::FnDef {
        name: field_str(n, "name"),
        params: slot_all(g, n, "params")
            .iter()
            .map(|p| {
                let pn = g.get(p).ok_or("missing param")?;
                Ok((
                    field_str(pn, "name"),
                    type_air_to_ast(g, &slot_first(g, pn, "type")?)?,
                ))
            })
            .collect::<Result<Vec<_>, String>>()?,
        returns: type_air_to_ast(g, &slot_first(g, n, "returns")?)?,
        pre: slot_all(g, n, "pre")
            .iter()
            .map(|c| contract_air_to_ast(g, c))
            .collect::<Result<Vec<_>, _>>()?,
        post: slot_all(g, n, "post")
            .iter()
            .map(|c| contract_air_to_ast(g, c))
            .collect::<Result<Vec<_>, _>>()?,
        inv: slot_all(g, n, "inv")
            .iter()
            .map(|c| contract_air_to_ast(g, c))
            .collect::<Result<Vec<_>, _>>()?,
        pure: n
            .fields
            .get("pure")
            .map(|v| v == &Value::Bool(true))
            .unwrap_or(false),
        eff,
        body: slot_all(g, n, "body")
            .first()
            .map(|b| {
                let bn = g.get(b).ok_or("missing body")?;
                slot_all(g, bn, "steps")
                    .iter()
                    .map(|c| expr_air_to_ast(g, c))
                    .collect::<Result<Vec<_>, _>>()
            })
            .unwrap_or(Ok(Vec::new()))?,
        span,
    })
}

fn contract_air_to_ast(g: &AirGraph, id: &str) -> Result<ast::Expr, String> {
    let n = g.get(id).ok_or("missing contract")?;
    expr_air_to_ast(g, &slot_first(g, n, "expr")?)
}

fn extern_air_to_ast(g: &AirGraph, id: &str) -> Result<ast::ExternDef, String> {
    let n = g.get(id).ok_or("missing extern")?;
    let span = crate::s_expr::Span { line: 0, col: 0 };
    let eff = match n.fields.get("eff") {
        Some(Value::Names(ns)) => ns.clone(),
        _ => Vec::new(),
    };
    Ok(ast::ExternDef {
        name: field_str(n, "name"),
        params: slot_all(g, n, "params")
            .iter()
            .map(|p| {
                let pn = g.get(p).ok_or("missing param")?;
                Ok((
                    field_str(pn, "name"),
                    type_air_to_ast(g, &slot_first(g, pn, "type")?)?,
                ))
            })
            .collect::<Result<Vec<_>, String>>()?,
        returns: type_air_to_ast(g, &slot_first(g, n, "returns")?)?,
        eff,
        pure: n
            .fields
            .get("pure")
            .map(|v| v == &Value::Bool(true))
            .unwrap_or(false),
        unsafe_ffi: n
            .fields
            .get("unsafe")
            .map(|v| v == &Value::Bool(true))
            .unwrap_or(false),
        template: field_str(n, "template"),
        span,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cycle_detection_self_and_two_node() {
        let mut g = AirGraph::new();
        let a = g.add("block", "", BTreeMap::new(), BTreeMap::new());
        let mut s = BTreeMap::new();
        s.insert("steps".to_string(), vec![a.clone()]);
        g.nodes.get_mut(&a).unwrap().slots = s;
        g.module_entities.push("module:m".to_string());
        g.heads.insert("module:m".to_string(), a.clone());
        assert!(!detect_cycles(&g).is_empty());

        let mut g2 = AirGraph::new();
        let x = g2.add("block", "", BTreeMap::new(), BTreeMap::new());
        let y = g2.add("block", "", BTreeMap::new(), BTreeMap::new());
        let mut s1 = BTreeMap::new();
        s1.insert("steps".to_string(), vec![y.clone()]);
        g2.nodes.get_mut(&x).unwrap().slots = s1;
        let mut s2 = BTreeMap::new();
        s2.insert("steps".to_string(), vec![x.clone()]);
        g2.nodes.get_mut(&y).unwrap().slots = s2;
        g2.module_entities.push("module:m".to_string());
        g2.heads.insert("module:m".to_string(), x.clone());
        assert!(!detect_cycles(&g2).is_empty());
    }

    #[test]
    fn shared_dag_is_not_a_cycle() {
        let mut g = AirGraph::new();
        let leaf = g.add("literal", "", BTreeMap::new(), BTreeMap::new());
        let mut s = BTreeMap::new();
        s.insert("steps".to_string(), vec![leaf.clone(), leaf.clone()]);
        let mid1 = g.add("block", "", BTreeMap::new(), s.clone());
        let mid2 = g.add("block", "", BTreeMap::new(), s);
        let mut root_s = BTreeMap::new();
        root_s.insert("steps".to_string(), vec![mid1.clone(), mid2.clone()]);
        let root = g.add("block", "", BTreeMap::new(), root_s);
        g.module_entities.push("module:m".to_string());
        g.heads.insert("module:m".to_string(), root);
        assert!(detect_cycles(&g).is_empty());
    }

    #[test]
    fn serialize_reserialize_is_canonical() {
        let mut g = AirGraph::new();
        let lit = g.add(
            "literal",
            "",
            BTreeMap::from([("value".to_string(), Value::Int(5))]),
            BTreeMap::new(),
        );
        let mut s = BTreeMap::new();
        s.insert("steps".to_string(), vec![lit]);
        let root = g.add("block", "", BTreeMap::new(), s);
        g.module_entities.push("module:m".to_string());
        g.heads.insert("module:m".to_string(), root);
        let bytes = graph_to_bytes(&g);
        let g2 = graph_from_bytes(&bytes).unwrap();
        assert_eq!(bytes, graph_to_bytes(&g2));
        assert!(g2.verify().is_empty());
    }

    #[test]
    fn random_bytes_never_panic() {
        let mut seed = 0x1234_5678u64;
        for _ in 0..200 {
            seed ^= seed << 13;
            seed ^= seed >> 7;
            seed ^= seed << 17;
            let mut data = Vec::with_capacity(64);
            for _ in 0..64 {
                data.push((seed & 0xFF) as u8);
                seed = seed
                    .wrapping_mul(6364136223846793005)
                    .wrapping_add(1442695040888963407);
            }
            let _ = graph_from_bytes(&data);
        }
    }

    #[test]
    fn malformed_inputs_rejected_without_panic() {
        assert!(graph_from_bytes(b"ALVA").is_err());
        let mut g = AirGraph::new();
        g.module_entities.push("module:m".to_string());
        let mut bytes = graph_to_bytes(&g);
        bytes.push(0xDE);
        assert!(graph_from_bytes(&bytes).is_err());
    }

    #[test]
    fn lexical_scope_ancestor_path() {
        let mut g = AirGraph::new();
        let ty_str = g.add(
            "type_expr",
            "",
            BTreeMap::from([
                ("shape".to_string(), Value::Str("prim".to_string())),
                ("name".to_string(), Value::Str("string".to_string())),
            ]),
            BTreeMap::new(),
        );
        let p_ref = g.add(
            "ref",
            "",
            BTreeMap::from([("name".to_string(), Value::Str("p".to_string()))]),
            BTreeMap::new(),
        );
        let outer_lit = g.add(
            "literal",
            "",
            BTreeMap::from([("value".to_string(), Value::Str("o".to_string()))]),
            BTreeMap::new(),
        );
        let mut vs = BTreeMap::new();
        vs.insert("value".to_string(), vec![outer_lit.clone()]);
        let outer = g.add(
            "binding",
            "",
            BTreeMap::from([("name".to_string(), Value::Str("outer".to_string()))]),
            vs,
        );
        let hole = g.add(
            "hole",
            "",
            BTreeMap::from([(
                "expected_type".to_string(),
                Value::Str("string".to_string()),
            )]),
            BTreeMap::new(),
        );
        // inner binding: value = hole, body = ref p
        let mut iv = BTreeMap::new();
        iv.insert("value".to_string(), vec![hole.clone()]);
        iv.insert("body".to_string(), vec![p_ref.clone()]);
        let inner = g.add(
            "binding",
            "",
            BTreeMap::from([("name".to_string(), Value::Str("inner".to_string()))]),
            iv,
        );
        let mut os = BTreeMap::new();
        os.insert("value".to_string(), vec![outer_lit.clone()]);
        os.insert("body".to_string(), vec![inner.clone()]);
        // outer is already added; rebuild binding with body
        g.nodes.get_mut(&outer).unwrap().slots = os;
        let mut bs = BTreeMap::new();
        bs.insert("steps".to_string(), vec![outer.clone()]);
        let block = g.add("block", "", BTreeMap::new(), bs);
        let param = g.add(
            "param",
            "",
            BTreeMap::from([("name".to_string(), Value::Str("p".to_string()))]),
            BTreeMap::from([("type".to_string(), vec![ty_str.clone()])]),
        );
        let mut fs = BTreeMap::new();
        fs.insert("params".to_string(), vec![param.clone()]);
        fs.insert("returns".to_string(), vec![ty_str.clone()]);
        fs.insert("body".to_string(), vec![block.clone()]);
        let f = g.add(
            "function",
            "",
            BTreeMap::from([("name".to_string(), Value::Str("f".to_string()))]),
            fs,
        );
        let mut ms = BTreeMap::new();
        ms.insert("functions".to_string(), vec![f.clone()]);
        let m = g.add(
            "module",
            "",
            BTreeMap::from([("name".to_string(), Value::Str("m".to_string()))]),
            ms,
        );
        g.module_entities.push("module:m".to_string());
        g.heads.insert("module:m".to_string(), m.clone());
        g.rebuild_revisions();
        let (_fid, scope) = lexical_scope(&g, &g.resolve_rev(&hole).unwrap());
        let names: Vec<String> = scope.iter().map(|(n, _)| n.clone()).collect();
        // hole is in inner's VALUE -> inner invisible, outer visible, param visible
        assert!(!names.contains(&"inner".to_string()));
        assert!(names.contains(&"outer".to_string()));
        assert!(names.contains(&"p".to_string()));
    }

    #[test]
    fn normalize_handle_representation_only() {
        assert_eq!(normalize_handle("  'rfc0005.a.a_fn'  "), "rfc0005.a.a_fn");
        assert_eq!(
            normalize_handle("function:rfc0005.a.a_fn"),
            "rfc0005.a.a_fn"
        );
        assert_eq!(normalize_handle("module:rfc0005.a"), "rfc0005.a");
        assert_eq!(
            normalize_handle("module:rfc0005.a/fn:a_fn/body:0/st:0"),
            "module:rfc0005.a/fn:a_fn"
        );
        assert_eq!(
            normalize_handle("module:rfc0005.a/fn:a_fn"),
            "module:rfc0005.a/fn:a_fn"
        );
        assert_eq!(normalize_handle("no_such_fn"), "no_such_fn");
    }

    #[test]
    fn canonical_resolution_is_strict() {
        let mut g = AirGraph::new();
        // module m with two functions ("a", "b")
        let mut fs = BTreeMap::new();
        for (name, entity) in [("a", "module:m/fn:a"), ("b", "module:m/fn:b")] {
            let f = g.add(
                "function",
                entity,
                BTreeMap::from([("name".to_string(), Value::Str(name.to_string()))]),
                BTreeMap::new(),
            );
            fs.insert(entity.to_string(), f);
        }
        let m = g.add(
            "module",
            "module:m",
            BTreeMap::from([("name".to_string(), Value::Str("m".to_string()))]),
            BTreeMap::from([("functions".to_string(), fs.values().cloned().collect())]),
        );
        g.module_entities.push("module:m".to_string());
        g.heads.insert("module:m".to_string(), m.clone());
        // unqualified "a" resolves uniquely
        match resolve_canonical(&g, "a", &["function"]) {
            CanonicalOutcome::Resolved(e) => assert_eq!(e, "module:m/fn:a"),
            other => panic!("expected Resolved, got {other:?}"),
        }
        // entity-path resolves
        match resolve_canonical(&g, "module:m/fn:b", &["function"]) {
            CanonicalOutcome::Resolved(e) => assert_eq!(e, "module:m/fn:b"),
            other => panic!("expected Resolved, got {other:?}"),
        }
        // module name with function expectation -> WrongKind (NAVIGATION kept)
        match resolve_canonical(&g, "m", &["function"]) {
            CanonicalOutcome::WrongKind { kind, .. } => assert_eq!(kind, "module"),
            other => panic!("expected WrongKind, got {other:?}"),
        }
        // unknown -> NotFound
        assert!(matches!(
            resolve_canonical(&g, "no_such", &["function"]),
            CanonicalOutcome::NotFound
        ));
    }
}
