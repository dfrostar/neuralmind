# Brain-Like Learning Guide (v0.3.2+)

> How to teach your project to improve retrieval relevance through query patterns

## Overview

NeuralMind's learning system automatically improves as you use it. The more you query, the smarter it gets.

### The Learning Cycle

```
┌──────────────────────────────────────────────────────────┐
│ 1. Query Your Code                                       │
│    neuralmind query . "How does auth work?"              │
│    ↓ Events logged to .neuralmind/memory/                │
├──────────────────────────────────────────────────────────┤
│ 2. Collect Patterns                                      │
│    After 5-10 queries, run:                              │
│    neuralmind learn .                                    │
│    ↓ Analyzes which modules appear together              │
├──────────────────────────────────────────────────────────┤
│ 3. Automatic Improvement                                 │
│    Next queries automatically boost related modules      │
│    ↓ Better results in fewer tokens                      │
├──────────────────────────────────────────────────────────┤
│ 4. Continuous Learning                                   │
│    Each new query adds to the pattern                    │
│    Run neuralmind learn . weekly for updates             │
└──────────────────────────────────────────────────────────┘
```

## Step-by-Step Workflow

### Step 1: Enable Memory Logging

First-time only. When you run your first query, you'll be prompted:

```bash
$ neuralmind query . "How does authentication work?"

Enable local NeuralMind memory logging to improve retrieval over time? [y/N]: y
```

✅ Consent saved to `~/.neuralmind/memory_consent.json`

**To disable:** Set `NEURALMIND_MEMORY=0` or `NEURALMIND_LEARNING=0`

### Step 2: Use NeuralMind Naturally

Just query as usual. Events are logged automatically.

```bash
# Daily usage - these all get logged
neuralmind query . "How does authentication work?"
neuralmind query . "What are the API endpoints?"
neuralmind query . "How is data validated?"
neuralmind query . "Where's the database logic?"
neuralmind query . "What's the error handling?"
```

Each query logs:
- The question you asked
- Which modules were retrieved
- How many tokens used
- Which communities matched

### Step 3: Analyze Patterns

After collecting 5-10 queries, analyze the patterns:

```bash
$ neuralmind learn .

Analyzing 8 query events...
✓ Learned 12 cooccurrence patterns
✓ Patterns saved to .neuralmind/learned_patterns.json
✓ Next query will apply learned patterns for improved retrieval

Top cooccurrence patterns:
  community_0|community_1: 5 times (100% - auth + validation)
  community_1|community_2: 4 times (validation + middleware)
  community_0|community_2: 3 times (auth + middleware)
```

### Step 4: Automatic Improvements

On your next query, learned patterns are applied automatically:

```bash
$ neuralmind query . "How does auth work?"

## Search Results

1. **validate_user** (score: 0.85 +0.25 boost)  ← Boosted due to cooccurrence!
   Type: function
   File: auth.py

2. **authenticate** (score: 0.91)
   Type: function
   File: auth.py

3. **check_permissions** (score: 0.78 +0.18 boost)  ← Also boosted!
   Type: function
   File: middleware.py
```

**What happened:**
- System recognized "auth" question
- Looked for modules that frequently appear with auth
- Boosted validation and middleware in results
- Same token budget, better relevance ✅

### Step 5: Continuous Improvement

Run `neuralmind learn .` weekly or after major development:

```bash
# Weekly learning update
0 9 * * 1 neuralmind learn /path/to/project
```

Each run:
- Reads new query events
- Updates pattern weights
- Saves improved patterns

## Understanding Patterns

### What Gets Learned

The system tracks **module cooccurrence** — which code parts appear together in successful queries.

```json
{
  "cooccurrence": {
    "community_0|community_1": 5,
    "community_0|community_2": 3,
    "community_1|community_2": 4
  },
  "module_frequency": {
    "community_0": 8,
    "community_1": 12,
    "community_2": 7
  }
}
```

**Example:** If users ask about authentication, validation modules usually appear in L2 context (frequency: 5). The system learns this relationship.

### How Reranking Uses Patterns

When you query:

1. **L2 identifies context modules** — which communities match your question
2. **L3 searches normally** — semantic search finds candidates
3. **Reranker boosts results** — modules cooccurring with L2 context get +0.3 multiplier
4. **Final ranking** — better matches rise to top

**Boost formula:**
```
combined_score = semantic_score × (1.0 + 0.3 × cooccurrence_strength)
```

Where `cooccurrence_strength` is 0-1 (normalized to max pattern).

### Pattern Examples

#### Example 1: Authentication System

```
Queries ask about: auth, validation, permissions
System learns: These modules appear together
Effect: "How does auth work?" automatically includes validation
Token savings: -20% (fewer irrelevant results)
```

#### Example 2: API Layer

```
Queries ask about: API endpoints, routes, handlers
System learns: These modules always appear together
Effect: "What are the endpoints?" automatically includes handler details
Token savings: -15% (more complete context)
```

#### Example 3: Data Pipeline

```
Queries ask about: database, models, migrations
System learns: These concepts are linked
Effect: "How's the data stored?" includes migration history
Token savings: -25% (better context relevance)
```

## Privacy & Data

✅ **100% Local** — All learning happens on your machine
✅ **No Telemetry** — Nothing sent to servers
✅ **User Control** — One-time consent, can disable anytime
✅ **Persistent** — Patterns stay in your `.neuralmind/` directory

### File Locations

```
~/.neuralmind/
├── memory_consent.json              # Consent flag (once per user)
└── memory/
    └── query_events.jsonl           # Global event log

project/.neuralmind/
├── memory/
│   └── query_events.jsonl           # Project-specific events
└── learned_patterns.json            # Learned patterns (created by neuralmind learn)
```

### Environment Variables

```bash
# Disable memory logging
export NEURALMIND_MEMORY=0

# Disable learning
export NEURALMIND_LEARNING=0

# Use both to disable completely
export NEURALMIND_MEMORY=0 NEURALMIND_LEARNING=0
```

## Troubleshooting

### "No query events found"

**Problem:** You run `neuralmind learn .` but see "No query events found"

**Solution:**
1. Have you run at least 1 query? `neuralmind query . "test"`
2. Did you consent to memory logging? You should see prompt on first query
3. Check memory file exists: `ls -la project/.neuralmind/memory/query_events.jsonl`
4. Check NEURALMIND_MEMORY not set to 0

### "Learned 0 patterns"

**Problem:** You see "Learned 0 cooccurrence patterns"

**Solution:**
1. You may need 5+ queries for meaningful patterns
2. Your queries might be too different (no overlapping modules)
3. Try a few more queries, then run learn again

### "Patterns not being applied"

**Problem:** You see no boost scores in search results

**Solution:**
1. Run `neuralmind query . "test"` again (must be AFTER learning)
2. Check file exists: `ls -la project/.neuralmind/learned_patterns.json`
3. Check logs aren't disabled: `echo $NEURALMIND_LEARNING`
4. Try with a fresh query (not the exact same as before)

## Best Practices

### 1. Natural Querying
```bash
✅ DO: Ask questions naturally as they come up
neuralmind query . "How does user login work?"

❌ DON'T: Artificially create queries just for learning
```

### 2. Regular Learning
```bash
✅ DO: Run learn after several days/weeks of usage
neuralmind learn . # Weekly is ideal

❌ DON'T: Rely on very fresh patterns (need 5+ queries)
```

### 3. Meaningful Questions
```bash
✅ DO: Ask varied questions about your codebase
- "How does auth work?"
- "What are the API routes?"
- "How is data validated?"

❌ DON'T: Ask the exact same question repeatedly
```

### 4. Monitoring Patterns
```bash
✅ DO: Check top patterns to understand your code structure
neuralmind learn . | grep "cooccurrence"

❌ DON'T: Manually edit learned_patterns.json (it's auto-generated)
```

## Performance Impact

Learning has **zero overhead**:

- **Pattern loading:** ~1ms (lazy loaded, happens once)
- **Reranking:** ~5ms (only sort, no compute)
- **Memory:** ~10KB for patterns file
- **Storage:** ~50KB for event logs (100 queries)

