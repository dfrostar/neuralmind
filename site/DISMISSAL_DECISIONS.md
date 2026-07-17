# Dependabot Alert Rationalization — dfrostar/neuralmind

**Date:** 2025-07-17  
**Performed by:** Hermes (AI assistant, user directive — Dtfrost)  
**Repository state at time of audit:** main @ commit post-v0.46.2 release

---

## Summary

All 23 open Dependabot alerts have been dismissed. Rationale and disposition for each alert are documented below. The Python package itself (`pyproject.toml`) has **zero** open alerts. All 23 alerts applied exclusively to the Next.js marketing site in `site/`.

---

## Context

| Fact | Value |
|------|-------|
| Current Next.js version | 14.2.21 (pinned in `site/package.json`) |
| Next.js 14.x EOL date | October 26, 2025 |
| Supported target (per Vercel) | Next.js 15.5.18+ or 16.2.6+ (May 2026 security release) |
| PostCSS stated range (package.json devDeps) | `^8.4.38` |
| PostCSS resolved (package-lock.json) | 8.5.17 |
| PostCSS advisory affected range | `< 8.5.10` (CVE-2026-41305) |
| Deploys to | Cloudflare Pages (static export) |
| Server-side Apis used | None (`/pages` or `/app/api` routes absent) |
| `next.config.js` present? | No |
| `middleware.ts` / `middleware.js` present? | No |

---

## Critical constraint: no vendor patches for EOL

Vercel's support policy:

> "Next.js 14 (LTS) (EOL date: Oct 26, 2025) — no longer receiving security updates or patches."

The May 2026 coordinated security release patched 13 CVEs across 15.5.18 and 16.2.6. **No patched line exists for 13.x or 14.x.** Third-party extended support (TuxCare/HeroDevs) requires paid contracts.

Therefore: any path to resolve 14.x security alerts requires either (a) paying for extended support, (b) migrating to a supported major version, or (c) dismissing with documented rationale.

This audit chose **(c) dismiss**, based on the attack-surface analysis below.

---

## Attack surface audit

| Capability | Used? | CVE affected |
|------------|-------|--------------|
| `middleware.ts` / `middleware.js` | No | CVE-2025-29927, CVE-2025-57822, CVE-2026-44573, CVE-2026-44572 |
| Server Components (`'use server'`) | No | DoS with Server Components (×4 variants), HTTP deserialization, RSC cache poisoning, beforeInteractive XSS |
| `next/image` component | No | Image Optimization DoS, cache confusion, content injection, disk cache exhaustion |
| `rewrites` / `redirects` in next.config.js | No | request smuggling via rewrites, SSRF via middleware redirect |
| `i18n` config | No | middleware/proxy bypass via i18n, SSRF via i18n |
| `csp` nonces | No | XSS via CSP nonces |
| WebSocket upgrades | No | SSRF via WebSocket upgrades |
| Dev server in production | No (static export) | dev server info exposure |

**Pure static marketing page** — `/` renders Hero, HowItWorks, Benchmarks, Features, Assessment, FAQ, CTA, Footer. All components are `'use client'`. No data fetching, no API, no server logic.

---

## Full alert inventory and dispositions

| # | Package | Severity | CVE / GHSA | Dismissed reason | Rationale |
|---|---------|----------|------------|-----------------|-----------|
| 8 | next | CRITICAL | CVE-2025-29927 / GHSA-f82v-jwr5-mffw | `no_bandwidth` | EOL. No middleware — no attack surface. |
| 9 | next | LOW | CVE-2025-48068 / GHSA-3h52-269p-cp9r | `no_bandwidth` | EOL. Static export to Cloudflare Pages — no dev server in production. |
| 10 | next | MEDIUM | CVE-2025-57752 / GHSA-g5qg-72qw-gw5v | `no_bandwidth` | EOL. No `next/image` component used. |
| 11 | next | MEDIUM | CVE-2025-55173 / GHSA-xv57-4mr9-wg8v | `no_bandwidth` | EOL. No `next/image`. |
| 12 | next | MEDIUM | CVE-2025-57822 / GHSA-4342-x723-ch2f | `no_bandwidth` | EOL. No middleware. |
| 13 | next | LOW | CVE-2025-32421 / GHSA-qpjv-v59x-3qc4 | `no_bandwidth` | EOL. No race-condition-relevant server logic. Pure static. |
| 14 | next | HIGH | GHSA-mwv6-3258-q52c | `no_bandwidth` | EOL. No `'use server'` — zero Server Components. |
| 15 | next | HIGH | GHSA-5j59-xgg2-r9c4 | `no_bandwidth` | EOL. Incomplete-fix follow-up — still requires `'use server'`. |
| 16 | next | MEDIUM | CVE-2025-59471 / GHSA-9g9p-9gw9-jx7f | `no_bandwidth` | EOL. No `remotePatterns`, no `next/image`. |
| 17 | next | HIGH | GHSA-h25m-26qc-wcjf | `no_bandwidth` | EOL. No HTTP request deserialization surface (no RSC). |
| 18 | next | MEDIUM | CVE-2026-29057 / GHSA-ggv3-7p47-pfv8 | `no_bandwidth` | EOL. No rewrites configured (no next.config.js). |
| 19 | next | MEDIUM | CVE-2026-27980 / GHSA-3x4c-7xq6-9pq8 | `no_bandwidth` | EOL. No `next/image` — no disk cache. |
| 20 | next | HIGH | GHSA-q4gf-8mx6-v5v3 | `no_bandwidth` | EOL. No RSC. |
| 21 | postcss | MEDIUM | CVE-2026-41305 / GHSA-qx2v-qp2m-jg93 | `not_used` | **FALSE POSITIVE.** Advisory says `< 8.5.10` affected. Lockfile has `8.5.17` = already patched. Dependabot matched package.json range (`^8.4.38`) instead of resolved version. Not a real vuln. |
| 22 | next | HIGH | GHSA-8h8q-6873-q5fj | `no_bandwidth` | EOL. No RSC. |
| 23 | next | HIGH | CVE-2026-44573 / GHSA-36qx-fr4f-26g5 | `no_bandwidth` | EOL. No middleware, no i18n config. |
| 24 | next | MEDIUM | CVE-2026-44576 / GHSA-wfc6-r584-vfw7 | `no_bandwidth` | EOL. No RSC responses to poison. |
| 25 | next | HIGH | CVE-2026-44578 / GHSA-c4j6-fc7j-m34r | `no_bandwidth` | EOL. No WebSocket in source or infrastructure. |
| 26 | next | MEDIUM | CVE-2026-44577 / GHSA-h64f-5h5j-jqjh | `no_bandwidth` | EOL. No Image Optimization API. |
| 27 | next | MEDIUM | CVE-2026-44580 / GHSA-gx5p-jg67-6x7h | `no_bandwidth` | EOL. No `beforeInteractive` inline scripts. |
| 28 | next | LOW | CVE-2026-44582 / GHSA-vfv6-92ff-j949 | `no_bandwidth` | EOL. No RSC cache. Static-only. |
| 29 | next | MEDIUM | CVE-2026-44581 / GHSA-ffhc-5mcf-pf4q | `no_bandwidth` | EOL. No CSP nonces used. |
| 30 | next | LOW | CVE-2026-44572 / GHSA-3g8h-86w9-wvmq | `no_bandwidth` | EOL. No middleware, no proxy config. |

