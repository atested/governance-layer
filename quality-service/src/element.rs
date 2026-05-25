use crate::canonical::{record_hash, record_hash_preimage};
use crate::config::Config;
use crate::key::verifying_key_from_private_key;
use crate::writer::QaChainWriter;
use base64::engine::general_purpose::URL_SAFE_NO_PAD;
use base64::Engine as _;
use ed25519_dalek::{Signature, Verifier};
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};
use std::fs;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ElementFinding {
    pub element_id: String,
    pub severity: String,
    pub detail: String,
    pub condition_id: Option<String>,
}

impl ElementFinding {
    pub fn value(&self) -> Value {
        json!({
            "element_id": self.element_id,
            "severity": self.severity,
            "detail": self.detail,
            "condition_id": self.condition_id,
        })
    }
}

#[derive(Clone, Debug)]
pub struct ElementVerificationResult {
    pub elements_checked: usize,
    pub elements_passed: usize,
    pub elements_flagged: usize,
    pub elements_skipped: usize,
    pub findings: Vec<ElementFinding>,
}

impl ElementVerificationResult {
    pub fn active_conditions(&self) -> Vec<String> {
        self.findings
            .iter()
            .filter(|finding| finding.severity == "critical")
            .filter_map(|finding| finding.condition_id.clone())
            .collect()
    }
}

pub fn run_element_verification(
    config: &Config,
    records: &[Value],
    writer: &mut QaChainWriter,
) -> Result<ElementVerificationResult, String> {
    let result = verify_elements(config, records);
    let coverage = json!({
        "active_verified": result.elements_passed,
        "active_unverified": 0,
        "not_observable": 0,
        "not_implemented": 0,
        "contradictory": 0,
        "suspended": 0,
    });
    writer.append_element_verification(
        "hand-curated-quality-service-v1",
        result.elements_checked,
        result.elements_passed,
        result.elements_flagged,
        result.elements_skipped,
        result.findings.iter().map(ElementFinding::value).collect(),
        coverage,
    )?;
    Ok(result)
}

pub fn verify_elements(config: &Config, records: &[Value]) -> ElementVerificationResult {
    let recent = tail(records, config.element_tail_records);
    let mut checks = Vec::new();
    checks.push(chain_record_schema(config, &recent));
    checks.push(hash_linkage(&recent));
    checks.push(signature_validity(config, &recent));
    checks.push(negative_constraints(&recent));
    checks.push(configuration_state(config));
    checks.push(tier_registry_consistency(config));

    let mut findings = Vec::new();
    let mut passed = 0usize;
    let mut skipped = 0usize;
    for check in checks {
        match check {
            CheckResult::Pass => passed += 1,
            CheckResult::Skip => skipped += 1,
            CheckResult::Findings(mut new_findings) => findings.append(&mut new_findings),
        }
    }
    ElementVerificationResult {
        elements_checked: 6,
        elements_passed: passed,
        elements_flagged: findings.len(),
        elements_skipped: skipped,
        findings,
    }
}

enum CheckResult {
    Pass,
    Skip,
    Findings(Vec<ElementFinding>),
}

fn chain_record_schema(config: &Config, records: &[Value]) -> CheckResult {
    let schemas = load_event_schemas(config).unwrap_or_default();
    let mut findings = Vec::new();
    for record in records {
        if let Some(record_type) = record.get("record_type").and_then(Value::as_str) {
            if record_type == "mediated_decision" {
                for field in [
                    "record_type",
                    "timestamp_utc",
                    "original_tool",
                    "classification",
                    "policy_decision",
                    "matched_rule",
                    "prev_record_hash",
                    "record_hash",
                ] {
                    if record.get(field).is_none() {
                        findings.push(finding(
                            "CHAIN_RECORD_SCHEMA",
                            "high",
                            format!("mediated_decision missing required field {field}"),
                            None,
                        ));
                    }
                }
            }
        }
        let Some(event_type) = record.get("event_type").and_then(Value::as_str) else {
            continue;
        };
        let Some(required) = schemas.get(event_type) else {
            continue;
        };
        for field in required {
            if record.get(field).is_none() {
                findings.push(finding(
                    "CHAIN_RECORD_SCHEMA",
                    "high",
                    format!("{event_type} missing required field {field}"),
                    None,
                ));
            }
        }
    }
    if findings.is_empty() {
        CheckResult::Pass
    } else {
        CheckResult::Findings(findings)
    }
}

