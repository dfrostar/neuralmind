# Working with NeuralMind commercially

The software is MIT-licensed and free, forever — that isn't changing.
What's below is what you can *pay* for: accountability, assurance, and
deployment help, for teams that need someone on the hook.

Every engagement starts from measured numbers, not claims — usually via
the [free AI-spend assessment](ASSESSMENT.md). If the numbers say
NeuralMind isn't a fit for your workload, that's the answer you'll get
([the failure modes are public](BUSINESS-CASE.md#the-case-is-weaker-if)).

**Contact:** [hello@neuralmind.uk](mailto:hello@neuralmind.uk?subject=Commercial%20engagement)

Introductory pricing below — early engagements shape the offering, and
the price reflects that.

---

## 1. Free — the software and the assessment

- Everything in this repository: the full retrieval + synapse engine,
  team memory, audit log, all ten languages, every integration. MIT.
- The [self-serve assessment](ASSESSMENT.md): run
  `neuralmind benchmark .` on your own hardware, send the report, get a
  three-line spend model back in your numbers.

No seat counts, no feature gates, no time limits.

## 2. Paid pilot — fixed fee, two weeks, your repo

**$2,500–5,000 fixed** (scoped by repo count and team size).

A structured two-week evaluation with one of your teams, run against
the acceptance criteria in the [pilot BRD](PILOT-BRD.md):

- Install + `doctor` green on your dev machines, index built on your
  repo(s), hooks/MCP wired into your agents (Claude Code, Cursor,
  Cline, Continue).
- Your 30 golden queries measured: recall, token reduction,
  faithfulness delta — the same harness as the
  [public benchmark](benchmarks/public.md).
- Team-memory baseline committed and onboarding lift measured.
- Ends with a written verdict either way: the measured numbers, what
  worked, what didn't, and whether a rollout is justified. If the
  verdict is "don't roll this out," you still keep the report.

## 3. Support & assurance — annual subscription

**$3,000–6,000/yr flat** (by org size), for teams running NeuralMind in
environments where "the maintainer might answer a GitHub issue" isn't
an acceptable support posture:

- **Priority support** with committed response times, backed by the
  published [vulnerability disclosure SLA](../SECURITY.md).
- **Upgrade assurance:** advance notice of breaking changes, migration
  review for your deployment pattern, and a direct channel when an
  upgrade misbehaves.
- **Compliance pack, assembled for your deployment:** the
  [compliance summary](COMPLIANCE-SUMMARY.md),
  [security guide](SECURITY-GUIDE.md), SBOM + provenance walkthrough,
  and deployment-architecture review — in the shape your auditors ask
  for it.
- **Air-gap deployment support:** the
  [air-gapped install](use-cases/air-gapped.md) done with you, including
  offline upgrade procedure.

## 4. Enterprise add-on — design partners wanted

The multi-user governance layer (SSO/RBAC around team memory,
compliance export, audit retention policies) ships as a separate,
commercially-licensed package — the MIT core is not being relicensed,
and any license validation will be an **offline signed file**: this
product will never phone home, including to us.

It gets built in demand order: the first design partners pick the first
features and get founding-customer pricing. If your security review
needs one of these controls, [say so](mailto:hello@neuralmind.uk?subject=Enterprise%20design%20partner)
— that's what sequences the roadmap.

---

## What we won't sell you

Same rules as [everywhere else in this project](HONEST-ASSESSMENT.md):

- **No hosted SaaS.** Local-first is the product. If you want someone
  else to run it, we're the wrong vendor.
- **No savings we didn't measure.** Engagements start by measuring your
  ratio on your code; measured numbers are labeled measured, derived
  numbers derived.
- **No lock-in mechanics.** Everything your team learns (indexes,
  synapse maps, team memory) lives in your repo and your
  `.neuralmind/` directory in open formats. Walking away is a
  `pip uninstall`.
