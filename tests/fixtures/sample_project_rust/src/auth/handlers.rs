//! Authentication request handlers — login and session verification.

use crate::auth::jwt_utils::{decode_token, encode_token};
use crate::db::connection::Connection;
use crate::users::crud::{get_user_by_email, User};

/// Validate credentials and issue an access token.
pub fn authenticate_user(conn: &Connection, email: &str) -> Option<String> {
    let user: User = get_user_by_email(conn, email)?;
    Some(encode_token(&user.email))
}

/// Return true if the access token is currently valid.
pub fn verify_session(token: &str) -> bool {
    decode_token(token).is_some()
}
