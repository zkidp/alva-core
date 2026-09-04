//! Transport-neutral state and lifecycle for one AEP editing session.

use std::collections::BTreeMap;
use std::io::Write;
use std::path::{Component, Path, PathBuf};

use crate::{air, project};
use sha2::{Digest, Sha256};

#[derive(Debug, PartialEq, Eq)]
pub(crate) struct CommitResult {
    pub(crate) generation: u64,
    pub(crate) revision: String,
}

#[derive(Debug, PartialEq, Eq)]
pub(crate) struct TextPatchResult {
    pub(crate) path: String,
    pub(crate) replacements: usize,
    pub(crate) content_sha256: String,
    pub(crate) revision: String,
}

#[derive(Debug, PartialEq, Eq)]
pub(crate) struct SourceProjectionPreview {
    pub(crate) path: String,
    pub(crate) source_sha256: String,
    pub(crate) projection_sha256: String,
    pub(crate) revision: String,
    pub(crate) changed: bool,
    pub(crate) projection_preview: String,
    pub(crate) projection_truncated: bool,
}

#[derive(Debug, PartialEq, Eq)]
pub(crate) struct SourceProjectionResult {
    pub(crate) path: String,
    pub(crate) source_sha256: String,
    pub(crate) projection_sha256: String,
    pub(crate) revision: String,
    pub(crate) changed: bool,
    pub(crate) all_sources_converged: bool,
}

#[derive(Debug, PartialEq, Eq)]
pub(crate) struct TransactionWorkReport {
    pub(crate) stored_nodes: usize,
    pub(crate) reachable_nodes: usize,
    pub(crate) base_reachable_nodes: usize,
    pub(crate) reused_reachable_nodes: usize,
    pub(crate) added_reachable_nodes: usize,
    pub(crate) removed_reachable_nodes: usize,
    pub(crate) changed_module_count: usize,
    pub(crate) changed_modules: Vec<String>,
    pub(crate) changed_modules_truncated: bool,
    pub(crate) rebuild_root_modules: usize,
    pub(crate) rebuild_node_visits: usize,
    pub(crate) rebuild_unique_nodes_visited: usize,
    pub(crate) rebuild_rewritten_nodes: usize,
    pub(crate) full_check_runs: u64,
    pub(crate) graph_construction_scope: &'static str,
    pub(crate) semantic_check_scope: &'static str,
}

struct SourceDocument {
    module_name: String,
    path: PathBuf,
    text: String,
    disk_sha256: String,
    content_sha256: String,
}

#[derive(Default)]
pub(crate) struct AgentRuntime {
    session: Option<air::EditSession>,
    base_graph: Option<air::AirGraph>,
    project_dir: PathBuf,
    source_documents: BTreeMap<PathBuf, SourceDocument>,
    source_order: Vec<PathBuf>,
    source_projection_revision: Option<String>,
    text_input_staged: bool,
}

impl AgentRuntime {
    pub(crate) fn session_mut(&mut self) -> Result<&mut air::EditSession, String> {
        self.session
            .as_mut()
            .ok_or_else(|| "E_AEP_NO_TRANSACTION".to_string())
    }