**Total cost:** Negligible compared to network latency of semantic search.

## v0.4 Synapse Layer

v0.4.0 adds a second learning system that runs **in parallel with** the
v0.3.2 cooccurrence reranker described above. They are complementary —
read this section as "what v0.4 adds on top".

### How v0.3.2 reranking and v0.4 synapses differ

| Aspect | v0.3.2 reranker | v0.4 synapse layer |
|--------|-----------------|---------------------|
| Data structure | Cooccurrence counts in JSON (`.neuralmind/learned_patterns.json`) | Weighted graph in SQLite (`.neuralmind/synapses.db`) |
| Update timing | Batch — runs `neuralmind learn .` after collecting events | Continuous — updates on every query, tool call, file edit |
| What it influences | Re-orders L3 search hits | Adds a new retrieval path (spreading activation) and surfaces associations to Claude Code's auto-memory |
| Memory model | Logged event history | Hebbian + decay + LTP (long-term potentiation) |
| Forgets stale patterns? | No (only what you analyze) | Yes (multiplicative decay; LTP floor protects frequent associations) |

In short: the **reranker** improves the ordering of vector-search hits
based on cooccurrence patterns from the past. The **synapse layer** is
an independent associative memory that can recall related code even when
vector search wouldn't have found it — because the relationship isn't
textual or graph-structural, it's *behavioral*, learned from
co-activation.

### How synapse learning happens

Five activation paths, all of which strengthen pairwise edges between
co-active nodes (Hebbian: "nodes that fire together wire together"):

1. **Every `mind.query()`** — top search hits + loaded communities reinforce.
2. **`PostToolUse` hook** — when the agent reads/runs/searches code together.
3. **`UserPromptSubmit` hook** — current prompt's neighbors get an activation pulse.
4. **`SessionStart` hook** — runs decay so weights age between sessions, then exports memory.
5. **`neuralmind watch` daemon** — debounces file edits into co-activation batches; co-edited files wire together.

### Quick start

```bash
# One-time: install the lifecycle hooks (idempotent — safe to re-run)
neuralmind install-hooks .

# Optional: always-on learning from file edits
neuralmind watch &

# That's it — the synapse store grows continuously.

# Inspect what was learned
cat .neuralmind/SYNAPSE_MEMORY.md
```

### Surface in Claude Code

Each `SessionStart` re-exports the synapse memory as markdown to:

- `<project>/.neuralmind/SYNAPSE_MEMORY.md` — import in `CLAUDE.md`
  via `@.neuralmind/SYNAPSE_MEMORY.md` so it's part of every session.
- `~/.claude/projects/<slug>/memory/synapse-activations.md` — Claude
  Code's auto-memory directory (when present); the model picks it up
  natively without anyone calling an MCP tool.

### Privacy

Local-only, project-scoped, same as the v0.3.x memory layer. No
external services. Disable with:

- `NEURALMIND_SYNAPSE_INJECT=0` — skip prompt-time recall injection
- `NEURALMIND_SYNAPSE_EXPORT=0` — skip the auto-memory export
- `NeuralMind(..., enable_synapses=False)` — disable the layer entirely
- `mind.synapses.reset()` — wipe the learned graph any time

### Read more

- [v0.4.0 Release Notes](../blob/main/RELEASE_NOTES_v0.4.0.md) — full feature walkthrough
- [Architecture: Synapse Layer (v0.4)](Architecture#synapse-layer-v04) — design and activation channels

## What's Coming (after v0.4.0)

- **Synapse import/export** — let teams share a learned brain.
- **Quality benchmark** — measure retrieval gain with vs without synapses.
- **Auto-watcher launch from `SessionStart`** — no manual `watch` invocation needed.
- **Feedback signals** — explicit ratings improve pattern accuracy.

## See Also

- [CLI Reference](CLI-Reference) — All commands
- [Brain-Like Learning](../brain_like_learning.md) — v0.3.x design rationale
- [Architecture](Architecture#synapse-layer-v04) — v0.4 synapse layer architecture
- [Troubleshooting](Troubleshooting) — Common issues
