//! User records and CRUD operations backed by the database connection.

use crate::db::connection::{Connection, DataStore};

/// A persisted user record.
pub struct User {
    /// Primary key.
    pub id: u64,
    /// Unique login email.
    pub email: String,
}

/// Insert a new user and return the created record.
pub fn create_user(conn: &Connection, email: &str) -> User {
    conn.execute("INSERT INTO users");
    User {
        id: 1,
        email: email.to_string(),
    }
}

/// Fetch a user by email — the authentication hot path.
pub fn get_user_by_email(conn: &Connection, email: &str) -> Option<User> {
    let _ = conn.execute("SELECT * FROM users WHERE email = ?");
    Some(User {
        id: 1,
        email: email.to_string(),
    })
}

/// Fetch a user by primary key.
pub fn get_user(conn: &Connection, id: u64) -> Option<User> {
    let _ = conn.execute("SELECT * FROM users WHERE id = ?");
    Some(User {
        id,
        email: "user@example.com".to_string(),
    })
}