    pub(crate) fn begin(&mut self, file: &str) -> Result<String, String> {
        if file.is_empty() {
            return Err("begin_transaction requires 'project'".to_string());
        }
        let manifest = Path::new(file);
        let project = project::load_project(manifest)?;
        let project_dir = manifest.parent().unwrap_or(Path::new("."));
        let has_authoritative = project_dir
            .join(air::AIR_STORE_DIR)
            .join("current")
            .exists();
        let graph = if has_authoritative {
            air::load_authoritative(project_dir)?
        } else {
            project::to_air(&project)?.0
        };
        let revision = graph.semantic_hash();
        let mut source_documents = BTreeMap::new();
        let mut source_order = Vec::new();
        for (module_name, path) in &project.modules {
            let Ok(canonical) = std::fs::canonicalize(path) else {
                continue;
            };
            let Ok(text) = std::fs::read_to_string(&canonical) else {
                continue;
            };
            source_order.push(canonical.clone());
            source_documents.insert(
                canonical.clone(),
                SourceDocument {
                    module_name: module_name.clone(),
                    path: canonical,
                    disk_sha256: sha256_text(&text),
                    content_sha256: sha256_text(&text),
                    text,
                },
            );
        }
        let source_projection_revision = if source_documents.len() == project.modules.len() {
            source_graph(&source_documents, &source_order)
                .ok()
                .map(|graph| graph.semantic_hash())
        } else {
            None
        };
        self.project_dir = project_dir.to_path_buf();
        self.base_graph = Some(graph.clone());
        self.session = Some(air::EditSession::begin(graph, revision.clone()));
        self.source_documents = source_documents;
        self.source_order = source_order;
        self.source_projection_revision = source_projection_revision;
        self.text_input_staged = false;
        Ok(revision)
    }

    pub(crate) fn check(&mut self) -> Result<(), String> {
        let errors = self.check_problems()?;
        if errors.is_empty() {
            Ok(())
        } else {
            Err(format!("check failed: {}", errors.join("; ")))
        }
    }

    pub(crate) fn check_problems(&mut self) -> Result<Vec<String>, String> {
        Ok(self.session_mut()?.check())
    }

    pub(crate) fn preview_semantic_diff(&mut self) -> Result<String, String> {
        let empty = air::AirGraph::new();
        let base = self.base_graph.as_ref().unwrap_or(&empty);
        let session = self
            .session
            .as_mut()
            .ok_or_else(|| "E_AEP_NO_TRANSACTION".to_string())?;
        Ok(session.diff_vs_base(base).summary.trim().to_string())
    }

    /// Report actual transaction work and revision reuse. This intentionally
    /// identifies the current full-project paths so later incremental changes
    /// can be compared against a stable, model-free baseline.
    pub(crate) fn inspect_transaction_work(&self) -> Result<TransactionWorkReport, String> {
        let session = self
            .session
            .as_ref()
            .ok_or_else(|| "E_AEP_NO_TRANSACTION".to_string())?;
        let base = self
            .base_graph
            .as_ref()
            .ok_or_else(|| "E_AEP_NO_TRANSACTION".to_string())?;
        let reachable = session.graph.reachable();
        let base_reachable = base.reachable();
        let reused_reachable_nodes = reachable.intersection(&base_reachable).count();
        let added_reachable_nodes = reachable.difference(&base_reachable).count();
        let removed_reachable_nodes = base_reachable.difference(&reachable).count();
        let mut all_changed_modules = session
            .graph
            .module_entities
            .iter()
            .chain(base.module_entities.iter())
            .filter(|module| session.graph.heads.get(*module) != base.heads.get(*module))
            .cloned()
            .collect::<std::collections::BTreeSet<_>>()
            .into_iter()
            .collect::<Vec<_>>();
        let changed_module_count = all_changed_modules.len();
        let changed_modules_truncated = changed_module_count > 32;
        all_changed_modules.truncate(32);
        let rebuild = session.last_rebuild_stats.clone().unwrap_or_default();
        Ok(TransactionWorkReport {
            stored_nodes: session.graph.nodes.len(),
            reachable_nodes: reachable.len(),
            base_reachable_nodes: base_reachable.len(),
            reused_reachable_nodes,
            added_reachable_nodes,
            removed_reachable_nodes,
            changed_module_count,
            changed_modules: all_changed_modules,
            changed_modules_truncated,
            rebuild_root_modules: rebuild.root_modules,
            rebuild_node_visits: rebuild.node_visits,
            rebuild_unique_nodes_visited: rebuild.unique_nodes_visited,
            rebuild_rewritten_nodes: rebuild.rewritten_nodes,
            full_check_runs: session.full_check_runs,
            graph_construction_scope: if self.text_input_staged {
                "full_project_source_reparse"
            } else if session.last_rebuild_stats.is_some() {
                "all_module_roots_revision_rebuild"
            } else {
                "none_since_begin"
            },
            semantic_check_scope: "full_project_when_check_runs",
        })
    }

