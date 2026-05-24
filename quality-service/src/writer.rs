use crate::canonical::{canonical_json, record_hash, record_hash_preimage};
use crate::checks::EnvironmentSnapshot;
use crate::key::QaSigningKey;
use chrono::Utc;
use serde_json::{Map, Value};
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};

/// Maximum total serialized bytes the `findings` array of an aggregate QA
/// record (qa_behavioral_analysis, qa_element_verification) may consume.
/// Picked to leave ~1KB of headroom under the 4096-byte writer cap for the
/// rest of the record envelope (event_type, sequence, timestamps, hashes,
/// signature, signing_key_id, plus per-record summary fields). When the
/// caller's findings exceed this budget the writer truncates the array and
/// sets `findings_truncated: true`; the original total stays visible via
/// the existing anomaly_count / elements_flagged fields on the record.
const FINDINGS_BUDGET_BYTES: usize = 3000;

pub struct QaChainWriter {
    path: PathBuf,
    key: QaSigningKey,
    next_sequence: u64,
    prev_record_hash: Option<String>,
}

impl QaChainWriter {
    pub fn new(path: PathBuf, key: QaSigningKey) -> Result<Self, String> {
        let (next_sequence, prev_record_hash) = inspect_tail(&path)?;
        Ok(Self {
            path,
            key,
            next_sequence,
            prev_record_hash,
        })
    }

