# Enterprise Deployment Guide

**Deploying NeuralMind to production at scale with security, compliance, and reliability.**

---

## Table of Contents

- [Architecture Patterns](#architecture-patterns)
- [Deployment Options](#deployment-options)
- [Security Hardening](#security-hardening)
- [Performance Tuning](#performance-tuning)
- [Monitoring & Alerting](#monitoring--alerting)
- [Backup & Recovery](#backup--recovery)
- [Scaling to Large Teams](#scaling-to-large-teams)

---

## Architecture Patterns

### Single-Machine Deployment (Monorepo/Team)

**Best for:** Teams <20 people, codebases <500K LOC

```
Developer Machines
       ↓
[NeuralMind CLI] → [Local ChromaDB] → [graph.json]
       ↓
Claude Code / Cursor / ChatGPT
```

**Setup:**
```bash
# Per developer
pip install neuralmind
graphify update /path/to/project
neuralmind build /path/to/project
```

**Pros:** Zero infrastructure, instant setup, full privacy
**Cons:** Index duplication, manual updates per developer

---

### Centralized Shared Index (Enterprise)

**Best for:** Teams 20-200+ people, mission-critical codebases

```
Git Repository
       ↓
[Build Pipeline] → [PostgreSQL pgvector] ← [Audit Logs]
       ↓
[MCP Server] (with RBAC)
       ↓
Claude Code / Cursor / Internal Tools
```

**Setup:**

1. **PostgreSQL + pgvector** (central)
```bash
# On DB server
docker run -d \
  -e POSTGRES_DB=neuralmind \
  -e POSTGRES_PASSWORD=secure_password \
  -p 5432:5432 \
  pgvector/pgvector:latest

# Create neuralmind user
psql -U postgres -c "CREATE USER neuralmind WITH PASSWORD 'password';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE neuralmind TO neuralmind;"
```

2. **Index Builder Pipeline** (CI/CD)
```yaml
# .github/workflows/build-index.yml
name: Build NeuralMind Index

on:
  push:
    branches: [main]

jobs:
  build-index:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - run: pip install neuralmind graphifyy
      - run: graphify update .
      
      - name: Build index
        env:
          NEURALMIND_BACKEND: postgres
          NEURALMIND_DB_URL: postgresql://neuralmind:${{ secrets.DB_PASSWORD }}@db.company.com/neuralmind
        run: neuralmind build . --backend postgres
      
      - name: Generate audit report
        run: neuralmind audit-report . --format json --output audit_${{ github.run_number }}.json
      
      - uses: actions/upload-artifact@v3
        with:
          name: audit-report
          path: audit_*.json
```

3. **MCP Server** (per team/environment)
```bash
# Launch MCP server with security
neuralmind-mcp \
  --project-path /path/to/project \
  --backend postgres \
  --db-url postgresql://neuralmind:password@db.company.com/neuralmind \
  --rbac-enabled \
  --rate-limit-per-minute 60 \
  --port 8000
```

**Pros:** Shared index, audit trail, RBAC, scales to 1M+ nodes
**Cons:** Requires infrastructure, complexity

---

## Deployment Options

### Option 1: Local Development (Recommended for Teams <20)

**Installation per developer:**
```bash
pip install neuralmind
neuralmind install-hooks .  # PostToolUse compression
neuralmind init-hook .       # Auto-rebuild on commits
```

**Pros:** Instant, private, zero infrastructure  
**Cons:** Index duplication, requires manual sync

---

### Option 2: Docker Container

**Dockerfile for MCP server:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN pip install neuralmind

# Copy project
COPY . /project

# Build index on startup
RUN cd /project && graphify update . && neuralmind build .

# Launch MCP server
CMD ["neuralmind-mcp", "--project-path", "/project", "--port", "8000"]
```

**Docker Compose** (MCP + PostgreSQL):
```yaml
version: '3.9'

services:
  db:
    image: pgvector/pgvector:latest
    environment:
      POSTGRES_DB: neuralmind
      POSTGRES_PASSWORD: secure_password
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  neuralmind-mcp:
    build: .
    environment:
      NEURALMIND_BACKEND: postgres
      NEURALMIND_DB_URL: postgresql://postgres:secure_password@db:5432/neuralmind
      NEURALMIND_RBAC_ENABLED: "true"
    ports:
      - "8000:8000"
    depends_on:
      - db

volumes:
  pgdata:
```

**Deploy:**
```bash
docker-compose up -d
```

---

### Option 3: Kubernetes (Large Enterprise)

**Helm values** (`values.yaml`):
```yaml
replicaCount: 3

image:
  repository: ghcr.io/dfrostar/neuralmind
  tag: v0.4.2

backend:
  type: postgres
  postgres:
    host: postgres.default.svc.cluster.local
    port: 5432
    database: neuralmind
    user: neuralmind
    passwordSecret: neuralmind-db-pass

rbac:
  enabled: true
  roles:
    - name: viewer
    - name: developer
    - name: admin

resources:
  requests:
    memory: "2Gi"
    cpu: "1"
  limits:
    memory: "4Gi"
    cpu: "2"

autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
```

**Deploy:**
```bash
helm install neuralmind ./charts/neuralmind -f values.yaml
```

---

## Security Hardening

### Network Security

**1. Firewall Rules** (allow only from trusted networks)
```bash
# Allow only internal IPs to MCP server
ufw allow from 10.0.0.0/8 to any port 8000
ufw allow from 192.168.0.0/16 to any port 8000

# Deny everything else
ufw default deny incoming
```

**2. TLS/SSL** (encrypt all connections)
```bash
# Generate self-signed cert (dev) or use Let's Encrypt (prod)
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365

# Run MCP server with TLS
neuralmind-mcp \
  --project-path /path \
  --tls-cert cert.pem \
  --tls-key key.pem \
  --port 8000
```

**3. VPN/Private Network** (for remote teams)
```bash
# Run MCP behind VPN gateway
# Connect via: vpn.company.com → internal-neuralmind-server
```

### Access Control

**1. RBAC Configuration**
```python
from neuralmind.mcp_security import MCPSecurityMiddleware, Role

# Define roles
roles = {
    "viewer": {
        "permissions": ["query", "search", "wakeup"],
        "rate_limit": 30  # per minute
    },
    "developer": {
        "permissions": ["query", "search", "skeleton", "audit-report"],
        "rate_limit": 60
    },
    "admin": {
        "permissions": ["*"],
        "rate_limit": 0  # unlimited
    }
}

# Enforce per request
middleware = MCPSecurityMiddleware(
    project_path=".",
    user_id=request.user.email,
    role=get_user_role(request.user),  # From LDAP/OAuth
    rate_limit_config=RateLimit(calls_per_minute=60)
)
```

**2. Authentication**
```bash
# OAuth 2.0 / SAML integration
# Route MCP server through auth proxy:
# Client → [Auth Proxy] → [NeuralMind MCP] → [PostgreSQL]

# Example: nginx with OAuth2 proxy
upstream neuralmind {
    server localhost:8000;
}

server {
    listen 443 ssl;
    server_name neuralmind.company.com;
    
    ssl_certificate /etc/ssl/certs/cert.pem;
    ssl_certificate_key /etc/ssl/private/key.pem;
    
    location / {
        auth_request /oauth2/auth;
        proxy_pass http://neuralmind;
    }
}
```

### Secret Management

**1. No Secrets in Code**
```bash
# ✅ Good: Use environment variables
NEURALMIND_DB_PASSWORD=$(aws secretsmanager get-secret-value --secret-id neuralmind-db-pass --query SecretString --output text)

# ✅ Good: Use Kubernetes secrets
kubectl create secret generic neuralmind-db --from-literal=password=...

# ❌ Bad: Hardcode passwords
# neuralmind-mcp --db-url postgresql://user:password@host/db
```

**2. Secret Scanning in Indexes**
```bash
# NeuralMind automatically detects and redacts secrets
neuralmind scan-for-secrets .

# Output:
# ⚠️  Found 3 potential secrets:
#   - AWS_SECRET_ACCESS_KEY in src/config.py:42
#   - GITHUB_TOKEN in .env (already in .gitignore)
#   - STRIPE_API_KEY in tests/fixtures.py:10

# Fix secrets before building index
neuralmind build . --exclude-secrets
```

---

## Performance Tuning

### Index Size Optimization

**For large codebases (1M+ LOC):**

```bash
# 1. Exclude unnecessary files
# In neuralmind.toml:
[build]
exclude_patterns = [
    "*.test.js",
    "*.spec.py",
    "node_modules/",
    ".git/",
    "dist/",
    "build/"
]

# 2. Rebuild with optimization
neuralmind build . --optimize

# 3. Check node count
neuralmind stats .
# Nodes: 15234
# Size: 245 MB
```

### Embedding Backend Performance

**ChromaDB (local, <100K nodes):**
```bash
neuralmind build . --backend chromadb
# Fast startup, zero server cost
```

**PostgreSQL pgvector (enterprise, 100K-10M nodes):**
```bash
# Use connection pooling (PgBouncer)
neuralmind build . \
  --backend postgres \
  --db-url postgresql://neuralmind:pass@pgbouncer:6432/neuralmind \
  --batch-size 1000
```

**LanceDB (edge/offline, fast):**
```bash
neuralmind build . --backend lancedb
# Lightweight, Rust-based, serverless
```

---

## Monitoring & Alerting

### Health Checks

```bash
# Liveness check (server is running)
curl http://localhost:8000/health

# Readiness check (index is ready)
curl http://localhost:8000/ready

# Full status
curl http://localhost:8000/status
# Returns:
# {
#   "status": "healthy",
#   "index_version": "v0.4.2",
#   "nodes_indexed": 15234,
#   "last_build": "2026-04-22T10:30:00Z",
#   "backend": "postgres",
#   "uptime_seconds": 864000
# }
```

### Metrics Export

```bash
# Prometheus metrics
curl http://localhost:8000/metrics

# Includes:
# - neuralmind_query_duration_seconds
# - neuralmind_index_size_bytes
# - neuralmind_rbac_rejections_total
# - neuralmind_audit_events_total
```

### Logging

```bash
# Structured JSON logging
tail -f neuralmind.log | jq

# Monitor for errors
grep "ERROR" neuralmind.log

# Audit trail
grep "audit" neuralmind.log
```

---

## Backup & Recovery

### Backup Strategy

**Daily backups of index + audit logs:**

```bash
#!/bin/bash
# backup-neuralmind.sh

BACKUP_DIR="/backups/neuralmind-$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup PostgreSQL
pg_dump -U neuralmind neuralmind > "$BACKUP_DIR/index.sql.gz"

# Backup audit logs
cp -r .neuralmind/audit "$BACKUP_DIR/audit"

# Backup code graph
cp graphify-out/graph.json "$BACKUP_DIR/"

# Upload to S3
aws s3 sync "$BACKUP_DIR" s3://company-backups/neuralmind/

echo "Backup complete: $BACKUP_DIR"
```

**Schedule in cron:**
```bash
# Daily at 2 AM
0 2 * * * /scripts/backup-neuralmind.sh
```

### Recovery

```bash
# 1. Restore database
psql -U neuralmind < /backups/neuralmind-20260422_020000/index.sql.gz

# 2. Verify index
neuralmind stats .

# 3. Restore audit logs (for compliance)
cp -r /backups/neuralmind-20260422_020000/audit .neuralmind/
```

---

## Scaling to Large Teams

### Multi-Region Deployment

```
US Region              EU Region              APAC Region
[PostgreSQL]          [PostgreSQL]           [PostgreSQL]
    ↓                     ↓                       ↓
[MCP Server]          [MCP Server]           [MCP Server]
    ↓                     ↓                       ↓
Users (US)            Users (EU)             Users (APAC)
```

**Setup:**
```bash
# Use read replicas for scaling
psql -U postgres -c "CREATE PUBLICATION neuralmind_pub FOR ALL TABLES;"

# Configure each region's standby
pg_basebackup -h primary.us.db.company.com -D /var/lib/postgresql/data
```

### Load Balancing

```nginx
upstream neuralmind {
    server mcp-1.internal:8000;
    server mcp-2.internal:8000;
    server mcp-3.internal:8000;
}

server {
    listen 443 ssl;
    server_name neuralmind.company.com;
    
    location / {
        proxy_pass http://neuralmind;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### Cost Optimization

| Deployment | Scale | Cost/Month | Notes |
|------------|-------|-----------|-------|
| Local (1 dev) | 1-5 people | $0 | Free, private |
| Docker (team) | 5-50 people | $100-500 | Small server |
| PostgreSQL (enterprise) | 50-500 people | $1K-5K | Database + servers |
| Kubernetes (massive) | 500+ people | $5K-50K | Auto-scaling |

---

## Troubleshooting Deployments

### Index Build Fails

```bash
# Check graph exists
ls -la graphify-out/graph.json

# Check database connection
neuralmind backend-check postgres

# Enable debug logging
NEURALMIND_DEBUG=1 neuralmind build .
```

### MCP Server Crashes

```bash
# Check logs
journalctl -u neuralmind-mcp -n 100

# Verify database
psql -h db.internal -U neuralmind -c "SELECT COUNT(*) FROM embeddings;"

# Restart
systemctl restart neuralmind-mcp
```

### Performance Degradation

```bash
# Check index size
neuralmind stats .

# Monitor DB connections
psql -c "SELECT * FROM pg_stat_activity;"

# Rebuild if needed
neuralmind build . --force --optimize
```

---

## Best Practices Checklist

- ✅ Use PostgreSQL for teams >20 people
- ✅ Enable RBAC and audit logging
- ✅ Encrypt data in transit (TLS) and at rest
- ✅ Back up daily with recovery tested
- ✅ Monitor index health and query latency
- ✅ Use version pinning for dependencies
- ✅ Document your deployment architecture
- ✅ Test disaster recovery quarterly

