# Govern what your team's agents share

**Best for:** teams that commit a `.neuralmind-team-memory.json` bundle so every
developer's agent inherits what the others learned, and the reviewer who has to
sign off on that.

**Primary goal:** decide what a publish may take off a developer's machine, pull
back an association the team shouldn't share, and hand an auditor a record they
can verify (v4.6.0+; free at 1 seat).

Shared memory steers every teammate's agent. Team memory travels through git
(`neuralmind memory publish` writes learned weights between files, never source
code), and imports already pass a quality-scored review queue. Governance adds
three things to that: a publish policy, retraction, and an audit trail.

---

## 1. Set up governance

```bash
neuralmind onboarding           # license (free, 1 seat), scope, threshold, your admin email
neuralmind team governance status
```

`onboarding` writes `~/.config/neuralmind/tier2.yaml`. Until that file exists,
nothing in the team-memory flow is gated or audited. Admin commands take
`--admin <email>`, or set `NEURALMIND_ACTOR_EMAIL` once.

## 2. Choose what a publish may share

```bash
neuralmind team governance set-scope shared --admin you@yourco.com
neuralmind team governance set-weight-threshold 0.2 --admin you@yourco.com
```

| Scope | What `neuralmind memory publish` writes |
|---|---|
| `personal` | Nothing. Publish refuses and exits 1; memory stays on each machine |
| `shared` | Only the team baseline (the `shared` namespace): what the team already inherited or approved |
| `both` *(default)* | The developer's own learned memory plus the shared baseline |

The weight threshold (default 0.1) leaves weaker associations out of the
bundle. It applies to synapse edges; transitions are on a different scale and
aren't filtered.

## 3. Publish

```
$ neuralmind memory publish .
Published team memory → /repo/.neuralmind-team-memory.json (412 synapses, 37 transitions).
Team governance applied: scope=both, weight threshold 0.2 — 58 edge(s) below the threshold left out; audited.
```

The bundle's `provenance.governance` records the policy it was published under,
so the reviewer of the commit sees it in the diff. Under scope `personal`:

```
$ neuralmind memory publish .
Not published: Team governance scope is 'personal': memory stays on each machine, so `memory publish` is disabled. An admin can change it with `neuralmind team governance set-scope shared|both --admin <email>`.
```

A governance config that exists but can't be read (say, a hand-edited invalid
scope) makes publish refuse rather than publish ungoverned memory.

## 4. Review what comes in

When a teammate's bundle is imported (automatically, at session start or
build), each association is quality-scored: strong ones enter `shared`,
borderline ones wait for a human.

```bash
neuralmind memory review-list .
neuralmind memory review-approve auth/handlers.py auth/jwt_utils.py .
neuralmind memory review-reject legacy/session.py auth/session.py .
```

## 5. Stop sharing one association

```bash
neuralmind team governance list-shared --project .
neuralmind team governance remove-edge legacy/session.py auth/session.py --project . --admin you@yourco.com
git add .neuralmind-team-memory.json && git commit -m "Retract a stale team association"
```

`remove-edge` deletes the association from this machine's `shared` memory and
review queue, drops it from the bundle, and lists it under the bundle's
`retracted` key. That changes the bundle's content hash, so:

- each teammate's next session imports the update and deletes the pair from
  their `shared` memory;
- no later `memory publish` re-adds it, from anyone's personal memory included.

## 6. Hand the trail to an auditor

```bash
neuralmind team audit verify                                   # walk the SHA-256 hash chain
neuralmind team audit export --format csv --output audit.csv   # or --format json
```

| Action | Recorded when |
|---|---|
| `config_change` | An admin changes scope, threshold or enablement |
| `publish` | A publish runs, including one governance refused (`"blocked": true`) |
| `import` | A teammate's bundle is imported (counts promoted / held for review / retracted) |
| `review_approve`, `review_reject` | Someone decides on a held association |
| `remove` | An admin retracts an association |

The actor is `--admin` for admin commands, otherwise `NEURALMIND_ACTOR_EMAIL`,
the repository's `git config user.email`, or the OS user.

## Limits

- **The policy lives in each user's config, not in the repository.** It binds
  publishes made on machines where it's configured. To hold every publish to
  it, have teammates run `neuralmind onboarding` with the same settings, or
  have the admin publish. The bundle is a committed file either way, so code
  review sees every change to it.
- **Retraction reaches `shared` memory only.** Team flows never write a
  developer's `personal` memory, so an association a teammate learned on their
  own stays in their personal memory.
- **`set-governance-enabled false`** turns the scope and threshold gates off.
  Events are still audited.

## Related

- [Release notes v4.6.0](../releases/RELEASE_NOTES_v4.6.0.md)
- CLI reference: [`team governance`](../wiki/CLI-Reference.md#team-governance) ·
  [`memory`](../wiki/CLI-Reference.md#memory-v0240)
- [Team tier operator guide](../wiki/Tier2-Operator-Guide.md)
- [Branch-isolated memory & team baselines](./branch-isolated-memory.md)
