use crate::writer::QaChainWriter;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::PathBuf;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SpcBaseline {
    pub metric_id: String,
    pub metric_name: String,
    pub center_line: f64,
    pub stddev: f64,
    pub ucl: f64,
    pub lcl: f64,
    pub samples: usize,
    pub window: String,
}

#[derive(Debug)]
pub struct SpcMonitor {
    min_decisions: usize,
    baseline_path: PathBuf,
    decisions: Vec<Value>,
    baselines: BTreeMap<String, SpcBaseline>,
    active_findings: BTreeSet<String>,
}

impl SpcMonitor {
    pub fn new(min_decisions: usize, baseline_path: PathBuf) -> Self {
        let baselines = load_baselines(&baseline_path).unwrap_or_default();
        Self {
            min_decisions,
            baseline_path,
            decisions: Vec::new(),
            baselines,
            active_findings: BTreeSet::new(),
        }
    }

    pub fn initialize(&mut self, records: &[Value]) -> Result<(), String> {
        self.decisions = records
            .iter()
            .filter(|record| is_decision(record))
            .cloned()
            .collect();
        if self.baselines.is_empty() && self.decisions.len() >= self.min_decisions {
            self.baselines = compute_baselines(&self.decisions);
            self.persist()?;
        }
        Ok(())
    }

    pub fn learning(&self) -> bool {
        self.decisions.len() < self.min_decisions || self.baselines.is_empty()
    }

    pub fn decisions_collected(&self) -> usize {
        self.decisions.len()
    }

    pub fn observe_decision(
        &mut self,
        record: &Value,
        writer: &mut QaChainWriter,
    ) -> Result<Vec<String>, String> {
        if !is_decision(record) {
            return Ok(Vec::new());
        }
        self.decisions.push(record.clone());
        if self.learning() {
            if self.decisions.len() >= self.min_decisions && self.baselines.is_empty() {
                self.baselines = compute_baselines(&self.decisions);
                self.persist()?;
            }
            return Ok(Vec::new());
        }

        let current = current_metrics(&self.decisions);
        let mut findings = Vec::new();
        for (metric_id, value) in current {
            let Some(baseline) = self.baselines.get(&metric_id) else {
                continue;
            };
            let outside = value > baseline.ucl || value < baseline.lcl;
            if outside {
                let status = if value > baseline.ucl {
                    "above_ucl"
                } else {
                    "below_lcl"
                };
                writer.append_spc_finding(
                    &baseline.metric_id,
                    &baseline.metric_name,
                    value,
                    baseline.ucl,
                    baseline.lcl,
                    &baseline.window,
                    status,
                )?;
                self.active_findings.insert(metric_id.clone());
                findings.push(metric_id);
            } else {
                self.active_findings.remove(&metric_id);
            }
        }
        Ok(findings)
    }

    pub fn active_findings(&self) -> BTreeSet<String> {
        self.active_findings.clone()
    }

    fn persist(&self) -> Result<(), String> {
        if let Some(parent) = self.baseline_path.parent() {
            fs::create_dir_all(parent).map_err(|err| {
                format!(
                    "failed to create SPC baseline directory {}: {err}",
                    parent.display()
                )
            })?;
        }
        let raw = serde_json::to_string_pretty(&self.baselines)
            .map_err(|err| format!("failed to encode SPC baselines: {err}"))?;
        fs::write(&self.baseline_path, raw).map_err(|err| {
            format!(
                "failed to write SPC baseline file {}: {err}",
                self.baseline_path.display()
            )
        })
    }
}

pub fn compute_baselines(decisions: &[Value]) -> BTreeMap<String, SpcBaseline> {
    let mut map = BTreeMap::new();
    let metrics = current_metrics(decisions);
    for (metric_id, value) in metrics {
        let (name, window) = metric_info(&metric_id);
        map.insert(
            metric_id.clone(),
            SpcBaseline {
                metric_id,
                metric_name: name.to_string(),
                center_line: value,
                stddev: 0.0,
                ucl: value,
                lcl: value,
                samples: decisions.len(),
                window: window.to_string(),
            },
        );
    }
    map
}

pub fn current_metrics(decisions: &[Value]) -> BTreeMap<String, f64> {
    let mut map = BTreeMap::new();
    let count = decisions.len().max(1) as f64;
    let allow = decisions
        .iter()
        .filter(|record| record.get("policy_decision").and_then(Value::as_str) == Some("ALLOW"))
        .count() as f64;
    let approvals = decisions
        .iter()
        .filter(|record| record.get("approval_event_id").is_some())
        .count() as f64;
    let mut classes: BTreeMap<String, usize> = BTreeMap::new();
    let mut rules: BTreeMap<String, usize> = BTreeMap::new();
    let mut tools: BTreeSet<String> = BTreeSet::new();
    for record in decisions {
        *classes.entry(classification(record)).or_insert(0) += 1;
        *rules.entry(rule(record)).or_insert(0) += 1;
        tools.insert(tool(record));
    }
    map.insert("SPC-001".to_string(), allow / count);
    map.insert("SPC-002".to_string(), entropy(&classes, count));
    map.insert(
        "SPC-003".to_string(),
        rules.values().copied().max().unwrap_or(0) as f64 / count,
    );
    map.insert("SPC-004".to_string(), approvals);
    map.insert("SPC-005".to_string(), count);
    map.insert("SPC-006".to_string(), tools.len() as f64);
    map.insert("SPC-007".to_string(), average_latency(decisions));
    map
}

