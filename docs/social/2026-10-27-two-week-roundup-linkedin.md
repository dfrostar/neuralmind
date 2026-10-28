# LinkedIn post — 2026-10-27: two weeks of releases, v4.16 to v4.22

**Draft, ready to post.** https://neuralmind.uk/whats-new/ is live, and every
feature below is on PyPI.

Company-page post rounding up the eleven releases from v4.16.0 (2026-10-17) to
v4.22.1 (2026-10-27). It complements
[#730](https://github.com/dfrostar/neuralmind/pull/730), which pitches the drift
and debt guards and links the same page. Drafted here so
`tests/test_docs_claims.py` vets it before it is posted.

LinkedIn renders plain text: paste the post as it stands, with no Markdown.
The first two lines show above "see more". If reach matters, move the link into
the first comment and end the post with "Link in the comments."

## Before posting

- [ ] Run `gh release list`. If v4.23.0 ([#728](https://github.com/dfrostar/neuralmind/pull/728))
      is out, make the first line "Twelve NeuralMind releases … v4.16 to v4.23".
- [ ] Post on a different day from #730's What's New post: both link the same
      page and mention `doctor`'s wiring check, the stale-index line and the
      task-outcome pilot.
- [ ] Don't add "compliant", "certified" or "CMMC-ready": NeuralMind supports
      controls in *your* system; your assessment decides compliance.

## Post text

Eleven NeuralMind releases in two weeks, v4.16 to v4.22. Here's what changed for the people using it.

For teams putting AI coding agents on CUI or federal code:
• One setting, security.profile: cui, turns on NeuralMind's hardened configuration and refuses changes that would weaken it
• Signed audit checkpoints, so the audit log can't be shortened or rewritten without "neuralmind audit verify" failing
• Live audit forwarding to syslog, with an alert when a record can't be written
• An OSCAL component definition for SP 800-53, and "neuralmind hardening", which checks a 17-rule baseline and exits non-zero on any failure
• "neuralmind data-locations", which lists every place NeuralMind keeps a project's data
These support controls in your system; your assessment decides compliance.

For everyone else:
• An answer from a stale index now says so, wherever the agent reads it
• A feature branch's call graph and memory stay on that branch, out of main's recall
• "neuralmind doctor" shows whether anything actually calls NeuralMind, with the fix for each missing piece
• "neuralmind demo" runs offline straight after install, with no model download (Linux, Apple Silicon, 64-bit Windows)

And on evidence: every number on neuralmind.uk is now rendered from committed benchmark data, on one proof page that lists the misses too. We also published a pilot in which NeuralMind made no measurable difference to cost per task; in those runs the agent never called a NeuralMind tool. Getting agents to use what it finds is the work now.

Every release, with notes: https://neuralmind.uk/whats-new/

#DeveloperTools #AIEngineering #CMMC

## Fact check

| Claim | Source |
|---|---|
| Eleven releases, v4.16.0 (2026-10-17) to v4.22.1 (2026-10-27) | `gh release list`; v4.20.0 is site-only and v4.22.1 docs-only, both still releases |
| `security.profile: cui` turns on the hardened settings and refuses what would weaken them | `docs/releases/RELEASE_NOTES_v4.16.0.md` |
| Signed checkpoints: newest records can't be removed, or the chain recomputed, without `audit verify` failing | `docs/releases/RELEASE_NOTES_v4.16.0.md` |
| Every record to syslog as written; alert when a record can't be written | `docs/releases/RELEASE_NOTES_v4.19.0.md` (`security.audit_syslog`, the AU.L2-3.3.4 alert) |
| OSCAL component definition for SP 800-53 | `security/neuralmind.oscal-component-definition.json` |
| `hardening` checks 17 rules, exits 1 on a failure | `docs/compliance/SP800-53-HARDENING.md` (NMH-1 to NMH-17), `tests/test_cli_exit_codes.py` (`hardening-baseline-not-met`) |
| `data-locations` lists every place NeuralMind keeps a project's data | `docs/releases/RELEASE_NOTES_v4.18.0.md` |
| A stale index says so in `query`, the MCP tools and the prompt block | `docs/releases/RELEASE_NOTES_v4.17.0.md` |
| A feature branch's calls and memory stay on the branch | `docs/releases/RELEASE_NOTES_v4.22.0.md` (#710, #717) |
| `doctor`'s Wiring section, each warning with its fix command | `docs/releases/RELEASE_NOTES_v4.22.0.md` (#700) |
| `demo` offline with no model download, on Linux, Apple Silicon macOS and 64-bit Windows only | `docs/releases/RELEASE_NOTES_v4.19.0.md` (#694 and its added note) |
| Site numbers rendered from committed data; one proof page with the misses | `docs/releases/RELEASE_NOTES_v4.20.0.md` (#695), `site/src/lib/evidence.ts` |
| Pilot: no measurable cost difference; no NeuralMind tool called in the 60 runs with it | `bench/task_outcome/pilot/report.txt`, `runs.jsonl`; `site/claims.json` pilot entry |
| What's New page lists the releases | `site/src/app/whats-new/page.tsx` (#718) |

Left out on purpose: the ChromaDB fallback in v4.21.0. Intel macOS still needs
a toolchain to compile `cryptography`, and Windows on ARM needs WSL 2, which is
more caveat than a roundup line can carry.
