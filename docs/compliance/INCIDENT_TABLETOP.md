# Incident Response Tabletop Exercise

**Date:** 2026-10-19
**Version:** 1.0
**SOC 2 Controls:** CC7.4, CC7.5 · **NIST SP 800-53:** IR-3

---

## 1. Purpose

The [incident response plan](INCIDENT_RESPONSE.md) is to be tested once a year
by a tabletop exercise, and none has been run. This is the kit for running one
in about an hour: a scenario in four timed parts, the questions each part asks,
and a record to fill in as you go.

A tabletop is a walk-through, not a drill. You say what you would do and show
where you would do it (the page, the button, the setting), but you don't
revoke, yank or publish anything. What it tests is whether the plan, the
access and the knowledge needed to follow it exist before they're needed.

One person can run it alone. It works better with a second person who reads
each part aloud, keeps time and asks "show me where": an advisor, a peer
maintainer, or a customer's security contact.

## 2. Before you start (10 minutes)

Have these open:

- [`INCIDENT_RESPONSE.md`](INCIDENT_RESPONSE.md) and [`SECURITY.md`](../../SECURITY.md)
- The repository's **Security** tab (advisories, Dependabot, code scanning)
- **Settings → Secrets and variables → Actions** and **Settings → Deploy keys**
- The PyPI project page for `neuralmind` (logged in) and the GHCR package page
- The Cloudflare Pages project `neuralmind-marketing`
- A copy of the record in §4 and a timer

Ground rules: say each step out loud before checking it; when you can't find
something within two minutes, write it down as a finding and move on.

## 3. Scenario: a critical flaw in a dependency, then a leaked credential

### Part 1: the report (0–15 minutes)

> A security researcher files a report through GitHub's private vulnerability
> reporting. A library the MCP server depends on has a remote code execution
> flaw in how it parses requests. They plan to publish a proof of concept in
> five days.

Questions:

1. How does the report reach you, and how would you notice it on a weekend?
   Show the notification setting that makes it reach you.
2. `SECURITY.md` promises an acknowledgement within 2 business days. Draft the
   acknowledgement now: what does it say?
3. Open the draft security advisory the report created, or show where you'd
   create one by hand. Who else can see it?
4. What severity is this, by the plan's §3 table, and what fix target does that
   set?
5. How do you decide whether NeuralMind's use of the library is exploitable?
   Name the tools (`pip-audit`, the call path from `neuralmind serve`, the VEX
   file `security/neuralmind.openvex.json`) and what you'd record in each.

### Part 2: it's reachable (15–30 minutes)

> You confirm the flaw is reachable: a request to the MCP server can trigger it.
> No fix has been released upstream yet.

Questions:

1. What do users run in the meantime? Is there a setting or flag that turns the
   vulnerable path off, and where is it documented?
2. Should the current release be yanked on PyPI? Show where you would do it and
   say what a yank does and doesn't do (it hides the version from new
   installs; installed copies keep running).
3. What happens to the GHCR `latest` tag and the published image?
4. Who has to be told before the fix ships: paid customers, the reporter,
   the library's maintainers? Where is the list of paid customers' security
   contacts?
5. What goes in the advisory's draft so far, and what stays out of it?

### Part 3: a leaked credential (30–45 minutes)

> While you work, a user reports that a CI log from one of the repository's
> workflows printed what looks like a secret.

The repository's workflows use four secrets: `MAIN_PUSH_DEPLOY_KEY`,
`GH_PAT`, `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`. PyPI publishing
uses trusted publishing (OIDC), with no stored token.

Questions:

1. For each secret: what could someone holding it do? (The deploy key pushes
   to `main` without a pull request; the Cloudflare token can deploy a
   different site to neuralmind.uk.)
2. For each: where do you rotate it, and what breaks until the new value is
   stored? Show the page for each.
3. How would you tell whether a leaked secret was used? Show where you'd look:
   recent pushes to `main` and who made them, Cloudflare Pages' deployment
   history, your GitHub account's security log.
4. How do you get the log line removed? (A workflow run's logs can be deleted
   from the run's page.)
5. Is this a second incident with its own advisory, or part of the first?

### Part 4: the fix ships (45–60 minutes)

> Upstream releases a fix. You update the dependency floor and are ready to
> release.

Questions:

1. Walk the release path: pull request, CI (the Windows job takes about
   30 minutes), the release-please pull request, the tag, PyPI and GHCR. How
   long is that end to end, and does it fit the 24–72 hour target?
2. What gets published, in order: the release, the advisory, a CVE request
   (GitHub can assign one from the advisory), the VEX update?
3. What do the release notes say, and what do they leave out?
4. How do you confirm the fix reached users (the PyPI version, the image tag)?
5. What would you change in the plan after this?

## 4. Record

Copy this into the record and fill it in during the exercise. Time how long
each "show me where" took; anything over two minutes is a finding.

```
Tabletop exercise record

Date:                     Start time:        End time:
Participants (and roles):
Scenario: critical dependency flaw, then a leaked credential (INCIDENT_TABLETOP.md v1.0)

Part 1, the report
  What I would do:
  Where I found it / time to find:
  Gaps:

Part 2, it's reachable
  What I would do:
  Where I found it / time to find:
  Gaps:

Part 3, a leaked credential
  What I would do:
  Where I found it / time to find:
  Gaps:

Part 4, the fix ships
  What I would do:
  Where I found it / time to find:
  Gaps:

Findings
  | # | Gap | Severity | Fix | Owner | Due | Done |
  |---|-----|----------|-----|-------|-----|------|

Changes to INCIDENT_RESPONSE.md:

Next exercise due:
Signed:
```

## 5. After the exercise

1. Keep the completed record privately (it lists the gaps an attacker would
   want to know), with the company's other internal records.
2. Add a line to §7 of [`INCIDENT_RESPONSE.md`](INCIDENT_RESPONSE.md) with the
   date the exercise was run and the plan changes it led to.
3. Turn each finding into a task with an owner and a due date. A finding about
   access or secrets (a missing notification, a rotation nobody could find)
   is fixed before anything else.
4. Put the next exercise in the calendar for a year out, and vary the
   scenario: a malicious pull request, a compromised maintainer account, or a
   defaced site.
