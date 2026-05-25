use crate::canonical::{record_hash, record_hash_preimage};
use crate::config::Config;
use crate::key::verifying_key_from_private_key;
use crate::spc::SpcMonitor;
use crate::writer::QaChainWriter;
use base64::engine::general_purpose::URL_SAFE_NO_PAD;
use base64::Engine as _;
use ed25519_dalek::{Signature, Verifier, VerifyingKey};
use serde_json::{json, Map, Value};
use std::collections::VecDeque;
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct CheckOutcome {
    pub status: String,
    pub detail: String,
    pub severity: String,
    pub condition_id: Option<String>,
    pub condition_type: Option<String>,
}

impl CheckOutcome {
    pub fn pass() -> Self {
        Self {
            status: "pass".to_string(),
            detail: String::new(),
            severity: "medium".to_string(),
            condition_id: None,
            condition_type: None,
        }
    }

    pub fn fail(
        severity: &str,
        detail: impl Into<String>,
        condition_id: Option<&str>,
        condition_type: Option<&str>,
    ) -> Self {
        Self {
            status: "fail".to_string(),
            detail: detail.into(),
            severity: severity.to_string(),
            condition_id: condition_id.map(str::to_string),
            condition_type: condition_type.map(str::to_string),
        }
    }
}

#[derive(Clone, Debug)]
pub struct DecisionVerification {
    pub governance_record_hash: String,
    pub decision_type: String,
    pub tool_name: String,
    pub checks: Vec<(String, CheckOutcome)>,
}

impl DecisionVerification {
    pub fn all_clear(&self) -> bool {
        self.checks
            .iter()
            .all(|(_name, outcome)| outcome.status == "pass")
    }

    pub fn checks_value(&self) -> Value {
        let mut map = Map::new();
        for (name, outcome) in &self.checks {
            if outcome.status == "pass" {
                map.insert(name.clone(), Value::String("pass".to_string()));
            } else {
                map.insert(
                    name.clone(),
                    json!({
                        "status": outcome.status,
                        "severity": outcome.severity,
                        "detail": outcome.detail,
                        "condition_id": outcome.condition_id,
                    }),
                );
            }
        }
        Value::Object(map)
    }

    pub fn findings_value(&self) -> Vec<Value> {
        self.checks
            .iter()
            .filter_map(|(name, outcome)| {
                if outcome.status == "pass" {
                    return None;
                }
                Some(json!({
                    "check": name,
                    "severity": outcome.severity,
                    "detail": outcome.detail,
                    "condition_id": outcome.condition_id,
                    "condition_type": outcome.condition_type,
                }))
            })
            .collect()
    }
}

#[derive(Debug)]
pub struct GovernanceChainWatcher {
    path: PathBuf,
    cached_mtime_ns: Option<u128>,
    cached_size: u64,
    cached_offset: u64,
    records: Vec<Value>,
}

impl GovernanceChainWatcher {
    pub fn new(path: PathBuf) -> Self {
        Self {
            path,
            cached_mtime_ns: None,
            cached_size: 0,
            cached_offset: 0,
            records: Vec::new(),
        }
    }

    pub fn poll_new_records(&mut self) -> Result<Vec<Value>, String> {
        let stat = match self.path.metadata() {
            Ok(stat) => stat,
            Err(err) if err.kind() == std::io::ErrorKind::NotFound => {
                self.reset();
                return Ok(Vec::new());
            }
            Err(err) => {
                return Err(format!(
                    "failed to stat governance chain {}: {err}",
                    self.path.display()
                ));
            }
        };
        let mtime_ns = mtime_ns(&stat);
        if self.cached_mtime_ns == Some(mtime_ns) && self.cached_size == stat.len() {
            return Ok(Vec::new());
        }
        if stat.len() < self.cached_offset {
            self.reset();
        }
        let raw = if self.cached_offset == 0 {
            fs::read_to_string(&self.path).map_err(|err| {
                format!(
                    "failed to read governance chain {}: {err}",
                    self.path.display()
                )
            })?
        } else {
            use std::io::{Read, Seek, SeekFrom};
            let mut file = fs::File::open(&self.path).map_err(|err| {
                format!(
                    "failed to open governance chain {}: {err}",
                    self.path.display()
                )
            })?;
            file.seek(SeekFrom::Start(self.cached_offset))
                .map_err(|err| format!("failed to seek governance chain: {err}"))?;
            let mut raw = String::new();
            file.read_to_string(&mut raw)
                .map_err(|err| format!("failed to read governance chain tail: {err}"))?;
            raw
        };
        let new_records = parse_lines(&raw)?;
        self.cached_mtime_ns = Some(mtime_ns);
        self.cached_size = stat.len();
        self.cached_offset = stat.len();
        self.records.extend(new_records.clone());
        Ok(new_records)
    }

