use crate::config::Config;
use crate::writer::QaChainWriter;
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};

/// Per-finding cap on the evidence_records hash list. The aggregate
/// qa_behavioral_analysis record is bounded by FINDINGS_BUDGET_BYTES in
/// writer.rs, but capping evidence at the source keeps each individual
/// finding small enough that the bound rarely needs to truncate the
/// findings array itself — especially when a pattern (e.g. an overly
/// broad rule) would otherwise embed every governance-chain decision
/// hash in a single finding. When the source list exceeds this cap, the
/// finding's evidence_records is sliced to the first N entries; the full
/// count is preserved as evidence_records_total on the finding object.
const MAX_EVIDENCE_RECORDS_PER_FINDING: usize = 5;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct BehavioralFinding {
    pub finding_type: String,
    pub subtype: String,
    pub detail: String,
    pub severity: String,
    pub evidence_records: Vec<String>,
}

impl BehavioralFinding {
    pub fn value(&self) -> Value {
        let total = self.evidence_records.len();
        let sample: Vec<String> = self
            .evidence_records
            .iter()
            .take(MAX_EVIDENCE_RECORDS_PER_FINDING)
            .cloned()
            .collect();
        let mut object = json!({
            "type": self.finding_type,
            "subtype": self.subtype,
            "detail": self.detail,
            "severity": self.severity,
            "evidence_records": sample,
            "evidence_records_total": total,
        });
        if total > MAX_EVIDENCE_RECORDS_PER_FINDING {
            object["evidence_records_truncated"] = Value::Bool(true);
        }
        object
    }
}

pub fn run_behavioral_analysis(
    config: &Config,
    records: &[Value],
    writer: &mut QaChainWriter,
) -> Result<Vec<BehavioralFinding>, String> {
    let findings = analyze_behavior(config, records);
    writer.append_behavioral_analysis(
        "1h",
        findings.iter().map(BehavioralFinding::value).collect(),
    )?;
    Ok(findings)
}

pub fn analyze_behavior(config: &Config, records: &[Value]) -> Vec<BehavioralFinding> {
    let decisions: Vec<&Value> = records
        .iter()
        .filter(|record| is_decision(record))
        .collect();
    let mut findings = Vec::new();
    findings.extend(classification_consistency(&decisions));
    findings.extend(decision_reversals(records, &decisions));
    findings.extend(approval_provenance(config, records, &decisions));
    findings.extend(temporal_patterns(&decisions));
    findings.extend(policy_rule_coverage(config, &decisions));
    findings.extend(security_relevant_patterns(&decisions, records));
    findings
}

fn classification_consistency(decisions: &[&Value]) -> Vec<BehavioralFinding> {
    let mut findings = Vec::new();
    for pair in decisions.windows(2) {
        let previous = pair[0];
        let current = pair[1];
        if tool(previous) != tool(current) {
            continue;
        }
        if classification(previous) != classification(current)
            && decision(previous) != decision(current)
            && !has_intervening_update(&[], previous, current)
        {
            findings.push(BehavioralFinding {
                finding_type: "classification_inconsistency".to_string(),
                subtype: "same_tool_reclassified".to_string(),
                detail: format!(
                    "{} changed classification {} -> {} with decision {} -> {}",
                    tool(current),
                    classification(previous),
                    classification(current),
                    decision(previous),
                    decision(current)
                ),
                severity: "medium".to_string(),
                evidence_records: hashes(&[previous, current]),
            });
        }
    }
    findings
}

fn decision_reversals(records: &[Value], decisions: &[&Value]) -> Vec<BehavioralFinding> {
    let mut findings = Vec::new();
    let mut last_by_tool: BTreeMap<String, &Value> = BTreeMap::new();
    for current in decisions {
        let name = tool(current);
        if let Some(previous) = last_by_tool.get(&name) {
            if decision(previous) != decision(current)
                && !has_intervening_update(records, previous, current)
                && decision(previous) != "UNKNOWN"
                && decision(current) != "UNKNOWN"
            {
                findings.push(BehavioralFinding {
                    finding_type: "decision_reversal".to_string(),
                    subtype: "visible_cause_absent".to_string(),
                    detail: format!(
                        "{} reversed {} -> {} with no visible policy, approval, or classifier change",
                        name,
                        decision(previous),
                        decision(current)
                    ),
                    severity: "medium".to_string(),
                    evidence_records: hashes(&[previous, current]),
                });
            }
        }
        last_by_tool.insert(name, current);
    }
    findings
}