fn hash_linkage(records: &[Value]) -> CheckResult {
    let mut findings = Vec::new();
    for record in records {
        match record_hash(record) {
            Ok(expected)
                if record.get("record_hash").and_then(Value::as_str) == Some(expected.as_str()) => {
            }
            Ok(expected) => findings.push(finding(
                "HASH_LINKAGE",
                "critical",
                format!(
                    "record_hash mismatch: expected {expected}, got {:?}",
                    record.get("record_hash").and_then(Value::as_str)
                ),
                Some("CR-CRIT-005"),
            )),
            Err(err) => findings.push(finding(
                "HASH_LINKAGE",
                "critical",
                err,
                Some("CR-CRIT-005"),
            )),
        }
    }
    for pair in records.windows(2) {
        let previous = pair[0].get("record_hash").and_then(Value::as_str);
        let current_prev = pair[1].get("prev_record_hash").and_then(Value::as_str);
        if current_prev != previous {
            findings.push(finding(
                "HASH_LINKAGE",
                "critical",
                format!("prev_record_hash mismatch: expected {previous:?}, got {current_prev:?}"),
                Some("CR-CRIT-005"),
            ));
        }
    }
    if findings.is_empty() {
        CheckResult::Pass
    } else {
        CheckResult::Findings(findings)
    }
}

fn signature_validity(config: &Config, records: &[Value]) -> CheckResult {
    let Some(path) = &config.governance_signing_key_path else {
        return CheckResult::Skip;
    };
    let verifying = match verifying_key_from_private_key(path) {
        Ok(key) => key,
        Err(err) => {
            return CheckResult::Findings(vec![finding(
                "SIGNATURE_VALIDITY",
                "critical",
                err,
                Some("CR-CRIT-005"),
            )])
        }
    };
    let mut findings = Vec::new();
    for record in records {
        let Some(signature) = record.get("signature").and_then(Value::as_str) else {
            findings.push(finding(
                "SIGNATURE_VALIDITY",
                "critical",
                "unsigned record while signing key is configured",
                Some("CR-HIGH-002"),
            ));
            continue;
        };
        let Ok(bytes) = URL_SAFE_NO_PAD.decode(signature.as_bytes()) else {
            findings.push(finding(
                "SIGNATURE_VALIDITY",
                "critical",
                "invalid signature encoding",
                Some("CR-HIGH-002"),
            ));
            continue;
        };
        let Ok(signature) = Signature::from_slice(&bytes) else {
            findings.push(finding(
                "SIGNATURE_VALIDITY",
                "critical",
                "invalid signature bytes",
                Some("CR-HIGH-002"),
            ));
            continue;
        };
        let Ok(preimage) = record_hash_preimage(record) else {
            findings.push(finding(
                "SIGNATURE_VALIDITY",
                "critical",
                "record cannot produce signature preimage",
                Some("CR-HIGH-002"),
            ));
            continue;
        };
        if verifying.verify(preimage.as_bytes(), &signature).is_err() {
            findings.push(finding(
                "SIGNATURE_VALIDITY",
                "critical",
                "signature verification failed",
                Some("CR-HIGH-002"),
            ));
        }
    }
    if findings.is_empty() {
        CheckResult::Pass
    } else {
        CheckResult::Findings(findings)
    }
}

fn negative_constraints(records: &[Value]) -> CheckResult {
    let mut findings = Vec::new();
    for record in records {
        scan_plaintext_license(record, "", &mut findings);
    }
    if findings.is_empty() {
        CheckResult::Pass
    } else {
        CheckResult::Findings(findings)
    }
}

fn configuration_state(config: &Config) -> CheckResult {
    let mut findings = Vec::new();
    for (name, path) in [
        ("policy-rules.json", &config.policy_rules_path),
        ("capability-registry.json", &config.capability_registry_path),
    ] {
        match fs::read_to_string(path) {
            Ok(raw) => {
                if let Err(err) = serde_json::from_str::<Value>(&raw) {
                    findings.push(finding(
                        "CONFIGURATION_STATE",
                        "high",
                        format!("{name} is not valid JSON: {err}"),
                        None,
                    ));
                }
            }
            Err(err) => findings.push(finding(
                "CONFIGURATION_STATE",
                "high",
                format!("failed to read {name}: {err}"),
                None,
            )),
        }
    }
    if findings.is_empty() {
        CheckResult::Pass
    } else {
        CheckResult::Findings(findings)
    }
}

