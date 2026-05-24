use base64::Engine as _;
use ed25519_dalek::{Signature, Verifier, VerifyingKey};
use quality_service::canonical::{
    canonical_json, canonical_policy_hash, record_hash, record_hash_preimage,
};
use serde_json::{json, Value};
use sha2::Digest as _;
use std::fs;
use std::process::{Command, Stdio};
use std::thread;
use std::time::{Duration, Instant};
use tempfile::TempDir;

const TEST_PRIVATE_PEM: &str = "-----BEGIN PRIVATE KEY-----\nMC4CAQAwBQYDK2VwBCIEIAABAgMEBQYHCAkKCwwNDg8QERITFBUWFxgZGhscHR4f\n-----END PRIVATE KEY-----\n";
const TEST_PUBLIC_RAW_HEX: &str =
    "03a107bff3ce10be1d70dd18e74bc09967e4d6309ba50d5f1ddc8664125531b8";

#[test]
fn quality_service_writes_snapshots_and_proxy_reader_reads_them() {
    let env = TestEnv::new();
    let ready_file = env.runtime.path().join("supervisor/quality-service.ready");
    let mut child = Command::new(env!("CARGO_BIN_EXE_quality-service"))
        .env("ATESTED_REPO_ROOT", repo_root())
        .env("GOV_RUNTIME_DIR", env.runtime.path())
        .env("ATESTED_QA_SIGNING_KEY_PATH", &env.qa_key)
        .env("GOV_POLICY_RULES_PATH", &env.policy_path)
        .env("GOV_CAPABILITY_REGISTRY_PATH", &env.capability_path)
        .env("GOV_DECISION_CHAIN_PATH", &env.governance_chain)
        .env("GOV_QA_CHAIN_PATH", &env.qa_chain)
        .env("ATESTED_QS_HEARTBEAT_SECONDS", "1")
        .env("ATESTED_QS_READY_FILE", &ready_file)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("spawn quality service");

    wait_for(|| ready_file.exists(), "ready file");
    wait_for(
        || read_records(&env.qa_chain).len() >= 1,
        "initial QA snapshot",
    );
    let initial = read_records(&env.qa_chain);
    assert_snapshot_valid(&initial[0], 1, None);
    assert_eq!(initial[0]["overall"], "healthy");

    let python_status = Command::new("python3")
        .arg("-c")
        .arg(format!(
            "import sys; sys.path[:0]=[{repo:?},{scripts:?}]; from proxy.qa_gate import QAChainTailReader; r=QAChainTailReader({qa:?}).latest_snapshot(); print(r.status, r.snapshot.get('sequence'))",
            repo = repo_root(),
            scripts = format!("{}/scripts", repo_root()),
            qa = env.qa_chain.display().to_string(),
        ))
        .output()
        .expect("run python qa gate");
    assert!(
        python_status.status.success(),
        "{}",
        String::from_utf8_lossy(&python_status.stderr)
    );
    assert_eq!(
        String::from_utf8_lossy(&python_status.stdout).trim(),
        "ok 1"
    );

    fs::write(
        &env.policy_path,
        "{\"rules\":[],\"default_decision\":\"DENY\"}\n",
    )
    .unwrap();
    wait_for(
        || {
            latest_snapshot(&env.qa_chain)["active_conditions"]
                .as_array()
                .unwrap()
                .iter()
                .any(|value| value.as_str() == Some("CR-CRIT-001"))
        },
        "stale policy condition",
    );
    let stale = latest_snapshot(&env.qa_chain);
    assert_eq!(stale["overall"], "unhealthy");

    fs::write(
        &env.policy_path,
        "{\"rules\":[],\"default_decision\":\"ALLOW\"}\n",
    )
    .unwrap();
    wait_for(
        || {
            latest_snapshot(&env.qa_chain)["overall"] == "healthy"
                && latest_snapshot(&env.qa_chain)["active_conditions"]
                    .as_array()
                    .unwrap()
                    .is_empty()
        },
        "condition clear",
    );
    let records = read_records(&env.qa_chain);
    assert!(records.len() >= 3);
    for (idx, record) in records.iter().enumerate() {
        let prev = if idx == 0 {
            None
        } else {
            records[idx - 1]["record_hash"].as_str()
        };
        assert_record_valid(record, (idx + 1) as u64, prev);
    }

    child.kill().ok();
    child.wait().ok();
}

#[test]
fn startup_gate_aborts_on_critical_failure() {
    let env = TestEnv::new();
    fs::write(&env.governance_chain, "").unwrap();
    let output = Command::new(env!("CARGO_BIN_EXE_quality-service"))
        .arg("--once")
        .env("ATESTED_REPO_ROOT", repo_root())
        .env("GOV_RUNTIME_DIR", env.runtime.path())
        .env("ATESTED_QA_SIGNING_KEY_PATH", &env.qa_key)
        .env(
            "GOV_POLICY_RULES_PATH",
            env.runtime.path().join("missing-policy.json"),
        )
        .env("GOV_CAPABILITY_REGISTRY_PATH", &env.capability_path)
        .env("GOV_DECISION_CHAIN_PATH", &env.governance_chain)
        .env("GOV_QA_CHAIN_PATH", &env.qa_chain)
        .output()
        .expect("run quality service once");
    assert!(!output.status.success());
    assert!(String::from_utf8_lossy(&output.stderr).contains("startup gate failed"));
}