fn approval_provenance(
    config: &Config,
    records: &[Value],
    decisions: &[&Value],
) -> Vec<BehavioralFinding> {
    let mut findings = Vec::new();
    let mut prior_operators = BTreeSet::new();
    for record in records {
        if event_type(record) != "opaque_artifact_approval" {
            continue;
        }
        if let Some(operator) = operator(record) {
            prior_operators.insert(operator);
        }
    }
    for decision_record in decisions {
        if decision(decision_record) != "ALLOW"
            || matched_rule(decision_record) != "approved_lookup"
        {
            continue;
        }
        let Some(approval) = approval_for(records, decision_record) else {
            continue;
        };
        if let (Some(approval_ts), Some(decision_ts)) = (
            timestamp_seconds(approval),
            timestamp_seconds(decision_record),
        ) {
            let age = decision_ts.saturating_sub(approval_ts);
            if age > config.approval_max_age_seconds {
                findings.push(BehavioralFinding {
                    finding_type: "approval_provenance".to_string(),
                    subtype: "approval_age_exceeded".to_string(),
                    detail: format!("approval age {age}s exceeds configured maximum"),
                    severity: "medium".to_string(),
                    evidence_records: hashes(&[approval, decision_record]),
                });
            }
        }
        if let Some(approval_operator) = operator(approval) {
            let previous_seen = records
                .iter()
                .take_while(|candidate| !same_record(candidate, approval))
                .any(|candidate| {
                    event_type(candidate) == "opaque_artifact_approval"
                        && operator(candidate) == Some(approval_operator.clone())
                });
            if !previous_seen && !prior_operators.is_empty() {
                findings.push(BehavioralFinding {
                    finding_type: "approval_provenance".to_string(),
                    subtype: "unrecognized_operator".to_string(),
                    detail: format!("operator {approval_operator} had no prior approval history"),
                    severity: "medium".to_string(),
                    evidence_records: hashes(&[approval, decision_record]),
                });
            }
        }
    }
    findings
}

fn temporal_patterns(decisions: &[&Value]) -> Vec<BehavioralFinding> {
    let off_hours: Vec<&Value> = decisions
        .iter()
        .copied()
        .filter(|record| timestamp_hour(record).map(|hour| hour < 6).unwrap_or(false))
        .collect();
    let business_hours = decisions
        .iter()
        .filter(|record| {
            timestamp_hour(record)
                .map(|hour| (8..=18).contains(&hour))
                .unwrap_or(false)
        })
        .count();
    if !off_hours.is_empty() && business_hours >= off_hours.len() * 3 {
        return vec![BehavioralFinding {
            finding_type: "temporal_pattern".to_string(),
            subtype: "off_hours_activity".to_string(),
            detail: format!(
                "{} decision(s) occurred outside historical activity hours",
                off_hours.len()
            ),
            severity: "medium".to_string(),
            evidence_records: hashes(&off_hours),
        }];
    }
    Vec::new()
}

fn policy_rule_coverage(config: &Config, decisions: &[&Value]) -> Vec<BehavioralFinding> {
    let mut findings = Vec::new();
    let matched: BTreeMap<String, usize> =
        decisions.iter().fold(BTreeMap::new(), |mut acc, record| {
            *acc.entry(matched_rule(record)).or_insert(0) += 1;
            acc
        });
    if let Ok(raw) = std::fs::read_to_string(&config.policy_rules_path) {
        if let Ok(value) = serde_json::from_str::<Value>(&raw) {
            for rule in value
                .get("rules")
                .and_then(Value::as_array)
                .into_iter()
                .flatten()
            {
                let name = rule
                    .get("id")
                    .or_else(|| rule.get("name"))
                    .and_then(Value::as_str)
                    .unwrap_or("");
                if !name.is_empty() && !matched.contains_key(name) {
                    findings.push(BehavioralFinding {
                        finding_type: "policy_rule_coverage".to_string(),
                        subtype: "dead_rule".to_string(),
                        detail: format!("policy rule {name} matched zero decisions"),
                        severity: "medium".to_string(),
                        evidence_records: Vec::new(),
                    });
                }
            }
        }
    }
    for (rule, count) in matched {
        if !rule.is_empty() && count == decisions.len() && decisions.len() > 1 {
            findings.push(BehavioralFinding {
                finding_type: "policy_rule_coverage".to_string(),
                subtype: "overly_broad_rule".to_string(),
                detail: format!("policy rule {rule} matched every decision in window"),
                severity: "medium".to_string(),
                evidence_records: hashes(decisions),
            });
        }
    }
    findings
}

