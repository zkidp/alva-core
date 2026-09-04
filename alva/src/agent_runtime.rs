//! Transport-neutral state and lifecycle for one AEP editing session.

use std::path::{Path, PathBuf};

use crate::{air, project};

#[derive(Debug, PartialEq, Eq)]
pub(crate) struct CommitResult {
    pub(crate) generation: u64,
    pub(crate) revision: String,
}

#[derive(Default)]
pub(crate) struct AgentRuntime {
    session: Option<air::EditSession>,
    base_graph: Option<air::AirGraph>,
    project_dir: PathBuf,
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
        self.project_dir = project_dir.to_path_buf();
        self.base_graph = Some(graph.clone());
        self.session = Some(air::EditSession::begin(graph, revision.clone()));
        Ok(revision)
    }

    pub(crate) fn check(&mut self) -> Result<(), String> {
        let errors = self.session_mut()?.check();
        if errors.is_empty() {
            Ok(())
        } else {
            Err(format!("check failed: {}", errors.join("; ")))
        }
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
}
