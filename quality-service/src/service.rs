use crate::behavioral::run_behavioral_analysis;
use crate::checks::{critical_failures, run_all_checks, EnvironmentSnapshot};
use crate::config::Config;
use crate::element::run_element_verification;
use crate::governance::{GovernanceChainWatcher, PostHocVerifier};
use crate::key::QaSigningKey;
use crate::spc::SpcMonitor;
use crate::writer::QaChainWriter;
use notify::{RecommendedWatcher, RecursiveMode, Watcher};
use std::fs;
use std::sync::mpsc::{channel, RecvTimeoutError};
use std::time::Instant;

pub fn run_once(config: &Config) -> Result<(), String> {
    let key = QaSigningKey::load_or_generate(&config.qa_signing_key_path)?;
    let mut writer = QaChainWriter::new(config.qa_chain_path.clone(), key)?;
    let mut watcher = GovernanceChainWatcher::new(config.governance_chain_path.clone());
    let new_records = watcher.poll_new_records()?;
    let mut spc = SpcMonitor::new(config.spc_min_decisions, config.spc_baseline_path.clone());
    spc.initialize(watcher.records())?;
    let mut post_hoc = PostHocVerifier::new(config.clone());
    post_hoc.enqueue_records(new_records, &mut writer)?;
    post_hoc.drain_queue(watcher.records(), &mut spc, &mut writer)?;
    let snapshot = with_extra_conditions(run_all_checks(config), post_hoc.active_conditions());
    let failures = critical_failures(&snapshot);
    if !failures.is_empty() {
        return Err(format!(
            "quality service startup gate failed: {}",
            failures.join("; ")
        ));
    }
    writer.append_environmental_snapshot(&snapshot)?;
    run_behavioral_analysis(config, watcher.records(), &mut writer)?;
    let element = run_element_verification(config, watcher.records(), &mut writer)?;
    if !element.active_conditions().is_empty() {
        let snapshot = with_extra_conditions(
            run_all_checks(config),
            combined_conditions(&post_hoc.active_conditions(), &element.active_conditions()),
        );
        writer.append_environmental_snapshot(&snapshot)?;
    }
    signal_ready(config)?;
    Ok(())
}