fn security_relevant_patterns(decisions: &[&Value], records: &[Value]) -> Vec<BehavioralFinding> {
    let mut findings = Vec::new();
    let split = decisions.len().saturating_sub(10);
    let prior_tools: BTreeSet<String> = decisions[..split]
        .iter()
        .map(|record| tool(record))
        .collect();
    let mut reported = BTreeSet::new();
    for record in &decisions[split..] {
        let name = tool(record);
        if !prior_tools.contains(&name) && reported.insert(name.clone()) {
            findings.push(BehavioralFinding {
                finding_type: "security_relevant_pattern".to_string(),
                subtype: "new_tool_appeared".to_string(),
                detail: format!("tool_name {name} not seen in prior chain history"),
                severity: "medium".to_string(),
                evidence_records: hashes(&[*record]),
            });
        }
    }
    for pair in records.windows(2) {
        if event_type(&pair[0]) == "opaque_artifact_approval"
            && event_type(&pair[1]) == "opaque_artifact_revocation"
        {
            findings.push(BehavioralFinding {
                finding_type: "security_relevant_pattern".to_string(),
                subtype: "rapid_approval_revocation".to_string(),
                detail: "approval and revocation occurred in adjacent chain records".to_string(),
                severity: "medium".to_string(),
                evidence_records: hashes(&[&pair[0], &pair[1]]),
            });
        }
    }
    let mut class_counts = BTreeMap::new();
    for record in decisions {
        *class_counts.entry(classification(record)).or_insert(0usize) += 1;
    }
    if let Some((class, count)) = class_counts.iter().max_by_key(|(_class, count)| *count) {
        if decisions.len() >= 10 && *count * 100 / decisions.len() > 90 {
            findings.push(BehavioralFinding {
                finding_type: "security_relevant_pattern".to_string(),
                subtype: "classification_distribution_shift".to_string(),
                detail: format!("{class} classifications dominate the analysis window"),
                severity: "medium".to_string(),
                evidence_records: Vec::new(),
            });
        }
    }
    findings
}

fn is_decision(record: &Value) -> bool {
    matches!(
        record.get("policy_decision").and_then(Value::as_str),
        Some("ALLOW") | Some("DENY")
    )
}

fn has_intervening_update(records: &[Value], previous: &Value, current: &Value) -> bool {
    let Some(start) = records
        .iter()
        .position(|candidate| same_record(candidate, previous))
    else {
        return false;
    };
    let Some(end) = records
        .iter()
        .position(|candidate| same_record(candidate, current))
    else {
        return false;
    };
    records[start + 1..end].iter().any(|record| {
        let event = event_type(record);
        event.contains("policy")
            || event.contains("approval")
            || event.contains("revocation")
            || event.contains("classifier")
            || event.contains("capability_registry")
    })
}

fn approval_for<'a>(records: &'a [Value], decision_record: &Value) -> Option<&'a Value> {
    let approval_id = decision_record
        .get("approval_event_id")
        .or_else(|| decision_record.get("approval_id"))
        .and_then(Value::as_str)?;
    records.iter().find(|record| {
        event_type(record) == "opaque_artifact_approval"
            && (record.get("event_id").and_then(Value::as_str) == Some(approval_id)
                || record.get("approval_id").and_then(Value::as_str) == Some(approval_id)
                || record.get("record_hash").and_then(Value::as_str) == Some(approval_id))
    })
}

fn same_record(left: &Value, right: &Value) -> bool {
    left.get("record_hash").and_then(Value::as_str)
        == right.get("record_hash").and_then(Value::as_str)
}

fn event_type(record: &Value) -> String {
    record
        .get("event_type")
        .or_else(|| record.get("record_type"))
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string()
}

fn tool(record: &Value) -> String {
    record
        .get("original_tool")
        .or_else(|| record.get("tool_name"))
        .and_then(Value::as_str)
        .unwrap_or("unknown")
        .to_string()
}

fn classification(record: &Value) -> String {
    let classification = record.get("classification").unwrap_or(&Value::Null);
    classification
        .get("category")
        .or_else(|| classification.get("action_type"))
        .map(|value| {
            value
                .as_str()
                .map(str::to_string)
                .unwrap_or_else(|| value.to_string())
        })
        .unwrap_or_else(|| "unknown".to_string())
}

fn decision(record: &Value) -> String {
    record
        .get("policy_decision")
        .and_then(Value::as_str)
        .unwrap_or("UNKNOWN")
        .to_string()
}

fn matched_rule(record: &Value) -> String {
    record
        .get("matched_rule")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string()
}

fn operator(record: &Value) -> Option<String> {
    record
        .get("approving_operator")
        .or_else(|| record.get("operator"))
        .and_then(Value::as_str)
        .map(str::to_string)
}

