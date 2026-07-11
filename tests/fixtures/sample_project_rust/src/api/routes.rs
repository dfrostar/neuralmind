//! HTTP route table wiring auth and billing handlers to paths.

use crate::auth::handlers::{authenticate_user, verify_session};
use crate::billing::stripe_client::StripeClient;
use crate::db::connection::Connection;

/// The HTTP methods the fixture router understands.
pub enum Method {
    Get,
    Post,
    Delete,
}

/// A single registered route.
pub struct Route {
    /// URL path, e.g. `/api/auth/login`.
    pub path: String,
    /// HTTP method for the route.
    pub method: Method,
}

/// POST /api/auth/login — issue a token for valid credentials.
pub fn login_endpoint(conn: &Connection, email: &str) -> Option<String> {
    authenticate_user(conn, email)
}

/// GET /api/users/me — requires a valid session token.
pub fn get_me_endpoint(token: &str) -> bool {
    verify_session(token)
}

/// POST /api/billing/charge — charge the authenticated user.
pub fn charge_endpoint(client: &StripeClient, cents: u64) -> String {
    client.charge_customer(cents)
}

/// Build the route table for the service.
pub fn build_routes() -> Vec<Route> {
    vec![
        Route {
            path: "/api/auth/login".to_string(),
            method: Method::Post,
        },
        Route {
            path: "/api/users/me".to_string(),
            method: Method::Get,
        },
    ]
}
