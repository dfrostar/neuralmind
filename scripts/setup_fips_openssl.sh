#!/usr/bin/env bash
# Build the OpenSSL FIPS provider and write an OpenSSL config that enforces it,
# so Python's hashlib behaves as it does on a host with the OS FIPS mode on.
#
# Why: CMMC SC.L2-3.13.11 has operators turn the OS FIPS mode on, and there
# OpenSSL refuses MD5 unless the caller passes usedforsecurity=False. Document
# ingestion (`neuralmind ingest`) crashed on such hosts until that was fixed;
# the `fips` CI job runs the whole test suite under this config so it can't
# come back (tests/test_fips_hash_usage.py is the static half of the guard).
#
# This emulates the FIPS provider's algorithm restrictions. It is not a
# validated deployment and proves nothing about the host's own cryptography.
#
# What it does:
#   1. Downloads OpenSSL ${OPENSSL_VERSION}, checks its SHA-256, and builds
#      only providers/fips.so (skipped when DEST already has one).
#   2. Runs `openssl fipsinstall`, which runs the provider's self-tests.
#   3. Writes DEST/openssl-fips.cnf: FIPS, base and default providers loaded,
#      default property query `fips=yes`. Non-FIPS algorithms then fail unless
#      a caller asks for them with usedforsecurity=False, as on a FIPS host.
#   4. Checks that the Python on PATH (or $PYTHON) really enforces it.
#
# Usage:
#   bash scripts/setup_fips_openssl.sh <dest-dir>
#   export OPENSSL_CONF=<dest-dir>/openssl-fips.cnf OPENSSL_MODULES=<dest-dir>
#   pytest tests/
#
# Needs: curl, perl, make, a C compiler, and an OpenSSL 3 `openssl` CLI.

set -euo pipefail

OPENSSL_VERSION="3.0.9"
OPENSSL_SHA256="eb1ab04781474360f77c318ab89d8c5a03abc38e63d65a603cabbf1b00a1dc90"

if [ "$#" -ne 1 ]; then
  echo "usage: $0 <dest-dir>" >&2
  exit 2
fi
mkdir -p "$1"
DEST="$(cd "$1" && pwd)"
PYTHON="${PYTHON:-python3}"

if [ ! -f "${DEST}/fips.so" ]; then
  WORK="$(mktemp -d)"
  trap 'rm -rf "${WORK}"' EXIT
  TARBALL="openssl-${OPENSSL_VERSION}.tar.gz"
  curl -fsSL -o "${WORK}/${TARBALL}" \
    "https://github.com/openssl/openssl/releases/download/openssl-${OPENSSL_VERSION}/${TARBALL}"
  echo "${OPENSSL_SHA256}  ${WORK}/${TARBALL}" | sha256sum -c -
  tar -xzf "${WORK}/${TARBALL}" -C "${WORK}"
  (
    cd "${WORK}/openssl-${OPENSSL_VERSION}"
    ./Configure enable-fips no-tests >/dev/null
    make -j"$(nproc)" build_generated >/dev/null
    make -j"$(nproc)" providers/fips.so >/dev/null
  )
  cp "${WORK}/openssl-${OPENSSL_VERSION}/providers/fips.so" "${DEST}/fips.so"
fi

openssl fipsinstall -quiet -out "${DEST}/fipsmodule.cnf" -module "${DEST}/fips.so"

cat >"${DEST}/openssl-fips.cnf" <<EOF
config_diagnostics = 1
openssl_conf = openssl_init

.include ${DEST}/fipsmodule.cnf

[openssl_init]
providers = provider_sect
alg_section = algorithm_sect

[provider_sect]
fips = fips_sect
base = base_sect
default = default_sect

[base_sect]
activate = 1

[default_sect]
activate = 1

[algorithm_sect]
default_properties = fips=yes
EOF

# A config that silently fails to load would turn the CI job into a plain
# test run, so prove it's enforced: MD5 must fail, and work when marked.
OPENSSL_CONF="${DEST}/openssl-fips.cnf" OPENSSL_MODULES="${DEST}" "${PYTHON}" - <<'EOF'
import hashlib
import ssl

print(f"{ssl.OPENSSL_VERSION} with the FIPS provider enforced")
try:
    hashlib.md5(b"x")
except ValueError:
    pass
else:
    raise SystemExit("FIPS provider not enforced: hashlib.md5() succeeded")
hashlib.md5(b"x", usedforsecurity=False)
hashlib.sha256(b"x")
EOF
