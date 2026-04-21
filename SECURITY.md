# Security Policy

## Executive Summary for Enterprise

NeuralMind is designed with **enterprise security as a first-class concern**:

- **No external API calls** – all processing happens locally on your machines
- **No data exfiltration** – your code never leaves your development environment
- **Fully auditable** – open-source code, MIT license, complete transparency
- **Zero telemetry** – no usage tracking, no analytics, no hidden data collection
- **Compliance-ready** – works with GDPR, HIPAA, and other regulatory frameworks
- **Supply-chain safe** – minimal dependencies, all vendorable, no cloud lock-in

---

## Supported Versions

We release patches for security vulnerabilities in the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

We take the security of NeuralMind seriously. If you have discovered a security vulnerability, please report it responsibly.

### How to Report

**Please do NOT report security vulnerabilities through public GitHub issues.**

Instead, please report them via one of these methods:

1. **GitHub Security Advisories** (Preferred)
   - Go to the [Security tab](https://github.com/dfrostar/neuralmind/security)
   - Click "Report a vulnerability"
   - Fill in the details

2. **Email**
   - Send details to the project maintainers
   - Include "SECURITY" in the subject line

### What to Include

Please include the following information:

- Type of vulnerability (e.g., injection, authentication bypass, information disclosure)
- Full paths of source file(s) related to the vulnerability
- Location of the affected source code (tag/branch/commit or direct URL)
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the vulnerability
- Suggested fix (if any)

### Response Timeline

- **Initial Response**: Within 48 hours
- **Confirmation**: Within 1 week
- **Fix Timeline**: Depends on severity (see below)

### Severity Levels

| Severity | Description | Target Fix Time |
|----------|-------------|----------------|
| Critical | Remote code execution, data breach | 24-48 hours |
| High | Significant security impact | 1 week |
| Medium | Limited security impact | 2-4 weeks |
| Low | Minimal security impact | Next release |

## Security Considerations

### Data Handling

NeuralMind processes code from your projects. Here's what you should know:

1. **Local Processing**: All embeddings are generated and stored locally using ChromaDB
2. **No External Transmission**: Code is not sent to external servers (unless you use a remote ChromaDB)
3. **Storage Location**: Database files are stored in `graphify-out/neuralmind_db/`

### Best Practices for Enterprise Deployments

**For individuals:**
1. Ensure the neural index files have appropriate permissions:
   ```bash
   # Set restrictive permissions on database
   chmod 700 graphify-out/neuralmind_db/
   ```

2. Add the database to `.gitignore`:
   ```
   graphify-out/neuralmind_db/
   ```

**For enterprise/shared environments:**

1. **Centralized Index Storage**
   - Build the index on a secure, controlled machine
   - Store in a centralized location (shared filesystem, artifact repo)
   - Limit access to developers who need it (ACLs, RBAC)
   - Version-lock indexes to git commits for reproducibility

2. **Secrets Management**
   - NeuralMind never transmits code externally, but be cautious when processing repositories containing:
     - API keys or secrets (use `.gitignore` or secret scanning first)
     - Credentials
     - Proprietary algorithms
     - Personal data (PII)
   - Recommendation: Strip or mask secrets before indexing if at all possible

3. **Compliance & Audit Trails**
   - Log which teams/users access the index
   - Track changes to the knowledge graph with git commit history
   - Document your data retention policy (indexes can be regenerated)
   - Provide evidence of local-only processing to auditors

4. **On-Premise / Air-Gapped Deployments**
   - NeuralMind works without any internet access
   - Pre-build the index offline, then copy to disconnected environments
   - Perfectly suited for SCIF (Sensitive Compartmented Information Facility) or other classified environments

### Known Security Considerations

1. **ChromaDB**: We rely on ChromaDB for vector storage. Monitor their security advisories.

2. **MCP Server**: If using the MCP server, be aware:
   - It runs locally by default
   - Ensure firewall rules if exposing to network
   - Consider authentication if in shared environments

3. **Dependencies**: Keep dependencies updated:
   ```bash
   pip install --upgrade neuralmind
   ```

---

## Compliance Framework Alignment

NeuralMind is **designed to support** standard enterprise compliance requirements. Because it runs entirely locally and makes no external calls, it can fit into existing compliance workflows:

*Note: NeuralMind itself is not "certified" for any framework, but the tool's architecture aligns with the security requirements of these standards.*

### ✅ GDPR (General Data Protection Regulation)
- **Data Residency**: All code remains in your jurisdiction (on your machine/infrastructure)
- **No External Processing**: No third-party APIs, no cloud services
- **Data Deletion**: Delete `graphify-out/neuralmind_db/` to fully remove the index
- **Transparency**: Open-source code for full audit trail

### ✅ HIPAA (Health Insurance Portability and Accountability Act)
- **Encryption at Rest**: Store index on encrypted filesystems (you control encryption)
- **Access Controls**: Use OS-level permissions to restrict index access
- **Audit Logging**: All processing happens locally with no external calls
- **Business Associate Agreements**: No BAA needed (no external vendors processing your data)

### ✅ SOC 2 Type II
- **Security**: Local processing, no exfiltration, encrypted at rest (your choice)
- **Availability**: No dependencies on external services for core functionality
- **Confidentiality**: No data leaves your organization
- **Integrity**: Deterministic, reproducible indexing from your source code
- **Privacy**: No collection, no analytics, no tracking

### ✅ ISO 27001 / 27002
- **Information Security Management**: Runs entirely within your security perimeter
- **Access Controls**: Fine-grained OS-level permissions on index files
- **Encryption**: Compatible with whatever encryption strategy you use
- **Supplier Management**: Open-source, no hidden dependencies or data sharing agreements

### ✅ PCI DSS (Payment Card Industry Data Security Standard)
- **Local Processing**: Never transmits code to external networks
- **Network Segmentation**: Can run on completely isolated networks
- **Audit Capability**: Fully transparent, no black-box components
- **Change Management**: Source code control, open-source, version-locked

### ✅ FedRAMP / Government Compliance
- **Air-Gap Ready**: Works completely offline
- **On-Premise**: No cloud dependencies
- **Classified Environments**: Suitable for SCIF and other compartmented processing
- **Supply Chain Security**: Minimal dependencies, vendorable, no external calls

## Disclosure Policy

When we receive a security report:

1. We will confirm receipt within 48 hours
2. We will investigate and validate the issue
3. We will work on a fix
4. We will release a patch
5. We will credit the reporter (unless they prefer anonymity)

## Security Updates

Security updates are announced through:

- [GitHub Security Advisories](https://github.com/dfrostar/neuralmind/security/advisories)
- [Release Notes](https://github.com/dfrostar/neuralmind/releases)

## Auditability & Explainability

One of the biggest enterprise concerns with AI tools is the "black box" problem — models make decisions without clear justification, leading to hallucinations and liability.

### How NeuralMind Solves This

NeuralMind is **transparent by design**:

#### Full Query Provenance

When NeuralMind answers a question, it provides complete metadata about the context:

- **Which layers were used** – L0 (identity), L1 (summary), L2 (on-demand modules), L3 (semantic search)
- **Which code communities were loaded** – Specific clusters of related code
- **Search quality metrics** – Number of semantic hits, relevance scores
- **Token budget breakdown** – Exactly how many tokens came from each layer
- **Reduction ratio** – How much you saved vs. loading the full codebase

You can always:
- **Reproduce any result** – Same query + same codebase = same context (deterministic)
- **Audit the decision path** – See exactly which code entities and clusters were selected
- **Verify completeness** – Check if all relevant code was captured
- **Understand the tradeoffs** – View the token budget breakdown by layer

#### Transparency by Design

All processing is local and observable:
- No hidden cloud processing or external model calls
- No black-box ranking algorithms (semantic search is transparent)
- Can read the source code selection in full
- Every decision is reproducible and explainable

This is critical for regulated industries (healthcare, finance, legal, government) where AI recommendations must be auditable and verifiable.

---

## Acknowledgments

We thank all security researchers who help keep NeuralMind and its users safe.

---

_This security policy is subject to change. Last updated: 2026_
