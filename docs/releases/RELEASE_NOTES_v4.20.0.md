# NeuralMind v4.20.0 — the site shows its evidence: one proof page with every number and every miss, and a security page that starts with verifying the release

**Type:** Minor release | **Theme:** the public site at [neuralmind.uk](https://neuralmind.uk/); nothing changes in the package

**No change to what your agent does.** The package, the CLI, the MCP tools, the
Claude Code hooks and the Hermes plugin are the same as in
[v4.19.0](RELEASE_NOTES_v4.19.0.md). This release is the site redesign
([#695](https://github.com/dfrostar/neuralmind/pull/695)). You don't need to
upgrade for it. release-please versions every `feat:` commit, so the site change
gets a version number.

The old homepage had eleven sections, three of them proof blocks in a row, and
the same field report was on two pages. Its numbers were typed into the page by
hand. Now each number is rendered from the file that measured it, and one page
holds all of them.

---

## What a visitor sees now

### A homepage of six sections, each answering one question

| Section | What it answers |
|---|---|
| **Hero** | What it does against the baseline you'd use anyway: the public benchmark's ripgrep comparison, a three-command install, and one benchmark query shown side by side |
| **How it works** | The steps, a five-command quickstart, and real `neuralmind query` output |
| **Features** | Four pillars: the right code in fewer tokens; stays current and remembers; local and verifiable; works with your agent |
| **Proof** | One block: the per-repo table, the CI gates, the refactor field report once (with its fixed-50K baseline named), a *Not measured* callout, and a comparison table limited to what is measured |
| **Teams & security** | Price, seats and billing, read from [`commercial-terms.json`](../../commercial-terms.json) |
| **FAQ / install** | The questions people ask before installing |

The Problem, Benchmarks, ProveIt, BusinessCase and Assessment sections are gone.

### `/benchmark` is the one proof page

[neuralmind.uk/benchmark](https://neuralmind.uk/benchmark/) is where every
performance claim on the site leads:

- **The headline and per-repo results**, read at build time from the committed
  run in `bench/public/results.json`: the gold file on 40 of 40 queries, against
  32 of 40 for keyword ripgrep opening its top five files whole, at 31–67× fewer
  tokens than that ripgrep baseline.
- **Where NeuralMind loses**, computed from the same run rather than written by
  hand. A plain vector index ranks the gold file higher on two of the four repos
  and costs fewer tokens.
- **The task-outcome pilot.** A pre-registered 20-task pilot ran Claude Code
  with and without NeuralMind and found no difference: 18 of 20 tasks solved in
  both arms, median per-task cost change +0.0% (95% CI −5.2% to +8.6%). The
  agent never called NeuralMind's MCP tools; NeuralMind reached it only through
  its hooks. The page gives the per-arm table, why it came out null, and what a
  pilot can and can't show
  ([#task-outcomes](https://neuralmind.uk/benchmark/#task-outcomes)).
- **What this does not measure.**
- **A ledger of every number the site quotes**
  ([#every-number](https://neuralmind.uk/benchmark/#every-number)): each with its
  evidence level (CI-gated, reproducible on demand, a one-repo field report, a
  pilot), where it was measured and the command that reproduces it.

The numbers are rendered, not retyped. `site/src/lib/evidence.ts` reads
[`site/claims.json`](../../site/claims.json), `bench/public/results.json` and the
150-question retrieval eval's output. `ratio()` throws on a value claims.json
doesn't list. The build fails if the ledger leaves out a ratio claims.json lists.
A number that drifts from its measurement breaks the site build, so it can't be
published.

### `/security` is the landing page for security and compliance teams

[neuralmind.uk/security](https://neuralmind.uk/security/) is in the order a
security review asks its questions:

1. **Verify a release.** The `cosign verify` and `gh attestation verify`
   commands for the image, wheel and sdist, the release's CycloneDX SBOM, the
   OpenVEX document, and the NIST SP 800-218 (SSDF) mapping. The commands name
   the latest release, which the page reads from GitHub at build time. A release
   from before signing began (v4.14.0) is labelled as unsigned instead of
   getting commands that would fail.
2. **What goes over the network.** By default NeuralMind sends no telemetry and
   transmits no repository content off your machine. The page lists everything
   it can send: the one-time embedding-model download, opt-in LLM seeding, and
   opt-in audit forwarding. It also lists your agent's own traffic, which
   NeuralMind makes smaller but doesn't control.
3. **Air-gapped install**, as commands.
4. **Controls you can turn on**, each with the command that shows it working:
   the CUI profile, the SP 800-53 hardening check, syslog audit forwarding,
   signed audit checkpoints, `scan-for-secrets` and `data-locations`. Each
   control says which release it shipped in. One that is on `main` but not yet
   released says so.
5. **Compliance evidence**: the SP 800-53 OSCAL component definition and the
   NIST overview. NeuralMind holds no certification. Whether a deployment meets a
   framework is decided by assessing that deployment.

The new walkthrough
**[Verify a NeuralMind release before installing it](../use-cases/verify-a-release.md)**
gives the verification steps one at a time: what each check proves, what it
doesn't, and what a failure looks like.

### Fewer offers, no savings promise

- The site offers one paid engagement, the Codebase Fit Assessment. The free
  AI-spend assessment and the "free spend model" offer are removed, and their
  links go to [/services#fit-assessment](https://neuralmind.uk/services/#fit-assessment).
- Cost-saving calls to action are removed. The pilot found no cost difference,
  so the site doesn't promise one. `tests/test_site_claims.py` rejects them if
  they come back.
- *For teams* in the hero goes to [/team](https://neuralmind.uk/team/).

### `/effectiveness` redirects to the field report

`/effectiveness` repeated the refactor field report. It now 301-redirects to
[/field-reports/measure-memory-across-a-refactor](https://neuralmind.uk/field-reports/measure-memory-across-a-refactor/),
whose honesty notes include its "what we can't claim" list. The nav's *Field
report* link and the footer point there. Old links and bookmarks still work.

## What the agent actually sees

Nothing new. No command, hook, MCP tool, environment variable or output changed.
There is no per-agent table because every agent gets the same as with v4.19.0.

## Upgrading

v4.20.0 behaves the same as v4.19.0. That includes a known defect: on Intel
macOS and Windows on ARM, where `pip install neuralmind` installs ChromaDB
instead of turbovec, every build fails unless the project sets
`backend: graph`.
[v4.20.1](RELEASE_NOTES_v4.20.1.md) fixes it. Every release is still signed,
attested and has an SBOM, and you can verify v4.20.0 like any other:
[Verify a NeuralMind release before installing it](../use-cases/verify-a-release.md).

## Reproduce

```bash
# The site's numbers against their canon (stdlib-only)
python -m pytest -q tests/test_site_claims.py tests/test_docs_claims.py

# Build the site: fails if a quoted ratio isn't in site/claims.json
# or the /benchmark ledger leaves one out
cd site && npm ci && npm run build
```

## Related

- [Public benchmark methodology and results](../benchmarks/public.md)
- [Task-outcome benchmark spec](../specs/TASK-OUTCOME-BENCHMARK-SPEC.md) and the pilot's raw data in `bench/task_outcome/pilot/`
- [SSDF mapping](../compliance/SSDF.md) and [NIST overview](../compliance/NIST.md)
- [Run NeuralMind air-gapped](../use-cases/air-gapped.md)