    pub(crate) fn commit(&mut self) -> Result<CommitResult, String> {
        self.verify_text_sources_unchanged()?;
        let Some(mut session) = self.session.take() else {
            return Err("E_AEP_NO_TRANSACTION".to_string());
        };
        let errors = session.check();
        if !errors.is_empty() {
            self.session = Some(session);
            return Err(format!("check failed: {}", errors.join("; ")));
        }
        let base = session.base_hash.clone();
        match air::write_authoritative(&self.project_dir, &session.graph, Some(&base)) {
            Ok(generation) => Ok(CommitResult {
                generation,
                revision: session.graph.semantic_hash(),
            }),
            Err(error) => {
                self.session = Some(session);
                Err(error)
            }
        }
    }

    pub(crate) fn abort(&mut self) {
        self.session = None;
    }

    pub(crate) fn stage_text_patch(
        &mut self,
        path: &str,
        expected_sha256: &str,
        old: &str,
        new: &str,
        replace_all: bool,
    ) -> Result<TextPatchResult, String> {
        self.session_mut()?;
        if path.is_empty() || Path::new(path).is_absolute() {
            return Err("E_AEP_TEXT_PATH: path must be project-relative".to_string());
        }
        if Path::new(path).components().any(|component| {
            matches!(
                component,
                Component::ParentDir | Component::RootDir | Component::Prefix(_)
            )
        }) {
            return Err("E_AEP_TEXT_PATH: path traversal is forbidden".to_string());
        }
        let requested = std::fs::canonicalize(self.project_dir.join(path))
            .map_err(|error| format!("E_AEP_TEXT_PATH: cannot resolve '{path}': {error}"))?;
        let Some(current_projection) = self.source_projection_revision.as_deref() else {
            return Err(
                "E_AEP_TEXT_SOURCE_UNAVAILABLE: complete checked module sources are required"
                    .to_string(),
            );
        };
        let current_revision = self
            .session
            .as_ref()
            .map(|session| session.graph.semantic_hash())
            .ok_or_else(|| "E_AEP_NO_TRANSACTION".to_string())?;
        if current_revision != current_projection {
            return Err(
                "E_AEP_TEXT_MIXED_MODE: text patch requires an unchanged source-derived transaction graph"
                    .to_string(),
            );
        }
        let document = self.source_documents.get(&requested).ok_or_else(|| {
            "E_AEP_TEXT_PATH: path is not a manifest-declared module source".to_string()
        })?;
        let disk = std::fs::read_to_string(&document.path)
            .map_err(|error| format!("E_AEP_TEXT_SOURCE_CHANGED: {error}"))?;
        if sha256_text(&disk) != document.disk_sha256 {
            return Err(
                "E_AEP_TEXT_SOURCE_CHANGED: module bytes changed after transaction begin"
                    .to_string(),
            );
        }
        if expected_sha256 != document.content_sha256 {
            return Err(format!(
                "E_AEP_TEXT_STALE: expected {} but current content is {}",
                expected_sha256, document.content_sha256
            ));
        }
        if old.is_empty() {
            return Err("E_AEP_TEXT_PATCH: old text must not be empty".to_string());
        }
        let occurrences = document.text.match_indices(old).count();
        if occurrences == 0 {
            return Err("E_AEP_TEXT_PATCH: old text was not found".to_string());
        }
        if !replace_all && occurrences != 1 {
            return Err(format!(
                "E_AEP_TEXT_PATCH_AMBIGUOUS: old text occurs {occurrences} times"
            ));
        }
        let patched_text = if replace_all {
            document.text.replace(old, new)
        } else {
            document.text.replacen(old, new, 1)
        };
        let limits = crate::s_expr::Limits::from_env();
        if patched_text.len() > limits.max_source_bytes {
            return Err(format!(
                "E_AEP_TEXT_TOO_LARGE: patched source is {} bytes, limit {}",
                patched_text.len(),
                limits.max_source_bytes
            ));
        }
        let sources = self
            .source_order
            .iter()
            .map(|source_path| {
                let source = &self.source_documents[source_path];
                let text = if source_path == &requested {
                    patched_text.clone()
                } else {
                    source.text.clone()
                };
                (source.module_name.clone(), text)
            })
            .collect::<Vec<_>>();
        let graph = project::graph_from_source_texts(&sources)
            .map_err(|problems| format!("E_AEP_TEXT_CHECK: {}", problems.join("; ")))?;
        let revision = graph.semantic_hash();
        let content_sha256 = sha256_text(&patched_text);
        let session = self.session_mut()?;
        session.graph = graph;
        session.errors.clear();
        let document = self.source_documents.get_mut(&requested).unwrap();
        document.text = patched_text;
        document.content_sha256 = content_sha256.clone();
        self.source_projection_revision = Some(revision.clone());
        self.text_input_staged = true;
        Ok(TextPatchResult {
            path: path.to_string(),
            replacements: if replace_all { occurrences } else { 1 },
            content_sha256,
            revision,
        })
    }

