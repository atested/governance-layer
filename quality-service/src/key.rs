use base64::engine::general_purpose::{STANDARD, URL_SAFE_NO_PAD};
use base64::Engine as _;
use ed25519_dalek::{Signer, SigningKey, Verifier, VerifyingKey};
use rand_core::OsRng;
use sha2::{Digest, Sha256};
use std::fs;
use std::path::Path;

// PKCS#8 OneAsymmetricKey envelope for Ed25519 (RFC 8410).
// Structure: SEQUENCE { version=0, AlgorithmIdentifier { Ed25519 OID 1.3.101.112 },
//                       OCTET STRING { OCTET STRING { 32-byte seed } } }
// Total 48 bytes: 16 bytes of envelope DER + 32 bytes of seed.
// Matches the format produced by scripts/atested_cli.py for the governance key.
const ED25519_PKCS8_ENVELOPE_PREFIX: [u8; 16] = [
    0x30, 0x2e, 0x02, 0x01, 0x00, 0x30, 0x05, 0x06, 0x03, 0x2b, 0x65, 0x70, 0x04, 0x22, 0x04, 0x20,
];

#[cfg(unix)]
use std::os::unix::fs::PermissionsExt;

pub struct QaSigningKey {
    key: SigningKey,
    key_id: String,
}

impl QaSigningKey {
    pub fn load(path: &Path) -> Result<Self, String> {
        let raw = fs::read_to_string(path)
            .map_err(|err| format!("failed to read QA signing key {}: {err}", path.display()))?;
        let seed = parse_seed(&raw)?;
        let key = SigningKey::from_bytes(&seed);
        let public = key.verifying_key();
        let key_id = format!("ed25519:{}", hex_encode(&Sha256::digest(public.as_bytes())));
        Ok(Self { key, key_id })
    }

    /// Load the QA signing key, generating one if the file does not exist.
    ///
    /// On first run the QA chain has no signing key. Rather than failing
    /// closed and requiring the operator to run a key-generation tool, the
    /// quality service produces a fresh Ed25519 keypair (PKCS#8 PEM, 0o600)
    /// at the configured path. The key persists across restarts because the
    /// file is written to disk before the first record is signed.
    ///
    /// This mirrors the governance signing key's auto-create-on-first-init
    /// behavior in scripts/atested_cli.py.
    pub fn load_or_generate(path: &Path) -> Result<Self, String> {
        if path.exists() {
            return Self::load(path);
        }
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent).map_err(|err| {
                format!(
                    "failed to create QA signing key parent {}: {err}",
                    parent.display()
                )
            })?;
        }
        let signing = SigningKey::generate(&mut OsRng);
        let seed = signing.to_bytes();
        let mut der = Vec::with_capacity(48);
        der.extend_from_slice(&ED25519_PKCS8_ENVELOPE_PREFIX);
        der.extend_from_slice(&seed);
        let b64 = STANDARD.encode(&der);
        let pem = format!("-----BEGIN PRIVATE KEY-----\n{b64}\n-----END PRIVATE KEY-----\n");
        fs::write(path, pem.as_bytes())
            .map_err(|err| format!("failed to write QA signing key {}: {err}", path.display()))?;
        #[cfg(unix)]
        {
            if let Err(err) = fs::set_permissions(path, fs::Permissions::from_mode(0o600)) {
                eprintln!(
                    "warning: failed to chmod 0600 on QA signing key {}: {err}",
                    path.display()
                );
            }
        }
        Self::load(path)
    }

    pub fn key_id(&self) -> &str {
        &self.key_id
    }

    pub fn sign_b64url(&self, message: &[u8]) -> String {
        URL_SAFE_NO_PAD.encode(self.key.sign(message).to_bytes())
    }

    pub fn self_check(&self) -> Result<(), String> {
        let message = b"atested-quality-service-key-self-check";
        let signature = self.key.sign(message);
        self.key
            .verifying_key()
            .verify(message, &signature)
            .map_err(|err| format!("QA signing key self-check failed: {err}"))
    }
}

pub fn validate_ed25519_private_key(path: &Path) -> Result<String, String> {
    let raw = fs::read_to_string(path)
        .map_err(|err| format!("failed to read signing key {}: {err}", path.display()))?;
    let seed = parse_seed(&raw)?;
    let key = SigningKey::from_bytes(&seed);
    let verifying: VerifyingKey = key.verifying_key();
    Ok(format!(
        "ed25519:{}",
        hex_encode(&Sha256::digest(verifying.as_bytes()))
    ))
}

pub fn verifying_key_from_private_key(path: &Path) -> Result<VerifyingKey, String> {
    let raw = fs::read_to_string(path)
        .map_err(|err| format!("failed to read signing key {}: {err}", path.display()))?;
    let seed = parse_seed(&raw)?;
    Ok(SigningKey::from_bytes(&seed).verifying_key())
}

fn parse_seed(raw: &str) -> Result<[u8; 32], String> {
    let trimmed = raw.trim();
    if trimmed.starts_with("-----BEGIN PRIVATE KEY-----") {
        let b64: String = trimmed
            .lines()
            .filter(|line| !line.starts_with("-----"))
            .collect();
        let der = STANDARD
            .decode(b64.as_bytes())
            .map_err(|err| format!("invalid PEM base64: {err}"))?;
        if der.len() < 32 {
            return Err("PKCS#8 key is too short".to_string());
        }
        let seed = &der[der.len() - 32..];
        return seed
            .try_into()
            .map_err(|_| "failed to extract Ed25519 seed".to_string());
    }
    let hex: String = trimmed.chars().filter(|ch| !ch.is_whitespace()).collect();
    if hex.len() == 64 && hex.chars().all(|ch| ch.is_ascii_hexdigit()) {
        let bytes = hex_decode(&hex)?;
        return bytes
            .try_into()
            .map_err(|_| "expected a 32 byte Ed25519 seed".to_string());
    }
    Err("unsupported signing key format; expected PKCS#8 PEM or 32 byte seed hex".to_string())
}

fn hex_decode(hex: &str) -> Result<Vec<u8>, String> {
    if hex.len() % 2 != 0 {
        return Err("odd hex length".to_string());
    }
    let mut out = Vec::with_capacity(hex.len() / 2);
    for idx in (0..hex.len()).step_by(2) {
        out.push(u8::from_str_radix(&hex[idx..idx + 2], 16).map_err(|err| err.to_string())?);
    }
    Ok(out)
}

fn hex_encode(bytes: &[u8]) -> String {
    bytes.iter().map(|byte| format!("{byte:02x}")).collect()
}
