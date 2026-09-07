//! Intent-preserving recovery state for named-entity stale conflicts.
//!
//! The context contains only public writer obligations and facts derived from
//! the original and current AIR revisions. Hidden evaluators are not inputs.

use crate::air;
use crate::execution_events::VerificationStatus;
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::collections::BTreeSet;

const MAX_OBLIGATIONS: usize = 16;
const MAX_OBLIGATION_BYTES: usize = 1024;
const MAX_TOTAL_OBLIGATION_BYTES: usize = 8192;
const MAX_CHANGE_SUMMARIES: usize = 8;

#[derive(Clone, Debug)]
pub(crate) struct RecoveryIntent {
    pub(crate) original_base_revision: String,
    pub(crate) original_obligations: Vec<String>,
    pub(crate) original_target: TargetSnapshot,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
pub(crate) struct TargetSnapshot {
    pub(crate) requested: String,
    pub(crate) entity: String,
    pub(crate) kind: String,
    pub(crate) qualified: String,
    pub(crate) revision: String,
    pub(crate) signature: Option<String>,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub(crate) enum RebindingKind {
    SameEntity,
    Renamed,
    SignatureChanged,
    RenamedAndSignatureChanged,
    OtherChange,
    Missing,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
pub(crate) struct TargetChangeSummary {
    pub(crate) entity: String,
    pub(crate) before: Option<TargetSnapshot>,
    pub(crate) after: Option<TargetSnapshot>,
    pub(crate) change: RebindingKind,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
pub(crate) struct ConcurrentChangeSummary {
    pub(crate) changed_modules: Vec<String>,
    pub(crate) changed_targets: Vec<TargetChangeSummary>,
    pub(crate) changed_targets_truncated: bool,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
pub(crate) struct RecoveryContext {
    pub(crate) recovery_id: String,
    pub(crate) rejected_event_id: String,
    pub(crate) original_base_revision: String,
    pub(crate) current_revision: String,
    pub(crate) original_obligations: Vec<String>,
    pub(crate) original_target: TargetSnapshot,
    pub(crate) current_target: Option<TargetSnapshot>,
    pub(crate) target_rebinding: RebindingKind,
    pub(crate) concurrent_change_summary: ConcurrentChangeSummary,
    pub(crate) preserved_obligations: Vec<String>,
    pub(crate) unresolved_obligations: Vec<String>,
    pub(crate) validation_state: VerificationStatus,
}

pub(crate) fn register_intent(
    graph: &air::AirGraph,
    base_revision: String,
    requested_target: &str,
    obligations: Vec<String>,
) -> Result<RecoveryIntent, String> {
    validate_obligations(&obligations)?;
    let original_target = resolve_target(graph, requested_target)?.ok_or_else(|| {
        format!("E_AEP_RECOVERY_TARGET_NOT_FOUND: named target '{requested_target}' was not found")
    })?;
    Ok(RecoveryIntent {
        original_base_revision: base_revision,
        original_obligations: obligations,
        original_target,
    })
}

pub(crate) fn build_context(
    intent: &RecoveryIntent,
    base: &air::AirGraph,
    current: &air::AirGraph,
    rejected_event_id: String,
) -> RecoveryContext {
    let current_revision = current.semantic_hash();
    let current_target = target_by_entity(current, &intent.original_target.entity);
    let target_rebinding = classify_change(Some(&intent.original_target), current_target.as_ref());
    let concurrent_change_summary = summarize_changes(base, current);
    let recovery_id = recovery_id(
        &rejected_event_id,
        &intent.original_base_revision,
        &current_revision,
        &intent.original_obligations,
    );
    RecoveryContext {
        recovery_id,
        rejected_event_id,
        original_base_revision: intent.original_base_revision.clone(),
        current_revision,
        original_obligations: intent.original_obligations.clone(),
        original_target: intent.original_target.clone(),
        current_target,
        target_rebinding,
        concurrent_change_summary,
        preserved_obligations: intent.original_obligations.clone(),
        unresolved_obligations: intent.original_obligations.clone(),
        validation_state: VerificationStatus::Unknown,
    }
}

/// Verifier-owned transition. This function is intentionally not wired into
/// AEP or MCP; an agent cannot self-assert task correctness.
#[allow(dead_code)]
pub(crate) fn apply_verifier_decision(context: &mut RecoveryContext, status: VerificationStatus) {
    context.validation_state = status;
    if status == VerificationStatus::Passed {
        context.unresolved_obligations.clear();
    }
}

fn validate_obligations(obligations: &[String]) -> Result<(), String> {
    if obligations.is_empty() {
        return Err(
            "E_AEP_RECOVERY_OBLIGATIONS_EMPTY: at least one public obligation is required"
                .to_string(),
        );
    }
    if obligations.len() > MAX_OBLIGATIONS {
        return Err(format!(
            "E_AEP_RECOVERY_OBLIGATIONS_LIMIT: at most {MAX_OBLIGATIONS} obligations are allowed"
        ));
    }
    let mut total = 0usize;
    for obligation in obligations {
        let bytes = obligation.trim().len();
        if bytes == 0 || bytes > MAX_OBLIGATION_BYTES {
            return Err(format!(
                "E_AEP_RECOVERY_OBLIGATION_SIZE: each obligation must contain 1..={MAX_OBLIGATION_BYTES} bytes"
            ));
        }
        total += bytes;
    }
    if total > MAX_TOTAL_OBLIGATION_BYTES {
        return Err(format!(
            "E_AEP_RECOVERY_OBLIGATIONS_SIZE: total obligation bytes exceed {MAX_TOTAL_OBLIGATION_BYTES}"
        ));
    }
    Ok(())
}

fn resolve_target(
    graph: &air::AirGraph,
    requested: &str,
) -> Result<Option<TargetSnapshot>, String> {
    match air::resolve_canonical(graph, requested, &["any"]) {
        air::CanonicalOutcome::Resolved(handle) => {
            let entity = air::canonical_entities(graph)
                .into_iter()
                .find(|candidate| candidate.handle == handle || candidate.entity == handle)
                .ok_or_else(|| {
                    "E_AEP_RECOVERY_TARGET_UNSTABLE: recovery requires a named entity".to_string()
                })?;
            Ok(target_by_entity(graph, &entity.entity).map(|mut target| {
                target.requested = requested.to_string();
                target
            }))
        }
        air::CanonicalOutcome::Ambiguous(candidates) => Err(format!(
            "E_AEP_RECOVERY_TARGET_AMBIGUOUS: {}",
            candidates.join(", ")
        )),
        air::CanonicalOutcome::WrongKind { .. } => unreachable!("any accepts every named kind"),
        air::CanonicalOutcome::NotFound => Ok(None),
    }
}

fn target_by_entity(graph: &air::AirGraph, entity_id: &str) -> Option<TargetSnapshot> {
    let entity = air::canonical_entities(graph)
        .into_iter()
        .find(|candidate| candidate.entity == entity_id)?;
    let revision = graph.heads.get(entity_id)?.clone();
    let signature = (entity.kind == "function").then(|| function_signature(graph, &revision));
    Some(TargetSnapshot {
        requested: entity.qualified.clone(),
        entity: entity.entity,
        kind: entity.kind,
        qualified: entity.qualified,
        revision,
        signature,
    })
}

fn function_signature(graph: &air::AirGraph, revision: &str) -> String {
    air::view_function(graph, revision)
        .lines()
        .take_while(|line| {
            let trimmed = line.trim_start();
            !trimmed.starts_with("revision ") && !trimmed.starts_with("body:")
        })
        .enumerate()
        .map(|(index, line)| {
            if index == 0 {
                line.find(" -> ")
                    .map(|offset| format!("fn{}", &line[offset..]))
                    .unwrap_or_else(|| line.to_string())
            } else {
                line.to_string()
            }
        })
        .collect::<Vec<_>>()
        .join("\n")
}

fn classify_change(
    before: Option<&TargetSnapshot>,
    after: Option<&TargetSnapshot>,
) -> RebindingKind {
    let (Some(before), Some(after)) = (before, after) else {
        return RebindingKind::Missing;
    };
    let renamed = before.qualified != after.qualified;
    let signature_changed = before.signature != after.signature;
    match (
        renamed,
        signature_changed,
        before.revision != after.revision,
    ) {
        (true, true, _) => RebindingKind::RenamedAndSignatureChanged,
        (true, false, _) => RebindingKind::Renamed,
        (false, true, _) => RebindingKind::SignatureChanged,
        (false, false, true) => RebindingKind::OtherChange,
        (false, false, false) => RebindingKind::SameEntity,
    }
}

fn summarize_changes(base: &air::AirGraph, current: &air::AirGraph) -> ConcurrentChangeSummary {
    let diff = air::diff_graphs(base, current);
    let mut entity_ids = BTreeSet::new();
    entity_ids.extend(
        air::canonical_entities(base)
            .into_iter()
            .map(|item| item.entity),
    );
    entity_ids.extend(
        air::canonical_entities(current)
            .into_iter()
            .map(|item| item.entity),
    );
    let mut changed_targets = entity_ids
        .into_iter()
        .filter_map(|entity| {
            let before = target_by_entity(base, &entity);
            let after = target_by_entity(current, &entity);
            let changed = before.as_ref().map(|item| &item.revision)
                != after.as_ref().map(|item| &item.revision);
            changed.then(|| TargetChangeSummary {
                entity,
                change: classify_change(before.as_ref(), after.as_ref()),
                before,
                after,
            })
        })
        .collect::<Vec<_>>();
    let changed_targets_truncated = changed_targets.len() > MAX_CHANGE_SUMMARIES;
    changed_targets.truncate(MAX_CHANGE_SUMMARIES);
    ConcurrentChangeSummary {
        changed_modules: diff.changed_modules,
        changed_targets,
        changed_targets_truncated,
    }
}

fn recovery_id(
    rejected_event_id: &str,
    base_revision: &str,
    current_revision: &str,
    obligations: &[String],
) -> String {
    let mut digest = Sha256::new();
    for value in std::iter::once(rejected_event_id)
        .chain(std::iter::once(base_revision))
        .chain(std::iter::once(current_revision))
        .chain(obligations.iter().map(String::as_str))
    {
        digest.update((value.len() as u64).to_be_bytes());
        digest.update(value.as_bytes());
    }
    format!("recovery_{}", &crate::air::hex(&digest.finalize())[..24])
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn verifier_is_the_only_transition_out_of_unknown() {
        assert!(crate::aep::lookup("complete_recovery").is_none());
        assert!(crate::aep::lookup("final_task_verified").is_none());
        let target = TargetSnapshot {
            requested: "m.f".into(),
            entity: "module:m/fn:f".into(),
            kind: "function".into(),
            qualified: "m.f".into(),
            revision: "base-target".into(),
            signature: Some("fn f -> i64".into()),
        };
        let mut context = RecoveryContext {
            recovery_id: "r".into(),
            rejected_event_id: "e".into(),
            original_base_revision: "base".into(),
            current_revision: "current".into(),
            original_obligations: vec!["preserve behavior".into()],
            original_target: target.clone(),
            current_target: Some(target),
            target_rebinding: RebindingKind::SameEntity,
            concurrent_change_summary: ConcurrentChangeSummary {
                changed_modules: vec![],
                changed_targets: vec![],
                changed_targets_truncated: false,
            },
            preserved_obligations: vec!["preserve behavior".into()],
            unresolved_obligations: vec!["preserve behavior".into()],
            validation_state: VerificationStatus::Unknown,
        };
        assert_eq!(context.validation_state, VerificationStatus::Unknown);
        apply_verifier_decision(&mut context, VerificationStatus::Passed);
        assert_eq!(context.validation_state, VerificationStatus::Passed);
        assert!(context.unresolved_obligations.is_empty());
    }
}