    /// Render the authoritative transaction graph back to canonical `.alva`
    /// without changing either AIR or source bytes. The entire manifest source
    /// set must round-trip to the same semantic revision before any individual
    /// projection is offered.
    pub(crate) fn preview_source_projection(
        &self,
        path: &str,
    ) -> Result<SourceProjectionPreview, String> {
        let requested = self.resolve_source_path(path)?;
        let projections = self.canonical_projection_set()?;
        let projection = &projections[&requested];
        let document = &self.source_documents[&requested];
        let projection_sha256 = sha256_text(projection);
        let revision = self.session_revision()?;
        let max_preview_bytes = 4096;
        let (projection_preview, projection_truncated) =
            bounded_utf8_prefix(projection, max_preview_bytes);
        Ok(SourceProjectionPreview {
            path: path.to_string(),
            source_sha256: document.content_sha256.clone(),
            projection_sha256,
            revision,
            changed: projection != &document.text,
            projection_preview,
            projection_truncated,
        })
    }

    /// Explicitly materialize one canonical AIR projection into a manifest
    /// source file. This is deliberately separate from semantic commit: it is
    /// a CAS-protected projection write, not an atomic AIR+source transaction.
    pub(crate) fn materialize_source_projection(
        &mut self,
        path: &str,
        expected_source_sha256: &str,
        expected_projection_sha256: &str,
        expected_revision: &str,
    ) -> Result<SourceProjectionResult, String> {
        let requested = self.resolve_source_path(path)?;
        let revision = self.session_revision()?;
        if revision != expected_revision {
            return Err(format!(
                "E_AEP_PROJECTION_STALE_AIR: expected {expected_revision} but transaction revision is {revision}"
            ));
        }
        let base_revision = self
            .base_graph
            .as_ref()
            .map(air::AirGraph::semantic_hash)
            .ok_or_else(|| "E_AEP_NO_TRANSACTION".to_string())?;
        if revision != base_revision {
            return Err(
                "E_AEP_PROJECTION_UNCOMMITTED: commit semantic changes before materializing source"
                    .to_string(),
            );
        }
        let projections = self.canonical_projection_set()?;
        let projection = projections[&requested].clone();
        let projection_sha256 = sha256_text(&projection);
        if projection_sha256 != expected_projection_sha256 {
            return Err(format!(
                "E_AEP_PROJECTION_STALE_OUTPUT: expected {expected_projection_sha256} but canonical projection is {projection_sha256}"
            ));
        }
        let document = &self.source_documents[&requested];
        if document.content_sha256 != expected_source_sha256 {
            return Err(format!(
                "E_AEP_PROJECTION_STALE_SOURCE: expected {expected_source_sha256} but transaction source is {}",
                document.content_sha256
            ));
        }
        let disk = std::fs::read_to_string(&document.path)
            .map_err(|error| format!("E_AEP_PROJECTION_SOURCE_CHANGED: {error}"))?;
        if sha256_text(&disk) != document.disk_sha256 {
            return Err(
                "E_AEP_PROJECTION_SOURCE_CHANGED: module bytes changed after transaction begin"
                    .to_string(),
            );
        }

        // Serialize projection writes with authoritative commits. Re-read AIR
        // under that lock so a concurrent commit cannot be projected by this
        // stale transaction.
        let store = self.project_dir.join(air::AIR_STORE_DIR);
        std::fs::create_dir_all(&store).map_err(|error| error.to_string())?;
        let _lock = air::acquire_store_lock(&store)?;
        let current = air::load_authoritative(&self.project_dir)?;
        let current_revision = current.semantic_hash();
        if current_revision != revision {
            return Err(format!(
                "E_AEP_PROJECTION_CONFLICT: authoritative revision {current_revision} != transaction revision {revision}"
            ));
        }
        let disk = std::fs::read_to_string(&requested)
            .map_err(|error| format!("E_AEP_PROJECTION_SOURCE_CHANGED: {error}"))?;
        if sha256_text(&disk) != expected_source_sha256 {
            return Err(
                "E_AEP_PROJECTION_SOURCE_CHANGED: module bytes changed before projection write"
                    .to_string(),
            );
        }
        let changed = disk != projection;
        if changed {
            atomic_replace_source(&requested, projection.as_bytes())?;
        }

        let document = self.source_documents.get_mut(&requested).unwrap();
        document.text = projection;
        document.disk_sha256 = projection_sha256.clone();
        document.content_sha256 = projection_sha256.clone();
        let projected_revision = source_graph(&self.source_documents, &self.source_order)
            .ok()
            .map(|graph| graph.semantic_hash());
        let all_sources_converged = projected_revision.as_deref() == Some(revision.as_str());
        self.source_projection_revision = projected_revision;
        self.text_input_staged = false;
        Ok(SourceProjectionResult {
            path: path.to_string(),
            source_sha256: expected_source_sha256.to_string(),
            projection_sha256,
            revision,
            changed,
            all_sources_converged,
        })
    }