fn load_baselines(path: &PathBuf) -> Result<BTreeMap<String, SpcBaseline>, String> {
    if !path.exists() {
        return Ok(BTreeMap::new());
    }
    let raw = fs::read_to_string(path)
        .map_err(|err| format!("failed to read SPC baselines {}: {err}", path.display()))?;
    serde_json::from_str(&raw)
        .map_err(|err| format!("failed to parse SPC baselines {}: {err}", path.display()))
}

fn is_decision(record: &Value) -> bool {
    matches!(
        record.get("policy_decision").and_then(Value::as_str),
        Some("ALLOW") | Some("DENY")
    )
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

fn rule(record: &Value) -> String {
    record
        .get("matched_rule")
        .and_then(Value::as_str)
        .unwrap_or("unknown")
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

fn entropy(counts: &BTreeMap<String, usize>, total: f64) -> f64 {
    counts
        .values()
        .map(|count| {
            let p = *count as f64 / total;
            if p > 0.0 {
                -(p * p.log2())
            } else {
                0.0
            }
        })
        .sum()
}

fn average_latency(decisions: &[Value]) -> f64 {
    let mut values = Vec::new();
    for record in decisions {
        if let Some(value) = record
            .get("decision_latency_ms")
            .or_else(|| record.get("latency_ms"))
            .and_then(Value::as_f64)
        {
            values.push(value);
        }
    }
    if values.is_empty() {
        0.0
    } else {
        values.iter().sum::<f64>() / values.len() as f64
    }
}

fn metric_info(metric_id: &str) -> (&'static str, &'static str) {
    match metric_id {
        "SPC-001" => ("ALLOW rate", "aggregate"),
        "SPC-002" => ("Classification entropy", "24h"),
        "SPC-003" => ("Rule concentration", "24h"),
        "SPC-004" => ("Approval velocity", "24h"),
        "SPC-005" => ("Decision throughput", "aggregate"),
        "SPC-006" => ("Tool diversity", "24h"),
        "SPC-007" => ("Decision latency", "per-decision"),
        _ => ("Unknown metric", "aggregate"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::canonical::record_hash;
    use crate::key::QaSigningKey;
    use crate::writer::QaChainWriter;
    use serde_json::{json, Value};
    use std::fs;

    const TEST_PRIVATE_PEM: &str = "-----BEGIN PRIVATE KEY-----\nMC4CAQAwBQYDK2VwBCIEIAABAgMEBQYHCAkKCwwNDg8QERITFBUWFxgZGhscHR4f\n-----END PRIVATE KEY-----\n";

    #[test]
    fn spc_baseline_computation_from_chain() {
        let decisions = decisions(100, "DENY");
        let baselines = compute_baselines(&decisions);
        assert_eq!(baselines["SPC-001"].center_line, 0.0);
        assert_eq!(baselines["SPC-005"].center_line, 100.0);
        assert!(baselines.contains_key("SPC-007"));
    }

    #[test]
    fn spc_learning_mode_does_not_produce_findings_before_minimum() {
        let dir = tempfile::tempdir().unwrap();
        let mut monitor = SpcMonitor::new(100, dir.path().join("spc.json"));
        monitor.initialize(&decisions(10, "DENY")).unwrap();
        assert!(monitor.learning());
        let mut writer = writer(dir.path());
        let findings = monitor
            .observe_decision(&decision("ALLOW", 11), &mut writer)
            .unwrap();
        assert!(findings.is_empty());
        assert!(!dir.path().join("qa-chain.jsonl").exists());
    }

    #[test]
    fn spc_metric_crossing_control_limit_produces_finding() {
        let dir = tempfile::tempdir().unwrap();
        let mut monitor = SpcMonitor::new(100, dir.path().join("spc.json"));
        monitor.initialize(&decisions(100, "DENY")).unwrap();
        assert!(!monitor.learning());
        let mut writer = writer(dir.path());
        let findings = monitor
            .observe_decision(&decision("ALLOW", 101), &mut writer)
            .unwrap();
        assert!(findings.contains(&"SPC-001".to_string()));
        let raw = fs::read_to_string(dir.path().join("qa-chain.jsonl")).unwrap();
        assert!(raw.contains("qa_spc_finding"));
        assert!(raw.contains("SPC-001"));
    }

    #[test]
    fn spc_metric_returning_within_limits_clears_finding() {
        let dir = tempfile::tempdir().unwrap();
        let mut monitor = SpcMonitor::new(100, dir.path().join("spc.json"));
        monitor.initialize(&decisions(100, "DENY")).unwrap();
        let mut writer = writer(dir.path());
        monitor
            .observe_decision(&decision("ALLOW", 101), &mut writer)
            .unwrap();
        assert!(monitor.active_findings().contains("SPC-001"));

        monitor.baselines.get_mut("SPC-001").unwrap().ucl = 1.0;
        monitor
            .observe_decision(&decision("DENY", 102), &mut writer)
            .unwrap();
        assert!(!monitor.active_findings().contains("SPC-001"));
    }

    fn decisions(count: usize, policy_decision: &str) -> Vec<Value> {
        (0..count)
            .map(|idx| decision(policy_decision, idx as u64))
            .collect()
    }

    fn decision(policy_decision: &str, idx: u64) -> Value {
        let mut record = json!({
            "record_type": "mediated_decision",
            "timestamp_utc": "2026-05-23T14:30:00Z",
            "original_tool": format!("tool-{}", idx % 3),
            "classification": {"action_type": "read"},
            "policy_decision": policy_decision,
            "matched_rule": "baseline_rule",
            "policy_reasons": [],
            "decision_latency_ms": 1.0,
            "prev_record_hash": null,
            "record_hash": null,
        });
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