    pub fn records(&self) -> &[Value] {
        &self.records
    }

    fn reset(&mut self) {
        self.cached_mtime_ns = None;
        self.cached_size = 0;
        self.cached_offset = 0;
        self.records.clear();
    }
}

#[derive(Debug)]
pub struct PostHocVerifier {
    config: Config,
    queue: VecDeque<Value>,
    active_conditions: Vec<String>,
}

impl PostHocVerifier {
    pub fn new(config: Config) -> Self {
        Self {
            config,
            queue: VecDeque::new(),
            active_conditions: Vec::new(),
        }
    }

    pub fn active_conditions(&self) -> Vec<String> {
        self.active_conditions.clone()
    }

    pub fn enqueue_records(
        &mut self,
        records: Vec<Value>,
        writer: &mut QaChainWriter,
    ) -> Result<(), String> {
        for record in records.into_iter().filter(is_governance_decision) {
            if self.queue.len() >= self.config.verification_queue_depth {
                writer.append_verification_backlog_warning(
                    self.queue.len(),
                    self.config.verification_queue_depth,
                )?;
                let hash = record
                    .get("record_hash")
                    .and_then(Value::as_str)
                    .unwrap_or("unknown");
                writer.append_decision_verification_skipped(hash, "verification_queue_overflow")?;
            } else {
                self.queue.push_back(record);
            }
        }
        Ok(())
    }

    pub fn drain_queue(
        &mut self,
        all_records: &[Value],
        spc: &mut SpcMonitor,
        writer: &mut QaChainWriter,
    ) -> Result<Vec<DecisionVerification>, String> {
        let mut output = Vec::new();
        while let Some(record) = self.queue.pop_front() {
            let verification = verify_decision(&self.config, all_records, &record, spc);
            writer.append_decision_verification(
                &verification.governance_record_hash,
                &verification.decision_type,
                &verification.tool_name,
                verification.checks_value(),
                verification.all_clear(),
                verification.findings_value(),
            )?;
            for (_name, outcome) in &verification.checks {
                if outcome.status == "fail" && outcome.severity == "critical" {
                    let condition_id = outcome
                        .condition_id
                        .clone()
                        .unwrap_or_else(|| "CR-CRIT-005".to_string());
                    if !self.active_conditions.contains(&condition_id) {
                        self.active_conditions.push(condition_id.clone());
                    }
                    writer.append_condition_detected(
                        &condition_id,
                        outcome
                            .condition_type
                            .as_deref()
                            .unwrap_or("post_hoc_verification_failure"),
                        "critical",
                        &outcome.detail,
                        Some(&verification.governance_record_hash),
                    )?;
                }
            }
            spc.observe_decision(&record, writer)?;
            output.push(verification);
        }
        Ok(output)
    }
}

pub fn verify_decision(
    config: &Config,
    all_records: &[Value],
    record: &Value,
    spc: &SpcMonitor,
) -> DecisionVerification {
    let governance_record_hash = record
        .get("record_hash")
        .and_then(Value::as_str)
        .unwrap_or("unknown")
        .to_string();
    let decision_type = record
        .get("policy_decision")
        .and_then(Value::as_str)
        .unwrap_or("UNKNOWN")
        .to_string();
    let tool_name = tool_name(record);
    let checks = vec![
        (
            "structural_integrity".to_string(),
            structural_integrity(config, all_records, record),
        ),
        (
            "classification_consistency".to_string(),
            classification_consistency(config, all_records, record),
        ),
        (
            "approval_provenance".to_string(),
            approval_provenance(config, all_records, record),
        ),
        (
            "negative_constraints".to_string(),
            negative_constraint_compliance(record),
        ),
        ("behavioral_baseline".to_string(), behavioral_baseline(spc)),
    ];
    DecisionVerification {
        governance_record_hash,
        decision_type,
        tool_name,
        checks,
    }
}

pub fn is_governance_decision(record: &Value) -> bool {
    matches!(
        record.get("policy_decision").and_then(Value::as_str),
        Some("ALLOW") | Some("DENY")
    )
}