fn tier_registry_consistency(config: &Config) -> CheckResult {
    let raw = match fs::read_to_string(&config.tier_registry_path) {
        Ok(raw) => raw,
        Err(err) => {
            return CheckResult::Findings(vec![finding(
                "TIER_REGISTRY_CONSISTENCY",
                "high",
                format!("failed to read tier registry: {err}"),
                None,
            )])
        }
    };
    let value: Value = match serde_json::from_str(&raw) {
        Ok(value) => value,
        Err(err) => {
            return CheckResult::Findings(vec![finding(
                "TIER_REGISTRY_CONSISTENCY",
                "high",
                format!("tier registry is not valid JSON: {err}"),
                None,
            )])
        }
    };
    let tiers = value.get("tiers").and_then(Value::as_object);
    let missing: Vec<&str> = ["personal", "personal_plus", "crew", "team", "institution"]
        .into_iter()
        .filter(|tier| tiers.map(|map| !map.contains_key(*tier)).unwrap_or(true))
        .collect();
    if missing.is_empty() {
        CheckResult::Pass
    } else {
        CheckResult::Findings(vec![finding(
            "TIER_REGISTRY_CONSISTENCY",
            "high",
            format!(
                "tier registry missing canonical tier(s): {}",
                missing.join(", ")
            ),
            None,
        )])
    }
}

fn load_event_schemas(config: &Config) -> Result<BTreeMap<String, BTreeSet<String>>, String> {
    let raw = fs::read_to_string(&config.chain_events_spec_path)
        .map_err(|err| format!("failed to read chain events spec: {err}"))?;
    let value: serde_yaml::Value = serde_yaml::from_str(&raw)
        .map_err(|err| format!("failed to parse chain events spec: {err}"))?;
    let mut schemas = BTreeMap::new();
    let Some(elements) = value
        .get("elements")
        .and_then(serde_yaml::Value::as_sequence)
    else {
        return Ok(schemas);
    };
    for element in elements {
        let Some(event) = element.get("event").and_then(serde_yaml::Value::as_str) else {
            continue;
        };
        let mut required = BTreeSet::new();
        if let Some(fields) = element
            .get("required")
            .and_then(serde_yaml::Value::as_sequence)
        {
            for field in fields {
                if let Some(name) = field.as_str() {
                    required.insert(name.to_string());
                }
            }
        }
        schemas.insert(event.to_string(), required);
    }
    Ok(schemas)
}

fn scan_plaintext_license(value: &Value, path: &str, findings: &mut Vec<ElementFinding>) {
    match value {
        Value::String(text) => {
            if looks_like_license_token(text) {
                findings.push(finding(
                    "NEGATIVE_CONSTRAINTS",
                    "critical",
                    format!("plaintext license-like token found at {path}"),
                    Some("CR-CRIT-002"),
                ));
            }
        }
        Value::Array(items) => {
            for (idx, item) in items.iter().enumerate() {
                scan_plaintext_license(item, &format!("{path}[{idx}]"), findings);
            }
        }
        Value::Object(map) => {
            for (key, item) in map {
                scan_plaintext_license(item, &format!("{path}.{key}"), findings);
            }
        }
        _ => {}
    }
}

fn looks_like_license_token(text: &str) -> bool {
    let parts: Vec<&str> = text.split('.').collect();
    parts.len() == 2
        && parts[0].len() >= 20
        && parts[1].len() >= 20
        && parts.iter().all(|part| {
            part.chars()
                .all(|ch| ch.is_ascii_alphanumeric() || ch == '-' || ch == '_')
        })
}

fn tail(records: &[Value], limit: usize) -> Vec<Value> {
    if records.len() <= limit {
        records.to_vec()
    } else {
        records[records.len() - limit..].to_vec()
    }
}

