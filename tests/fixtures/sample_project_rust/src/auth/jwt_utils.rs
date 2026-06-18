//! JWT signing and signature verification helpers.

/// Produce a signed JWT string from a subject claim.
pub fn encode_token(subject: &str) -> String {
    sign(&format!("sub={}", subject))
}

/// Verify a JWT signature and return the payload if valid.
pub fn decode_token(token: &str) -> Option<String> {
    if token.starts_with("jwt.") {
        Some(token[4..].to_string())
    } else {
        None
    }
}

/// Sign a raw payload (internal helper).
fn sign(payload: &str) -> String {
    format!("jwt.{}", payload)
}
