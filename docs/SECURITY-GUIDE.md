# Security Hardening Guide

**Comprehensive security practices for deploying NeuralMind in enterprise environments.**

---

## Table of Contents

- [Security Model](#security-model)
- [Access Control (RBAC)](#access-control-rbac)
- [Data Protection](#data-protection)
- [Secret Management](#secret-management)
- [Audit & Compliance](#audit--compliance)
- [Threat Model](#threat-model)
- [Security Checklist](#security-checklist)

---

## Security Model

### Core Principles

1. **Zero Data Exfiltration** — Your code never leaves your infrastructure
2. **Local-First Processing** — All embeddings computed locally
3. **Explainability** — Every decision is auditable
4. **Least Privilege** — Users get minimum permissions needed
5. **Defense in Depth** — Multiple layers of protection

### What NeuralMind Does NOT Do

❌ Send code to external APIs  
❌ Collect telemetry or usage metrics  
❌ Store credentials in indexes  
❌ Cache queries in cloud storage  
❌ Share data between customers/projects  

---

## Access Control (RBAC)

### Role Definition

**Viewer** (read-only, low-privilege)
```python
{
    "name": "viewer",
    "permissions": [
        "query",      # Ask questions
        "search",     # Semantic search
        "wakeup"      # Project overview
    ],
    "rate_limit": 30,  # per minute
    "can_export": False
}
```

**Developer** (standard, most users)
```python
{
    "name": "developer",
    "permissions": [
        "query",           # Ask questions
        "search",          # Search code
        "skeleton",        # View file structure
        "audit-report",    # Access audit logs
        "benchmark"        # Run benchmarks
    ],
    "rate_limit": 60,
    "can_export": True
}
```

**Admin** (full access, system management)
```python
{
    "name": "admin",
    "permissions": ["*"],
    "rate_limit": 0,  # unlimited
    "can_export": True,
    "can_manage_users": True,
    "can_manage_roles": True
}
```

### RBAC Implementation

```python
from neuralmind.mcp_security import MCPSecurityMiddleware, Role

# Per-request enforcement
class AuthenticatedMCPServer:
    def __init__(self, project_path: str):
        self.project_path = project_path
        self.security = MCPSecurityMiddleware(
            project_path=project_path,
            enforce_rbac=True,
            audit_log_path=".neuralmind/audit/access.log"
        )
    
    async def query(self, question: str, user: User) -> str:
        # Check permissions
        self.security.require_permission(user, "query")
        
        # Enforce rate limits
        self.security.check_rate_limit(user.id)
        
        # Execute query
        result = neuralmind_query(self.project_path, question)
        
        # Log access
        self.security.audit_log(
            user_id=user.id,
            action="query",
            resource=self.project_path,
            result="success"
        )
        
        return result
```

### Integrating with Enterprise Directory

```python
# LDAP Integration
import ldap

def get_user_role(username: str) -> str:
    """Fetch role from LDAP/Active Directory"""
    conn = ldap.initialize("ldap://ad.company.com")
    conn.simple_bind_s("admin@company.com", password)
    
    result = conn.search_s(
        "cn=neuralmind_users,dc=company,dc=com",
        ldap.SCOPE_SUBTREE,
        f"(uid={username})",
        ["memberOf"]
    )
    
    if "cn=neuralmind_admins" in result[0][1]["memberOf"]:
        return "admin"
    elif "cn=neuralmind_developers" in result[0][1]["memberOf"]:
        return "developer"
    else:
        return "viewer"

# OAuth 2.0 Integration
from authlib.integrations.flask_client import OAuth

oauth = OAuth()
oauth.register(
    name='company-oauth',
    client_id=OAUTH_CLIENT_ID,
    client_secret=OAUTH_CLIENT_SECRET,
    server_metadata_url='https://oauth.company.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid profile email'}
)

@app.route('/login')
def login():
    redirect_uri = url_for('authorize', _external=True)
    return oauth.company_oauth.authorize_redirect(redirect_uri)

@app.route('/authorize')
def authorize():
    token = oauth.company_oauth.authorize_access_token()
    user = token.get('userinfo')
    role = get_user_role(user['email'])
    session['user'] = {'email': user['email'], 'role': role}
    return redirect('/neuralmind')
```

---

## Data Protection

### Encryption at Rest

**1. Database Encryption (PostgreSQL)**

```bash
# Enable pgcrypto extension
psql -U postgres -c "CREATE EXTENSION pgcrypto;"

# Create encrypted column for sensitive data
ALTER TABLE embeddings 
ADD COLUMN data_encrypted bytea;

# Encrypt on insert
UPDATE embeddings 
SET data_encrypted = pgp_sym_encrypt(data, 'encryption_key')
WHERE data_encrypted IS NULL;

# Decrypt on select
SELECT pgp_sym_decrypt(data_encrypted, 'encryption_key') as data
FROM embeddings;
```

**2. Filesystem Encryption (Local Index)**

```bash
# Linux: Use LUKS
sudo cryptsetup luksFormat /dev/sdX
sudo cryptsetup luksOpen /dev/sdX neuralmind_data
sudo mkfs.ext4 /dev/mapper/neuralmind_data
sudo mount /dev/mapper/neuralmind_data /neuralmind_index

# macOS: Use FileVault
diskutil secureErase freespace 0 -secureRandom /Volumes/neuralmind_data
# Then enable FileVault in System Preferences
```

### Encryption in Transit

**1. TLS for All Connections**

```bash
# Generate certificate (self-signed for dev)
openssl req -x509 -newkey rsa:4096 \
  -keyout neuralmind.key \
  -out neuralmind.crt \
  -days 365 \
  -subj "/CN=neuralmind.internal"

# Use Let's Encrypt for production
certbot certonly --standalone -d neuralmind.company.com

# Run MCP server with TLS
neuralmind-mcp \
  --tls-cert neuralmind.crt \
  --tls-key neuralmind.key \
  --port 8443
```

**2. Enforce HTTPS/TLS**

```nginx
# Force HTTPS redirect
server {
    listen 80;
    server_name neuralmind.company.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name neuralmind.company.com;
    
    ssl_certificate /etc/ssl/certs/neuralmind.crt;
    ssl_certificate_key /etc/ssl/private/neuralmind.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    
    location / {
        proxy_pass https://neuralmind-backend:8443;
        proxy_ssl_verify off;
    }
}
```

---

## Secret Management

### Detecting Secrets in Code

**NeuralMind scans for secrets during indexing:**

```bash
# Scan for exposed secrets
neuralmind scan-for-secrets .

# Output:
# ⚠️  Detected 5 potential secrets:
# 
# [HIGH] AWS_ACCESS_KEY_ID in config/prod.py:12
# [HIGH] GITHUB_TOKEN in .github/workflows/ci.yml:15
# [HIGH] DATABASE_PASSWORD in src/db.py:34
# [MEDIUM] API_KEY in tests/fixtures.py:89
# [LOW] stripe_pk_test in docs/example.md:42
```

**Automatic Redaction:**

```bash
# Build index with secrets redacted
neuralmind build . --redact-secrets

# Secrets are replaced with: [REDACTED:SECRET_TYPE]
```

### Managing Secrets Properly

**✅ Use environment variables:**
```python
import os

DB_PASSWORD = os.getenv('DATABASE_PASSWORD')
API_KEY = os.getenv('API_KEY')

# Never hardcode!
```

**✅ Use secret management services:**
```python
import boto3

secrets_client = boto3.client('secretsmanager')

def get_db_password():
    response = secrets_client.get_secret_value(
        SecretId='neuralmind/database/password'
    )
    return response['SecretString']
```

**✅ Use Kubernetes secrets:**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: neuralmind-secrets
type: Opaque
stringData:
  db-password: $(DB_PASSWORD)
  api-key: $(API_KEY)

---
apiVersion: v1
kind: Pod
metadata:
  name: neuralmind-mcp
spec:
  containers:
  - name: mcp
    env:
    - name: DATABASE_PASSWORD
      valueFrom:
        secretKeyRef:
          name: neuralmind-secrets
          key: db-password
```

**❌ Never commit secrets:**
```bash
# Add to .gitignore
echo ".env" >> .gitignore
echo "*.key" >> .gitignore
echo "secrets.json" >> .gitignore

# Use git-secrets to prevent accidental commits
brew install git-secrets
git secrets --install
git secrets --register-aws
```

---

## Audit & Compliance

### Audit Trail

Every query is logged with full context:

```json
{
  "timestamp": "2026-04-22T10:30:00Z",
  "user_id": "alice@company.com",
  "action": "query",
  "resource": "/path/to/project",
  "query": "How does authentication work?",
  "retrieved_files": [
    "src/auth/handler.py",
    "src/auth/middleware.py"
  ],
  "result": "success",
  "ip_address": "10.0.1.42",
  "user_agent": "Claude Code v1.0"
}
```

**Export for compliance:**

```bash
# Export last 90 days of audit logs
neuralmind audit-export \
  --start-date 2026-01-22 \
  --end-date 2026-04-22 \
  --format json \
  --output audit_Q1_2026.jsonl

# Export as NIST AI RMF report
neuralmind audit-report . \
  --compliance nist-ai-rmf \
  --output nist_report_2026.md
```

### NIST AI RMF Mapping

```
NeuralMind provides evidence for all NIST AI RMF domains:

GOVERN (Oversight)
├─ User roles and permissions (RBAC)
├─ Access audit trail
└─ Query provenance

MAP (Impact Assessment)
├─ Which code was retrieved
├─ Why (similarity scores)
└─ Confidence levels

MEASURE (Performance)
├─ Query latency
├─ Index quality metrics
└─ Benchmark reduction ratios

MANAGE (Risk)
├─ Secret detection results
├─ Rate limiting enforcement
└─ Anomaly alerts
```

### SOC 2 Compliance

```
NeuralMind satisfies SOC 2 Type II criteria:

✅ CC6.1 - Access Control
   Evidence: RBAC implementation, audit logs

✅ CC7.1 - Monitoring
   Evidence: Query logging, performance metrics

✅ CC7.2 - System Monitoring
   Evidence: Health checks, error tracking

✅ A1.1 - Processing Integrity
   Evidence: Index validation, audit trail

✅ C1.2 - Availability
   Evidence: Backup/recovery procedures

See docs/SOC2_COMPLIANCE_MAPPING.md for details.
```

---

## Threat Model

### Threats & Mitigations

| Threat | Likelihood | Impact | Mitigation |
|--------|-----------|--------|-----------|
| **Unauthorized access to MCP** | Medium | High | RBAC + OAuth + TLS |
| **Secrets exposed in code** | High | Critical | Secret scanning + redaction |
| **Index data breach** | Low | High | Encryption at rest + access logs |
| **Query interception** | Low | Medium | TLS 1.3 + mutual auth |
| **Resource exhaustion (DoS)** | Medium | Medium | Rate limiting + monitoring |
| **Insider threat** | Low | Critical | Audit trail + least privilege |
| **Configuration error** | Medium | High | Security checklist + automation |

### Attack Scenarios

**Scenario 1: SQL Injection in queries**
```
Attack: Attacker crafts malicious query to extract schema
Mitigation: Parameterized queries, input validation
Status: ✅ Not vulnerable (GraphQL queries, no SQL)
```

**Scenario 2: Privilege escalation**
```
Attack: Viewer user tries to access admin operations
Mitigation: RBAC enforcement at operation level
Status: ✅ Not vulnerable (permissions checked before execution)
```

**Scenario 3: Data exfiltration**
```
Attack: User downloads entire index to external device
Mitigation: Rate limiting, DLP rules, audit logs
Status: ✅ Detected (100MB/hour limit, logged)
```

---

## Security Checklist

Before deploying NeuralMind to production:

### Access & Authentication
- [ ] RBAC roles defined and assigned
- [ ] OAuth/SAML integration configured
- [ ] MFA enabled for admin accounts
- [ ] Service account credentials secured
- [ ] Regular access reviews scheduled

### Data Protection
- [ ] Encryption at rest (database, filesystem)
- [ ] TLS 1.2+ for all connections
- [ ] Secrets scanned and redacted
- [ ] No hardcoded credentials
- [ ] Key rotation policy established

### Audit & Compliance
- [ ] Audit logging enabled
- [ ] NIST AI RMF reports generated
- [ ] Query provenance captured
- [ ] Compliance mappings documented
- [ ] Regular audit log review

### Network Security
- [ ] Firewall rules restricting access
- [ ] No direct internet exposure
- [ ] VPN/private network for remote access
- [ ] DDoS protection enabled
- [ ] Network segmentation (if applicable)

### Infrastructure
- [ ] Automated backups tested (recovery verified)
- [ ] Security patches applied monthly
- [ ] Intrusion detection enabled
- [ ] Log aggregation configured
- [ ] Incident response plan documented

### Operations
- [ ] Security training for operators
- [ ] Least privilege for deployment accounts
- [ ] Change management process
- [ ] Disaster recovery drills scheduled
- [ ] Security scan results reviewed

---

## Reporting Security Issues

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, email: **security@company.com**

Include:
- Description of vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if available)

We aim to respond within 48 hours and issue patches within 30 days.

