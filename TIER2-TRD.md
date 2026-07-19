# Tier 2 (Team) — Technical Requirements Document (TRD)

**Product:** NeuralMind
**Tier:** Team ($29/user/mo, annual)
**Version:** v0.52.0 → v1.0.0
**Author:** Darren Frost
**Date:** 2026-07-19

---

## 1. Executive Summary

This TRD defines the technical architecture for NeuralMind Tier 2 (Team). It builds on the existing v0.52.0 MIT core, adding governance, audit, self-hosted deployment, and seat management without breaking backward compatibility.

---

## 2. Architecture Overview

### 2.1 High-level components

```
┌─────────────────────────────────────────────────────────────────────┐
│                        NeuralMind Tier 2                            │
│                                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────────────┐  │
│  │  Team Gov   │  │  Audit Log   │  │  Self-Hosted Deployer     │  │
│  │  Module     │  │  Module      │  │  Module                   │  │
│  │  (new)      │  │  (new)       │  │  (new)                    │  │
│  └──────┬──────┘  └──────┬───────┘  └─────────────┬─────────────┘  │
│         │                │                         │                │
│  ┌──────▼────────────────────────────────────────────────────────┐  │
│  │                        API Layer                               │  │
│  └──────┬────────────────────────────────────────────────────────┘  │
│         │                                                          │
│  ┌──────▼────────────────────────────────────────────────────────┐  │
│  │                      Data Layer                                │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────┐  │  │
│  │  │  synapses.db │  │  audit.db    │  │  license.json       │  │  │
│  │  │  (existing)  │  │  (new)       │  │  (new)              │  │  │
│  │  └──────────────┘  └──────────────┘  └─────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Module Layout

```
neuralmind/
├── tier2/                      # NEW: Tier 2 module package
│   ├── __init__.py
│   ├── governance.py           # Team memory governance logic
│   ├── audit.py                # Audit log (append-only)
│   ├── self_hosted.py          # Self-hosted mode detection + config
│   ├── license.py              # License validation (online/offline)
│   ├── seats.py                # Seat management
│   ├── config.py               # Tier 2 YAML config schema
│   └── cli.py                  # Tier 2 admin CLI commands
├── cli.py                      # EXTENDED: Add tier2 subcommands
├── core.py                     # MINOR: Expose governance hooks
└── ...
```

### 2.3 Dependencies (新增)

| Dependency | Purpose | License |
|------------|---------|---------|
| `pydantic` | Config validation | MIT |
| `cryptography` | License key signing, encryption | BSD |
| `docker` (compose file) | Self-hosted deployment | n/a |

---

## 3. Data Model

### 3.1 Audit Log (new table — `audit.db`)

```sql
CREATE TABLE IF NOT EXISTS audit_log (
    id              TEXT PRIMARY KEY,       -- UUID
    ts              REAL NOT NULL,           -- Unix timestamp
    actor           TEXT NOT NULL,           -- user id or "system"
    action          TEXT NOT NULL,           | -- "publish" | "remove" | "config_change"
    target          TEXT,                    | -- repo, edge, config key
    details         TEXT,                    | -- JSON blob
    tier            TEXT NOT NULL DEFAULT "team"
);
CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log(actor);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
```

### 3.2 Governance Config (new table — `synapses.db` `meta` extension)

```sql
-- Reuse existing meta table pattern (key-value)
CREATE TABLE IF NOT EXISTS meta (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
);

-- New meta keys for Tier 2:
-- team_governance_enabled: "true" | "false"
-- team_publishing_scope: "personal" | "shared" | "both"
-- team_weight_threshold: float (0.0 - 1.0)
-- team_auto_decay_half_life: float (days)
-- team_admin_emails: JSON array of admin email addresses
-- team_license_key: encrypted license string
-- team_license_expires: ISO date
```

### 3.3 License File (new — `license.json`)

```json
{
  "tier": "team",
  "seats": 15,
  "issued_at": "2026-07-19T00:00:00Z",
  "expires_at": "2027-07-19T00:00:00Z",
  "issued_to": "acme-corp",
  "signature": "ed25519_signature_here"
}
```

---

## 4. API Design

### 4.1 Governance API (Tier 2 CLI + Python)

```python
# governance.py
class TeamGovernance:
    def __init__(self, db_path: Path, config: Tier2Config): ...
    def is_publishing_allowed(self, repo: str, edge_weight: float) -> bool: ...
    def get_shared_namespace(self) -> list[dict]: ...
    def remove_edge_from_shared(self, edge_id: str, admin: str) -> None: ...
    def set_publishing_scope(self, scope: str, admin: str) -> None: ...
    def set_weight_threshold(self, threshold: float, admin: str) -> None: ...
```

### 4.2 Audit API

```python
# audit.py
class AuditLog:
    def __init__(self, db_path: Path): ...
    def log(self, actor: str, action: str, target: str | None, details: dict) -> str: ...
    def export(self, since: float | None, until: float | None, actor: str | None) -> list[dict]: ...
    def export_csv(self, path: Path, **filters) -> None: ...
    def export_json(self, path: Path, **filters) -> None: ...
```

### 4.3 Self-Hosted API

```python
# self_hosted.py
class SelfHostedConfig:
    data_dir: Path
    license_path: Path
    bind_address: str  # default 127.0.0.1
    port: int          # default 8765

def is_self_hosted() -> bool: ...
def get_self_hosted_config() -> SelfHostedConfig: ...
```

### 4.4 License Validation

```python
# license.py
class LicenseValidator:
    def __init__(self, public_key: str, license_path: Path): ...
    def validate(self) -> LicenseStatus: ...  # VALID | EXPIRED | INVALID | OFFLINE_OK
    def can_operate_offline(self) -> bool: ...  # within 30-day grace

