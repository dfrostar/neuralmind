#!/usr/bin/env bash
# setup-discussions.sh — bootstrap NeuralMind's GitHub Discussions.
#
# What it does:
#   - Enables the Discussions feature on the repo (idempotent)
#   - Discovers category IDs (Announcements, Q&A, Ideas)
#   - Creates 3 pinned starter posts:
#       1. "Welcome to NeuralMind — start here"          (Announcements)
#       2. "📖 Before you ask…"                          (Q&A)
#       3. "💡 How to propose a feature…"                (Ideas)
#   - Pins each one
#
# What it CANNOT do (GitHub's API doesn't expose these — UI only):
#   - Set category descriptions
#   - Set discussion templates
#
#   After running this script, finish setup at:
#     https://github.com/dfrostar/neuralmind/discussions/categories
#
# Idempotency: safe to re-run. Posts with matching titles are skipped.
#
# Prereqs:
#   - gh CLI logged in: https://cli.github.com/  (`gh auth login`)
#   - jq:  `brew install jq` / `apt-get install jq` / equivalent
#
# Usage:
#   chmod +x scripts/setup-discussions.sh
#   ./scripts/setup-discussions.sh

set -euo pipefail

OWNER="dfrostar"
REPO="neuralmind"

# ---------- sanity ----------
command -v gh >/dev/null || {
    echo "ERROR: gh CLI not installed — see https://cli.github.com/"
    exit 1
}
command -v jq >/dev/null || {
    echo "ERROR: jq not installed — brew install jq / apt-get install jq"
    exit 1
}
gh auth status >/dev/null 2>&1 || {
    echo "ERROR: gh not authed — run 'gh auth login'"
    exit 1
}
echo "✓ gh + jq available, authenticated"

# ---------- enable discussions ----------
echo "Enabling Discussions on $OWNER/$REPO…"
gh api "repos/$OWNER/$REPO" --method PATCH -F has_discussions=true >/dev/null
echo "✓ Discussions enabled (or already was)"

# ---------- discover IDs ----------
echo "Discovering category and existing-discussion IDs…"
QUERY='query($o:String!, $r:String!) {
  repository(owner:$o, name:$r) {
    id
    discussionCategories(first:25) { nodes { id name slug } }
    discussions(first:50)          { nodes { id title } }
  }
}'

RESP=$(gh api graphql -f query="$QUERY" -F o="$OWNER" -F r="$REPO")
REPO_ID=$(echo "$RESP" | jq -r '.data.repository.id')
ANNOUNCE_ID=$(echo "$RESP" | jq -r '.data.repository.discussionCategories.nodes[] | select(.slug=="announcements") | .id')
QA_ID=$(echo "$RESP" | jq -r '.data.repository.discussionCategories.nodes[] | select(.slug=="q-a") | .id')
IDEAS_ID=$(echo "$RESP" | jq -r '.data.repository.discussionCategories.nodes[] | select(.slug=="ideas") | .id')

for label in REPO_ID ANNOUNCE_ID QA_ID IDEAS_ID; do
    val="${!label}"
    if [ -z "$val" ] || [ "$val" = "null" ]; then
        echo "ERROR: couldn't find $label — categories may not be set up yet."
        echo "Visit https://github.com/$OWNER/$REPO/discussions once to provision the default categories, then re-run."
        exit 1
    fi
done
echo "✓ Found repo + 3 category IDs"

# ---------- helpers ----------
title_exists() {
    echo "$RESP" | jq -e --arg t "$1" '.data.repository.discussions.nodes[] | select(.title==$t)' >/dev/null
}

create_and_pin() {
    local cat_id="$1" title="$2" body="$3"
    if title_exists "$title"; then
        echo "⊝ Skipping '$title' — already exists"
        return
    fi
    echo "Creating '$title'…"
    CREATE='mutation($r:ID!, $c:ID!, $t:String!, $b:String!) {
      createDiscussion(input:{repositoryId:$r, categoryId:$c, title:$t, body:$b}) {
        discussion { id url }
      }
    }'
    CREATED=$(gh api graphql -f query="$CREATE" -F r="$REPO_ID" -F c="$cat_id" -F t="$title" -F b="$body")
    DISC_ID=$(echo "$CREATED" | jq -r '.data.createDiscussion.discussion.id')
    DISC_URL=$(echo "$CREATED" | jq -r '.data.createDiscussion.discussion.url')
    echo "  → $DISC_URL"

    PIN='mutation($id:ID!) {
      pinDiscussion(input:{discussionId:$id}) {
        pinnedDiscussion { id }
      }
    }'
    gh api graphql -f query="$PIN" -F id="$DISC_ID" >/dev/null
    echo "  ✓ Pinned"
}

