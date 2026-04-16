# Security Policy

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

### Best Practices

When using NeuralMind:

1. **Sensitive Code**: Be cautious when processing repositories containing:
   - API keys or secrets
   - Credentials
   - Proprietary algorithms
   - Personal data

2. **Access Control**: Ensure the neural index files have appropriate permissions:
   ```bash
   # Set restrictive permissions on database
   chmod 700 graphify-out/neuralmind_db/
   ```

3. **Gitignore**: Add the database to `.gitignore` if not already:
   ```
   graphify-out/neuralmind_db/
   ```

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

## Acknowledgments

We thank all security researchers who help keep NeuralMind and its users safe.

---

_This security policy is subject to change. Last updated: 2024_
