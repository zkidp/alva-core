//! Typed execution telemetry shared by the AEP CLI and MCP adapter.
//!
//! The durable JSONL stream is system evidence. Agent-facing responses receive
//! only [`CompactExecutionProjection`]. Recovery action success is deliberately
//! distinct from recovery completion and intent verification.

use serde::Serialize;
use serde_json::{json, Value};
use std::fs::{File, OpenOptions};
use std::io::{BufWriter, Write};
use std::path::Path;

pub const EVENT_SCHEMA_VERSION: &str = "alva.execution-event.v1";

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
#[allow(dead_code)] // recovery/final-verifier variants are consumed by VNext-02B
pub enum ExecutionEventKind {
    OperationRequested,
    OperationRejected,
    TransactionStarted,
    TransactionAborted,
    MutationStaged,
    SemanticCheckPassed,
    CommitAttempted,
    CommitSucceeded,
    StaleWriteRejected,
    RecoveryStarted,
    RecoveryActionSucceeded,
    RecoveryCompleted,
    FinalTaskVerified,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
#[allow(dead_code)] // populated by recovery completion and external verification hooks
pub enum VerificationStatus {
    Passed,
    Failed,
    Unknown,
}

#[derive(Clone, Debug, Default)]
pub struct EventFields {
    pub transaction_id: Option<String>,
    pub operation: Option<String>,
    pub target_entity: Option<String>,
    pub base_revision: Option<String>,
    pub current_revision: Option<String>,
    pub resulting_revision: Option<String>,
    pub rejection_reason: Option<String>,
    pub parent_event_id: Option<String>,
    pub verification_status: Option<VerificationStatus>,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
pub struct ExecutionEvent {
    pub schema_version: &'static str,
    pub event_id: String,
    pub sequence: u64,
    pub event: ExecutionEventKind,
    pub session_id: String,
    pub transaction_id: Option<String>,
    pub operation: Option<String>,
    pub target_entity: Option<String>,
    pub base_revision: Option<String>,
    pub current_revision: Option<String>,
    pub resulting_revision: Option<String>,
    pub rejection_reason: Option<String>,
    pub parent_event_id: Option<String>,
    pub verification_status: Option<VerificationStatus>,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
pub struct CompactExecutionProjection {
    pub event_id: String,
    pub parent_event_id: Option<String>,
    pub state: ExecutionEventKind,
    pub current_revision: Option<String>,
    pub resulting_revision: Option<String>,
    pub rejection_reason: Option<String>,
}

pub struct EventRecorder {
    session_id: String,
    transaction_id: Option<String>,
    sequence: u64,
    events: Vec<ExecutionEvent>,
    sink: Option<BufWriter<File>>,
}

impl EventRecorder {
    pub fn new(
        session_id: impl Into<String>,
        transaction_id: Option<String>,
        event_log: Option<&Path>,
    ) -> Result<Self, String> {
        let session_id = session_id.into();
        if session_id.trim().is_empty() {
            return Err("E_AEP_EVENT_SCHEMA: session_id must not be empty".to_string());
        }
        if transaction_id
            .as_deref()
            .is_some_and(|id| id.trim().is_empty())
        {
            return Err("E_AEP_EVENT_SCHEMA: transaction_id must not be empty".to_string());
        }
        let sink = event_log
            .map(|path| {
                OpenOptions::new()
                    .create(true)
                    .append(true)
                    .open(path)
                    .map(BufWriter::new)
                    .map_err(|error| {
                        format!("E_AEP_EVENT_LOG: cannot open {}: {error}", path.display())
                    })
            })
            .transpose()?;
        Ok(Self {
            session_id,
            transaction_id,
            sequence: 0,
            events: Vec::new(),
            sink,
        })
    }

    pub fn record(
        &mut self,
        event: ExecutionEventKind,
        mut fields: EventFields,
    ) -> Result<String, String> {
        let requires_verification = matches!(
            event,
            ExecutionEventKind::RecoveryCompleted | ExecutionEventKind::FinalTaskVerified
        );
        if requires_verification != fields.verification_status.is_some() {
            return Err(format!(
                "E_AEP_EVENT_SCHEMA: {event:?} verification_status requirement violated"
            ));
        }
        self.sequence += 1;
        let event_id = format!("{}:{:06}", self.session_id, self.sequence);
        if fields.transaction_id.is_none() {
            fields.transaction_id = self.transaction_id.clone();
        }
        let item = ExecutionEvent {
            schema_version: EVENT_SCHEMA_VERSION,
            event_id: event_id.clone(),
            sequence: self.sequence,
            event,
            session_id: self.session_id.clone(),
            transaction_id: fields.transaction_id,
            operation: fields.operation,
            target_entity: fields.target_entity,
            base_revision: fields.base_revision,
            current_revision: fields.current_revision,
            resulting_revision: fields.resulting_revision,
            rejection_reason: fields.rejection_reason,
            parent_event_id: fields.parent_event_id,
            verification_status: fields.verification_status,
        };
        if let Some(sink) = &mut self.sink {
            let mut line = serde_json::to_vec(&item)
                .map_err(|error| format!("E_AEP_EVENT_LOG: cannot encode event: {error}"))?;
            line.push(b'\n');
            sink.write_all(&line)
                .and_then(|()| sink.flush())
                .map_err(|error| format!("E_AEP_EVENT_LOG: cannot append event: {error}"))?;
        }
        self.events.push(item);
        Ok(event_id)
    }

