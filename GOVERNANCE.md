# Project Governance

**Scope:** how the NeuralMind open-source project is maintained and how
decisions get made. (Customer-facing *team governance* — publish
scoping, audit, seats — is a product feature; see
[docs/wiki/Tier2-Operator-Guide.md](docs/wiki/Tier2-Operator-Guide.md).)

## Roles

- **Maintainer:** Darren Frost ([@dfrostar](https://github.com/dfrostar)),
  acting for Cheval-Volant LLC (d/b/a NeuralMind, Texas, USA) — the
  legal steward of the project.
- **Contributors:** anyone submitting PRs under the DCO
  ([docs/DCO.md](docs/DCO.md)). Review is gated by
  [.github/CODEOWNERS](.github/CODEOWNERS).

## Decision-making

- Day-to-day decisions (merges, releases, roadmap ordering) are made by
  the maintainer. Releases are automated via release-please from
  conventional commits; every release publishes a CycloneDX SBOM.
- Significant product or licensing changes are proposed as PRDs under
  `docs/prd/` and discussed in GitHub issues/discussions before landing.
- Licensing boundaries are fixed in [LICENSING.md](LICENSING.md) and
  [commercial-terms.json](commercial-terms.json) (CI-gated); changing
  either requires an explicit maintainer decision, never a drive-by PR.

## Continuity — what happens if the maintainer stops

- **The MIT core is permanently forkable.** Every release up to and
  including v2.0.1 is entirely MIT; the core remains MIT thereafter.
  There is no CLA assigning copyright — contributions stay with their
  authors under DCO + MIT, so no single party can retroactively close
  the core.
- **Paid users keep what they licensed.** `neuralmind/tier2/` is
  source-available in-repo: licensees can read, build, and keep running
  it even if distribution stops, and the free 1-seat grant never
  expires.
- **A successor needs nothing private to operate the project:** source,
  docs, wiki, benchmarks, per-release SBOMs, and CI workflows are all
  in-repo or public.
- If the project is transferred or archived, notice will be posted in
  README.md and on neuralmind.uk.

## Security & conduct

- Vulnerabilities: [SECURITY.md](SECURITY.md) (private disclosure).
- Community standards: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Contact

hello@neuralmind.uk (general) · legal@neuralmind.uk (licensing, trademarks)