    fn resolve_source_path(&self, path: &str) -> Result<PathBuf, String> {
        self.session
            .as_ref()
            .ok_or_else(|| "E_AEP_NO_TRANSACTION".to_string())?;
        if path.is_empty() || Path::new(path).is_absolute() {
            return Err("E_AEP_PROJECTION_PATH: path must be project-relative".to_string());
        }
        if Path::new(path).components().any(|component| {
            matches!(
                component,
                Component::ParentDir | Component::RootDir | Component::Prefix(_)
            )
        }) {
            return Err("E_AEP_PROJECTION_PATH: path traversal is forbidden".to_string());
        }
        let requested = std::fs::canonicalize(self.project_dir.join(path))
            .map_err(|error| format!("E_AEP_PROJECTION_PATH: cannot resolve '{path}': {error}"))?;
        if !self.source_documents.contains_key(&requested) {
            return Err(
                "E_AEP_PROJECTION_PATH: path is not a manifest-declared module source".to_string(),
            );
        }
        Ok(requested)
    }

    fn session_revision(&self) -> Result<String, String> {
        self.session
            .as_ref()
            .map(|session| session.graph.semantic_hash())
            .ok_or_else(|| "E_AEP_NO_TRANSACTION".to_string())
    }

    fn canonical_projection_set(&self) -> Result<BTreeMap<PathBuf, String>, String> {
        let session = self
            .session
            .as_ref()
            .ok_or_else(|| "E_AEP_NO_TRANSACTION".to_string())?;
        if self.source_documents.is_empty() {
            return Err("E_AEP_PROJECTION_SOURCE_UNAVAILABLE: no module sources".to_string());
        }
        let mut projections = BTreeMap::new();
        let mut sources = Vec::with_capacity(self.source_order.len());
        for path in &self.source_order {
            let document = &self.source_documents[path];
            let entity = format!("module:{}", document.module_name);
            if !session.graph.module_entities.contains(&entity) {
                return Err(format!(
                    "E_AEP_PROJECTION_MODULE_MISSING: authoritative AIR has no module '{}'",
                    document.module_name
                ));
            }
            let module_revision = session.graph.heads.get(&entity).ok_or_else(|| {
                format!(
                    "E_AEP_PROJECTION_MODULE_MISSING: authoritative AIR has no head for module '{}'",
                    document.module_name
                )
            })?;
            let projection = air::module_to_sexpr(&session.graph, module_revision);
            sources.push((document.module_name.clone(), projection.clone()));
            projections.insert(path.clone(), projection);
        }
        let round_trip = project::graph_from_source_texts(&sources)
            .map_err(|problems| format!("E_AEP_PROJECTION_ROUNDTRIP: {}", problems.join("; ")))?;
        let expected = session.graph.semantic_hash();
        let actual = round_trip.semantic_hash();
        if actual != expected {
            return Err(format!(
                "E_AEP_PROJECTION_ROUNDTRIP: canonical source revision {actual} != AIR revision {expected}"
            ));
        }
        Ok(projections)
    }