# ---------- post 1: welcome (Announcements) ----------
read -r -d '' WELCOME_BODY <<'EOF' || true
👋 Welcome. NeuralMind is **persistent memory for AI coding agents** — your agent learns your codebase the way a senior engineer would, and the memory persists across sessions without anyone asking it to remember.

## What's shipping

**v0.11.0 (latest)** — *Directional Synapses.* The brain layer now learns *what comes next*, not just *what goes together*. Your agent can predict the file you'll likely open after editing a given one. [Release notes](https://github.com/dfrostar/neuralmind/blob/main/RELEASE_NOTES_v0.11.0.md)

Previous releases:
- **v0.10** — Agent Ergonomics ([notes](https://github.com/dfrostar/neuralmind/blob/main/RELEASE_NOTES_v0.10.0.md))
- **v0.9** — Enterprise-Ready ([notes](https://github.com/dfrostar/neuralmind/blob/main/RELEASE_NOTES_v0.9.0.md))
- **v0.4** — Brain-like Synapse Layer (origin of the memory model)

## Where to go from here

- **First-time visitor?** → Read the [README](https://github.com/dfrostar/neuralmind#-what-changes-when-an-agent-has-memory)
- **30-second test on your code** → `pip install neuralmind && bash scripts/demo.sh`
- **Want to ask something?** → Q&A category
- **Want to suggest something?** → Ideas category
- **Found a bug?** → [Issues](https://github.com/dfrostar/neuralmind/issues/new)

## What's next on the roadmap

- Surfacing transition signals deeper into context selection (matrix powers, k-hop forecasts)
- Hidden Markov model regime detection over edit streams
- Multi-repo synapse store (cross-repo associations for monorepos and microservices)

This thread will get updated on every release. Subscribe (top right of this discussion) to get notified.
EOF

# ---------- post 2: Q&A starter ----------
read -r -d '' QA_BODY <<'EOF' || true
A self-FAQ to triage your question before you post a new one. If your question is here, the answer link is here. If not, **please post a new Q&A thread**.

## Triage — which category fits?

| You want to… | Use |
|---|---|
| Ask "how do I do X" | This category (Q&A) |
| Report a bug or unexpected behavior | [Issues](https://github.com/dfrostar/neuralmind/issues/new) |
| Suggest a feature or "wouldn't it be cool if…" | Ideas category |
| Show how you use NeuralMind | "Show and tell" category |
| See what's shipping next | Announcements category |

## Common pre-install questions

### How is NeuralMind different from Cursor / Copilot / Sourcegraph?

Cursor is an editor with built-in AI, Copilot is inline completions, Sourcegraph is code search. NeuralMind is none of those — it's a **memory layer that works alongside** any of them via MCP. See [docs/comparisons/](https://github.com/dfrostar/neuralmind/tree/main/docs/comparisons) for detailed head-to-heads.

### Does my code leave my machine?

No. Embeddings are local via ChromaDB; synapses live in a local SQLite file at `<project>/.neuralmind/synapses.db`. No telemetry, no cloud upload. See the [compliance summary](https://github.com/dfrostar/neuralmind/blob/main/docs/COMPLIANCE-SUMMARY.md).

### What does the agent actually see post-install?

Three things appear automatically:

1. `<project>/.neuralmind/SYNAPSE_MEMORY.md` is written into Claude Code's auto-memory dir → agent boots with your codebase's associations and transitions in context.
2. PostToolUse hooks compress Bash/Read/Grep output before the agent reads it.
3. MCP tools (`neuralmind_query`, `neuralmind_next_likely`, etc.) become available.

### How long until the memory becomes useful?

The undirected synapse layer learns from the first session — edges form after ~10 file co-edits. The directional transitions (v0.11) need longer — typically 3-5 sessions before predictions converge. Running `neuralmind watch` as a service shortens this from weeks to days.

### What if I have a multi-repo / monorepo / microservices setup?

NeuralMind runs per-repo. Multi-repo synapses are on the roadmap, not shipped.

### Will this work with my model — Gemini / GPT-4 / local Llama?

The MCP server is model-agnostic. For non-MCP chats: `neuralmind wakeup . | pbcopy` pipes context into any chat window. Only the PostToolUse compression hooks are Claude-Code-specific.

### How do I measure ROI?

`neuralmind benchmark . --json` produces per-query token reduction, hit-rate, dollar-saved-per-month estimates. CI auto-comments the same numbers on every PR. See the [interactive dashboard](https://dfrostar.github.io/neuralmind/benchmarks/) for community submissions.

## If your question isn't here

Post it as a new Q&A thread. The template will pre-fill — describe the goal (not just the failing command), what you ran, what you saw, what you expected. Good question = good answer in <24h.
EOF

# ---------- post 3: Ideas starter ----------
read -r -d '' IDEAS_BODY <<'EOF' || true
A pre-flight for the Ideas category. Read before posting so your idea lands somewhere productive.

## The three-bucket test

Before opening an Ideas thread, ask which bucket your proposal fits:

| Type | Goes to |
|---|---|
| "Something is broken / doesn't work as documented" | [Issues](https://github.com/dfrostar/neuralmind/issues/new) — not Ideas |
| "I want to do X, what's the recommended approach?" | Q&A — not Ideas |
| "What if NeuralMind could do X" / "Have you considered Y" | **Ideas (this category)** |
| "Here's how I use it / a cool integration I built" | Show and tell — not Ideas |

If you're not sure, post anyway and we'll redirect.

## What's already on the roadmap

So you don't duplicate. Listed in roughly the order I'd ship them.

### Near-term

- **Reranker deprecation** — `learned_patterns` is runtime-superseded by synapses; cleanup tracked in [#143](https://github.com/dfrostar/neuralmind/issues/143).
- **Multi-step prediction** — raise the transition matrix to the k-th power for k-hop forecasts.
- **Surface top transitions in `wakeup`** — currently transitions only land in `SYNAPSE_MEMORY.md`.

### Medium-term

- **Self-improvement engine** — auto-tunes `l2_recall_k` + transition thresholds. Design tracked in [#156](https://github.com/dfrostar/neuralmind/issues/156).
- **HMM regime detection** — discover "modes" (debugging / feature-add / refactor) from edit streams.
- **Multi-repo synapse store** — cross-repo associations for monorepos and microservices fleets.
- **Team brain (private SaaS, separate repo)** — shared synapse store across an organization.

### Explicitly out of scope

- **Cloud-hosted core** — local-first is the moat for compliance-sensitive users.
- **Built-in inline completion** — Cursor and Copilot do this well; we layer on top.
- **Telemetry / phone-home**, even opt-in — the offline guarantee is more valuable than usage data.
- **Replacing tree-sitter / graphify for graph extraction** — we compose on top of those.

## How to write a good Ideas thread

The template auto-fills the right structure. Examples of good titles:

- ✅ "Surface transition predictions in `neuralmind wakeup` output"
- ✅ "VS Code extension that shows synapse weights on hover"
- ❌ "Make it better" (too vague)
- ❌ "Add Python 2.7 support" (out of scope; would need a strong reason)

## How decisions get made

I read every Ideas thread. Active discussion (3+ thoughtful comments) earns a place on the roadmap. Stale ideas with zero engagement get a "Not planned" comment after 60 days. You can always re-open.
EOF

# ---------- create + pin ----------
create_and_pin "$ANNOUNCE_ID" "Welcome to NeuralMind — start here" "$WELCOME_BODY"
create_and_pin "$QA_ID"       "📖 Before you ask — common questions, where to find answers" "$QA_BODY"
create_and_pin "$IDEAS_ID"    "💡 How to propose a feature, what's on the roadmap, what's out of scope" "$IDEAS_BODY"

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  All discussions posted + pinned."
echo "  https://github.com/$OWNER/$REPO/discussions"
echo ""
echo "  Still to do in the UI (~6 min):"
echo "    1. Category descriptions (6 categories)"
echo "    2. Discussion templates (4 categories — Announcements / Q&A / Ideas / Show-and-tell)"
echo "  Edit page: https://github.com/$OWNER/$REPO/discussions/categories"
echo "════════════════════════════════════════════════════════════"