fn structural_integrity(config: &Config, all_records: &[Value], record: &Value) -> CheckOutcome {
    match record_hash(record) {
        Ok(expected)
            if record.get("record_hash").and_then(Value::as_str) == Some(expected.as_str()) => {}
        Ok(expected) => {
            return CheckOutcome::fail(
                "critical",
                format!(
                    "record_hash mismatch: expected {expected}, got {:?}",
                    record.get("record_hash").and_then(Value::as_str)
                ),
                Some("CR-CRIT-005"),
                Some("environment_critical"),
            );
        }
        Err(err) => {
            return CheckOutcome::fail(
                "critical",
                err,
                Some("CR-CRIT-005"),
                Some("environment_critical"),
            );
        }
    }

    if let Some(index) = all_records
        .iter()
        .position(|candidate| same_record(candidate, record))
    {
        let expected_prev = if index == 0 {
            None
        } else {
            all_records[index - 1]
                .get("record_hash")
                .and_then(Value::as_str)
        };
        let actual_prev = record.get("prev_record_hash").and_then(Value::as_str);
        if actual_prev != expected_prev {
            return CheckOutcome::fail(
                "critical",
                format!(
                    "prev_record_hash mismatch: expected {expected_prev:?}, got {actual_prev:?}"
                ),
                Some("CR-CRIT-005"),
                Some("environment_critical"),
            );
        }
    }

    if let Some(signature) = record.get("signature").and_then(Value::as_str) {
        if !signature.is_empty() {
            if let Some(path) = &config.governance_signing_key_path {
                match verify_signature(path, record, signature) {
                    Ok(()) => {}
                    Err(err) => {
                        return CheckOutcome::fail(
                            "critical",
                            err,
                            Some("CR-HIGH-002"),
                            Some("unsigned_or_invalid_record"),
                        );
                    }
                }
            }
        }
    }
    CheckOutcome::pass()
}

fn verify_signature(path: &Path, record: &Value, signature: &str) -> Result<(), String> {
    let verifying: VerifyingKey = verifying_key_from_private_key(path)?;
    let signature_bytes = URL_SAFE_NO_PAD
        .decode(signature.as_bytes())
        .map_err(|err| format!("invalid signature base64url: {err}"))?;
    let signature = Signature::from_slice(&signature_bytes)
        .map_err(|err| format!("invalid Ed25519 signature bytes: {err}"))?;
    let preimage = record_hash_preimage(record)?;
    verifying
        .verify(preimage.as_bytes(), &signature)
        .map_err(|err| format!("signature verification failed: {err}"))
}

fn classification_consistency(
    config: &Config,
    all_records: &[Value],
    record: &Value,
) -> CheckOutcome {
    let tool = tool_name(record);
    let current = classification_category(record);
    let Some(index) = all_records
        .iter()
        .position(|candidate| same_record(candidate, record))
    else {
        return CheckOutcome::pass();
    };
    let mut seen = 0usize;
    for prior in all_records[..index].iter().rev() {
        if !is_governance_decision(prior) || tool_name(prior) != tool {
            continue;
        }
        seen += 1;
        let previous = classification_category(prior);
        if previous != current && !classifier_update_between(&all_records[..index], prior, record) {
            return CheckOutcome::fail(
                "high",
                format!("classification changed for {tool}: {previous} -> {current}"),
                Some("CR-HIGH-001"),
                Some("classification_anomaly"),
            );
        }
        if seen >= config.classification_history {
            break;
        }
    }
    CheckOutcome::pass()
}