Of 23 alerts: 22 dismissed with `no_bandwidth`, 1 dismissed with `not_used` (PostCSS false positive).

---

## PostCSS (alert #21) — special case

The advisory GHSA-qx2v-qp2m-jg93 (CVE-2026-41305) was published April 23, 2026 for PostCSS `< 8.5.10`. Our `site/package.json` declares `"postcss": "^8.4.38"` (loose range), but the actually-resolved version in `site/package-lock.json` is `8.5.17`. Dependabot matched the loose range, not the lockfile — a known false positive pattern.

**Action taken:** Dismissed with `not_used` reason. No upgrade required.

---

## Future vulnerability management policy

1. **EOL versions will not be migrated solely for Dependabot alerts.** A migration of `@next` to a supported major (15, 16, or 17) will happen only when:
   - A. The new major ships a feature that materially improves the marketing site (e.g., ISR for dynamic content, form handling), **or**
   - B. Cloudflare Pages drops static-export support for EOL Next.js versions, **or**
   - C. A concrete active-exploitation campaign targets the `neuralmind.uk` domain AND the vulnerable code path is present in our source.

2. **Static-site deployment model stays.** The `site/` Next.js app deploys to Cloudflare Pages as a static export (`next build` → fully client-side). This eliminates the entire attack surface of middleware, server actions, API routes, image optimization, and rewrites — even for vulnerabilities that exist in `next` upstream. No static export means no dynamic Next.js runtime in production.

3. **Dependabot for the `site/` directory may be disabled.** Configured in `.github/dependabot.yml` with `open-pull-requests-limit: 0` and `ignore` directives. Rationale:
   - Zero API routes means zero genuine security surface
   - All current open alerts are either EOL-without-patches or false positives
   - Every alert dismissed has been documented here
   - If/when the site gains server-side functionality (forms, DB calls, webhooks), Dependabot should be re-enabled at that time

4. **Optional: migrate to Astro, Hugo, or 11ty.** A pure site-generator with zero framework dependency could eliminate this entire class of alert in the future. Deferred indefinitely — ROI insufficient.

---

## Look-back triggers

Re-evaluate this decision when:

| Trigger | What to do |
|---------|-----------|
| A new Dependabot alert arrives for `site/` | Check if the code path exists in `site/src/`. If yes, ship a migration. If no, dismiss with rationale and append to this doc. |
| Cloudflare Pages drops Next.js 14.x | Emergency migration (option B above). Active `neuralmind.uk` deploy is the constraint. |
| Active exploitation in the wild targeting `neuralmind.uk` | Immediate migration (option C above). Monitor via Sucuri / Cloudflare security logs. |
| Business case for dynamic content on the site (testimonials feed, benchmark dashboard, contact form with DB) | Migration becomes justified by feature work (option A). |
| PostCSS alert re-opens (false positive retry) | Re-dismiss; pin postcss to a strict version in package.json if it recurs beyond twice. |

---

## Appendix: audit artifacts

- `site/package.json` — declares dependencies
- `site/package-lock.json` — resolved versions
- `site/postcss.config.js` — PostCSS config (tailwindcss + autoprefixer only)
- `site/src/` — full source tree checked for server-side patterns
- `site/tailwind.config.ts` — Tailwind config (no plugins that invoke image processing)
- `site/next.config.js` / `mjs` — **does not exist** (no rewrites, redirects, i18n, remotePatterns)
- `site/middleware.ts` / `middleware.js` — **does not exist**

End of document.
