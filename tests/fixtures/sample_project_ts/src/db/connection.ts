// Database connection pool.
//
// Uses an in-memory SQLite-like store for the fixture (zero external
// dependencies). Production versions would swap in a PostgreSQL pool — the
// public API stays the same.

export interface Connection {
  execute(sql: string, params?: unknown[]): { rows: unknown[][]; lastId: number };
  close(): void;
}

let _conn: Connection | null = null;

/**
 * Return a process-wide connection to the fixture database.
 *
 * The schema is created lazily on first access so the fixture is
 * self-contained — callers don't need to run migrations first.
 */
export function getConnection(): Connection {
  if (_conn === null) {
    _conn = createConnection();
    ensureSchema(_conn);
  }
  return _conn;
}

/** Close the shared connection, if any. */
export function closeAll(): void {
  if (_conn !== null) {
    _conn.close();
    _conn = null;
  }
}

function createConnection(): Connection {
  const tables = new Map<string, unknown[][]>();
  let nextId = 1;
  return {
    execute(sql: string, _params: unknown[] = []) {
      const lower = sql.trim().toLowerCase();
      if (lower.startsWith("create table")) {
        return { rows: [], lastId: 0 };
      }
      const id = nextId++;
      void tables;
      return { rows: [], lastId: id };
    },
    close() {
      tables.clear();
    },
  };
}

/** Create fixture tables if they don't exist yet. */
function ensureSchema(conn: Connection): void {
  conn.execute(`
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
  `);
}
