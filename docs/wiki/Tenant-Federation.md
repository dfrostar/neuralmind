# Tenant Federation

Agent OS supports multi-tenant isolation with a file-based registry. This document describes the single-instance architecture, multi-instance federation pattern, and known limitations.

## Single-Instance File-Based Registry

By default, Agent OS uses a local file-based tenant registry. Each tenant is stored as a JSON file in the `NEURALMIND_TENANTS_DIR` directory (default: `~/.neuralmind/tenants/`).

```
~/.neuralmind/tenants/
├── acme.json      # Tenant "acme" with RBAC, projects, tier
├── zebra.json     # Tenant "zebra"
└── signals/
    ├── acme/
    │   ├── signals.jsonl   # Signal records
    │   └── insights.jsonl  # Correlator insights
    └── zebra/
        └── ...
```

**Isolation guarantees:**
- Each tenant's data is stored in a separate file
- RBAC is enforced at the API layer (tenant-scoped endpoints)
- Projects are conflict-checked across tenants (no project path can belong to two tenants)

## Multi-Instance Federation

For high-availability or geographic distribution, Agent OS can be deployed as multiple instances with a shared PostgreSQL backend.

### Shard by Tenant ID Hash

When multiple Agent OS instances run against the same PostgreSQL database, tenants are sharded by hashing their `tenant_id`:

```python
import hashlib

def shard_for_tenant(tenant_id: str, num_shards: int) -> int:
    """Determine which shard owns a tenant."""
    hash_bytes = hashlib.sha256(tenant_id.encode()).digest()
    return int.from_bytes(hash_bytes[:4], 'big') % num_shards
```

**Federation rules:**
1. **Write routing**: Each instance only writes to shards assigned to it
2. **Read routing**: Reads can come from any instance (PostgreSQL handles consistency)
3. **Conflict resolution**: Last-write-wins with timestamp-based resolution
4. **Signal isolation**: Signals are per-tenant; correlator runs per-instance but reads from shared PostgreSQL

### Deployment Topology

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Agent OS       │    │  Agent OS       │    │  Agent OS       │
│  Instance A     │    │  Instance B     │    │  Instance C     │
│  (shard 0,1)    │    │  (shard 2,3)    │    │  (shard 4,5)    │
└────────┬────────┘    └────────┬────────┘    └────────┬────────┘
         │                      │                      │
         └──────────────────────┼──────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    │   PostgreSQL Cluster  │
                    │   (shared tenant      │
                    │    registry, signals, │
                    │    insights)          │
                    └───────────────────────┘
```

## Known Limitations

1. **Signal detector is in-memory**: Page-Hinkley state is per-instance and does not survive restarts. For multi-instance deployments, signals are logged to PostgreSQL but the detector state is not shared.

2. **No cross-instance correlation**: Correlator runs per-instance. If a tenant is sharded across instances, each instance correlates independently.

3. **Human-in-the-loop for promotions**: Auto-promote is gated behind `MIN_SIGNALS_BEFORE_AUTO_PROMOTE` (currently 5). Multi-instance signal counts must be aggregated from PostgreSQL.

4. **Eventual consistency**: With multi-instance PostgreSQL, there may be a brief delay before signals written by one instance are visible to another.

5. **No automatic failover**: If an instance dies, its tenants' signals are preserved in PostgreSQL but the in-memory detector state is lost. A new instance must rebuild detector state from history.

## Configuration

```bash
# Single-instance (default)
export NEURALMIND_TENANTS_DIR=~/.neuralmind/tenants

# Multi-instance with PostgreSQL
export AGENT_OS_POSTGRES_DSN=postgresql://user:pass@host/agent_os
export AGENT_OS_SHARD_ID=0
export AGENT_OS_NUM_SHARDS=3
```

## Migration from File-Based to PostgreSQL

```bash
# Run migration
neuralmind agent-os migrate --postgresql $AGENT_OS_POSTGRES_DSN

# Verify migration
neuralmind agent-os migrate --status
```

## Schema

See `neuralmind/agent_os/postgres.py` for the full schema including:
- `signals` — anomaly signal records
- `insights` — correlator root-cause hypotheses
- `proposals` — improvement proposals with tags
- `experiments` — A/B experiment results with p-values
- `rollbacks` — promotion/rollback history
- `adversarial_queries` — generated stress cases
- `health_snapshots` — aggregated health metrics

## See Also

- `neuralmind/agent_os/tenant.py` — Tenant registry and RBAC
- `neuralmind/agent_os/signals_log.py` — Signal/insight storage
- `neuralmind/agent_os/postgres.py` — PostgreSQL schema
- `neuralmind/agent_os/promotion.py` — Auto-promote/rollback