fn timestamp_seconds(record: &Value) -> Option<u64> {
    let raw = record
        .get("timestamp_utc")
        .or_else(|| record.get("timestamp"))
        .and_then(Value::as_str)?;
    chrono::DateTime::parse_from_rfc3339(raw)
        .ok()
        .map(|dt| dt.timestamp().max(0) as u64)
}

fn timestamp_hour(record: &Value) -> Option<u32> {
    let raw = record
        .get("timestamp_utc")
        .or_else(|| record.get("timestamp"))
        .and_then(Value::as_str)?;
    use chrono::Timelike;
    chrono::DateTime::parse_from_rfc3339(raw)
        .ok()
        .map(|dt| dt.hour())
}

fn hashes(records: &[&Value]) -> Vec<String> {
    records
        .iter()
        .filter_map(|record| {
            record
                .get("record_hash")
                .and_then(Value::as_str)
                .map(str::to_string)
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::canonical::record_hash;
    use crate::writer::QaChainWriter;
    use crate::{config::Config, key::QaSigningKey};
    use serde_json::json;
    use std::fs;
    use std::time::Duration;

    const TEST_PRIVATE_PEM: &str = "-----BEGIN PRIVATE KEY-----\nMC4CAQAwBQYDK2VwBCIEIAABAgMEBQYHCAkKCwwNDg8QERITFBUWFxgZGhscHR4f\n-----END PRIVATE KEY-----\n";

    #[test]
    fn classification_consistency_detects_same_tool_reclassification() {
        let config = config(tempfile::tempdir().unwrap().path());
        let records = vec![
            decision_record(
                "Tool",
                "read",
                "ALLOW",
                "rule-a",
                "2026-05-23T12:00:00Z",
                None,
            ),
            decision_record(
                "Tool",
                "write",
                "DENY",
                "rule-b",
                "2026-05-23T12:01:00Z",
                None,
            ),
        ];
        let findings = analyze_behavior(&config, &records);
        assert!(has_subtype(&findings, "same_tool_reclassified"));
    }

    #[test]
    fn decision_reversal_detects_flip_without_policy_change() {
        let config = config(tempfile::tempdir().unwrap().path());
        let records = vec![
            decision_record(
                "Tool",
                "read",
                "DENY",
                "rule-a",
                "2026-05-23T12:00:00Z",
                None,
            ),
            decision_record(
                "Tool",
                "read",
                "ALLOW",
                "rule-a",
                "2026-05-23T12:01:00Z",
                None,
            ),
        ];
        let findings = analyze_behavior(&config, &records);
        assert!(has_subtype(&findings, "visible_cause_absent"));
    }

    #[test]
    fn approval_provenance_detects_aged_approval() {
        let dir = tempfile::tempdir().unwrap();
        let mut config = config(dir.path());
        config.approval_max_age_seconds = 60;
        let approval = event(
            "opaque_artifact_approval",
            json!({"event_id": "approval-1", "approving_operator": "greg"}),
            "2026-05-23T12:00:00Z",
        );
        let mut decision = decision_record(
            "Tool",
            "write",
            "ALLOW",
            "approved_lookup",
            "2026-05-23T12:10:00Z",
            None,
        );
        decision["approval_event_id"] = Value::String("approval-1".to_string());
        decision["record_hash"] = Value::String(record_hash(&decision).unwrap());
        let findings = analyze_behavior(&config, &[approval, decision]);
        assert!(has_subtype(&findings, "approval_age_exceeded"));
    }

    #[test]
    fn temporal_pattern_detects_off_hours_activity() {
        let config = config(tempfile::tempdir().unwrap().path());
        let mut records = Vec::new();
        for idx in 0..9 {
            records.push(decision_record(
                &format!("Tool{idx}"),
                "read",
                "ALLOW",
                "rule",
                "2026-05-23T12:00:00Z",
                None,
            ));
        }
        records.push(decision_record(
            "NightTool",
            "read",
            "ALLOW",
            "rule",
            "2026-05-23T02:00:00Z",
            None,
        ));
        let findings = analyze_behavior(&config, &records);
        assert!(has_subtype(&findings, "off_hours_activity"));
    }

    #[test]
    fn policy_rule_coverage_detects_dead_rule() {
        let dir = tempfile::tempdir().unwrap();
        let config = config(dir.path());
        fs::write(
            &config.policy_rules_path,
            r#"{"rules":[{"id":"dead-rule"},{"id":"used-rule"}]}"#,
        )
        .unwrap();
        let records = vec![decision_record(
            "Tool",
            "read",
            "ALLOW",
            "used-rule",
            "2026-05-23T12:00:00Z",
            None,
        )];
        let findings = analyze_behavior(&config, &records);
        assert!(has_subtype(&findings, "dead_rule"));
    }

    #[test]
    fn security_pattern_detects_new_tool_appearance() {
        let config = config(tempfile::tempdir().unwrap().path());
        let mut records = Vec::new();
        for idx in 0..11 {
            records.push(decision_record(
                "KnownTool",
                "read",
                "ALLOW",
                "rule",
                "2026-05-23T12:00:00Z",
                Some(idx),
            ));
        }
        records.push(decision_record(
            "NewTool",
            "read",
            "ALLOW",
            "rule",
            "2026-05-23T12:01:00Z",
            Some(99),
        ));
        let findings = analyze_behavior(&config, &records);
        assert!(has_subtype(&findings, "new_tool_appeared"));
    }

    #[test]
    fn behavioral_analysis_writes_qa_record() {
        let dir = tempfile::tempdir().unwrap();
        let config = config(dir.path());
        let mut writer = writer(dir.path());
        let records = vec![
            decision_record(
                "Tool",
                "read",
                "ALLOW",
                "rule-a",
                "2026-05-23T12:00:00Z",
                None,
            ),
            decision_record(
                "Tool",
                "write",
                "DENY",
                "rule-b",
                "2026-05-23T12:01:00Z",
                None,
            ),
        ];
        let findings = run_behavioral_analysis(&config, &records, &mut writer).unwrap();
        assert!(!findings.is_empty());
        assert!(fs::read_to_string(dir.path().join("qa-chain.jsonl"))
            .unwrap()
            .contains("qa_behavioral_analysis"));
    }

    fn has_subtype(findings: &[BehavioralFinding], subtype: &str) -> bool {
        findings.iter().any(|finding| finding.subtype == subtype)
    }

    fn config(root: &std::path::Path) -> Config {
        Config {
            repo_root: root.to_path_buf(),
            runtime_root: root.to_path_buf(),
            qa_signing_key_path: root.join("qa.pem"),
            governance_signing_key_path: None,
            policy_rules_path: root.join("policy.json"),
            capability_registry_path: root.join("capability.json"),
            governance_chain_path: root.join("decision-chain.jsonl"),
            qa_chain_path: root.join("qa-chain.jsonl"),
            heartbeat: Duration::from_secs(30),
            ready_file: None,
            require_proxy_running: false,
            tail_records: 10,
            verification_queue_depth: 1000,
            classification_history: 10,
            approval_max_age_seconds: 60,
            spc_min_decisions: 100,
            spc_baseline_path: root.join("quality-service/spc-baselines.json"),
            behavioral_interval: Duration::from_secs(3600),
            element_interval: Duration::from_secs(600),
            element_tail_records: 100,
            chain_events_spec_path: root.join("chain-events-v1.yaml"),
            chain_integrity_spec_path: root.join("chain-integrity-spec-v1.yaml"),
            tier_registry_path: root.join("tier-feature-registry.json"),
        }
    }

    fn decision_record(
        tool: &str,
        action: &str,
        policy_decision: &str,
        rule: &str,
        timestamp: &str,
        sequence: Option<u64>,
    ) -> Value {
        let mut record = json!({
            "record_type": "mediated_decision",
            "timestamp_utc": timestamp,
            "original_tool": tool,
            "classification": {"action_type": action},
            "policy_decision": policy_decision,
            "matched_rule": rule,
            "policy_reasons": [],
            "prev_record_hash": null,
            "record_hash": null,
        });
        if let Some(sequence) = sequence {
            record["request_id"] = Value::String(format!("req-{sequence}"));
        }
        record["record_hash"] = Value::String(record_hash(&record).unwrap());
        record
    }

    fn event(event_type: &str, extra: Value, timestamp: &str) -> Value {
        let mut record = json!({
            "event_type": event_type,
            "timestamp_utc": timestamp,
            "prev_record_hash": null,
            "record_hash": null,
        });
        for (key, value) in extra.as_object().unwrap() {
            record[key] = value.clone();
        }
        record["record_hash"] = Value::String(record_hash(&record).unwrap());
        record
    }

    fn writer(root: &std::path::Path) -> QaChainWriter {
        let key_path = root.join("qa.pem");
        fs::write(&key_path, TEST_PRIVATE_PEM).unwrap();
        QaChainWriter::new(
            root.join("qa-chain.jsonl"),
            QaSigningKey::load(&key_path).unwrap(),
        )
        .unwrap()
    }
}
