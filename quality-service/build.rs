// QS-039 Adv #13: capture the Rust toolchain version at build time so the
// running binary can stamp "what toolchain built me" into its first QA
// chain record. Captured from the compiler Cargo invokes (RUSTC), which is
// exactly the toolchain that produced this binary.
use std::process::Command;

fn main() {
    let rustc = std::env::var("RUSTC").unwrap_or_else(|_| "rustc".to_string());
    let version = Command::new(rustc)
        .arg("--version")
        .output()
        .ok()
        .filter(|out| out.status.success())
        .and_then(|out| String::from_utf8(out.stdout).ok())
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| "unknown".to_string());
    println!("cargo:rustc-env=ATESTED_RUSTC_VERSION={version}");
    println!("cargo:rerun-if-changed=build.rs");
}
