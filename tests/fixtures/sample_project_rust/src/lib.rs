//! Fixture crate root for the Rust retrieval-quality eval.
//!
//! Mirrors the Python/Go fixtures: auth, users, billing, api, db. The crate is
//! never compiled — it exists to be parsed by the built-in tree-sitter backend.

pub mod api;
pub mod auth;
pub mod billing;
pub mod db;
pub mod users;
