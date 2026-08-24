"""Fake credential fixtures, assembled at runtime.

Every value here is fabricated — none is a live credential. They still
match the same patterns real scanners use, so GitHub push protection
rejects a commit that carries them as contiguous literals. (That block
is what stopped the first push of this very change, which is a fair
demonstration that the shapes are right.)

Joining each value from fragments keeps the literal out of the source
file while producing, at import time, the exact string the detector under
test has to catch. Applied uniformly rather than only to the shapes a
scanner flags today, so a future rule change can't reintroduce the block.

Add new fixtures the same way: split the distinctive prefix across a
``_j()`` boundary.
"""

from __future__ import annotations


def _j(*parts: str) -> str:
    """Join fixture fragments so no secret-shaped literal sits in the file."""
    return "".join(parts)


ANTHROPIC_KEY = _j("sk-", "ant-", "api03-AbCdEf123456789_xyzXYZ098")
OPENAI_KEY = _j("sk-", "proj-", "AbCdEf1234567890abcdefXYZ")
AWS_KEY_ID = _j("AKIA", "IOSFODNN7EXAMPLE")
AWS_SECRET = _j("wJalrXUtnFEMI", "/K7MDENG/bPxRfiCYEXAMPLEKEY")
GITHUB_TOKEN = _j("ghp", "_", "16C7e42F292c6912E7710c838347Ae178B4a")
SLACK_TOKEN = _j("xoxb", "-123456789012-1234567890123-", "AbCdEfGhIjKlMnOpQrStUvWx")
GOOGLE_KEY = _j("AIza", "SyD-1234567890abcdefghijklmnopqrstu")
STRIPE_KEY = _j("sk", "_live_", "4eC39HqLyjWDarjtT1zdp7dc")
JWT = _j(
    "eyJ",
    "hbGciOiJIUzI1NiJ9.",
    "eyJzdWIiOiIxMjM0NTY3ODkwIn0.",
    "dozjgNryP4J3jVmNHl0w5N_XgL0",
)
# Assembled like the rest: unsplit, this is a high-entropy value after a
# `password`-family keyword, so the repository's own `--strict` self-scan
# reported it.
PG_PASSWORD = _j("sup3r", "S3cret", "Pw")
# A password containing ";", which truncates the generic-assignment value
# pattern. Split so no contiguous DSN literal sits in a test file.
TRUNCATING_PASSWORD = _j("pa;", "ssw0rdLongEnough")
PEM_BLOCK = _j(
    "-----BEGIN ",
    "RSA PRIVATE KEY-----\n",
    "MIIEowIBAAKCAQEA1234\n",
    "-----END RSA PRIVATE KEY-----",
)
GENERIC_SECRET = "9f8Kd2mQxZ7pLw3RtY6vNbHj4sA1"
# base64 of a fake "user:password123" — split so the literal is not in source.
BASIC_AUTH_B64 = _j("dXNlcjpw", "YXNzd29yZDEyMw==")


def pem_begin(kind: str = "RSA") -> str:
    """A PEM/PGP BEGIN marker, assembled so no literal sits in the source.

    Without this, `neuralmind scan-for-secrets .` flags this repository's
    own test files — and a scanner that cannot give its own project a clean
    run is hard to recommend to anyone else.
    """
    tail = "PRIVATE KEY BLOCK-----" if kind == "PGP" else "PRIVATE KEY-----"
    return _j("-----BEGIN ", f"{kind} ", tail)


def pem_end(kind: str = "RSA") -> str:
    """The matching END marker for :func:`pem_begin`."""
    tail = "PRIVATE KEY BLOCK-----" if kind == "PGP" else "PRIVATE KEY-----"
    return _j("-----END ", f"{kind} ", tail)