fn approval_provenance(config: &Config, all_records: &[Value], record: &Value) -> CheckOutcome {
    let approval_id = record
        .get("approval_event_id")
        .or_else(|| record.get("approval_id"))
        .and_then(Value::as_str);
    let uses_approval = approval_id.is_some()
        || record.get("matched_rule").and_then(Value::as_str) == Some("approved_lookup");
    if !uses_approval {
        return CheckOutcome::pass();
    }
    let Some(approval_id) = approval_id else {
        return CheckOutcome::fail(
            "critical",
            "decision used approval override but did not reference an approval event",
            Some("CR-CRIT-003"),
            Some("invalid_approval"),
        );
    };
    let Some(approval_index) = all_records.iter().position(|candidate| {
        candidate.get("event_type").and_then(Value::as_str) == Some("opaque_artifact_approval")
            && (candidate.get("event_id").and_then(Value::as_str) == Some(approval_id)
                || candidate.get("approval_id").and_then(Value::as_str) == Some(approval_id)
                || candidate.get("record_hash").and_then(Value::as_str) == Some(approval_id))
    }) else {
        return CheckOutcome::fail(
            "critical",
            format!("approval {approval_id} not found in chain history"),
            Some("CR-CRIT-003"),
            Some("invalid_approval"),
        );
    };
    if all_records[approval_index + 1..].iter().any(|candidate| {
        candidate.get("event_type").and_then(Value::as_str) == Some("opaque_artifact_revocation")
            && (candidate.get("approval_event_id").and_then(Value::as_str) == Some(approval_id)
                || candidate.get("event_id").and_then(Value::as_str) == Some(approval_id)
                || candidate.get("approval_id").and_then(Value::as_str) == Some(approval_id))
    }) {
        return CheckOutcome::fail(
            "critical",
            format!("approval {approval_id} was revoked before decision verification"),
            Some("CR-CRIT-003"),
            Some("invalid_approval"),
        );
    }
    if config.approval_max_age_seconds > 0 {
        if let (Some(approval_ts), Some(decision_ts)) = (
            timestamp_seconds(&all_records[approval_index]),
            timestamp_seconds(record),
        ) {
            let age = decision_ts.saturating_sub(approval_ts);
            if age > config.approval_max_age_seconds {
                return CheckOutcome::fail(
                    "critical",
                    format!("approval {approval_id} exceeded maximum age: {age}s"),
                    Some("CR-CRIT-007"),
                    Some("operator_session_expiry"),
                );
            }
        }
    }
    CheckOutcome::pass()
}

fn negative_constraint_compliance(record: &Value) -> CheckOutcome {
    if record.get("policy_decision").and_then(Value::as_str) != Some("ALLOW") {
        return CheckOutcome::pass();
    }
    let classification = record.get("classification").unwrap_or(&Value::Null);
    let explicit_match = classification
        .get("negative_constraint_match")
        .and_then(Value::as_bool)
        .unwrap_or(false)
        || record
            .get("matched_negative_constraint")
            .and_then(Value::as_str)
            .is_some();
    if explicit_match {
        return CheckOutcome::fail(
            "critical",
            "ALLOW decision matched a declared negative constraint",
            Some("CR-CRIT-002"),
            Some("negative_constraint_violation"),
        );
    }
    CheckOutcome::pass()
}

fn behavioral_baseline(spc: &SpcMonitor) -> CheckOutcome {
    if spc.learning() {
        CheckOutcome {
            status: "pass".to_string(),
            detail: "SPC baseline still learning".to_string(),
            severity: "medium".to_string(),
            condition_id: None,
            condition_type: None,
        }
    } else {
        CheckOutcome::pass()
    }
}

fn parse_lines(raw: &str) -> Result<Vec<Value>, String> {
    raw.lines()
        .filter(|line| !line.trim().is_empty())
        .map(|line| {
            serde_json::from_str(line).map_err(|err| format!("invalid governance JSON: {err}"))
        })
        .collect()
}

fn same_record(left: &Value, right: &Value) -> bool {
    left.get("record_hash").and_then(Value::as_str)
        == right.get("record_hash").and_then(Value::as_str)
}

fn tool_name(record: &Value) -> String {
    record
        .get("original_tool")
        .or_else(|| record.get("tool_name"))
        .and_then(Value::as_str)
        .unwrap_or("unknown")
        .to_string()
}

fn classification_category(record: &Value) -> String {
    let classification = record.get("classification").unwrap_or(&Value::Null);
    classification
        .get("category")
        .or_else(|| classification.get("action_type"))
        .or_else(|| classification.get("confidence_tier"))
        .map(|value| {
            value
                .as_str()
                .map(str::to_string)
                .unwrap_or_else(|| value.to_string())
        })
        .unwrap_or_else(|| "unknown".to_string())
}

fn classifier_update_between(slice: &[Value], prior: &Value, current: &Value) -> bool {
    let Some(start) = slice
        .iter()
        .position(|candidate| same_record(candidate, prior))
    else {
        return false;
    };
    let Some(end) = slice
        .iter()
        .position(|candidate| same_record(candidate, current))
    else {
        return slice[start + 1..].iter().any(is_classifier_update);
    };
    slice[start + 1..end].iter().any(is_classifier_update)
}

