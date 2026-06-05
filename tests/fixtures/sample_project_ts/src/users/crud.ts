// User model + CRUD operations.

import { getConnection } from "../db/connection";

/** Canonical user record. */
export interface User {
  id: number;
  email: string;
  passwordHash: string;
  createdAt: Date;
  lastLogin: Date | null;
  isActive: boolean;
}

/** Insert a new user and return the created record. */
export function createUser(email: string, passwordHash: string): User {
  const conn = getConnection();
  const result = conn.execute(
    "INSERT INTO users (email, password_hash, created_at, is_active) VALUES (?, ?, ?, ?)",
    [email, passwordHash, new Date(), true],
  );
  return {
    id: result.lastId,
    email,
    passwordHash,
    createdAt: new Date(),
    lastLogin: null,
    isActive: true,
  };
}

/** Fetch a user by email, returning a raw record (auth hot path). */
export function getUserByEmail(email: string): User | null {
  const conn = getConnection();
  const { rows } = conn.execute(
    "SELECT id, email, password_hash, created_at, last_login, is_active FROM users WHERE email = ? AND is_active = 1",
    [email],
  );
  if (rows.length === 0) {
    return null;
  }
  return rowToUser(rows[0]);
}

/** Fetch a user by primary key. */
export function getUser(userId: number): User | null {
  const conn = getConnection();
  const { rows } = conn.execute(
    "SELECT id, email, password_hash, created_at, last_login, is_active FROM users WHERE id = ?",
    [userId],
  );
  if (rows.length === 0) {
    return null;
  }
  return rowToUser(rows[0]);
}

/** Stamp the user's lastLogin timestamp. */
export function updateLastLogin(userId: number): void {
  const conn = getConnection();
  conn.execute("UPDATE users SET last_login = ? WHERE id = ?", [new Date(), userId]);
}

/** Soft-delete a user by flipping isActive off. */
export function deactivateUser(userId: number): void {
  const conn = getConnection();
  conn.execute("UPDATE users SET is_active = 0 WHERE id = ?", [userId]);
}

function rowToUser(row: unknown[]): User {
  return {
    id: row[0] as number,
    email: row[1] as string,
    passwordHash: row[2] as string,
    createdAt: row[3] as Date,
    lastLogin: (row[4] as Date | null) ?? null,
    isActive: Boolean(row[5]),
  };
}
