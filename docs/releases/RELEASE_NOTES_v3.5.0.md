# NeuralMind v3.5.0 — the state directory stops being a place secrets can hide

A user reported that NeuralMind leaked their API key. It's worth being
precise about what that did and didn't mean, because the shape of the bug
determines the fix.

NeuralMind has no egress. There is no NeuralMind server, no telemetry, and
nothing in the package posts your code anywhere — the only outbound request
in a default install is the one-time, SHA256-pinned ONNX model download. So
no key was transmitted.

What happened instead is worse in a quieter way. NeuralMind **wrote the key
down**, in plaintext, inside the user's repository, and nothing stopped them
from committing it.

Three things combined:

1. The PostToolUse Bash hook stashes the most recent command's raw
   stdout/stderr to `.neuralmind/last_output.json`, so `neuralmind last` can
   recover output elided by compression. It stored whatever the command
   printed — including `printenv`, `aws configure list`, and any `curl -H
   "Authorization: Bearer …"`, whose credential also appears in the cached
   command line.
2. Nothing git-ignored `.neuralmind/` in a *user's* project. This repository
   ignores it, and `SECURITY.md` said so — which read as a guarantee for
   everyone. It wasn't. A routine `git add -A` after a build staged the whole
   directory.
3. `SECURITY-GUIDE.md`, `DEPLOYMENT-GUIDE.md`, and the wiki FAQ all
   documented `neuralmind scan-for-secrets` and `neuralmind build
   --redact-secrets`. Neither existed. Anyone following the security guide
   ran a command that errored, and could reasonably have concluded that
   redaction was on.

v3.5.0 fixes all three.

## What's in this release

| Change | Was | Now |
|--------|-----|-----|
| **`.neuralmind/` in git** | Nothing ignored it in your project; `git add -A` staged cached command output | Created with its own `.gitignore` containing `*` — self-ignoring, no entry needed in your project's `.gitignore` |
| **Already-committed state** | Silent | `neuralmind build` warns and prints the `git rm -r --cached` recovery command |
| **Bash recovery cache** | Raw stdout/stderr/command written verbatim | Credentials replaced with `[REDACTED:<kind>]` before the write; the entry records which kinds were removed |
| **`scan-for-secrets`** | Documented, never implemented | Real command; exits non-zero on high-confidence findings so CI can gate |
| **`build --redact-secrets`** | Documented, never implemented | Real flag; scrubs detected credentials from text entering the index |
| **Security docs** | Referenced three commands and flags that did not exist (`--exclude-secrets` too) | Describe what actually ships, including what is *not* automatic |

## 1. The state directory ignores itself

`ensure_state_dir()` now creates `.neuralmind/` with a `.gitignore`
containing a single `*`, which makes the directory ignore its own contents —
itself included. The protection travels with the state rather than depending
on the host project's configuration, so it works in a repo that has never
heard of NeuralMind.

```bash
$ git add -A && git diff --cached --name-only
app.py            # .neuralmind/ is not staged
```

This runs both from `neuralmind build` and from the output-cache write path,
so the guard exists even if a hook is the first thing to create the directory.

**The ignore rule is not retroactive.** Files git already tracks stay tracked.
If you built with an earlier version, check:

```bash
git ls-files .neuralmind/          # expect no output
git rm -r --cached .neuralmind/    # untrack if it returned anything
```

`neuralmind build` now prints this warning itself when it detects tracked
state. If anything did reach a commit, **rotate the credential** — a key in
git history is compromised whether or not the repo is public.

## 2. The recovery cache is redacted

`.neuralmind/last_output.json` is scrubbed before it touches disk, by the new
`neuralmind/secret_scan.py`. High-confidence detection covers Anthropic and
OpenAI keys, AWS access key IDs and secret keys, GitHub tokens and
fine-grained PATs, Slack tokens, Google API keys, Stripe keys, PyPI and npm
tokens, PEM private-key blocks, JWTs, `Authorization: Bearer`/`Basic`
headers, and passwords embedded in database connection strings.