    fn verify_text_sources_unchanged(&self) -> Result<(), String> {
        if !self.text_input_staged {
            return Ok(());
        }
        for document in self.source_documents.values() {
            let disk = std::fs::read_to_string(&document.path)
                .map_err(|error| format!("E_AEP_TEXT_SOURCE_CHANGED: {error}"))?;
            if sha256_text(&disk) != document.disk_sha256 {
                return Err(format!(
                    "E_AEP_TEXT_SOURCE_CHANGED: '{}' changed after transaction begin",
                    document.path.display()
                ));
            }
        }
        Ok(())
    }
}

fn source_graph(
    documents: &BTreeMap<PathBuf, SourceDocument>,
    order: &[PathBuf],
) -> Result<air::AirGraph, Vec<String>> {
    let sources = order
        .iter()
        .map(|path| {
            let document = &documents[path];
            (document.module_name.clone(), document.text.clone())
        })
        .collect::<Vec<_>>();
    project::graph_from_source_texts(&sources)
}

fn sha256_text(text: &str) -> String {
    crate::air::hex(&Sha256::digest(text.as_bytes()))
}

fn bounded_utf8_prefix(text: &str, max_bytes: usize) -> (String, bool) {
    if text.len() <= max_bytes {
        return (text.to_string(), false);
    }
    let mut end = max_bytes;
    while !text.is_char_boundary(end) {
        end -= 1;
    }
    (text[..end].to_string(), true)
}

fn atomic_replace_source(path: &Path, bytes: &[u8]) -> Result<(), String> {
    let parent = path
        .parent()
        .ok_or_else(|| "E_AEP_PROJECTION_WRITE: source has no parent directory".to_string())?;
    let file_name = path
        .file_name()
        .and_then(|name| name.to_str())
        .ok_or_else(|| "E_AEP_PROJECTION_WRITE: invalid source filename".to_string())?;
    let tmp = parent.join(format!(
        ".{file_name}.alva-projection-{}.tmp",
        std::process::id()
    ));
    let write_result = (|| -> Result<(), String> {
        let mut file = std::fs::File::create(&tmp)
            .map_err(|error| format!("E_AEP_PROJECTION_WRITE: {error}"))?;
        file.write_all(bytes)
            .map_err(|error| format!("E_AEP_PROJECTION_WRITE: {error}"))?;
        file.sync_all()
            .map_err(|error| format!("E_AEP_PROJECTION_WRITE: {error}"))?;
        std::fs::rename(&tmp, path).map_err(|error| format!("E_AEP_PROJECTION_WRITE: {error}"))?;
        Ok(())
    })();
    if write_result.is_err() {
        let _ = std::fs::remove_file(&tmp);
    }
    write_result
}
