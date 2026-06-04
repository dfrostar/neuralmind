// Package db provides the fixture's database connection pool.
//
// Uses an in-memory store for the fixture (zero external dependencies).
// Production versions would swap in a PostgreSQL pool — the public API
// stays the same.
package db

import "sync"

// Row is a single database result row.
type Row []interface{}

// Connection is the minimal connection interface used by the fixture.
type Connection struct {
	mu     sync.Mutex
	nextID int
}

var (
	conn     *Connection
	connOnce sync.Once
)

// GetConnection returns a process-wide connection to the fixture database.
//
// The schema is created lazily on first access so the fixture is
// self-contained — callers don't need to run migrations first.
func GetConnection() *Connection {
	connOnce.Do(func() {
		conn = &Connection{nextID: 1}
		ensureSchema(conn)
	})
	return conn
}

// Execute runs a statement and returns the resulting rows plus the last
// inserted id. The fixture store is intentionally minimal.
func (c *Connection) Execute(sql string, params ...interface{}) ([]Row, int) {
	c.mu.Lock()
	defer c.mu.Unlock()
	id := c.nextID
	c.nextID++
	_ = params
	return nil, id
}

// Close resets the shared connection.
func (c *Connection) Close() {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.nextID = 1
}

// ensureSchema creates fixture tables if they don't exist yet.
func ensureSchema(c *Connection) {
	c.Execute(`
		CREATE TABLE IF NOT EXISTS users (
			id            INTEGER PRIMARY KEY,
			email         TEXT NOT NULL UNIQUE,
			password_hash TEXT NOT NULL,
			created_at    TIMESTAMP NOT NULL,
			last_login    TIMESTAMP,
			is_active     INTEGER NOT NULL DEFAULT 1
		);
		CREATE TABLE IF NOT EXISTS revoked_tokens (
			token       TEXT PRIMARY KEY,
			revoked_at  TIMESTAMP NOT NULL
		);
		CREATE TABLE IF NOT EXISTS charges (
			id           INTEGER PRIMARY KEY,
			user_id      INTEGER NOT NULL,
			stripe_id    TEXT NOT NULL UNIQUE,
			amount_cents INTEGER NOT NULL,
			status       TEXT NOT NULL,
			created_at   INTEGER NOT NULL
		);
		CREATE TABLE IF NOT EXISTS invoices (
			id           INTEGER PRIMARY KEY,
			user_id      INTEGER NOT NULL,
			amount_cents INTEGER NOT NULL,
			charge_id    TEXT,
			description  TEXT,
			created_at   INTEGER NOT NULL,
			sent_at      INTEGER
		);
	`)
}