    pub fn append_environmental_snapshot(
        &mut self,
        snapshot: &EnvironmentSnapshot,
    ) -> Result<Value, String> {
        let mut record = Map::new();
        record.insert(
            "event_type".to_string(),
            Value::String("qa_environmental_snapshot".to_string()),
        );
        record.insert("sequence".to_string(), Value::from(self.next_sequence));
        record.insert(
            "timestamp_utc".to_string(),
            Value::String(Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Millis, true)),
        );
        record.insert(
            "policy_rules_hash".to_string(),
            Value::String(snapshot.policy_rules_hash.clone()),
        );
        record.insert(
            "capability_registry_hash".to_string(),
            Value::String(snapshot.capability_registry_hash.clone()),
        );
        record.insert("checks".to_string(), snapshot.checks_value());
        record.insert(
            "active_conditions".to_string(),
            Value::Array(
                snapshot
                    .active_conditions
                    .iter()
                    .cloned()
                    .map(Value::String)
                    .collect(),
            ),
        );
        record.insert(
            "overall".to_string(),
            Value::String(snapshot.overall.clone()),
        );
        self.append_record(Value::Object(record))
    }

    pub fn append_decision_verification(
        &mut self,
        governance_record_hash: &str,
        decision_type: &str,
        tool_name: &str,
        checks_performed: Value,
        all_clear: bool,
        findings: Vec<Value>,
    ) -> Result<Value, String> {
        let mut record = base_event("qa_decision_verification", self.next_sequence);
        record.insert(
            "governance_record_hash".to_string(),
            Value::String(governance_record_hash.to_string()),
        );
        record.insert(
            "decision_type".to_string(),
            Value::String(decision_type.to_string()),
        );
        record.insert(
            "tool_name".to_string(),
            Value::String(tool_name.to_string()),
        );
        record.insert("checks_performed".to_string(), checks_performed);
        record.insert("all_clear".to_string(), Value::Bool(all_clear));
        record.insert("findings".to_string(), Value::Array(findings));
        self.append_record(Value::Object(record))
    }

    pub fn append_decision_verification_skipped(
        &mut self,
        governance_record_hash: &str,
        reason: &str,
    ) -> Result<Value, String> {
        let mut record = base_event("qa_decision_verification_skipped", self.next_sequence);
        record.insert(
            "governance_record_hash".to_string(),
            Value::String(governance_record_hash.to_string()),
        );
        record.insert("reason".to_string(), Value::String(reason.to_string()));
        self.append_record(Value::Object(record))
    }

    pub fn append_verification_backlog_warning(
        &mut self,
        queue_depth: usize,
        queue_capacity: usize,
    ) -> Result<Value, String> {
        let mut record = base_event("qa_verification_backlog_warning", self.next_sequence);
        record.insert("queue_depth".to_string(), Value::from(queue_depth as u64));
        record.insert(
            "queue_capacity".to_string(),
            Value::from(queue_capacity as u64),
        );
        self.append_record(Value::Object(record))
    }

    pub fn append_condition_detected(
        &mut self,
        condition_id: &str,
        condition_type: &str,
        severity: &str,
        detail: &str,
        governance_record_ref: Option<&str>,
    ) -> Result<Value, String> {
        let mut record = base_event("qa_condition_detected", self.next_sequence);
        record.insert(
            "condition_id".to_string(),
            Value::String(condition_id.to_string()),
        );
        record.insert(
            "condition_type".to_string(),
            Value::String(condition_type.to_string()),
        );
        record.insert("severity".to_string(), Value::String(severity.to_string()));
        record.insert("detail".to_string(), Value::String(detail.to_string()));
        record.insert(
            "governance_record_ref".to_string(),
            governance_record_ref
                .map(|value| Value::String(value.to_string()))
                .unwrap_or(Value::Null),
        );
        self.append_record(Value::Object(record))
    }

    pub fn append_spc_finding(
        &mut self,
        metric_id: &str,
        metric_name: &str,
        current_value: f64,
        ucl: f64,
        lcl: f64,
        window: &str,
        status: &str,
    ) -> Result<Value, String> {
        let mut record = base_event("qa_spc_finding", self.next_sequence);
        record.insert(
            "metric_id".to_string(),
            Value::String(metric_id.to_string()),
        );
        record.insert(
            "metric_name".to_string(),
            Value::String(metric_name.to_string()),
        );
        record.insert("current_value".to_string(), finite_value(current_value)?);
        record.insert("ucl".to_string(), finite_value(ucl)?);
        record.insert("lcl".to_string(), finite_value(lcl)?);
        record.insert("window".to_string(), Value::String(window.to_string()));
        record.insert("status".to_string(), Value::String(status.to_string()));
        self.append_record(Value::Object(record))
    }

    pub fn append_behavioral_analysis(
        &mut self,
        analysis_window: &str,
        findings: Vec<Value>,
    ) -> Result<Value, String> {
        let total = findings.len();
        let (bounded, truncated) = bound_findings_to_budget(findings, FINDINGS_BUDGET_BYTES);
        let mut record = base_event("qa_behavioral_analysis", self.next_sequence);
        record.insert(
            "analysis_window".to_string(),
            Value::String(analysis_window.to_string()),
        );
        record.insert("anomaly_count".to_string(), Value::from(total as u64));
        record.insert(
            "findings_included_count".to_string(),
            Value::from(bounded.len() as u64),
        );
        if truncated {
            record.insert("findings_truncated".to_string(), Value::Bool(true));
        }
        record.insert("findings".to_string(), Value::Array(bounded));
        self.append_record(Value::Object(record))
    }

    pub fn append_element_verification(
        &mut self,
        spec_id: &str,
        elements_checked: usize,
        elements_passed: usize,
        elements_flagged: usize,
        elements_skipped: usize,
        findings: Vec<Value>,
        coverage: Value,
    ) -> Result<Value, String> {
        let (bounded, truncated) = bound_findings_to_budget(findings, FINDINGS_BUDGET_BYTES);
        let mut record = base_event("qa_element_verification", self.next_sequence);
        record.insert("spec_id".to_string(), Value::String(spec_id.to_string()));
        record.insert(
            "elements_checked".to_string(),
            Value::from(elements_checked as u64),
        );
        record.insert(
            "elements_passed".to_string(),
            Value::from(elements_passed as u64),
        );
        record.insert(
            "elements_flagged".to_string(),
            Value::from(elements_flagged as u64),
        );
        record.insert(
            "elements_skipped".to_string(),
            Value::from(elements_skipped as u64),
        );
        record.insert(
            "findings_included_count".to_string(),
            Value::from(bounded.len() as u64),
        );
        if truncated {
            record.insert("findings_truncated".to_string(), Value::Bool(true));
        }
        record.insert("findings".to_string(), Value::Array(bounded));
        record.insert("coverage".to_string(), coverage);
        self.append_record(Value::Object(record))
    }

    pub fn append_record(&mut self, mut value: Value) -> Result<Value, String> {
        let object = value
            .as_object_mut()
            .ok_or_else(|| "QA chain record must be an object".to_string())?;
        object.insert(
            "prev_record_hash".to_string(),
            self.prev_record_hash
                .clone()
                .map(Value::String)
                .unwrap_or(Value::Null),
        );
        object.insert("record_hash".to_string(), Value::Null);
        object.insert("signature".to_string(), Value::Null);
        object.insert("signing_key_id".to_string(), Value::Null);

        let hash = record_hash(&value)?;
        value["record_hash"] = Value::String(hash.clone());
        let preimage = record_hash_preimage(&value)?;
        value["signature"] = Value::String(self.key.sign_b64url(preimage.as_bytes()));
        value["signing_key_id"] = Value::String(self.key.key_id().to_string());

        let line = canonical_json(&value)?;
        if line.len() > 4096 {
            return Err(format!(
                "QA chain record exceeds 4KB atomic append limit: {} bytes",
                line.len()
            ));
        }
        self.append_line(&line)?;
        self.prev_record_hash = Some(hash);
        self.next_sequence += 1;
        Ok(value)
    }

    fn append_line(&self, line: &str) -> Result<(), String> {
        if let Some(parent) = self.path.parent() {
            fs::create_dir_all(parent).map_err(|err| {
                format!(
                    "failed to create QA chain directory {}: {err}",
                    parent.display()
                )
            })?;
        }
        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.path)
            .map_err(|err| format!("failed to open QA chain {}: {err}", self.path.display()))?;
        file.write_all(line.as_bytes())
            .and_then(|_| file.write_all(b"\n"))
            .and_then(|_| file.flush())
            .map_err(|err| format!("failed to append QA chain record: {err}"))
    }
}

