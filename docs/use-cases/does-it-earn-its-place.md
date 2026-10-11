# Does NeuralMind earn its place on your repo?

**Best for:** anyone who installed NeuralMind a while ago and now has to say
whether it's helping, including the agent that installed it. Also teams being
asked to keep paying for it.

**Primary goal:** an answer you could defend to a skeptical reviewer, built
from your own past incidents and a read-only A/B of the learned layer
(v4.13.0+).

The easy way to judge a tool you chose yourself is to run a few queries, see the
right symbols come back, and call it a win. A NeuralMind user did exactly that,
then had a second agent review the claims adversarially. The verdict:
the retrieval demos proved the *mechanism*, not the *outcome*. Token ratios
were measured against pasting whole files, the easiest baseline there is. The
"learns over time" claim rested on a store that had recorded 0 transitions in
two months. And the agent grading the tool was the one that had installed it.

All fair. This walkthrough is the cheapest test that answers them.

---

## 1. Turn past incidents into gold questions

You already know the answers to your last few incidents: the OOM, the NaN
loss, the worker that kept getting killed. Each one is a question with a known
gold file. Write them down in `.neuralmind.eval.yaml`:

```yaml
- q: worker gets killed under load with exit code 137
  gold: [worker/limits.py]
- q: eval loss is NaN while train loss looks fine
  gold: [train/data_split.py]
- q: out of memory computing the loss with a large vocabulary
  gold: [train/losses.py]
```

Two rules keep this honest:

- **Phrase the symptom, not the fix.** You're writing these after you know
  the answer, so it's easy to slip the answer's vocabulary into the question
  ("chunked cross-entropy OOM"). Write what you saw *before* you knew: the
  error, the behaviour, the wrong number.
- **Write the next one before you fix it.** When the next incident starts,
  add its question with the gold file left as your best guess, and commit it.
  Correct the gold file once it's fixed. A question written before the answer
  is known is the only kind that can't leak it.

Ten questions is a start, not a sample. Keep adding.

## 2. Score it

```bash
neuralmind eval .
```

```
NeuralMind eval — myrepo (10 questions, read-only)
  hit@1 40% · hit@5 70% · MRR 0.52
  avg context 1,240 tokens · 5.8× vs gold files · 940.2× vs all indexed code (1,165,812 tokens, measured)
```

*(Illustrative numbers.)* hit@5 is the fraction of incidents where the file
that fixed it was in the top five the agent would have been given. That's the
outcome-adjacent number: if it's low on your own incidents, a big token ratio
doesn't matter.

Compare it with what you'd have done without NeuralMind. For each question,
run the grep you would actually have typed and see whether the gold file is in
the first five files it lists. If grep finds them just as often, keep grep.

## 3. A/B the learned layer

The synapse layer is the part that's supposed to improve with use. Measure it
instead of assuming it:

```bash
neuralmind eval . --synapse-ab
```

```
  learned recall off: hit@1 30% · hit@5 70% · MRR 0.46
  learned recall moved 2 question(s) up, 0 down, 8 unchanged · hit@5 0 won / 0 lost (exact McNemar p = 1.00)
  learned layer read: 3,612 edges (41 LTP), 0 transitions
```

*(Illustrative.)* Both runs use the same questions and the same index, and
both are read-only. The only difference is that the second run switches
learned recall off (`NEURALMIND_SYNAPSE_INJECT=0`). How to read it:

- **No difference and an empty layer** is the expected result early on, not a
  failure. The layer learns only what it's shown.
- **0 transitions** means nothing has recorded the order you work through
  files in. Transitions come from the Claude Code hooks
  (`neuralmind install-hooks`), the Hermes plugin (reads and edits, v4.13.0+),
  or `neuralmind watch .`. Queries alone never add them. `neuralmind stats .`
  shows the week's growth.
- **A p-value near 1** on ten questions says nothing either way. Two questions
  moved is a direction to watch, not a result.

## 4. Watch whether it compounds

Every `--synapse-ab` run is stored with the size of the layer it read. After a
few weeks:

```bash
neuralmind eval . --report
```

```
Learned recall on vs off (`--synapse-ab` runs):

| Date       | Commit  | Edges | Transitions | hit@5 off → on | MRR off → on | Up / down | p (hit@5) |
|------------|---------|------:|------------:|---------------:|-------------:|----------:|----------:|
| 2026-10-12 | a1b2c3d | 3,612 |           0 |      70% → 70% |  0.46 → 0.52 |     2 / 0 |      1.00 |
| 2026-11-09 | e4f5a6b | 5,980 |         214 |      70% → 80% |  0.48 → 0.61 |     4 / 1 |      0.50 |
```

*(Illustrative.)* "Compounding" is a claim about this table: the on-minus-off
gap should grow as edges and transitions grow. If the layer grows and the gap
doesn't, the learning isn't paying for itself on your repo, and you can say so
with numbers. Either way, you'll have the evidence a reviewer would ask for.

## 5. Before trusting any answer, check the index is current

A stale index answers just as confidently as a fresh one. Two guards:

```bash
neuralmind init-hook .     # rebuild after commits (and pulls, merges, branch switches, v4.13.0+)
neuralmind health .        # exit 1 when the index is behind the files
```

Run `health` before the eval too: scoring a stale index measures the index,
not NeuralMind.

---

## What this doesn't tell you

Even a good hit@5 on your incidents is still retrieval: the right file was in
the window. It doesn't measure whether the agent then fixed the bug faster, or
whether a small window left out a caveat a whole file would have shown. A
proper outcome test solves real tasks with and without NeuralMind and compares
time and errors. Nobody has published one for NeuralMind yet, including us.

## The potential use case: a running incident log that grades its own tools

Make "add the eval question" a step in your incident template, and run
`neuralmind eval . --synapse-ab` in a weekly job. Over a quarter you get a
pre-registered record of how often the retrieval layer pointed at the fix
before anyone knew what it was. That is evidence for or against keeping any
retrieval tool, not only this one.

Related: [Measure retrieval on your own repo](./measure-retrieval-on-your-repo.md) ·
[A/B-test a ranking change](./ab-test-a-ranking-change.md) ·
[Recover from a stale code graph](./recover-from-a-stale-graph.md) ·
[The honest public benchmark](../benchmarks/public.md) ·
[Learning Guide: what trains which part](../wiki/Learning-Guide.md) ·
[Release notes v4.13.0](../releases/RELEASE_NOTES_v4.13.0.md)
