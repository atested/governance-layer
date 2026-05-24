use serde_json::{Map, Number, Value};
use sha2::{Digest, Sha256};

pub fn canonical_json(value: &Value) -> Result<String, String> {
    let mut out = String::new();
    write_value(value, &mut out)?;
    Ok(out)
}

pub fn sha256_prefixed_bytes(bytes: &[u8]) -> String {
    let digest = Sha256::digest(bytes);
    format!("sha256:{:x}", digest)
}

pub fn sha256_prefixed(value: &Value) -> Result<String, String> {
    let canonical = canonical_json(value)?;
    Ok(sha256_prefixed_bytes(canonical.as_bytes()))
}

pub fn record_hash_preimage(record: &Value) -> Result<String, String> {
    let mut body = record
        .as_object()
        .ok_or_else(|| "record hash preimage requires an object".to_string())?
        .clone();
    body.insert("record_hash".to_string(), Value::Null);
    if body.contains_key("signature") {
        body.insert("signature".to_string(), Value::Null);
    }
    if body.contains_key("signing_key_id") {
        body.insert("signing_key_id".to_string(), Value::Null);
    }
    canonical_json(&Value::Object(body))
}

pub fn record_hash(record: &Value) -> Result<String, String> {
    let preimage = record_hash_preimage(record)?;
    Ok(sha256_prefixed_bytes(preimage.as_bytes()))
}

pub fn canonical_policy_hash(policy: &Value) -> Result<String, String> {
    let mut body = policy
        .as_object()
        .ok_or_else(|| "policy hash requires an object".to_string())?
        .clone();
    body.retain(|key, _value| !key.starts_with('_'));
    sha256_prefixed(&Value::Object(body))
}

fn write_value(value: &Value, out: &mut String) -> Result<(), String> {
    match value {
        Value::Null => out.push_str("null"),
        Value::Bool(true) => out.push_str("true"),
        Value::Bool(false) => out.push_str("false"),
        Value::Number(number) => out.push_str(&format_number(number)?),
        Value::String(text) => {
            out.push_str(&serde_json::to_string(text).map_err(|err| err.to_string())?)
        }
        Value::Array(items) => {
            out.push('[');
            for (idx, item) in items.iter().enumerate() {
                if idx > 0 {
                    out.push(',');
                }
                write_value(item, out)?;
            }
            out.push(']');
        }
        Value::Object(map) => write_object(map, out)?,
    }
    Ok(())
}

fn write_object(map: &Map<String, Value>, out: &mut String) -> Result<(), String> {
    let mut keys: Vec<&String> = map.keys().collect();
    keys.sort();
    out.push('{');
    for (idx, key) in keys.iter().enumerate() {
        if idx > 0 {
            out.push(',');
        }
        out.push_str(&serde_json::to_string(key).map_err(|err| err.to_string())?);
        out.push(':');
        write_value(&map[*key], out)?;
    }
    out.push('}');
    Ok(())
}

fn format_number(number: &Number) -> Result<String, String> {
    if let Some(value) = number.as_i64() {
        return Ok(value.to_string());
    }
    if let Some(value) = number.as_u64() {
        return Ok(value.to_string());
    }
    let raw = number.to_string();
    if !raw.contains('.') && !raw.contains('e') && !raw.contains('E') {
        return Ok(raw);
    }
    let value = number
        .as_f64()
        .ok_or_else(|| "unsupported JSON number".to_string())?;
    if !value.is_finite() {
        return Err("non-finite floats are not allowed".to_string());
    }
    if value == 0.0 {
        return if value.is_sign_negative() {
            Ok("-0.0".to_string())
        } else {
            Ok("0.0".to_string())
        };
    }

    let mut buffer = ryu::Buffer::new();
    let mut rendered = buffer.format_finite(value).to_string();
    if let Some(pos) = rendered.find('E').or_else(|| rendered.find('e')) {
        let mantissa = rendered[..pos].to_string();
        let exponent_raw = &rendered[pos + 1..];
        let exponent: i32 = exponent_raw
            .parse()
            .map_err(|_| format!("invalid exponent from ryu: {rendered}"))?;
        let sign = if exponent >= 0 { '+' } else { '-' };
        rendered = format!("{mantissa}e{sign}{:02}", exponent.abs());
    } else if !rendered.contains('.') {
        rendered.push_str(".0");
    }
    Ok(rendered)
}

#[cfg(test)]
mod tests {
    use super::*;
    use base64::engine::general_purpose::URL_SAFE_NO_PAD;
    use base64::Engine as _;
    use ed25519_dalek::{Signer, SigningKey};
    use serde_json::Value;
    use std::fs;
    use std::path::PathBuf;

    fn vector_path() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .unwrap()
            .parent()
            .unwrap()
            .parent()
            .unwrap()
            .join("project-management/atested/claude-project-files/canonical-form-vectors.json")
    }

    #[test]
    fn canonical_vectors_match_python() {
        let raw = fs::read_to_string(vector_path()).unwrap();
        let root: Value = serde_json::from_str(&raw).unwrap();
        for vector in root["vectors"].as_array().unwrap() {
            let id = vector["id"].as_str().unwrap();
            let actual = canonical_json(&vector["input"]).unwrap();
            assert_eq!(actual, vector["canonical_json"].as_str().unwrap(), "{id}");
            assert_eq!(
                sha256_prefixed_bytes(actual.as_bytes()),
                vector["sha256"].as_str().unwrap(),
                "{id}"
            );
        }
    }

    #[test]
    fn ed25519_signature_vector_matches_python() {
        let raw = fs::read_to_string(vector_path()).unwrap();
        let root: Value = serde_json::from_str(&raw).unwrap();
        let sig = &root["ed25519_signature_vector"];
        let seed = hex_to_32(sig["private_key_seed_hex"].as_str().unwrap());
        let key = SigningKey::from_bytes(&seed);
        let signature = key.sign(sig["message"].as_str().unwrap().as_bytes());
        assert_eq!(
            hex_encode(&signature.to_bytes()),
            sig["signature_hex"].as_str().unwrap()
        );
        assert_eq!(
            URL_SAFE_NO_PAD.encode(signature.to_bytes()),
            sig["signature_base64url_nopad"].as_str().unwrap()
        );
    }

    fn hex_to_32(hex: &str) -> [u8; 32] {
        let bytes = hex_decode(hex).unwrap();
        bytes.try_into().unwrap()
    }

    fn hex_decode(hex: &str) -> Result<Vec<u8>, String> {
        if hex.len() % 2 != 0 {
            return Err("odd hex length".to_string());
        }
        let mut out = Vec::new();
        for idx in (0..hex.len()).step_by(2) {
            out.push(u8::from_str_radix(&hex[idx..idx + 2], 16).map_err(|err| err.to_string())?);
        }
        Ok(out)
    }

    fn hex_encode(bytes: &[u8]) -> String {
        bytes.iter().map(|byte| format!("{byte:02x}")).collect()
    }
}