Redaction runs **before** truncation, so a secret can't survive inside a kept
head or tail slice of a large payload. The command line is scrubbed too, not
just the output.

```json
{
  "command": "curl -H \"Authorization: Bearer [REDACTED:github-token]\" ...",
  "stdout": "ANTHROPIC_API_KEY=[REDACTED:anthropic-api-key]\n",
  "redacted": ["anthropic-api-key", "github-token"]
}
```

The `redacted` list is there so you can tell scrubbing happened and re-run the
command yourself if you need the real value. Opt out with
`NEURALMIND_OUTPUT_REDACT=0`; there is no good reason to.

## 3. `scan-for-secrets` exists now

```bash
$ neuralmind scan-for-secrets .
NeuralMind secret scan — /home/dev/myproject

  [HIGH ] .env:1  anthropic-api-key  (sk-a…(43 chars))
  [HIGH ] src/config.py:8  aws-access-key-id  (AKIA…(20 chars))
  [maybe] src/db.py:34  generic-secret-assignment  (9f8K…(28 chars))

  2 high-confidence, 1 heuristic.
$ echo $?
1
```

Two tiers, because a scanner that cries wolf gets ignored. `HIGH` is a
vendor-specific shape that effectively never fires on prose. `maybe` is a
generic `SECRET=value` assignment that cleared a Shannon-entropy threshold and
a placeholder denylist — `password = "changeme"`, `api_key =
os.environ["X"]`, and `KEY=${VAR}` are not findings.

Previews carry a short prefix and a length, never the tail, so scan output is
safe to paste into an issue or a CI log.

Exit codes are built for gating: `0` clean, `1` on any high-confidence finding
(add `--strict` to fail on heuristics too), `2` on a bad path. `--json` for
machine-readable output, `--high-confidence-only` to drop the heuristic tier.

The scanner reads files directly rather than going through the indexer, so it
sees `.env` and everything else `build` never parses.

## 4. `build --redact-secrets` exists now

```bash
neuralmind build . --redact-secrets    # or NEURALMIND_REDACT_SECRETS=1
```

Scrubs detected credentials out of text on its way into the index — document
chunks and node descriptions both. Off by default, because redacting costs
recall on legitimately secret-shaped identifiers.

This is a **backstop, not a fix.** The credential is still in your working
tree, still in your git history, and still valid. Remove it and rotate it;
use the flag to keep an already-exposed value out of the index while you do.

## What the agent sees post-install

| Agent | What changes |
|-------|--------------|
| **Claude Code** | Hooks already installed: the recovery cache behind `neuralmind last` is redacted from the next Bash call onward. No re-install needed. Re-run `neuralmind install-hooks` only if you never had them. |
| **Cursor / Cline** | Via MCP: no tool-surface change. The redaction and gitignore guard apply to any `.neuralmind/` the server writes. |
| **Generic MCP client** | No new tools. `scan-for-secrets` is CLI-only by design — it reports credentials, and that output does not belong in an agent's context window. |
| **CI** | New gate available: `neuralmind scan-for-secrets .` exits `1` on a high-confidence finding. |

## Honest scope

- **Redaction is pattern-based.** It catches the vendor shapes listed above
  and high-entropy assignments. A bespoke internal token format with no
  distinctive prefix will not be detected. Do not treat a clean scan as proof
  a repo is secret-free.
- **The gitignore guard is not retroactive** — see §1.
- **`--redact-secrets` does not clean your working tree**, your git history,
  or a key that already leaked. Rotation is the only fix for an exposed
  credential.
- **Nothing here is new network behavior.** NeuralMind still makes no
  outbound calls, and these fixes are all local.

## Upgrading

```bash
pip install --upgrade neuralmind
neuralmind scan-for-secrets .      # check the working tree
git ls-files .neuralmind/          # check for previously committed state
```

Rotate anything either one turns up.
