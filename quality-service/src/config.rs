use std::env;
use std::path::PathBuf;
use std::time::Duration;

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
        let runtime_root = env::var("GOV_RUNTIME_DIR")
            .map(PathBuf::from)
            .unwrap_or_else(|_| repo_root.join("gov_runtime"));
        let qa_signing_key_path = env::var("ATESTED_QA_SIGNING_KEY_PATH")
            .or_else(|_| env::var("GOV_QA_SIGNING_KEY_PATH"))
            .map(PathBuf::from)
            .unwrap_or_else(|_| runtime_root.join(".atested-qa-signing-key.pem"));
        let governance_signing_key_path = env::var("GOV_SIGNING_KEY_PATH").ok().map(PathBuf::from);
        let policy_rules_path = env::var("GOV_POLICY_RULES_PATH")
            .map(PathBuf::from)
            .unwrap_or_else(|_| repo_root.join("capabilities/policy-rules.json"));
        let capability_registry_path = env::var("GOV_CAPABILITY_REGISTRY_PATH")
            .map(PathBuf::from)
            .unwrap_or_else(|_| repo_root.join("capabilities/capability-registry.json"));
        let governance_chain_path = env::var("GOV_DECISION_CHAIN_PATH")
            .map(PathBuf::from)
            .unwrap_or_else(|_| runtime_root.join("LOGS/decision-chain.jsonl"));
        let qa_chain_path = env::var("GOV_QA_CHAIN_PATH")
            .map(PathBuf::from)
            .unwrap_or_else(|_| runtime_root.join("LOGS/qa-chain.jsonl"));
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
        })
    }
}
