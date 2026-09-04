//! Transport-neutral state and lifecycle for one AEP editing session.

use std::collections::BTreeMap;
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