pub fn run_loop(config: Config) -> Result<(), String> {
    let key = QaSigningKey::load_or_generate(&config.qa_signing_key_path)?;
    let mut writer = QaChainWriter::new(config.qa_chain_path.clone(), key)?;
    let mut chain_watcher = GovernanceChainWatcher::new(config.governance_chain_path.clone());
    let initial_records = chain_watcher.poll_new_records()?;
    let mut spc = SpcMonitor::new(config.spc_min_decisions, config.spc_baseline_path.clone());
    spc.initialize(chain_watcher.records())?;
    let mut post_hoc = PostHocVerifier::new(config.clone());
    post_hoc.enqueue_records(initial_records, &mut writer)?;
    post_hoc.drain_queue(chain_watcher.records(), &mut spc, &mut writer)?;
    let first = with_extra_conditions(run_all_checks(&config), post_hoc.active_conditions());
    let failures = critical_failures(&first);
    if !failures.is_empty() {
        return Err(format!(
            "quality service startup gate failed: {}",
            failures.join("; ")
        ));
    }
    writer.append_environmental_snapshot(&first)?;
    run_behavioral_analysis(&config, chain_watcher.records(), &mut writer)?;
    let mut last_behavioral = Instant::now();
    let mut element = run_element_verification(&config, chain_watcher.records(), &mut writer)?;
    let mut last_element = Instant::now();
    if !element.active_conditions().is_empty() {
        let snapshot = with_extra_conditions(
            run_all_checks(&config),
            combined_conditions(&post_hoc.active_conditions(), &element.active_conditions()),
        );
        writer.append_environmental_snapshot(&snapshot)?;
    }
    signal_ready(&config)?;

    let (tx, rx) = channel();
    let mut fs_watcher: RecommendedWatcher = notify::recommended_watcher(move |result| {
        let _ = tx.send(result);
    })
    .map_err(|err| format!("failed to create file watcher: {err}"))?;
    if let Some(parent) = config.policy_rules_path.parent() {
        fs_watcher
            .watch(parent, RecursiveMode::NonRecursive)
            .map_err(|err| {
                format!(
                    "failed to watch policy directory {}: {err}",
                    parent.display()
                )
            })?;
    }
    if let Some(parent) = config.capability_registry_path.parent() {
        fs_watcher
            .watch(parent, RecursiveMode::NonRecursive)
            .map_err(|err| {
                format!(
                    "failed to watch capability directory {}: {err}",
                    parent.display()
                )
            })?;
    }
    if let Some(parent) = config.governance_chain_path.parent() {
        fs_watcher
            .watch(parent, RecursiveMode::NonRecursive)
            .map_err(|err| {
                format!(
                    "failed to watch governance chain directory {}: {err}",
                    parent.display()
                )
            })?;
    }

    let mut previous_fingerprint = fingerprint(&first);
    loop {
        match rx.recv_timeout(config.heartbeat) {
            Ok(_event) => {
                let new_records = chain_watcher.poll_new_records()?;
                post_hoc.enqueue_records(new_records, &mut writer)?;
                post_hoc.drain_queue(chain_watcher.records(), &mut spc, &mut writer)?;
                if last_behavioral.elapsed() >= config.behavioral_interval {
                    run_behavioral_analysis(&config, chain_watcher.records(), &mut writer)?;
                    last_behavioral = Instant::now();
                }
                if last_element.elapsed() >= config.element_interval {
                    element =
                        run_element_verification(&config, chain_watcher.records(), &mut writer)?;
                    last_element = Instant::now();
                }
                let snapshot = with_extra_conditions(
                    run_all_checks(&config),
                    combined_conditions(
                        &post_hoc.active_conditions(),
                        &element.active_conditions(),
                    ),
                );
                let current_fingerprint = fingerprint(&snapshot);
                if current_fingerprint != previous_fingerprint {
                    writer.append_environmental_snapshot(&snapshot)?;
                    previous_fingerprint = current_fingerprint;
                }
            }
            Err(RecvTimeoutError::Timeout) => {
                let new_records = chain_watcher.poll_new_records()?;
                post_hoc.enqueue_records(new_records, &mut writer)?;
                post_hoc.drain_queue(chain_watcher.records(), &mut spc, &mut writer)?;
                if last_behavioral.elapsed() >= config.behavioral_interval {
                    run_behavioral_analysis(&config, chain_watcher.records(), &mut writer)?;
                    last_behavioral = Instant::now();
                }
                if last_element.elapsed() >= config.element_interval {
                    element =
                        run_element_verification(&config, chain_watcher.records(), &mut writer)?;
                    last_element = Instant::now();
                }
                let snapshot = with_extra_conditions(
                    run_all_checks(&config),
                    combined_conditions(
                        &post_hoc.active_conditions(),
                        &element.active_conditions(),
                    ),
                );
                previous_fingerprint = fingerprint(&snapshot);
                writer.append_environmental_snapshot(&snapshot)?;
            }
            Err(RecvTimeoutError::Disconnected) => {
                return Err("file watcher disconnected".to_string());
            }
        }
    }
}

fn combined_conditions(left: &[String], right: &[String]) -> Vec<String> {
    let mut conditions = Vec::new();
    for condition in left.iter().chain(right.iter()) {
        if !conditions.contains(condition) {
            conditions.push(condition.clone());
        }
    }
    conditions
}

fn with_extra_conditions(
    mut snapshot: EnvironmentSnapshot,
    extra_conditions: Vec<String>,
) -> EnvironmentSnapshot {
    for condition in extra_conditions {
        if !snapshot.active_conditions.contains(&condition) {
            snapshot.active_conditions.push(condition);
        }
    }
    if !snapshot.active_conditions.is_empty() && snapshot.overall == "healthy" {
        snapshot.overall = "unhealthy".to_string();
    }
    snapshot
}

fn signal_ready(config: &Config) -> Result<(), String> {
    if let Some(path) = &config.ready_file {
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent).map_err(|err| {
                format!(
                    "failed to create readiness directory {}: {err}",
                    parent.display()
                )
            })?;
        }
        fs::write(path, b"ready\n")
            .map_err(|err| format!("failed to write readiness marker {}: {err}", path.display()))?;
    }
    println!("quality-service ready");
    Ok(())
}

fn fingerprint(snapshot: &EnvironmentSnapshot) -> String {
    let mut parts = Vec::new();
    parts.push(snapshot.policy_rules_hash.clone());
    parts.push(snapshot.capability_registry_hash.clone());
    parts.push(snapshot.overall.clone());
    parts.push(snapshot.active_conditions.join(","));
    for (id, check) in &snapshot.checks {
        parts.push(format!("{id}:{:?}:{:?}", check.status, check.detail));
    }
    parts.join("|")
}
