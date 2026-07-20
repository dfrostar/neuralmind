# Site Update — v0.53.0 (doc-code coupling + Tier 2 launch + free tier)

**Scope:** Bring docs.neuralmind.uk current with v0.52.0 → v0.54.0 milestones while respecting the per-seat pricing withdrawal.

---

## What ships in this update

**Featured release:** v0.53.0 — Free tier auto-provisioning

- Auto-provision a free-tier NeuralMind instance from `neuralmind doctor`
- Upgrade path: `free → team → enterprise` via `neuralmind team license provision --tier <free|team|enterprise>`
- Ed25519 license signature verified by OSS; privacy-first (no phone home)
- Tier 2 (Team): governance, audit log (SHA-256 hash-chain), seat management, self-hosted Docker

**Product release:** v0.54.0 (doc-code coupling + structural schema v2)

- `co-indexing v2`: doc files link to same-dir code files via `describes` edges
- Doctor shows: "526 doc files co-indexed with code"
- Structural schema v2 (backwards-compatible)
- 11,432 nodes indexed on self

---

## Draft site sections

### Banner block (docs/index.html)

```html
<meta name="description" content="NeuralMind v0.53.0 — persistent neural memory for AI coding agents. Free tier ships, Ed25519 license-gated Team tier, doc-code co-indexing (11,432 nodes). 40-70x token reduction. 100% local, MCP-native.">
<meta name="keywords" content="NeuralMind, AI coding agent memory, free tier, team tier, co-indexing, structural code graph, token reduction, MCP server, Ed25519 license, Claude Code">
```

```

### What's New in v0.53.0

**Free tier ship + Tier 2 governance: NeuralMind's OSS now auto-provisions a free instance, with an explicit upgrade path to team/enterprise tiers. v0.53.0 adds the `team` command for per-org assurance — governance, audit, seat management, self-hosted deployment — MIT path unchanged.**

*Three tiers, one commit:*

- **Free**: auto-provisioned. Full feature set. `neuralmind doctor` activates it.
- **Team ($org/mo)**: Governance + audit log (SHA-256 hash-chain, tamper-evident). Seat management. Self-hosted Docker. Activates with signed Ed25519 license.
- **Enterprise**: Reserved for regulated/air-gapped deployments. Custom contracts.

*The per-seat pricing page was withdrawn in favor of per-org assurance. docs/index.html does not list per-seat pricing.*

**Tier 2 security gated from OSS**

- Ed25519 license signing (no placeholder public key — real keypair, YubiKey cold-storage ready)
- Audit log: append-only hash-chained, `neuralmind team audit verify`
- Self-hosted: `docker-compose.yml` + `scripts/install-team.sh`, one-command deploy
- GDPR Articles 15-22, 33; privacy policy published; data-retention documented

---

### What's New in v0.54.0 (coming next release)

**Doc-code co-indexing v2: NeuralMind now links documentation files to the code they describe.**

*Same vector space, explicit edges:*
- File-level `.md` nodes link to file-level `.py`/`.ts`/etc. nodes in the same directory
- Headings that name a code symbol link to that symbol
- Result: `neuralmind query "X"` returns the design rationale alongside the implementation
- Doctor confirms: 526 doc files co-indexed, 26 explicit `describes` edges

**Structural schema v2 (backwards-compatible)**
- `describes` edge type added
- 11,430 nodes indexed on self-documenting NeuralMind checkout

---

## DRAFT: docs/about.html "What's New in v0.53.0" section

```html
<section id="whats-new-v0530">
    <div class="container">
        <h2>What's New in v0.53.0 — Free ships, team governance OSS-gated</h2>
        <p>NeuralMind's MIT core has always been free. v0.53.0 adds auto-provisioning, a free tier verification path, and drops the paywall down to a signed license check — no phone home, no SaaS dependency. Tier 2 (Team) ships the governance layer enterprises actually ask for: audit logs, seat management, self-hosted deployment, all activated offline with an Ed25519-signed license.</p>

        <h3>Free tier — auto-provisioned, OSS-native</h3>
        <p><code>neuralmind doctor</code> now activates a free license if none is present. Full retrieval, synapse layer, 10-language graphification. Zero network calls by default. The free tier is not a trial — it's the MIT product verifying itself.</p>

        <h3>Team tier — governance in OSS</h3>
        <ul>
            <li><strong>Per-org assurance pricing.</strong> Tier 2 is sold per organization, not per seat. Published pricing is gone — contracts are custom. No customer-facing per-seat comparisons.</li>
            <li><strong>Governance.</strong> Per-repo enable, personal/shared/both publish scope, admin-only, every config change logged.</li>
            <li><strong>Immutable audit log.</strong> Append-only SHA-256 hash-chained. <code>neuralmind team audit verify</code> walks the chain; tamper-evident by construction.</li>
            <li><strong>Self-hosted deploy.</strong> <code>docker-compose.yml</code>. One-command, air-gapped-ready, 30-day offline grace.</li>
            <li><strong>Seat management.</strong> Add/remove seats (soft-delete, preserves trail), <code>SeatLimitError</code> beyond license limit.</li>
        </ul>

        <h3>OSS integrity: real keypair, not placeholder</h3>
        <p>The Ed25519 signing key is generated by the operator and stored offline (YubiKey or paper). The public key in <code>neuralmind/tier2/license.py</code> is canonical — <code>scripts/verify_license_e2e.py</code> confirms sign→verify→tamper→expiry. No placeholder, no phone home.</p>

        <h3>GDPR + privacy</h3>
        <p>Privacy policy published at <code>neuralmind.uk/privacy</code>. GDPR Articles 6, 15-22, 33. Right-to-deletion process documented. Stripe DPA referenced. Cookie consent for analytics.</p>

        <p><a href="https://github.com/dfrostar/neuralmind/blob/main/RELEASE_NOTES_v0.53.0.md">Full v0.53.0 release notes →</a> &nbsp;|&nbsp; <a href="https://github.com/dfrostar/neuralmind/blob/main/docs/TIER2-BRD.md">Tier 2 BRD →</a> &nbsp;|&nbsp; <a href="https://github.com/dfrostar/neuralmind/blob/main/docs/TIER2-TRD.md">Tier 2 TRD →</a></p>
    </div>
