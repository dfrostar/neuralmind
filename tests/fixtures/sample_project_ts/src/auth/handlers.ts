// Authentication handlers — login, logout, token refresh.

import { scryptSync, timingSafeEqual } from "crypto";

import { getConnection } from "../db/connection";
import { getUserByEmail, updateLastLogin } from "../users/crud";
import { decodeToken, encodeToken } from "./jwtUtils";

const SESSION_TTL_SEC = 60 * 60; // 1 hour
const REFRESH_TTL_SEC = 60 * 60 * 24 * 30; // 30 days

/**
 * Validate credentials and issue an access + refresh token pair.
 *
 * Looks the user up by email, verifies the password hash, stamps a login
 * event, and returns JWT access and refresh tokens.
 */
export function authenticateUser(email: string, password: string): Record<string, unknown> {
  const user = getUserByEmail(email);
  if (user === null) {
    throw new InvalidCredentialsError("unknown email");
  }
  if (!verifyPassword(password, user.passwordHash)) {
    throw new InvalidCredentialsError("bad password");
  }

  updateLastLogin(user.id);

  const now = Math.floor(Date.now() / 1000);
  const access = encodeToken({ sub: user.id, exp: now + SESSION_TTL_SEC });
  const refresh = encodeToken({ sub: user.id, exp: now + REFRESH_TTL_SEC, kind: "refresh" });

  return { accessToken: access, refreshToken: refresh, userId: user.id };
}

/** Return the user id if the access token is valid; throw if not. */
export function verifySession(accessToken: string): number {
  const payload = decodeToken(accessToken);
  if (payload.kind === "refresh") {
    throw new InvalidTokenError("refresh token used as access");
  }
  return Number(payload.sub);
}

/** Exchange a refresh token for a new access token. */
export function refreshSession(refreshToken: string): Record<string, unknown> {
  const payload = decodeToken(refreshToken);
  if (payload.kind !== "refresh") {
    throw new InvalidTokenError("not a refresh token");
  }
  const now = Math.floor(Date.now() / 1000);
  const newAccess = encodeToken({ sub: payload.sub, exp: now + SESSION_TTL_SEC });
  return { accessToken: newAccess };
}

/** Revoke a refresh token by writing it to the revocation list. */
export function logout(refreshToken: string): void {
  const conn = getConnection();
  conn.execute("INSERT INTO revoked_tokens (token, revoked_at) VALUES (?, ?)", [
    refreshToken,
    new Date(),
  ]);
}

/**
 * Constant-time password verification against a stored scrypt hash.
 * Stored format is "saltHex:keyHex"; scrypt is a deliberately expensive KDF.
 */
export function verifyPassword(plain: string, hashed: string): boolean {
  const [saltHex, keyHex] = hashed.split(":");
  const salt = Buffer.from(saltHex, "hex");
  const expected = Buffer.from(keyHex, "hex");
  const derived = scryptSync(plain, salt, expected.length);
  return timingSafeEqual(derived, expected);
}

/** Raised when email or password does not match any user. */
export class InvalidCredentialsError extends Error {}

/** Raised when a token is malformed, expired, or misused. */
export class InvalidTokenError extends Error {}
