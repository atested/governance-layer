use std::env;
use std::path::PathBuf;
use std::time::Duration;

/// QS-033 A3: read an env var, preferring the `ATESTED_*` name and falling
/// back to a `GOV_*` legacy alias. A stderr deprecation warning is emitted
/// when the legacy variant is the only one set.
///
/// The legacy `GOV_*` names predate the QS-029 `ATESTED_*` naming convention.
/// QS-031 fell into the trap of guessing the prefix; the alias map plus the
/// warning surface the migration without breaking existing operator scripts.
fn read_env_preferred(canonical: &str, legacy: &str) -> Option<String> {
    if let Ok(value) = env::var(canonical) {
        return Some(value);
    }
    if let Ok(value) = env::var(legacy) {
        eprintln!(
            "warning: env var {legacy} is deprecated; use {canonical} (the legacy name still works for one release window)"
        );
        return Some(value);
    }
    None
}

#[derive(Clone, Debug)]
pub struct Config {
    pub repo_root: PathBuf,
    pub runtime_root: PathBuf,
    pub qa_signing_key_path: PathBuf,
    pub governance_signing_key_path: Option<PathBuf>,
    pub policy_rules_path: PathBuf,
    pub capability_registry_path: PathBuf,
    pub governance_chain_path: PathBuf,
    pub qa_chain_path: PathBuf,
    pub heartbeat: Duration,
    pub ready_file: Option<PathBuf>,
    pub require_proxy_running: bool,
    pub tail_records: usize,
    pub verification_queue_depth: usize,
    pub classification_history: usize,
    pub approval_max_age_seconds: u64,
    pub spc_min_decisions: usize,
    pub spc_baseline_path: PathBuf,
    pub behavioral_interval: Duration,
    pub element_interval: Duration,
    pub element_tail_records: usize,
    pub chain_events_spec_path: PathBuf,
    pub chain_integrity_spec_path: PathBuf,
    pub tier_registry_path: PathBuf,
    /// QS-039 Adv #13: sha256 of the running quality-service binary and the
    /// toolchain that built it. Stamped into the first qa_environmental_snapshot
    /// for the "what binary actually ran?" audit trail. Informational only —
    /// never consulted by the environmental gate.
    pub binary_sha256: String,
    pub toolchain_version: String,
}

/// sha256 of the currently-running executable, "sha256:" prefixed to match
/// the chain's hash convention. Returns "unknown" if the binary cannot be
/// located or read (e.g. an unusual exec environment) — this is an
/// informational field and must never block startup.
fn current_binary_sha256() -> String {
    use sha2::{Digest, Sha256};
    match env::current_exe().and_then(std::fs::read) {
        Ok(bytes) => format!("sha256:{:x}", Sha256::digest(&bytes)),
        Err(_) => "unknown".to_string(),
    }
}