    pub fn last(&self) -> Option<&ExecutionEvent> {
        self.events.last()
    }

    pub fn compact_projection(&self) -> Option<CompactExecutionProjection> {
        self.last().map(|event| CompactExecutionProjection {
            event_id: event.event_id.clone(),
            parent_event_id: event.parent_event_id.clone(),
            state: event.event,
            current_revision: event.current_revision.clone(),
            resulting_revision: event.resulting_revision.clone(),
            rejection_reason: event.rejection_reason.clone(),
        })
    }

    #[allow(dead_code)] // system-only hook consumed by VNext-02B recovery orchestration
    pub fn record_recovery_started(
        &mut self,
        parent_event_id: String,
        current_revision: Option<String>,
    ) -> Result<String, String> {
        self.record(
            ExecutionEventKind::RecoveryStarted,
            EventFields {
                parent_event_id: Some(parent_event_id),
                current_revision,
                ..EventFields::default()
            },
        )
    }

    #[allow(dead_code)] // action success intentionally precedes intent verification
    pub fn record_recovery_action_succeeded(
        &mut self,
        parent_event_id: String,
        resulting_revision: Option<String>,
    ) -> Result<String, String> {
        self.record(
            ExecutionEventKind::RecoveryActionSucceeded,
            EventFields {
                parent_event_id: Some(parent_event_id),
                resulting_revision,
                ..EventFields::default()
            },
        )
    }

    #[allow(dead_code)] // system-only hook consumed by VNext-02B recovery orchestration
    pub fn record_recovery_completed(
        &mut self,
        parent_event_id: String,
        intent_verification: VerificationStatus,
    ) -> Result<String, String> {
        self.record(
            ExecutionEventKind::RecoveryCompleted,
            EventFields {
                parent_event_id: Some(parent_event_id),
                verification_status: Some(intent_verification),
                ..EventFields::default()
            },
        )
    }

    #[allow(dead_code)] // invoked by a verifier-owning harness, never inferred by the compiler
    pub fn record_final_task_verified(
        &mut self,
        parent_event_id: String,
        status: VerificationStatus,
        resulting_revision: Option<String>,
    ) -> Result<String, String> {
        self.record(
            ExecutionEventKind::FinalTaskVerified,
            EventFields {
                parent_event_id: Some(parent_event_id),
                resulting_revision,
                verification_status: Some(status),
                ..EventFields::default()
            },
        )
    }
}

pub fn attach_compact_projection(
    response: &str,
    projection: Option<CompactExecutionProjection>,
) -> String {
    let Some(projection) = projection else {
        return response.to_string();
    };
    let Ok(mut value) = serde_json::from_str::<Value>(response) else {
        return response.to_string();
    };
    if let Some(object) = value.as_object_mut() {
        object.insert("execution".to_string(), json!(projection));
    }
    serde_json::to_string(&value).unwrap_or_else(|_| response.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn recovery_action_success_does_not_claim_intent_preservation() {
        let mut recorder = EventRecorder::new("s", Some("tx".into()), None).unwrap();
        let started = recorder
            .record_recovery_started("rejection".into(), Some("current".into()))
            .unwrap();
        let action = recorder
            .record_recovery_action_succeeded(started, Some("result".into()))
            .unwrap();
        assert_eq!(recorder.last().unwrap().verification_status, None);
        let completed = recorder
            .record_recovery_completed(action, VerificationStatus::Unknown)
            .unwrap();
        assert_eq!(
            recorder.last().unwrap().verification_status,
            Some(VerificationStatus::Unknown)
        );
        recorder
            .record_final_task_verified(
                completed,
                VerificationStatus::Failed,
                Some("result".into()),
            )
            .unwrap();
        assert_eq!(
            recorder.last().unwrap().event,
            ExecutionEventKind::FinalTaskVerified
        );
        assert_eq!(
            recorder.last().unwrap().verification_status,
            Some(VerificationStatus::Failed)
        );
    }

    #[test]
    fn recovery_action_success_rejects_verification_claim() {
        let mut recorder = EventRecorder::new("s", None, None).unwrap();
        let result = recorder.record(
            ExecutionEventKind::RecoveryActionSucceeded,
            EventFields {
                verification_status: Some(VerificationStatus::Passed),
                ..EventFields::default()
            },
        );
        assert!(result.unwrap_err().starts_with("E_AEP_EVENT_SCHEMA:"));
    }

    #[test]
    fn compact_projection_excludes_operation_and_target_details() {
        let mut recorder = EventRecorder::new("s", None, None).unwrap();
        recorder
            .record(
                ExecutionEventKind::OperationRejected,
                EventFields {
                    operation: Some("rename_entity".into()),
                    target_entity: Some("secret.internal".into()),
                    rejection_reason: Some("stale".into()),
                    ..EventFields::default()
                },
            )
            .unwrap();
        let value = serde_json::to_value(recorder.compact_projection()).unwrap();
        assert!(value.to_string().contains("stale"));
        assert!(!value.to_string().contains("rename_entity"));
        assert!(!value.to_string().contains("secret.internal"));
    }
}