fn finding(
    element_id: &str,
    severity: &str,
    detail: impl Into<String>,
    condition_id: Option<&str>,
) -> ElementFinding {
    ElementFinding {
        element_id: element_id.to_string(),
        severity: severity.to_string(),
        detail: detail.into(),
        condition_id: condition_id.map(str::to_string),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::canonical::record_hash;
    use crate::config::Config;
    use serde_json::json;
    use std::time::Duration;

    #[test]
    fn chain_record_schema_detects_missing_required_field() {
        let dir = tempfile::tempdir().unwrap();
        let config = config(dir.path());
        write_chain_events_spec(&config.chain_events_spec_path);
        let records = vec![json!({"event_type": "telemetry_submitted", "event_id": "evt"})];
        let result = verify_elements(&config, &records);
        assert!(has_element(&result, "CHAIN_RECORD_SCHEMA"));
    }

    #[test]
    fn hash_linkage_detects_broken_link() {
        let dir = tempfile::tempdir().unwrap();
        let config = config(dir.path());
        write_support_files(&config);
        let first = record("policy_rules_loaded", None);
        let second = record("telemetry_submitted", Some("sha256:bad"));
        let result = verify_elements(&config, &[first, second]);
        assert!(has_element(&result, "HASH_LINKAGE"));
        assert!(result
            .active_conditions()
            .contains(&"CR-CRIT-005".to_string()));
    }

    #[test]
    fn signature_validity_detects_invalid_signature() {
        let dir = tempfile::tempdir().unwrap();
        let mut config = config(dir.path());
        config.governance_signing_key_path = Some(dir.path().join("gov.pem"));
        std::fs::write(
            config.governance_signing_key_path.as_ref().unwrap(),
            super::tests_support::TEST_PRIVATE_PEM,
        )
        .unwrap();
        write_support_files(&config);
        let mut rec = record("policy_rules_loaded", None);
        rec["signature"] = Value::String("bad".to_string());
        let result = verify_elements(&config, &[rec]);
        assert!(has_element(&result, "SIGNATURE_VALIDITY"));
    }

    #[test]
    fn negative_constraint_detects_plaintext_license_pattern() {
        let dir = tempfile::tempdir().unwrap();
        let config = config(dir.path());
        write_support_files(&config);
        let mut rec = record("policy_rules_loaded", None);
        rec["license_key"] =
            Value::String("abcdefghijklmnopqrstuvwxyz.ABCDEFGHIJKLMNOPQRSTUVWXYZ".to_string());
        let result = verify_elements(&config, &[rec]);
        assert!(has_element(&result, "NEGATIVE_CONSTRAINTS"));
    }

    #[test]
    fn configuration_state_detects_missing_policy_file() {
        let dir = tempfile::tempdir().unwrap();
        let config = config(dir.path());
        write_chain_events_spec(&config.chain_events_spec_path);
        std::fs::write(&config.capability_registry_path, "{}").unwrap();
        std::fs::write(
            &config.tier_registry_path,
            r#"{"tiers":{"personal":{},"personal_plus":{},"crew":{},"team":{},"institution":{}}}"#,
        )
        .unwrap();
        let result = verify_elements(&config, &[]);
        assert!(has_element(&result, "CONFIGURATION_STATE"));
    }

    #[test]
    fn tier_registry_detects_missing_canonical_tier() {
        let dir = tempfile::tempdir().unwrap();
        let config = config(dir.path());
        write_chain_events_spec(&config.chain_events_spec_path);
        std::fs::write(&config.policy_rules_path, "{}").unwrap();
        std::fs::write(&config.capability_registry_path, "{}").unwrap();
        std::fs::write(&config.tier_registry_path, r#"{"tiers":{"personal":{}}}"#).unwrap();
        let result = verify_elements(&config, &[]);
        assert!(has_element(&result, "TIER_REGISTRY_CONSISTENCY"));
    }

    fn has_element(result: &ElementVerificationResult, element_id: &str) -> bool {
        result
            .findings
            .iter()
            .any(|finding| finding.element_id == element_id)
    }

    fn write_support_files(config: &Config) {
        write_chain_events_spec(&config.chain_events_spec_path);
        std::fs::write(&config.policy_rules_path, r#"{"rules":[]}"#).unwrap();
        std::fs::write(&config.capability_registry_path, r#"{"capabilities":[]}"#).unwrap();
        std::fs::write(
            &config.tier_registry_path,
            r#"{"tiers":{"personal":{},"personal_plus":{},"crew":{},"team":{},"institution":{}}}"#,
        )
        .unwrap();
    }

    fn write_chain_events_spec(path: &std::path::Path) {
        std::fs::write(
            path,
            r#"
elements:
  - element_type: chain_event_schema
    event: telemetry_submitted
    required: [event_type, event_id, timestamp_utc, record_hash]
"#,
        )
        .unwrap();
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
            binary_sha256: "sha256:test".to_string(),
            toolchain_version: "rustc-test".to_string(),
        }
    }

    fn record(event_type: &str, prev: Option<&str>) -> Value {
        let mut record = json!({
            "event_type": event_type,
            "event_id": "evt",
            "timestamp_utc": "2026-05-23T14:30:00Z",
            "prev_record_hash": prev,
            "record_hash": null,
        });
        record["record_hash"] = Value::String(record_hash(&record).unwrap());
        record
    }
}

#[cfg(test)]
mod tests_support {
    pub const TEST_PRIVATE_PEM: &str = "-----BEGIN PRIVATE KEY-----\nMC4CAQAwBQYDK2VwBCIEIAABAgMEBQYHCAkKCwwNDg8QERITFBUWFxgZGhscHR4f\n-----END PRIVATE KEY-----\n";
}
