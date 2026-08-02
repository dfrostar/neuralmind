"""Agent OS PostgreSQL persistence schema and migration.

Provides SQL schema for Agent OS tables and a migration CLI command.

Schema mirrors the governance SQLite pattern from ai-product_ops skill:
- signals: anomaly signals detected in metrics streams
- insights: root-cause hypotheses from correlator
- proposals: improvement proposals
- experiments: A/B experiment results
- rollbacks: promotion/rollback history
- adversarial_queries: generated stress cases

Usage:
    neuralmind agent-os migrate --postgres postgresql://...
    neuralmind agent-os migrate --status
"""

from __future__ import annotations

from typing import Any

AGENT_OS_POSTGRES_SCHEMA = """
-- Agent OS governance tables (PostgreSQL)
-- Schema version: 1

CREATE TABLE IF NOT EXISTS signals (
    id TEXT PRIMARY KEY,
    ts DOUBLE PRECISION NOT NULL,
    metric_name TEXT NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    baseline DOUBLE PRECISION NOT NULL,
    delta DOUBLE PRECISION NOT NULL,
    severity DOUBLE PRECISION NOT NULL,
    level TEXT NOT NULL DEFAULT 'info',
    acknowledged INTEGER NOT NULL DEFAULT 0,
    tenant_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_signals_ts ON signals (ts);
CREATE INDEX IF NOT EXISTS idx_signals_metric ON signals (metric_name);
CREATE INDEX IF NOT EXISTS idx_signals_tenant ON signals (tenant_id);

CREATE TABLE IF NOT EXISTS insights (
    id TEXT PRIMARY KEY,
    signal_id TEXT REFERENCES signals(id),
    ts DOUBLE PRECISION NOT NULL,
    hypothesis TEXT NOT NULL,
    cause_type TEXT NOT NULL,
    cause_ref TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    tenant_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_insights_signal ON insights (signal_id);
CREATE INDEX IF NOT EXISTS idx_insights_tenant ON insights (tenant_id);

CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    ts DOUBLE PRECISION NOT NULL,
    insight_id TEXT REFERENCES insights(id),
    title TEXT NOT NULL,
    hypothesis TEXT NOT NULL,
    expected_impact DOUBLE PRECISION,
    uncertainty DOUBLE PRECISION,
    effort_estimate DOUBLE PRECISION,
    status TEXT NOT NULL DEFAULT 'proposed',
    allocated_budget DOUBLE PRECISION,
    created_by TEXT DEFAULT 'autopilot',
    approved_by TEXT,
    approved_at DOUBLE PRECISION,
    shipped_tag TEXT,
    tenant_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals (status);
CREATE INDEX IF NOT EXISTS idx_proposals_tenant ON proposals (tenant_id);

CREATE TABLE IF NOT EXISTS experiments (
    id TEXT PRIMARY KEY,
    proposal_id TEXT REFERENCES proposals(id),
    ts DOUBLE PRECISION NOT NULL,
    experiment_type TEXT,
    baseline_tag TEXT,
    candidate_tag TEXT,
    metric_name TEXT NOT NULL,
    baseline_value DOUBLE PRECISION NOT NULL,
    candidate_value DOUBLE PRECISION NOT NULL,
    delta DOUBLE PRECISION NOT NULL,
    p_value DOUBLE PRECISION,
    verdict TEXT NOT NULL,
    tenant_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_experiments_proposal ON experiments (proposal_id);
CREATE INDEX IF NOT EXISTS idx_experiments_verdict ON experiments (verdict);
CREATE INDEX IF NOT EXISTS idx_experiments_tenant ON experiments (tenant_id);

CREATE TABLE IF NOT EXISTS rollbacks (
    id TEXT PRIMARY KEY,
    experiment_id TEXT REFERENCES experiments(id),
    ts DOUBLE PRECISION NOT NULL,
    reason TEXT NOT NULL,
    from_tag TEXT,
    to_tag TEXT,
    auto_triggered INTEGER NOT NULL DEFAULT 0,
    tenant_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_rollbacks_experiment ON rollbacks (experiment_id);
CREATE INDEX IF NOT EXISTS idx_rollbacks_tenant ON rollbacks (tenant_id);

CREATE TABLE IF NOT EXISTS adversarial_queries (
    id TEXT PRIMARY KEY,
    ts DOUBLE PRECISION NOT NULL,
    query TEXT NOT NULL,
    expected_behavior TEXT,
    source_signal_id TEXT REFERENCES signals(id),
    added_to_fixtures INTEGER NOT NULL DEFAULT 0,
    tenant_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_adversarial_signal ON adversarial_queries (source_signal_id);

CREATE TABLE IF NOT EXISTS health_snapshots (
    id TEXT PRIMARY KEY,
    ts DOUBLE PRECISION NOT NULL,
    signal_count INTEGER NOT NULL DEFAULT 0,
    insight_count INTEGER NOT NULL DEFAULT 0,
    proposal_count INTEGER NOT NULL DEFAULT 0,
    promoted_count INTEGER NOT NULL DEFAULT 0,
    rolled_back_count INTEGER NOT NULL DEFAULT 0,
    top_signal TEXT,
    top_proposal TEXT,
    tenant_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_health_ts ON health_snapshots (ts);
"""


def create_postgres_tables(dsn: str) -> bool:
    """Create Agent OS tables in a PostgreSQL database.

    Args:
        dsn: PostgreSQL connection string

    Returns:
        True if successful, False otherwise
    """
    try:
        import psycopg2
    except ImportError:
        print("psycopg2 is required for PostgreSQL support. Install with: pip install psycopg2-binary")
        return False

    try:
        conn = psycopg2.connect(dsn)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(AGENT_OS_POSTGRES_SCHEMA)
        conn.close()
        return True
    except Exception as e:
        print(f"Failed to create tables: {e}")
        return False


def migrate_status(dsn: str) -> dict[str, Any]:
    """Check migration status of Agent OS tables."""
    try:
        import psycopg2
    except ImportError:
        return {"error": "psycopg2 not installed"}

    try:
        conn = psycopg2.connect(dsn)
        conn.autocommit = True
        with conn.cursor() as cur:
            tables = [
                "signals", "insights", "proposals",
                "experiments", "rollbacks", "adversarial_queries",
                "health_snapshots",
            ]
            status = {}
            for table in tables:
                cur.execute(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_name = %s",
                    (table,),
                )
                exists = cur.fetchone()[0] > 0
                if exists:
                    cur.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cur.fetchone()[0]
                    status[table] = {"exists": True, "rows": count}
                else:
                    status[table] = {"exists": False, "rows": 0}
        conn.close()
        return status
    except Exception as e:
        return {"error": str(e)}