impl Config {
    pub fn from_env() -> Result<Self, String> {
        let repo_root = env::var("ATESTED_REPO_ROOT")
            .map(PathBuf::from)
            .unwrap_or_else(|_| {
                PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                    .parent()
                    .expect("quality-service has repo parent")
                    .to_path_buf()
            });
        // QS-033 A3: ATESTED_* is canonical; GOV_* aliases work but warn.
        // The Python codebase still uses GOV_* extensively — a sweep across
        // proxy/, dashboard/, scripts/ is a follow-on dispatch. The Rust
        // crate is the surface I burned on in QS-031, so it normalizes here
        // and the rest follows later without breaking existing operator env
        // exports.
        let runtime_root = read_env_preferred("ATESTED_RUNTIME_DIR", "GOV_RUNTIME_DIR")
            .map(PathBuf::from)
            .unwrap_or_else(|| repo_root.join("gov_runtime"));
        let qa_signing_key_path =
            read_env_preferred("ATESTED_QA_SIGNING_KEY_PATH", "GOV_QA_SIGNING_KEY_PATH")
                .map(PathBuf::from)
                .unwrap_or_else(|| runtime_root.join(".atested-qa-signing-key.pem"));
        let governance_signing_key_path =
            read_env_preferred("ATESTED_SIGNING_KEY_PATH", "GOV_SIGNING_KEY_PATH")
                .map(PathBuf::from);
        let policy_rules_path =
            read_env_preferred("ATESTED_POLICY_RULES_PATH", "GOV_POLICY_RULES_PATH")
                .map(PathBuf::from)
                .unwrap_or_else(|| repo_root.join("capabilities/policy-rules.json"));
        let capability_registry_path = read_env_preferred(
            "ATESTED_CAPABILITY_REGISTRY_PATH",
            "GOV_CAPABILITY_REGISTRY_PATH",
        )
        .map(PathBuf::from)
        .unwrap_or_else(|| repo_root.join("capabilities/capability-registry.json"));
        let governance_chain_path =
            read_env_preferred("ATESTED_DECISION_CHAIN_PATH", "GOV_DECISION_CHAIN_PATH")
                .map(PathBuf::from)
                .unwrap_or_else(|| runtime_root.join("LOGS/decision-chain.jsonl"));
        let qa_chain_path = read_env_preferred("ATESTED_QA_CHAIN_PATH", "GOV_QA_CHAIN_PATH")
            .map(PathBuf::from)
            .unwrap_or_else(|| runtime_root.join("LOGS/qa-chain.jsonl"));
        let heartbeat_seconds = env::var("ATESTED_QS_HEARTBEAT_SECONDS")
            .ok()
            .and_then(|value| value.parse::<u64>().ok())
            .unwrap_or(30);
        let ready_file = env::var("ATESTED_QS_READY_FILE").ok().map(PathBuf::from);
        let require_proxy_running = env::var("ATESTED_QS_REQUIRE_PROXY_RUNNING")
            .map(|value| matches!(value.as_str(), "1" | "true" | "TRUE" | "yes"))
            .unwrap_or(false);
        let tail_records = env::var("ATESTED_QS_TAIL_RECORDS")
            .ok()
            .and_then(|value| value.parse::<usize>().ok())
            .unwrap_or(100);
        let verification_queue_depth = env::var("ATESTED_QS_VERIFICATION_QUEUE_DEPTH")
            .ok()
            .and_then(|value| value.parse::<usize>().ok())
            .unwrap_or(1000);
        let classification_history = env::var("ATESTED_QS_CLASSIFICATION_HISTORY")
            .ok()
            .and_then(|value| value.parse::<usize>().ok())
            .unwrap_or(10);
        let approval_max_age_seconds = env::var("ATESTED_QS_APPROVAL_MAX_AGE_SECONDS")
            .ok()
            .and_then(|value| value.parse::<u64>().ok())
            .unwrap_or(24 * 60 * 60);
        let spc_min_decisions = env::var("ATESTED_QS_SPC_MIN_DECISIONS")
            .ok()
            .and_then(|value| value.parse::<usize>().ok())
            .unwrap_or(100);
        let spc_baseline_path = env::var("ATESTED_QS_SPC_BASELINE_PATH")
            .map(PathBuf::from)
            .unwrap_or_else(|_| runtime_root.join("quality-service/spc-baselines.json"));
        let behavioral_interval_seconds = env::var("ATESTED_QS_BEHAVIORAL_INTERVAL_SECONDS")
            .ok()
            .and_then(|value| value.parse::<u64>().ok())
            .unwrap_or(60 * 60);
        let element_interval_seconds = env::var("ATESTED_QS_ELEMENT_INTERVAL_SECONDS")
            .ok()
            .and_then(|value| value.parse::<u64>().ok())
            .unwrap_or(10 * 60);
        let element_tail_records = env::var("ATESTED_QS_ELEMENT_TAIL_RECORDS")
            .ok()
            .and_then(|value| value.parse::<usize>().ok())
            .unwrap_or(100);
        // Spec sources live in the repo at governance-layer/specs/. Prior to
        // QS-029 these defaults reached outside the repo into the Claude.ai
        // project mirror; QS-029 moved them in.
        let spec_root = repo_root.join("specs");
        let chain_events_spec_path = env::var("ATESTED_CHAIN_EVENTS_SPEC_PATH")
            .map(PathBuf::from)
            .unwrap_or_else(|_| spec_root.join("chain-events-v1.yaml"));
        let chain_integrity_spec_path = env::var("ATESTED_CHAIN_INTEGRITY_SPEC_PATH")
            .map(PathBuf::from)
            .unwrap_or_else(|_| spec_root.join("chain-integrity-spec-v1.yaml"));
        let tier_registry_path = env::var("ATESTED_TIER_REGISTRY_PATH")
            .map(PathBuf::from)
            .unwrap_or_else(|_| repo_root.join("dashboard/ui-next/tier-feature-registry.json"));

        Ok(Self {
            repo_root,
            runtime_root,
            qa_signing_key_path,
            governance_signing_key_path,
            policy_rules_path,
            capability_registry_path,
            governance_chain_path,
            qa_chain_path,
            heartbeat: Duration::from_secs(heartbeat_seconds.max(1)),
            ready_file,
            require_proxy_running,
            tail_records: tail_records.max(2),
            verification_queue_depth: verification_queue_depth.max(1),
            classification_history: classification_history.max(1),
            approval_max_age_seconds,
            spc_min_decisions: spc_min_decisions.max(1),
            spc_baseline_path,
            behavioral_interval: Duration::from_secs(behavioral_interval_seconds.max(1)),
            element_interval: Duration::from_secs(element_interval_seconds.max(1)),
            element_tail_records: element_tail_records.max(2),
            chain_events_spec_path,
            chain_integrity_spec_path,
            tier_registry_path,
            binary_sha256: current_binary_sha256(),
            toolchain_version: env!("ATESTED_RUSTC_VERSION").to_string(),
        })
    }
}