fn is_classifier_update(record: &Value) -> bool {
    let event = record
        .get("event_type")
        .or_else(|| record.get("record_type"))
        .and_then(Value::as_str)
        .unwrap_or("");
    event.contains("classifier") || event.contains("capability_registry")
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

fn mtime_ns(stat: &fs::Metadata) -> u128 {
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;
        stat.mtime() as u128 * 1_000_000_000 + stat.mtime_nsec() as u128
    }
    #[cfg(not(unix))]
    {
        stat.modified()
            .ok()
            .and_then(|time| time.duration_since(std::time::UNIX_EPOCH).ok())
            .map(|duration| duration.as_nanos())
            .unwrap_or(0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::canonical::{canonical_json, record_hash};
    use crate::key::QaSigningKey;
    use crate::spc::SpcMonitor;
    use crate::writer::QaChainWriter;
    use serde_json::json;
    use std::time::Duration;

    const TEST_PRIVATE_PEM: &str = "-----BEGIN PRIVATE KEY-----\nMC4CAQAwBQYDK2VwBCIEIAABAgMEBQYHCAkKCwwNDg8QERITFBUWFxgZGhscHR4f\n-----END PRIVATE KEY-----\n";

    #[test]
    fn governance_chain_watcher_detects_new_records() {
        let dir = tempfile::tempdir().unwrap();
        let chain = dir.path().join("decision-chain.jsonl");
        fs::write(&chain, "").unwrap();
        let mut watcher = GovernanceChainWatcher::new(chain.clone());
        assert!(watcher.poll_new_records().unwrap().is_empty());

        let record = decision("Read", "read", "ALLOW", None);
        fs::write(&chain, canonical_json(&record).unwrap() + "\n").unwrap();
        let records = watcher.poll_new_records().unwrap();
        assert_eq!(records.len(), 1);
        assert_eq!(records[0]["policy_decision"], "ALLOW");
    }

    #[test]
    fn structural_integrity_catches_tampered_hash() {
        let dir = tempfile::tempdir().unwrap();
        let config = test_config(dir.path());
        let mut record = decision("Read", "read", "ALLOW", None);
        record["record_hash"] = Value::String("sha256:bad".to_string());
        let spc = SpcMonitor::new(100, dir.path().join("spc.json"));
        let verification = verify_decision(&config, &[record.clone()], &record, &spc);
        assert_eq!(check(&verification, "structural_integrity").status, "fail");
    }

    #[test]
    fn structural_integrity_catches_broken_linkage() {
        let dir = tempfile::tempdir().unwrap();
        let config = test_config(dir.path());
        let first = decision("Read", "read", "ALLOW", None);
        let second = decision("Write", "write", "DENY", Some("sha256:not-previous"));
        let spc = SpcMonitor::new(100, dir.path().join("spc.json"));
        let verification = verify_decision(&config, &[first, second.clone()], &second, &spc);
        assert_eq!(check(&verification, "structural_integrity").status, "fail");
    }

    #[test]
    fn classification_consistency_flags_category_change() {
        let dir = tempfile::tempdir().unwrap();
        let config = test_config(dir.path());
        let first = decision("Tool", "read", "ALLOW", None);
        let second = decision(
            "Tool",
            "write",
            "DENY",
            first.get("record_hash").and_then(Value::as_str),
        );
        let spc = SpcMonitor::new(100, dir.path().join("spc.json"));
        let verification = verify_decision(&config, &[first, second.clone()], &second, &spc);
        assert_eq!(
            check(&verification, "classification_consistency").status,
            "fail"
        );
    }

    #[test]
    fn approval_provenance_detects_missing_approval() {
        let dir = tempfile::tempdir().unwrap();
        let config = test_config(dir.path());
        let mut record = decision("Write", "write", "ALLOW", None);
        record["matched_rule"] = Value::String("approved_lookup".to_string());
        record["approval_event_id"] = Value::String("approval-missing".to_string());
        record["record_hash"] = Value::String(record_hash(&record).unwrap());
        let spc = SpcMonitor::new(100, dir.path().join("spc.json"));
        let verification = verify_decision(&config, &[record.clone()], &record, &spc);
        assert_eq!(check(&verification, "approval_provenance").status, "fail");
    }

    #[test]
    fn approval_provenance_detects_revoked_approval() {
        let dir = tempfile::tempdir().unwrap();
        let config = test_config(dir.path());
        let approval = event(
            "opaque_artifact_approval",
            json!({"event_id": "approval-1"}),
            None,
        );
        let revocation = event(
            "opaque_artifact_revocation",
            json!({"approval_event_id": "approval-1"}),
            approval.get("record_hash").and_then(Value::as_str),
        );
        let mut record = decision(
            "Write",
            "write",
            "ALLOW",
            revocation.get("record_hash").and_then(Value::as_str),
        );
        record["matched_rule"] = Value::String("approved_lookup".to_string());
        record["approval_event_id"] = Value::String("approval-1".to_string());
        record["record_hash"] = Value::String(record_hash(&record).unwrap());
        let spc = SpcMonitor::new(100, dir.path().join("spc.json"));
        let all = vec![approval, revocation, record.clone()];
        let verification = verify_decision(&config, &all, &record, &spc);
        assert_eq!(check(&verification, "approval_provenance").status, "fail");
    }

    #[test]
    fn negative_constraint_compliance_flags_allow_match() {
        let dir = tempfile::tempdir().unwrap();
        let config = test_config(dir.path());
        let mut record = decision("Delete", "delete", "ALLOW", None);
        record["classification"]["negative_constraint_match"] = Value::Bool(true);
        record["record_hash"] = Value::String(record_hash(&record).unwrap());
        let spc = SpcMonitor::new(100, dir.path().join("spc.json"));
        let verification = verify_decision(&config, &[record.clone()], &record, &spc);
        assert_eq!(check(&verification, "negative_constraints").status, "fail");
    }

    #[test]
    fn queue_overflow_writes_backlog_warning_and_skip() {
        let dir = tempfile::tempdir().unwrap();
        let mut config = test_config(dir.path());
        config.verification_queue_depth = 1;
        let qa_key = dir.path().join("qa.pem");
        fs::write(&qa_key, TEST_PRIVATE_PEM).unwrap();
        let mut writer = QaChainWriter::new(
            dir.path().join("qa-chain.jsonl"),
            QaSigningKey::load(&qa_key).unwrap(),
        )
        .unwrap();
        let mut verifier = PostHocVerifier::new(config);
        verifier
            .enqueue_records(
                vec![
                    decision("Read", "read", "ALLOW", None),
                    decision("Write", "write", "DENY", None),
                ],
                &mut writer,
            )
            .unwrap();
        let raw = fs::read_to_string(dir.path().join("qa-chain.jsonl")).unwrap();
        assert!(raw.contains("qa_verification_backlog_warning"));
        assert!(raw.contains("qa_decision_verification_skipped"));
    }

    fn check<'a>(verification: &'a DecisionVerification, name: &str) -> &'a CheckOutcome {
        &verification
            .checks
            .iter()
            .find(|(candidate, _)| candidate == name)
            .unwrap()
            .1
    }

    fn test_config(root: &Path) -> Config {
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
            approval_max_age_seconds: 24 * 60 * 60,
            spc_min_decisions: 100,
            spc_baseline_path: root.join("quality-service/spc-baselines.json"),
            behavioral_interval: Duration::from_secs(3600),
            behavioral_min_decisions: 100,
            element_interval: Duration::from_secs(600),
            element_tail_records: 100,
            chain_events_spec_path: root.join("chain-events-v1.yaml"),
            chain_integrity_spec_path: root.join("chain-integrity-spec-v1.yaml"),
            tier_registry_path: root.join("tier-feature-registry.json"),
            binary_sha256: "sha256:test".to_string(),
            toolchain_version: "rustc-test".to_string(),
        }
    }

    fn decision(tool: &str, action: &str, policy_decision: &str, prev: Option<&str>) -> Value {
        let mut record = json!({
            "record_type": "mediated_decision",
            "timestamp_utc": "2026-05-23T14:30:00Z",
            "original_tool": tool,
            "classification": {"action_type": action, "confidence_tier": 1},
            "policy_decision": policy_decision,
            "matched_rule": "test_rule",
            "policy_reasons": [],
            "prev_record_hash": prev,
            "record_hash": null,
        });
        record["record_hash"] = Value::String(record_hash(&record).unwrap());
        record
    }

    fn event(event_type: &str, extra: Value, prev: Option<&str>) -> Value {
        let mut record = json!({
            "event_type": event_type,
            "timestamp_utc": "2026-05-23T14:30:00Z",
            "prev_record_hash": prev,
            "record_hash": null,
        });
        for (key, value) in extra.as_object().unwrap() {
            record[key] = value.clone();
        }
        record["record_hash"] = Value::String(record_hash(&record).unwrap());
        record
    }
}