</section>
```

---

## DRAFT: docs/about.html "What's New in v0.54.0" section

```html
<section id="whats-new-v0540">
    <div class="container">
        <h2>What's New in v0.54.0 — Doc-code co-indexing v2</h2>
        <p>NeuralMind has always co-indexed markdown and code in one vector space. v0.54.0 makes that relationship explicit: file-level document nodes now link to file-level code nodes in the same directory via <code>describes</code> edges. Headings that name a code symbol link to that symbol. The result: <code>neuralmind query "X"</code> returns the design rationale alongside the implementation.</p>

        <h3>How it works</h3>
        <ul>
            <li><strong>Path proximity.</strong> A <code>README.md</code> in <code>docs/foo/</code> links to every code file in <code>docs/foo/</code>.</li>
            <li><strong>Heading mentions.</strong> A heading named <code>finance.py</code> links to the code node labeled <code>finance.py</code>.</li>
            <li><strong>Capped at 50 edges.</strong> Prevents noise explosion. Doctor confirms: 26 explicit edges on the self-indexing checkout.</li>
        </ul>

        <h3>Structural schema v2</h3>
        <p>Backwards-compatible bump. New <code>describes</code> edge type. 11,430 nodes indexed on self-documenting NeuralMind checkout. <code>neuralmind doctor</code> reports: "526 doc files co-indexed with code (structural edges built)".</p>

        <p><a href="https://github.com/dfrostar/neuralmind/blob/main/RELEASE_NOTES_v0.54.0.md">Full v0.54.0 release notes →</a></p>
    </div>
</section>
```

---

## DRAFT: docs/sitemap.xml additions

```xml
<url>
    <loc>https://docs.neuralmind.uk/RELEASE_NOTES_v0.53.0.md</loc>
    <lastmod>2026-07-19</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
</url>
<url>
    <loc>https://docs.neuralmind.uk/RELEASE_NOTES_v0.54.0.md</loc>
    <lastmod>2026-07-19</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
</url>
<url>
    <loc>https://docs.neuralmind.uk/TIER2-BRD.md</loc>
    <lastmod>2026-07-19</lastmod>
    <changefreq>yearly</changefreq>
    <priority>0.4</priority>
</url>
<url>
    <loc>https://docs.neuralmind.uk/TIER2-TRD.md</loc>
    <lastmod>2026-07-19</lastmod>
    <changefreq>yearly</changefreq>
    <priority>0.4</priority>
</url>
```

---

## DRAFT: pyproject.toml keywords

```toml
keywords = [
    "AI coding agent memory",
    "semantic code search",
    "token optimization",
    "MCP server",
    "Claude Code",
    "tree-sitter code graph",
    "multi-language code indexing",
    "team memory",
    "governance",
    "audit log",
    "Ed25519 license",
    "self-hosted",
    "doc-code co-indexing",
    "structural code graph",
    "blast radius",
    "impact analysis",
    "synapse layer",
    "Hebbian learning",
    "local-first",
    "open source",
]
```

---

## What NOT to include

- Per-seat pricing ($29/user/mo) — withdrawn
- "Team of 5-50 seats" — replaced with per-org assurance
- Any pricing page or comparison table with per-seat numbers
- "Free trial" language — free tier is permanent, not a trial

---

## Files to edit

1. `docs/index.html` — banner + meta description + keywords
2. `docs/about.html` — new v0.53.0 + v0.54.0 sections, demote v0.52.0, update JSON-LD version
3. `docs/sitemap.xml` — new URLs
4. `pyproject.toml` — keywords
5. `RELEASE_NOTES_v0.53.0.md` — write canonical notes
6. `RELEASE_NOTES_v0.54.0.md` — write canonical notes
7. `README.md` — banner bump, release-notes row, in-context sections
8. `CHANGELOG.md` — release-please owns it, do NOT touch

---

## Release flow reminder

- `feat:` commits trigger release-please
- Release PR merges → tag → PyPI + GHCR
- Docs ship in same PR as feature
- Push to main → GitHub Pages auto-rebuild