struct TestEnv {
    runtime: TempDir,
    qa_key: std::path::PathBuf,
    policy_path: std::path::PathBuf,
    capability_path: std::path::PathBuf,
    governance_chain: std::path::PathBuf,
    qa_chain: std::path::PathBuf,
}

impl TestEnv {
    fn new() -> Self {
        let runtime = tempfile::tempdir().unwrap();
        let logs = runtime.path().join("LOGS");
        fs::create_dir_all(&logs).unwrap();
        let qa_key = runtime.path().join(".qa-key.pem");
        fs::write(&qa_key, TEST_PRIVATE_PEM).unwrap();
        let policy_path = runtime.path().join("policy-rules.json");
        fs::write(
            &policy_path,
            "{\"rules\":[],\"default_decision\":\"ALLOW\"}\n",
        )
        .unwrap();
        let capability_path = runtime.path().join("capability-registry.json");
        fs::write(&capability_path, "{\"capabilities\":[]}\n").unwrap();
        let governance_chain = logs.join("decision-chain.jsonl");
        let qa_chain = logs.join("qa-chain.jsonl");
        write_governance_chain(&governance_chain, &policy_path, &capability_path);
        Self {
            runtime,
            qa_key,
            policy_path,
            capability_path,
            governance_chain,
            qa_chain,
        }
    }
}

fn write_governance_chain(
    chain: &std::path::Path,
    policy: &std::path::Path,
    capability: &std::path::Path,
) {
    let policy_value: Value = serde_json::from_str(&fs::read_to_string(policy).unwrap()).unwrap();
    let policy_hash = canonical_policy_hash(&policy_value).unwrap();
    let cap_hash = format!(
        "sha256:{:x}",
        sha2::Sha256::digest(fs::read(capability).unwrap())
    );
    let mut record = json!({
        "event_type": "policy_rules_loaded",
        "timestamp_utc": "2026-05-23T14:30:00Z",
        "policy_rules_hash": policy_hash,
        "capability_registry_hash": cap_hash,
        "prev_record_hash": null,
        "record_hash": null,
        "signature": null,
        "signing_key_id": null
    });
    let hash = record_hash(&record).unwrap();
    record["record_hash"] = Value::String(hash);
    fs::write(chain, canonical_json(&record).unwrap() + "\n").unwrap();
}

fn repo_root() -> String {
    std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .display()
        .to_string()
}

fn read_records(path: &std::path::Path) -> Vec<Value> {
    let Ok(raw) = fs::read_to_string(path) else {
        return vec![];
    };
    raw.lines()
        .filter(|line| !line.trim().is_empty())
        .map(|line| serde_json::from_str(line).unwrap())
        .collect()
}

fn latest_snapshot(path: &std::path::Path) -> Value {
    read_records(path)
        .into_iter()
        .rev()
        .find(|record| record["event_type"] == "qa_environmental_snapshot")
        .unwrap()
}

fn assert_snapshot_valid(record: &Value, sequence: u64, prev: Option<&str>) {
    assert_eq!(record["event_type"], "qa_environmental_snapshot");
    assert_record_valid(record, sequence, prev);
}

fn assert_record_valid(record: &Value, sequence: u64, prev: Option<&str>) {
    assert_eq!(record["sequence"].as_u64().unwrap(), sequence);
    assert_eq!(record["prev_record_hash"].as_str(), prev);
    assert_eq!(
        record_hash(record).unwrap(),
        record["record_hash"].as_str().unwrap()
    );

    let preimage = record_hash_preimage(record).unwrap();
    let verifying = VerifyingKey::from_bytes(&hex_to_32(TEST_PUBLIC_RAW_HEX)).unwrap();
    let signature = base64::engine::general_purpose::URL_SAFE_NO_PAD
        .decode(record["signature"].as_str().unwrap())
        .unwrap();
    let signature = Signature::from_slice(&signature).unwrap();
    verifying.verify(preimage.as_bytes(), &signature).unwrap();
}

fn wait_for(mut predicate: impl FnMut() -> bool, label: &str) {
    let deadline = Instant::now() + Duration::from_secs(8);
    while Instant::now() < deadline {
        if predicate() {
            return;
        }
        thread::sleep(Duration::from_millis(100));
    }
    panic!("timed out waiting for {label}");
}

fn hex_to_32(hex: &str) -> [u8; 32] {
    let mut out = [0u8; 32];
    for idx in 0..32 {
        out[idx] = u8::from_str_radix(&hex[idx * 2..idx * 2 + 2], 16).unwrap();
    }
    out
}
