// JWT encode/decode helpers.

import { createHmac, timingSafeEqual } from "crypto";

const JWT_SECRET = "change-me-in-prod";
const ALGORITHM = "HS256";

/** Produce a signed JWT string from a claims object. */
export function encodeToken(claims: Record<string, unknown>): string {
  const header = { alg: ALGORITHM, typ: "JWT" };
  const headerB64 = b64url(Buffer.from(JSON.stringify(header)));
  const payloadB64 = b64url(Buffer.from(JSON.stringify(claims)));

  const signingInput = `${headerB64}.${payloadB64}`;
  const signature = sign(signingInput);
  return `${signingInput}.${b64url(signature)}`;
}

/** Verify signature + expiry and return the claims object. */
export function decodeToken(token: string): Record<string, unknown> {
  const segments = token.split(".");
  if (segments.length !== 3) {
    throw new MalformedTokenError("token must have 3 segments");
  }
  const [headerB64, payloadB64, sigB64] = segments;

  const signingInput = `${headerB64}.${payloadB64}`;
  const expected = sign(signingInput);
  if (!timingSafeEqual(expected, b64urlDecode(sigB64))) {
    throw new InvalidSignatureError("signature mismatch");
  }

  const payload = JSON.parse(b64urlDecode(payloadB64).toString());
  const exp = payload.exp as number | undefined;
  if (exp !== undefined && Math.floor(Date.now() / 1000) > exp) {
    throw new TokenExpiredError("token expired");
  }
  return payload;
}

function sign(data: string): Buffer {
  return createHmac("sha256", JWT_SECRET).update(data).digest();
}

function b64url(data: Buffer): string {
  return data.toString("base64url");
}

function b64urlDecode(s: string): Buffer {
  return Buffer.from(s, "base64url");
}

/** Raised when the exp claim is in the past. */
export class TokenExpiredError extends Error {}

/** Raised when the HMAC signature does not match. */
export class InvalidSignatureError extends Error {}

/** Raised when the token cannot be parsed. */
export class MalformedTokenError extends Error {}
