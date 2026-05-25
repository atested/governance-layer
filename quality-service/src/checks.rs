use crate::canonical::{canonical_policy_hash, record_hash, sha256_prefixed_bytes};
use crate::config::Config;
use crate::key::validate_ed25519_private_key;
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};
use std::collections::BTreeMap;
use std::fs;
use std::os::unix::ffi::OsStrExt;
use std::path::{Path, PathBuf};

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum CheckStatus {
    Pass,
    Fail,
    Warning,
    NotApplicable,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CheckResult {
    pub status: CheckStatus,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub detail: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub severity: Option<String>,
    #[serde(flatten)]
    pub metrics: BTreeMap<String, Value>,
}

impl CheckResult {
    pub fn pass() -> Self {
        Self {
            status: CheckStatus::Pass,
            detail: None,
            severity: None,
            metrics: BTreeMap::new(),
        }
    }

    pub fn fail(severity: &str, detail: impl Into<String>) -> Self {
        Self {
            status: CheckStatus::Fail,
            detail: Some(detail.into()),
            severity: Some(severity.to_string()),
            metrics: BTreeMap::new(),
        }
    }

    pub fn not_applicable(detail: impl Into<String>) -> Self {
        Self {
            status: CheckStatus::NotApplicable,
            detail: Some(detail.into()),
            severity: None,
            metrics: BTreeMap::new(),
        }
    }
}

#[derive(Clone, Debug)]
pub struct EnvironmentSnapshot {
    pub policy_rules_hash: String,
    pub capability_registry_hash: String,
    pub checks: BTreeMap<String, CheckResult>,
    pub active_conditions: Vec<String>,
    pub overall: String,
}

impl EnvironmentSnapshot {
    pub fn checks_value(&self) -> Value {
        let mut map = Map::new();
        for (id, check) in &self.checks {
            map.insert(
                id.clone(),
                serde_json::to_value(check)
                    .unwrap_or_else(|_| Value::String("serialization_error".to_string())),
            );
        }
        Value::Object(map)
    }
}

pub fn run_all_checks(config: &Config) -> EnvironmentSnapshot {
    let policy_rules_hash = compute_policy_rules_hash(&config.policy_rules_path)
        .unwrap_or_else(|err| format!("error:{err}"));
    let capability_registry_hash =
        compute_capability_registry_hash(&config.capability_registry_path)
            .unwrap_or_else(|err| format!("error:{err}"));

    let mut checks = BTreeMap::new();
    checks.insert(
        "ENV-001".to_string(),
        check_policy_rules_currency(config, &policy_rules_hash),
    );
    checks.insert("ENV-002".to_string(), check_governance_signing_key(config));
    checks.insert("ENV-003".to_string(), check_qa_signing_key(config));
    checks.insert(
        "ENV-004".to_string(),
        check_chain_health(&config.governance_chain_path, config.tail_records),
    );
    checks.insert(
        "ENV-005".to_string(),
        check_chain_health(&config.qa_chain_path, config.tail_records),
    );
    checks.insert(
        "ENV-006".to_string(),
        check_approval_store_consistency(&config.governance_chain_path),
    );
    checks.insert(
        "ENV-007".to_string(),
        check_disk_resources(&config.runtime_root),
    );
    checks.insert("ENV-008".to_string(), check_classifier_state(config));
    checks.insert("ENV-009".to_string(), check_proxy_process(config));
    checks.insert(
        "ENV-010".to_string(),
        check_capability_registry_currency(config, &capability_registry_hash),
    );
    checks.insert(
        "ENV-011".to_string(),
        check_governance_posture(&config.capability_registry_path),
    );

    let mut active_conditions = Vec::new();
    if checks
        .get("ENV-001")
        .map(|r| r.status == CheckStatus::Fail)
        .unwrap_or(false)
    {
        active_conditions.push("CR-CRIT-001".to_string());
    }
    if checks
        .get("ENV-010")
        .map(|r| r.status == CheckStatus::Fail)
        .unwrap_or(false)
    {
        active_conditions.push("CR-CRIT-004".to_string());
    }
    if checks
        .get("ENV-011")
        .map(|r| r.status == CheckStatus::Fail)
        .unwrap_or(false)
    {
        active_conditions.push("CR-HIGH-003".to_string());
    }
    for (id, result) in &checks {
        if result.status == CheckStatus::Fail && result.severity.as_deref() == Some("critical") {
            let condition = format!("CR-CRIT-005:{id}");
            if !active_conditions.contains(&condition) {
                active_conditions.push(condition);
            }
        }
    }

    let overall = if checks
        .values()
        .any(|result| result.status == CheckStatus::Fail)
    {
        "unhealthy".to_string()
    } else {
        "healthy".to_string()
    };

    EnvironmentSnapshot {
        policy_rules_hash,
        capability_registry_hash,
        checks,
        active_conditions,
        overall,
    }
}

pub fn critical_failures(snapshot: &EnvironmentSnapshot) -> Vec<String> {
    snapshot
        .checks
        .iter()
        .filter_map(|(id, result)| {
            if result.status == CheckStatus::Fail && result.severity.as_deref() == Some("critical")
            {
                Some(format!(
                    "{id}: {}",
                    result.detail.as_deref().unwrap_or("failed")
                ))
            } else {
                None
            }
        })
        .collect()
}

pub fn compute_policy_rules_hash(path: &Path) -> Result<String, String> {
    let raw = fs::read_to_string(path)
        .map_err(|err| format!("failed to read policy rules {}: {err}", path.display()))?;
    let value: Value = serde_json::from_str(&raw)
        .map_err(|err| format!("failed to parse policy rules {}: {err}", path.display()))?;
    canonical_policy_hash(&value)
}

pub fn compute_capability_registry_hash(path: &Path) -> Result<String, String> {
    let raw = fs::read(path).map_err(|err| {
        format!(
            "failed to read capability registry {}: {err}",
            path.display()
        )
    })?;
    Ok(sha256_prefixed_bytes(&raw))
}

fn check_policy_rules_currency(config: &Config, current_hash: &str) -> CheckResult {
    if current_hash.starts_with("error:") {
        return CheckResult::fail("critical", current_hash.to_string());
    }
    match last_governance_chain_hash(&config.governance_chain_path, "policy_rules_hash") {
        Ok(Some(proxy_hash)) if proxy_hash == current_hash => CheckResult::pass(),
        Ok(Some(proxy_hash)) => CheckResult::fail(
            "critical",
            format!("policy_rules_hash mismatch: current={current_hash}, proxy_chain={proxy_hash}"),
        ),
        Ok(None) => CheckResult::pass(),
        Err(err) => CheckResult::fail("critical", err),
    }
}

fn check_governance_signing_key(config: &Config) -> CheckResult {
    let Some(path) = &config.governance_signing_key_path else {
        return CheckResult::not_applicable("GOV_SIGNING_KEY_PATH is not configured");
    };
    match validate_ed25519_private_key(path) {
        Ok(fingerprint) => {
            let mut result = CheckResult::pass();
            result
                .metrics
                .insert("fingerprint".to_string(), Value::String(fingerprint));
            result
        }
        Err(err) => CheckResult::fail("high", err),
    }
}

fn check_qa_signing_key(config: &Config) -> CheckResult {
    match crate::key::QaSigningKey::load(&config.qa_signing_key_path)
        .and_then(|key| key.self_check())
    {
        Ok(()) => CheckResult::pass(),
        Err(err) => CheckResult::fail("critical", err),
    }
}

fn check_capability_registry_currency(config: &Config, current_hash: &str) -> CheckResult {
    if current_hash.starts_with("error:") {
        return CheckResult::fail("high", current_hash.to_string());
    }
    match last_governance_chain_hash(&config.governance_chain_path, "capability_registry_hash") {
        Ok(Some(proxy_hash)) if proxy_hash == current_hash => CheckResult::pass(),
        Ok(Some(proxy_hash)) => CheckResult::fail(
            "high",
            format!("capability_registry_hash mismatch: current={current_hash}, proxy_chain={proxy_hash}"),
        ),
        Ok(None) => CheckResult::pass(),
        Err(err) => CheckResult::fail("high", err),
    }
}

fn check_governance_posture(path: &Path) -> CheckResult {
    let raw = match fs::read_to_string(path) {
        Ok(raw) => raw,
        Err(err) => {
            return CheckResult::fail(
                "high",
                format!("failed to read capability registry {}: {err}", path.display()),
            );
        }
    };
    let value: Value = match serde_json::from_str(&raw) {
        Ok(value) => value,
        Err(err) => {
            return CheckResult::fail(
                "high",
                format!("failed to parse capability registry {}: {err}", path.display()),
            );
        }
    };
    let mode = value
        .get("governance_posture")
        .and_then(|posture| {
            if let Some(obj) = posture.as_object() {
                obj.get("mode").and_then(Value::as_str)
            } else {
                posture.as_str()
            }
        })
        .unwrap_or("production")
        .trim()
        .to_ascii_lowercase();
    let mut result = if mode == "developer" {
        CheckResult::fail(
            "high",
            "Proxy operating in developer mode — governance posture is relaxed for unrecognized formats",
        )
    } else {
        CheckResult::pass()
    };
    result
        .metrics
        .insert("mode".to_string(), Value::String(mode));
    result
}

fn check_chain_health(path: &Path, tail_records: usize) -> CheckResult {
    if !path.exists() {
        return CheckResult::pass();
    }
    match read_tail_records(path, tail_records) {
        Ok(records) => {
            for pair in records.windows(2) {
                let previous = &pair[0];
                let current = &pair[1];
                let Some(previous_hash) = previous.get("record_hash").and_then(Value::as_str)
                else {
                    return CheckResult::fail("critical", "chain record missing record_hash");
                };
                let current_prev = current.get("prev_record_hash").and_then(Value::as_str);
                if current_prev != Some(previous_hash) {
                    return CheckResult::fail(
                        "critical",
                        format!("hash linkage mismatch: expected prev_record_hash {previous_hash:?}, got {current_prev:?}"),
                    );
                }
            }
            for record in &records {
                match record_hash(record) {
                    Ok(expected) => {
                        if record.get("record_hash").and_then(Value::as_str)
                            != Some(expected.as_str())
                        {
                            return CheckResult::fail(
                                "critical",
                                "record_hash verification failed",
                            );
                        }
                    }
                    Err(err) => return CheckResult::fail("critical", err),
                }
            }
            CheckResult::pass()
        }
        Err(err) => CheckResult::fail("critical", err),
    }
}

fn check_approval_store_consistency(path: &Path) -> CheckResult {
    if !path.exists() {
        return CheckResult::pass();
    }
    match read_tail_records(path, usize::MAX) {
        Ok(records) => {
            let mut active = 0usize;
            for record in records {
                match record.get("event_type").and_then(Value::as_str) {
                    Some("opaque_artifact_approval") => active += 1,
                    Some("opaque_artifact_revocation") => active = active.saturating_sub(1),
                    _ => {}
                }
            }
            let mut result = CheckResult::pass();
            result
                .metrics
                .insert("active_approval_events".to_string(), Value::from(active));
            result
        }
        Err(err) => CheckResult::fail("high", err),
    }
}

fn check_disk_resources(path: &Path) -> CheckResult {
    match available_mb(path) {
        Ok(available) => {
            let mut result = if available < 100 {
                CheckResult::fail(
                    "high",
                    format!("disk_available_mb below threshold: {available}"),
                )
            } else {
                CheckResult::pass()
            };
            result
                .metrics
                .insert("disk_available_mb".to_string(), Value::from(available));
            result
        }
        Err(err) => CheckResult::fail("high", err),
    }
}

fn check_classifier_state(config: &Config) -> CheckResult {
    let classifier = config.repo_root.join("scripts/classifier.py");
    if classifier.is_file() {
        CheckResult::pass()
    } else {
        CheckResult::fail(
            "high",
            format!("classifier source not found: {}", classifier.display()),
        )
    }
}

fn check_proxy_process(config: &Config) -> CheckResult {
    let services_path = config.runtime_root.join("supervisor/services.json");
    if let Ok(raw) = fs::read_to_string(&services_path) {
        match serde_json::from_str::<Value>(&raw) {
            Ok(value) => {
                let running = value
                    .get("proxy")
                    .and_then(|proxy| proxy.get("running"))
                    .and_then(Value::as_bool)
                    .unwrap_or(false);
                if running {
                    CheckResult::pass()
                } else {
                    CheckResult::fail("critical", "supervisor reports proxy is not running")
                }
            }
            Err(err) => CheckResult::fail(
                "critical",
                format!("invalid supervisor services.json: {err}"),
            ),
        }
    } else if config.require_proxy_running {
        CheckResult::fail(
            "critical",
            "proxy process status unavailable and ATESTED_QS_REQUIRE_PROXY_RUNNING=true",
        )
    } else {
        CheckResult::not_applicable("proxy process check deferred until supervisor status exists")
    }
}

fn last_governance_chain_hash(path: &Path, field: &str) -> Result<Option<String>, String> {
    if !path.exists() {
        return Ok(None);
    }
    let records = read_tail_records(path, 200)?;
    for record in records.iter().rev() {
        if let Some(value) = record.get(field).and_then(Value::as_str) {
            return Ok(Some(value.to_string()));
        }
    }
    Ok(None)
}

fn read_tail_records(path: &Path, limit: usize) -> Result<Vec<Value>, String> {
    let raw = fs::read_to_string(path)
        .map_err(|err| format!("failed to read chain {}: {err}", path.display()))?;
    let mut lines: Vec<&str> = raw.lines().filter(|line| !line.trim().is_empty()).collect();
    if limit != usize::MAX && lines.len() > limit {
        lines = lines.split_off(lines.len() - limit);
    }
    let mut records = Vec::with_capacity(lines.len());
    for line in lines {
        let record: Value = serde_json::from_str(line)
            .map_err(|err| format!("invalid chain JSON in {}: {err}", path.display()))?;
        records.push(record);
    }
    Ok(records)
}

fn available_mb(path: &Path) -> Result<u64, String> {
    let mut current = PathBuf::from(path);
    while !current.exists() {
        if !current.pop() {
            break;
        }
    }
    let c_path = std::ffi::CString::new(current.as_os_str().as_bytes())
        .map_err(|_| format!("path contains NUL byte: {}", current.display()))?;
    let mut stat: libc::statvfs = unsafe { std::mem::zeroed() };
    let rc = unsafe { libc::statvfs(c_path.as_ptr(), &mut stat) };
    if rc != 0 {
        return Err(format!("statvfs failed for {}", current.display()));
    }
    let available = stat.f_bavail as u128 * stat.f_frsize as u128;
    Ok((available / 1024 / 1024) as u64)
}
