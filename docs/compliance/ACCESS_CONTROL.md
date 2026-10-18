# Access Control Policy

**Date:** 2026-10-03
**Version:** 1.1
**SOC 2 Controls:** CC6.1, CC6.2, CC6.3

---

## 1. Purpose

Define who can access NeuralMind systems and data, and how access is granted, reviewed, and revoked.

## 2. Scope

Covers access to:
- NeuralMind GitHub repository (dfrostar/neuralmind)
- NeuralMind MCP server (local stdio)
- NeuralMind Cloudflare Pages (neuralmind.uk)
- NeuralMind PyPI package (dfrostar)
- NeuralMind GHCR images (dfrostar)

## 3. Roles and Permissions

### 3.1 Product Roles

The default policy, when a project's `security.roles` doesn't replace it:

| Role | Permissions | Who |
|------|-------------|-----|
| **admin** | Every tool (`"*"`) | System operator, CI |
| **builder** | All 28 MCP tools the server lists | Developers using agents |
| **reader** | 24 of them: everything except `neuralmind_build`, `neuralmind_ingest_document`, `neuralmind_record_decision` and `neuralmind_invalidate_decision` | Read-only access |

Where roles are enforced:

- **MCP tools**: every call. Under `security.identity: declared` (the default)
  the role is what the caller declares, so it constrains a cooperating agent,
  not a hostile one. Under `identity: os` it comes from the OS account
  (`security.users`).
- **The daemon's routes** and **`neuralmind build` / `validate --write`**
  *(v4.17.1+)*: under `identity: os` only, each needs the role the MCP tool
  doing the same thing needs (`/build` and the CLI writes need
  `neuralmind_build`). With `identity: declared` nothing off the MCP path names
  a role, so nothing is checked.
- **Other CLI commands and the hooks** run with the OS account's own file
  permissions. Against a local account that owns the project's files, those
  permissions are the boundary, not the role.

Implementation: `neuralmind/mcp_security.py` (`DEFAULT_ROLE_POLICY`,
`authorize_local`). Tests: `tests/test_mcp_security.py`,
`tests/test_security_identity.py`, `tests/test_local_role_checks.py`.

### 3.2 GitHub Repository Roles

| Role | Permissions | Who |
|------|-------------|-----|
| **admin** | Full access | Repository owner (dfrostar) |
| **write** | Push, PR creation | Trusted contributors |
| **read** | View, fork | Public |

### 3.3 Cloudflare Pages

| Role | Permissions | Who |
|------|-------------|-----|
| **admin** | Deploy, configure | Repository owner |
| **viewer** | View dashboard | None currently |

## 4. Access Granting

### 4.1 New User Provisioning

1. Identify required role
2. Add to appropriate GitHub team / Cloudflare access
3. Document in access register (this section)
4. Notify user of their responsibilities

### 4.2 Current Access Register

| User | GitHub Role | MCP Role | Cloudflare Role | Date Granted |
|------|-------------|----------|-----------------|--------------|
| dfrostar | admin | admin | admin | 2024-01-01 |
| ci-watcher | N/A | admin (CI) | N/A | 2024-01-01 |

## 5. Access Reviews

### 5.1 Frequency

- **Quarterly:** Review all access grants
- **Trigger-based:** Review immediately after role change or departure

### 5.2 Process

1. List all current access grants
2. Verify each grant is still needed
3. Remove any unnecessary grants
4. Document review in `audit_events.jsonl` or private log

### 5.3 Last Review

| Date | Reviewer | Findings | Actions |
|------|----------|----------|---------|
| 2026-07-27 | dfrostar | Initial review | Access register created |

## 6. Access Revocation

### 6.1 Deprovisioning

When access is no longer needed:
1. Remove GitHub collaborator / team membership
2. Remove Cloudflare access
3. Rotate any shared secrets (API tokens, deploy keys)
4. Update access register

### 6.2 Immediate Revocation

For security incidents:
1. Revoke access immediately (no waiting for review)
2. Rotate all potentially compromised secrets
3. Document in incident report

## 7. Secrets Management

### 7.1 Approved Secrets

| Secret | Storage | Rotation |
|--------|---------|----------|
| `CLOUDFLARE_API_TOKEN` | GitHub Secrets | Annual |
| `CLOUDFLARE_ACCOUNT_ID` | GitHub Secrets | Never (account ID) |
| PyPI API token | GitHub Secrets (trusted publishing) | Use OIDC instead |
| GitHub PAT | Personal access | Annual |

### 7.2 Forbidden Practices

- No secrets in code (use GitHub Secrets)
- No shared accounts (each user has own)
- No long-lived deploy keys (prefer OIDC)

---

*This policy is reviewed annually. Last reviewed: 2026-07-27.*
