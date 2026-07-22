# Marketing — Index

**Last updated:** 2026-07-22  
**Active campaign:** v1.7.0 Free Tier Shipped  
**Claim-tier gate:** Every outbound claim traces to a CLI command or public doc. Audit at `campaign-v1.7.0/LINKEDIN-ABOUT-v1.7.0.md` § Claim-tier audit.

---

## Structure

```
docs/marketing/
├── README.md                          ← this file (index)
├── campaign-v1.7.0/                   ← time-bounded (v1.7.0 launch)
│   ├── LINKEDIN-ABOUT-v1.7.0.md       ← LinkedIn copy + claim audit
│   ├── LINKEDIN-ABOUT-TEMPLATE.md     ← blank template for next version
│   └── v1.7.0-OUTREACH-KIT.md         ← DM scripts + 5-target list
├── THREE-KEY-BENEFITS.md              ← permanent (pitch hierarchy)
├── MESSAGING-ARCHITECTURE.md          ← permanent (touchpoint inventory)
├── MEASUREMENT-FRAMEWORK.md           ← permanent (claim tiering)
├── GITHUB-WIKI-CORPORATE-PLAN.md      ← permanent (wiki refresh plan)
└── REBUILD-MEASUREMENT-20260723.md    ← dated (rebuild log)
```

**Rules:**
- **Campaign folders** are time-bounded. v1.7.0 ships → folder locks. Next version = new folder.
- **Core assets** are permanent — updated each release, never archived.
- **Dated logs** capture rebuild decisions — kept for reference, not deleted.
- **No file in this folder without a purpose.** If it's not a campaign asset, core reference, or dated log — delete it.

---

## Current Public Surfaces (2026-07-22)

| Surface | Last v1.7.0 update | File |
|---------|-------------------|------|
| GitHub README | `652d6a2` | `README.md` |
| GitHub Wiki Home | `652d6a2` | `docs/wiki/Home.md` |
| Website Hero | `652d6a2` | `site/src/components/sections/Hero.tsx` |
| Website Features | `652d6a2` | `site/src/components/sections/Features.tsx` |
| Website FAQ | `652d6a2` | `site/src/components/sections/FAQ.tsx` |
| Sitemap | `891f806` | `site/public/sitemap.xml` |
| LinkedIn About | `652d6a2` | `campaign-v1.7.0/LINKEDIN-ABOUT-v1.7.0.md` |
| LinkedIn DMs | `652d6a2` | `campaign-v1.7.0/v1.7.0-OUTREACH-KIT.md` |
| Release notes | `891f806` | `RELEASE_NOTES_v1.7.0.md` |
| Codex how-to page | `652d6a2` | `site/src/app/publications/codex-setup/page.tsx` |
| PyPI keywords | — | `pyproject.toml` (needs v1.7.0 keywords) |

---

## Claim-tier summary (this release)

| Claim | Tier | Verification |
|-------|------|-------------|
| Free tier auto-provision on first wakeup | A | `neuralmind wakeup .` writes `license.json` |
| Default tier flipped to "free" | A | `tier2/config.py:95` |
| Upgrade CTA at call 10 | A | `cli.py:_increment_wakeup_count()` |
| 40-70x token reduction | C | `python -m evals.public.run` |
| Team tier $29/user/mo | A | README pricing table |
| CFO Assessment $35K | B | `contracts/CONSULTING_AGREEMENT_TEMPLATE.md` |
| NIST AI RMF aligned | B | `SECURITY.md` |

**Cut from previous version:**
- `$15/mo Enterprise` — aspirational, not shipped (actual = $29/mo Team)
- `SOC2-ready` — architecture mapped, certification Q3 2027 (overclaim)

---

## Next marketing actions

1. [ ] Deploy site (`cd site && npm run build && npx wrangler pages deploy out`)
2. [ ] Update LinkedIn About with copy from `campaign-v1.7.0/LINKEDIN-ABOUT-v1.7.0.md`
3. [ ] Send Touch 1 DMs to 5 targets (see `v1.7.0-OUTREACH-KIT.md`)
4. [ ] Add `v1.7.0` section to `docs/wiki/CLI-Reference.md` (Tier2 ref footnote)
5. [ ] Add `v1.7.0` keywords to `pyproject.toml` (free-tier, auto-provision, upgrade-funnel)

---

## Skill dependencies

| Skill | Use |
|-------|-----|
| `neuralmind-marketing` | Product positioning, buyer personas, launch sequences |
| `b2b-social-content` | LinkedIn post/DM creation, claim-tier enforcement |
| `public-docs-refresh` | Per-release wiki/README/site refresh |

---

*Index v1.0. Release: v1.7.0 (2026-07-22). Next review: after Q3 2027 SOC 2 milestone.*