fn base_event(event_type: &str, sequence: u64) -> Map<String, Value> {
    let mut record = Map::new();
    record.insert(
        "event_type".to_string(),
        Value::String(event_type.to_string()),
    );
    record.insert("sequence".to_string(), Value::from(sequence));
    record.insert(
        "timestamp_utc".to_string(),
        Value::String(Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Millis, true)),
    );
    record
}

/// Truncate the findings array so its canonical serialization fits within
/// `budget_bytes`. Returns (bounded_array, truncated_flag). Findings are
/// included in order until the next one would exceed the budget, then the
/// remainder is dropped. A finding that, by itself, exceeds the budget is
/// also skipped (so the resulting array is empty but the truncated flag is
/// set, which signals the caller to investigate the producer). Producers
/// remain responsible for emitting per-item records when full fidelity is
/// required; this helper exists so aggregate summary records cannot push
/// the QA chain over the 4KB atomic-append limit on any single line.
pub(crate) fn bound_findings_to_budget(
    findings: Vec<Value>,
    budget_bytes: usize,
) -> (Vec<Value>, bool) {
    let total = findings.len();
    let mut included: Vec<Value> = Vec::with_capacity(total);
    // Track array overhead: opening '[', closing ']', and one ',' between
    // every adjacent pair. Each finding's own serialized form is counted
    // by canonical_json on the value.
    let mut used = 2usize; // for '[' and ']'
    for finding in findings.into_iter() {
        let serialized = match canonical_json(&finding) {
            Ok(text) => text,
            Err(_) => continue,
        };
        let separator = if included.is_empty() { 0 } else { 1 };
        let projected = used + separator + serialized.len();
        if projected > budget_bytes {
            // Stop on first finding that would overflow. Remaining findings
            // are dropped; the caller marks the record as truncated.
            return (included, true);
        }
        used = projected;
        included.push(finding);
    }
    let truncated = included.len() < total;
    (included, truncated)
}

fn finite_value(value: f64) -> Result<Value, String> {
    if !value.is_finite() {
        return Err("QA numeric fields must be finite".to_string());
    }
    serde_json::Number::from_f64(value)
        .map(Value::Number)
        .ok_or_else(|| "failed to encode finite number".to_string())
}

fn inspect_tail(path: &Path) -> Result<(u64, Option<String>), String> {
    if !path.exists() {
        return Ok((1, None));
    }
    let raw = fs::read_to_string(path)
        .map_err(|err| format!("failed to read existing QA chain {}: {err}", path.display()))?;
    let Some(line) = raw.lines().rev().find(|line| !line.trim().is_empty()) else {
        return Ok((1, None));
    };
    let record: Value = serde_json::from_str(line)
        .map_err(|err| format!("invalid last QA chain record in {}: {err}", path.display()))?;
    let sequence = record.get("sequence").and_then(Value::as_u64).unwrap_or(0);
    let hash = record
        .get("record_hash")
        .and_then(Value::as_str)
        .map(str::to_string);
    Ok((sequence + 1, hash))
}