def load_license(path: Path) -> LicenseStatus: ...
```

### 4.5 Seat Management

```python
# seats.py
class SeatManager:
    def __init__(self, db_path: Path): ...
    def add_seat(self, email: str) -> None: ...
    def remove_seat(self, email: str) -> None: ...
    def list_seats(self) -> list[dict]: ...
    def is_active_seat(self, email: str) -> bool: ...
    def active_count(self) -> int: ...
    def can_add_seat(self) -> bool: ...  # under license limit
```

---

## 5. CLI Extensions

### 5.1 New commands

```bash
# Governance
neuralmind team governance status
neuralmind team governance set-scope <personal|shared|both>
neuralmind team governance set-weight-threshold <0.0-1.0>
neuralmind team governance list-shared [--json]
neuralmind team governance remove-edge <edge_id>

# Audit
neuralmind team audit list [--since <ts>] [--until <ts>] [--actor <email>] [--json]
neuralmind team audit export --format <csv|json> --output <path>

# Seats
neuralmind team seats list [--json]
neuralmind team seats add <email>
neuralmind team seats remove <email>

# Self-hosted
neuralmind team self-hosted init [--data-dir <path>]
neuralmind team self-hosted status
neuralmind team self-hosted validate-license

# License
neuralmind team license status
neuralmind team license activate <key>
```

### 5.2 Existing commands that show Tier 2 info

| Existing command | Tier 2 addition |
|------------------|-----------------|
| `neuralmind --version` | Appends tier info: `0.52.0 (Team, 15 seats)` |
| `neuralmind doctor` | Adds governance + license + seat checks |

---

## 6. Configuration

### 6.1 Default Tier 2 config (YAML)

```yaml
# ~/.config/neuralmind/tier2.yaml
tier: team
license_file: ~/.config/neuralmind/license.json
audit_db: ~/.config/neuralmind/audit.db

governance:
  enabled: true
  publishing_scope: both     # personal | shared | both
  weight_threshold: 0.1      # minimum edge weight for auto-publish
  auto_decay_half_life: 30.0 # days

self_hosted:
  enabled: false
  data_dir: ~/.local/share/neuralmind/
  bind_address: 127.0.0.1
  port: 8765
  offline_grace_days: 30
```

---

## 7. Security & Compliance

### 7.1 Encryption

| Data | Method |
|------|--------|
| License key at rest | AES-256-GCM, key derived from machine ID |
| Audit log | SHA-256 hash chain for tamper detection |
| Team memory edges | Existing synapses.db encryption |

### 7.2 Audit log hash chain

```
audit_log.entry_n.hash = SHA256(entry_n.data + entry_n-1.hash)
```

First entry uses genesis hash `SHA256("neuralmind-team-audit-v1")`.

### 7.3 License signing

- Issuer: NeuralMind private Ed25519 key
- Verifier: public key embedded in `neuralmind/tier2/license.py`
- Offline: signature valid for 30 days without re-validation

---

## 8. Self-Hosted Deployment

### 8.1 Docker Compose

```yaml
# docker-compose.yml (new file at repo root)
version: "3.8"
services:
  neuralmind:
    image: ghcr.io/dfrostar/neuralmind:latest
    volumes:
      - neuralmind-data:/data
      - ./license.json:/app/license.json:ro
    ports:
      - "127.0.0.1:8765:8765"
    environment:
      - NEURALMIND_TIER=team
      - NEURALMIND_SELF_HOSTED=true
      - NEURALMIND_DATA_DIR=/data
    healthcheck:
      test: ["CMD", "neuralmind", "doctor"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

volumes:
  neuralmind-data:
```

### 8.2 One-command deploy

```bash
curl -fsSL https://neuralmind.uk/install-team.sh | bash
```

---

## 9. Backward Compatibility

| Concern | Handling |
|---------|----------|
| Existing `synapses.db` schema | Unchanged — new `meta` keys only, additive |
| Existing `neuralmind memory publish` | Respects governance config; still works |
| Existing Team Memory auto-import | Still works; governance gates what enters shared |
| MIT users | Zero changes; Tier 2 only activates with license |
| Upgrade path | `neuralmind team self-hosted init` creates Tier 2 schema additive |

---

## 10. Error Handling

| Error | Response |
|-------|----------|
| Invalid license | `neuralmind doctor` shows red; `neuralmind team license status` details |
| License expired (within 14-day grace) | Warning but functional |
| License expired (beyond grace) | Read-only mode; publish disabled |
| Offline > 30 days | Grace period; warn but allow |
| Seat limit exceeded | `neuralmind team seats add` rejects with clear message |

---

## 11. Testing Strategy

| Layer | Tool | Coverage |
|-------|------|----------|
| Unit | pytest | governance, audit, license, seats, config |
| Integration | pytest | synapses.db + audit.db interaction |
| CLI | `scripts/e2e_team_tier.sh` | All Tier 2 CLI commands |
| Docker | `scripts/test_self_hosted.sh` | One-command deploy, data persistence, license validation |

---

## 12. Migration Plan

1. Merge Tier 2 into main as additive (no breaking changes)
2. Tag as v1.0.0
3. Create `tier2` branch for ongoing maintenance
4. Backport critical fixes from main to tier2
5. Self-hosted Docker image published to GHCR

---

*TRD complete. Next: Test Plan → DeepSeek QA → Kickoff prompt.*
