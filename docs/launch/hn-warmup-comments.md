# HN warm-up comments

Genuine, on-topic comments for *existing* HN threads that are actually about
agent context / memory / coding-agent loops. These are **not** a vote-ring and
**not** drive-by promo: each leads with something substantive, and discloses the
NeuralMind affiliation the moment the project is named. If a comment wouldn't be
worth posting without the NeuralMind mention, don't post it.

**Rule:** mention NeuralMind only where it genuinely answers the thread's
question, and always with "(disclosure: I built it)" or equivalent. One link
max. No "check out my project" with no substance.

---

## Comment A — for a thread about coding-agent context/memory (e.g. the "Gora" thread)

```
The thing that bit us repeatedly is that the agent re-loads context it already
"understood" earlier in the session — every turn it re-reads the same files
because nothing persists between turns except the raw transcript. So the window
fills with re-derivation, not new reasoning.

Two angles that helped, independent of any specific tool:
1. Disclose context progressively. Don't paste files; give the agent a map
   first (symbols + call edges) and let it pull the bodies it actually needs.
   The recall hit from this is smaller than people expect if your retrieval is
   decent.
2. Persist associations, not just embeddings. Which files get edited together,
   which symbols get queried together — that signal is cheap to record and
   strong for "what should I look at next," and a static vector index throws it
   away every session.

(Disclosure: I went down this rabbit hole far enough that I built an open MCP
server around it — github.com/dfrostar/neuralmind — so take the framing with
that grain of salt. The reproducible benchmark is the part I'd actually defend.)
```

## Comment B — for a thread about RAG-for-code / retrieval quality (e.g. the "Zeroshot" thread)

```
One thing worth measuring that a lot of code-retrieval write-ups skip: report
cost and correctness *together*. A token-reduction number with no "did the right
file actually make it into the window" number attached is unfalsifiable.

A cheap objective oracle that avoids an LLM judge: pick the gold file as the
definition site of a named symbol, and say a method "answered" iff that file
lands in its assembled context. Verifiable with one rg command, deterministic,
nothing to rig. When I scored that way, plain ripgrep missed the right file ~29%
of the time (keyword search has no notion of meaning), while a same-encoder
vector RAG was genuinely strong on findability — which is the honest result, not
the marketing one.

(Disclosure: this is from building github.com/dfrostar/neuralmind; the harness
is in the repo if you want to tear the methodology apart, which is the point.)
```

## Comment C — for a thread about Claude Code / agent loops specifically

```
On the Claude Code loop specifically: the lifecycle hooks (SessionStart,
UserPromptSubmit, PreCompact, PostToolUse) are the underused seam. PreCompact in
particular is where you can persist a distilled memory before the window gets
summarized away, so the next compaction cycle doesn't start from zero. Most
"memory for agents" setups only write to a file the agent has to remember to
read; wiring it into the compaction lifecycle instead means the recall happens
whether or not the model thinks to ask for it.

(Disclosure: I build on these hooks in an open MCP server,
github.com/dfrostar/neuralmind — but the hook seam itself is just Claude Code's
public lifecycle API and worth using regardless of any tool.)
```

---

### Notes for posting

- Only post a comment if the thread is genuinely about this topic and the
  comment adds something a reader would value even without the disclosure line.
- Match the thread's specifics — edit the opening sentence to reference what the
  OP actually said. A generic paste reads as spam; a specific reply reads as a
  practitioner.
- Never post all three in a short window across threads. Space them; engage with
  replies.
