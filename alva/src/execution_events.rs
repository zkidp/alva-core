//! Typed, observational execution events emitted by [`crate::agent_runtime`].
//!
//! The JSONL sink is system evidence. Failures to open or append that sink are
//! deliberately ignored: telemetry must never alter transaction behavior.
//! Agent-facing responses receive only [`CompactExecutionProjection`].

use serde::Serialize;
use serde_json::{json, Value};
use std::fs::{File, OpenOptions};
use std::io::{BufWriter, Write};
use std::path::Path;

pub(crate) const EVENT_SCHEMA_VERSION: &str = "alva.execution-event.v1";

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
#[allow(dead_code)]
pub(crate) enum ExecutionEventKind {
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
#[allow(dead_code)]
pub(crate) enum VerificationStatus {
    Passed,
    Failed,
    Unknown,
}

#[derive(Clone, Debug, Default)]
pub(crate) struct EventFields {
    pub(crate) transaction_id: Option<String>,
    pub(crate) operation: Option<String>,
    pub(crate) target_entity: Option<String>,
    pub(crate) base_revision: Option<String>,
    pub(crate) current_revision: Option<String>,
    pub(crate) resulting_revision: Option<String>,
    pub(crate) rejection_reason: Option<String>,
    pub(crate) parent_event_id: Option<String>,
    pub(crate) verification_status: Option<VerificationStatus>,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
pub(crate) struct ExecutionEvent {
    pub(crate) schema_version: &'static str,
    pub(crate) event_id: String,
    pub(crate) sequence: u64,
    pub(crate) event: ExecutionEventKind,
    pub(crate) session_id: String,
    pub(crate) transaction_id: Option<String>,
    pub(crate) operation: Option<String>,
    pub(crate) target_entity: Option<String>,
    pub(crate) base_revision: Option<String>,
    pub(crate) current_revision: Option<String>,
    pub(crate) resulting_revision: Option<String>,
    pub(crate) rejection_reason: Option<String>,
    pub(crate) parent_event_id: Option<String>,
    pub(crate) verification_status: Option<VerificationStatus>,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
pub(crate) struct CompactExecutionProjection {
    pub(crate) event_id: String,
    pub(crate) parent_event_id: Option<String>,
    pub(crate) state: ExecutionEventKind,
    pub(crate) current_revision: Option<String>,
    pub(crate) resulting_revision: Option<String>,
    pub(crate) rejection_reason: Option<String>,
}

pub(crate) struct EventRecorder {
    session_id: String,
    transaction_id: Option<String>,
    sequence: u64,
    events: Vec<ExecutionEvent>,
    sink: Option<BufWriter<File>>,
}

impl Default for EventRecorder {
    fn default() -> Self {
        Self::new(format!("agent_{:x}", std::process::id()), None, None)
    }
}

impl EventRecorder {
    pub(crate) fn new(
        session_id: impl Into<String>,
        transaction_id: Option<String>,
        event_log: Option<&Path>,
    ) -> Self {
        let supplied = session_id.into();
        let session_id = if supplied.trim().is_empty() {
            format!("agent_{:x}", std::process::id())
        } else {
            supplied
        };
        let transaction_id = transaction_id.filter(|id| !id.trim().is_empty());
        let sink = event_log.and_then(|path| {
            OpenOptions::new()
                .create(true)
                .append(true)
                .open(path)
                .ok()
                .map(BufWriter::new)
        });
        Self {
            session_id,
            transaction_id,
            sequence: 0,
            events: Vec::new(),
            sink,
        }
    }

    pub(crate) fn record(
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
            let appended = serde_json::to_vec(&item).ok().and_then(|mut line| {
                line.push(b'\n');
                sink.write_all(&line).and_then(|()| sink.flush()).ok()
            });
            if appended.is_none() {
                self.sink = None;
            }
        }
        self.events.push(item);
        Ok(event_id)
    }

    pub(crate) fn last(&self) -> Option<&ExecutionEvent> {
        self.events.last()
    }

    pub(crate) fn compact_projection(&self) -> Option<CompactExecutionProjection> {
        self.last().map(|event| CompactExecutionProjection {
            event_id: event.event_id.clone(),
            parent_event_id: event.parent_event_id.clone(),
            state: event.event,
            current_revision: event.current_revision.clone(),
            resulting_revision: event.resulting_revision.clone(),
            rejection_reason: event.rejection_reason.clone(),
        })
    }

    #[allow(dead_code)]
    pub(crate) fn record_recovery_started(
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

    #[allow(dead_code)]
    pub(crate) fn record_recovery_action_succeeded(
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

    #[allow(dead_code)]
    pub(crate) fn record_recovery_completed(
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

    #[allow(dead_code)]
    pub(crate) fn record_final_task_verified(
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

pub(crate) fn attach_compact_projection(
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
    fn recovery_action_success_does_not_claim_verification() {
        let mut recorder = EventRecorder::new("s", Some("tx".into()), None);
        let started = recorder
            .record_recovery_started("rejection".into(), Some("current".into()))
            .unwrap();
        let action = recorder
            .record_recovery_action_succeeded(started, Some("result".into()))
            .unwrap();
        assert_eq!(recorder.last().unwrap().verification_status, None);
        recorder
            .record_recovery_completed(action, VerificationStatus::Unknown)
            .unwrap();
        assert_eq!(
            recorder.last().unwrap().verification_status,
            Some(VerificationStatus::Unknown)
        );
    }

    #[test]
    fn action_event_rejects_verification_claim() {
        let mut recorder = EventRecorder::new("s", None, None);
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
    fn compact_projection_excludes_operation_and_target() {
        let mut recorder = EventRecorder::new("s", None, None);
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
