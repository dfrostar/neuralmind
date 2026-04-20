# Brain-Like Learning: Your Project Learns Your Patterns

NeuralMind now learns which directories and modules matter for your questions. After a few queries, it understands your codebase's structure—and remembers it. **Fully local. Fully under your control.**

---

## Why This Matters

### The Problem
You ask similar questions repeatedly:
- "How do I add an API endpoint?"
- "Where's the auth validation?"
- "How does the database layer work?"

Each time, NeuralMind searches from scratch. You get the same 50 files as context, even though only 5 are ever useful for *your* questions.

### The Solution
After asking 10 similar questions, NeuralMind learns: "When they ask about APIs, they care about routes/, middleware/, and models/. Everything else is noise."

Query 11 costs half the tokens and gives better context.

---

## What You'll See: Before & After

### First Query (No Memory Yet)
```bash
$ neuralmind query . "How do I add a new API endpoint?"
Retrieved 15 files (1,200 tokens):
  • app/routes/api.py (relevant ✓)
  • app/middleware/auth.py (relevant ✓)
  • tests/test_api.py (relevant ✓)
  • docs/architecture.md (not relevant)
  • utils/helpers.py (not relevant)
  • config/settings.py (not relevant)
  • [12 more not very relevant]
```

### 10th Query (Memory Learned Patterns)
```bash
$ neuralmind query . "How do I add a new API endpoint?"
Retrieved 5 files (600 tokens):
  • app/middleware/auth.py (learned: always appears with API questions)
  • app/routes/api.py (learned: core for API questions)
  • app/models.py (learned: correlates with route definitions)
  
"NeuralMind learned from 10 API questions: routes/ → middleware/ → models/"
```

**Result:** Same question, half the tokens, better signal-to-noise.

---

## How to Enable It

### First-Time Setup
When you run `neuralmind query .` for the first time with learning enabled, you'll see:

```
┌─────────────────────────────────────────────────────────┐
│ NeuralMind would like to learn from your queries.       │
│                                                         │
│ Your project patterns will be stored locally in         │
│ .neuralmind/memory/ and never uploaded anywhere.       │
│                                                         │
│ Enable learning? (y/n)                                 │
└─────────────────────────────────────────────────────────┘
```

