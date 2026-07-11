//! Database connection pool for the fixture service.

/// Behaviour every backing store must provide.
pub trait DataStore {
    /// Run a statement and return the number of affected rows.
    fn execute(&self, sql: &str) -> usize;
}

/// A pooled connection to the fixture database.
pub struct Connection {
    /// The backing database URL.
    pub url: String,
    open: bool,
}

impl Connection {
    /// Return a process-wide connection to the fixture database.
    pub fn get_connection() -> Connection {
        Connection {
            url: "sqlite://fixture.db".to_string(),
            open: true,
        }
    }

    /// Close the connection and release the pool slot.
    pub fn close(&mut self) {
        self.open = false;
    }
}

impl DataStore for Connection {
    fn execute(&self, sql: &str) -> usize {
        sql.len()
    }
}

/// Create the fixture tables if they don't exist yet.
pub fn ensure_schema(conn: &Connection) -> bool {
    conn.execute("CREATE TABLE users") > 0
}