- **Type `y`** → Learning enabled (opt-in stored, won't ask again)
- **Type `n`** → Learning disabled for this project
- **Not a TTY?** → Defaults to OFF (won't spam CI/scripts)

### Disable Learning (Anytime)

```bash
# Disable globally
export NEURALMIND_LEARNING=0

# Disable for this project only
export NEURALMIND_MEMORY=0

# Or delete the memory
neuralmind memory reset .
```

---

## Privacy & Data: 100% Local

### Where Your Data Lives
```
Your project:
  .neuralmind/memory/
    ├── traces.jsonl          # Your queries + what was retrieved
    └── patterns.json         # Learned patterns (when you run: neuralmind learn)

Global (cross-project patterns):
  ~/.neuralmind/memory/
    └── global_traces.jsonl   # Personal patterns across all projects
```

**Size:** ~100 KB per 100 queries. Negligible.

### What We Collect
- Your query text
- Which files/modules were retrieved
- Timestamps

**What we DON'T collect:**
- Code contents
- Your identity
- Where your project lives
- Any information sent to servers

### Reset Anytime
```bash
# Delete all learning for this project
neuralmind memory reset .

# Delete all global learning
neuralmind memory reset --global

# Start fresh after a refactor
neuralmind memory reset . --full
neuralmind learn . --dry-run
```

---

## See It In Action

### Check What's Been Learned
```bash
$ neuralmind stats --memory

Memory size: 47 traces (2.3 KB)
Scope: Project
Collection started: 2026-04-15
Last learned: (not yet, ready for v0.2.1)

Top patterns discovered:
  1. auth queries
     → [auth/, validation/, middleware/] (22 queries)
     
  2. database queries
     → [db/, cache/, models/] (15 queries)
     
  3. api queries
     → [routes/, serializers/, middleware/] (13 queries)

Ready to learn? Run: neuralmind learn . (v0.2.1+)
```

### Preview What Would Be Learned
```bash
$ neuralmind learn . --dry-run

Analyzing 47 memory traces...
Found 3 strong patterns:

1. auth (85% confidence)
   Modules: auth/, validation/, middleware/
   Queries: 22
   
2. database (78% confidence)
   Modules: db/, cache/, models/
   Queries: 15
   
3. api (72% confidence)
   Modules: routes/, serializers/, middleware/
   Queries: 13

Confidence threshold: 75%
Action: These patterns are ready to learn (when v0.2.1 ships)
```

---

## Examples by Role

### App Developer
**Your question:** "Where do I handle user authentication?"

**With learning:**
- First time: Gets auth/, validation/, middleware/, but also docs/, tests/, utils/
- After 5 auth questions: Learns which *specific* files you always use
- Query 6: Returns your exact pattern in half the tokens

### Data Scientist
**Your question:** "What features correlate with churn?"

**With learning:**
- Early exploration: Lots of broad results, lots of feature table noise
- After 10 exploratory queries: Learns which preprocessing steps led to good insights
- Query 11: Reranks preprocessing → feature tables → models

### DevOps / Multi-Service Systems
**Your question:** "How does payment flow through the system?"

**With learning:**
- First time: Returns all 10 services
- After 5 payment queries: Learns payment-service → billing-service → database-service pattern
- Query 6: Returns exact service sequence, context is focused

### Onboarding New Developers
**The setup:**
1. Senior dev explores codebase, asks good questions
2. NeuralMind learns patterns from those questions
3. New dev joins, asks similar exploratory questions
4. Gets the same good patterns the senior dev found

**Result:** Onboarding context is project-specific and proven.

---

## Troubleshooting

### "I refactored my code, but patterns are stale"
```bash
# Reset memory and let it relearn from fresh queries
neuralmind memory reset .
neuralmind query . "your first question"  # Fresh learning starts
```

### "The patterns seem wrong"
```bash
# Preview before applying
neuralmind learn . --dry-run

# If they look bad, reset and try again
neuralmind memory reset .
```

### "I don't want learning on this project"
```bash
# Disable for this project
export NEURALMIND_MEMORY=0

# Or delete the memory
neuralmind memory reset .
```

### "How much data is being stored?"
```bash
# Check memory size
neuralmind stats --memory

# See example: 47 queries = 2.3 KB (negligible)
```

---

## How It Works (Technical)

### Collection (v0.2.0)
Every time you run `neuralmind query .`:

1. Query text is recorded
2. Retrieved modules/files are recorded
3. Timestamp is added
4. Entry is appended to `traces.jsonl`

```jsonl
{"query": "auth flow", "retrieved": ["auth/", "validation/", "middleware/"], "timestamp": "2026-04-20T14:30:00Z"}
{"query": "authentication handler", "retrieved": ["auth/", "validation/", "middleware/", "tests/auth/"], "timestamp": "2026-04-20T14:35:00Z"}
...
```

### Learning (v0.2.1+)
When you run `neuralmind learn .`:

1. Reads all traces
2. Analyzes which modules appear together in similar queries
3. Computes confidence scores (how often do they co-occur?)
4. Builds a reranker: "For queries like this, prioritize these modules"
5. Future queries: semantic search results → reranker → boosted context

### Decay & Freshness (Planned)
- Memory traces have timestamps
- Old patterns gradually matter less
- After major refactors, you can reset and relearn

---

## Summary

| Feature | Status | Details |
|---------|--------|---------|
| Collection | ✅ v0.2.0 | Implicit logging, local storage |
| Visibility | ✅ v0.2.0 | `neuralmind stats --memory` |
| Preview | ✅ v0.2.0 | `neuralmind learn . --dry-run` |
| Reranking | 🔄 v0.2.1 | Coming soon, based on real patterns |
| Decay | 🔄 v0.2.2 | Memory freshness management |
| Reset | ✅ v0.2.0 | Clear anytime |
| Privacy Controls | ✅ v0.2.0 | Env vars, local-only storage |

---

## Next Steps

1. **Enable learning** — Say "yes" to the first-time prompt
2. **Use normally** — `neuralmind query .` collects patterns
3. **Check progress** — `neuralmind stats --memory`
4. **When v0.2.1 ships** — Run `neuralmind learn .` to activate reranking
5. **Enjoy** — Watch your context get smarter over time

---

## Questions?

- **Privacy:** All stored locally, never uploaded. Delete anytime.
- **Performance:** Collection adds <1% overhead. Preview before learning.
- **Troubleshooting:** See section above or check logs with `--verbose`

This feature is designed to fade into the background and just work. You focus on your code; NeuralMind learns your patterns.
