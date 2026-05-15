# 60-second screencast script — NeuralMind v0.6.0

Three beats. Sixty seconds total. Recorded on the maintainer's
machine against a real codebase (the bundled demo's pulse rings
are sparse — see ROADMAP.md for the recording runbook).

The job of this clip is to flip the pitch from "code RAG" to
"associative memory you can watch learn." The first two beats
re-state the existing claim. The third beat is the new claim.

---

## Format

- **Length:** 60 seconds, hard cut.
- **Aspect:** 16:9 for LinkedIn / X / blog embed; 9:16 vertical
  re-cut for mobile-first surfaces.
- **Resolution:** 1920×1080 minimum; capture at retina/2× if
  possible — terminals look much sharper.
- **Audio:** No voice-over. Soft ambient or none. Text overlays
  for narration so the clip plays muted on autoplay surfaces.
- **Terminal theme:** Dark background, monospace font ≥ 18pt. The
  numbers have to be legible at thumbnail size.
- **Browser theme:** Dark; canvas readable in thumbnails.

## Beat 1 — The number (0:00–0:20)

**Visual:** Full-screen terminal. Type and run:

```bash
bash scripts/demo.sh
```

The demo script's output scrolls. The hero line in the output is
the average-reduction summary block — make sure it lands in the
last 5 seconds of this beat.

```
Q: How does authentication work in this codebase?
   naive = 4,736 tok   neuralmind =  829 tok   reduction =   5.7×
...
Average reduction:   5.5×  across 3 queries
Wall time:           0.85s
```

**Text overlay (bottom third):**

> 30-second proof on a fresh clone.
> Real repos consistently hit 40–70×.

**Cut at:** the "Wall time" line, before the next prompt.

## Beat 2 — The graph (0:20–0:40)

**Visual:** Cut to a browser. URL bar shows `127.0.0.1:8765`.
Canvas already rendered — force-directed graph of the codebase,
nodes colored by community, structural edges visible.

**On-screen actions:**

- Mouse over a node — detail panel pops in.
- Click the semantic search field. Type `auth`. The matching
  node focuses; its synaptic neighbors highlight.
- Click an edge. Tooltip appears showing relationship type + weight.

**Text overlay:**

> `neuralmind serve` — Obsidian-style graph view.
> Backlinks, synapse overlay, semantic quick-switcher.

**Cut at:** mouse moving toward the terminal (visual transition
to beat 3).

## Beat 3 — The pulse (0:40–1:00)

**THIS IS THE MONEY SHOT.** Everything in beats 1 and 2 is
context for this beat.

**Visual:** Split-screen if your recording app supports it, else
quick cuts back and forth.

- **Left half / cut A:** Editor (VS Code or similar) showing
  a file in the demo project. Visible cursor position.
- **Right half / cut B:** The graph view, canvas centered on
  the file's corresponding node.

**On-screen actions:**

1. In the editor, make a one-line change (add a comment, change
   a string — anything that triggers a save).
2. Save the file (Cmd-S / Ctrl-S).
3. Cut to the graph view — within ~1s, the corresponding node
   **pulses** with an animated radial ring. The sidebar feed shows
   a fresh `file_activity` event.
4. (If achievable in the take) Run `neuralmind query .
   "auth"` in a third terminal — a second wave of pulses fires on
   the canvas as the synapse store reinforces the co-activated
   nodes.

**Text overlay (timed to the first pulse):**

> Edit a file. The brain pulses.
> v0.6.0 — see the synapses learn, live.

**End frame (last 3 seconds):**

Static frame. NeuralMind logo bottom-left. URL bottom-right:

> github.com/dfrostar/neuralmind

## Pitfalls / things to avoid

- **Don't show the wakeup output in full.** It's text-heavy and
  doesn't read at 5x speed. The terminal in beat 1 should be the
  demo summary, not raw context.
- **Don't include voice-over.** LinkedIn autoplays muted; X
  autoplays muted. A voice-over that's only audible if the viewer
  unmutes loses 80%+ of the impact. Text overlays do the job.
- **Don't slow-mo the pulse.** It looks gimmicky and people
  assume it's a render effect. Real-time playback makes it look
  alive; slowed it looks fake.
- **Don't show the JSONL bridge file.** The `events.jsonl` is
  the boring side channel — opening it in a text editor is the
  *opposite* of the punchy visual we want. The bridge is in the
  release notes and the wiki; it doesn't earn screen time.
- **Don't try to fit all eight features.** Pin glyph, depth
  slider, replay overlay, edge tooltips — none of them are the
  hero. The hero is the pulse. If you have 90 seconds instead of
  60, add one more action in beat 2 (depth slider drag); past
  that, cut.

## Recording checklist

- [ ] Demo project pre-built (`graphify update .` and
      `neuralmind build .` already run, otherwise beat 1's
      timing breaks).
- [ ] `neuralmind serve` running before the recording starts.
- [ ] Browser window pre-positioned and pre-zoomed.
- [ ] Editor open on a file with one obvious one-line edit
      already staged in muscle memory.
- [ ] Screen recording app set to capture at 60fps if possible
      (the pulse animation looks dramatically better at 60fps).
- [ ] Run-through twice off-camera to get terminal timings
      consistent.

## Post-production

- Hard cuts only. No fades. Each beat starts at second 0/20/40.
- Color-grade the terminal slightly warmer than default — pure
  white text on pure black tests as sterile in thumbnails.
- The first frame of beat 3 (the pulse) is your **thumbnail
  candidate**. Export a still from the moment a pulse is at full
  radius for use as the YouTube/LinkedIn thumbnail.

## Distribution

- LinkedIn — native video upload preferred over embed; LinkedIn
  algorithmically favors native. Use the LinkedIn draft from
  [`LINKEDIN-POST-DRAFT.md`](LINKEDIN-POST-DRAFT.md) as the
  caption.
- X / Twitter — 60s fits in a single tweet. Lead the tweet with
  the still-frame thumbnail.
- README — embed the asciinema-style version (terminal-only
  beats 1 + 3) at the top of the README, above the existing
  30-second-proof block. Browser-based beat 2 doesn't asciinema
  cleanly; show it as a separate animated PNG/GIF.
- Blog / about page — embed the full 60s in the "What's new in
  v0.6.0" callout.

## TODO / not yet recorded

The clip itself has not been recorded as of the v0.6.0 docs PR.
This file is the script; the recording is a maintainer-run step
(can't run in CI because of the chromadb model download — same
constraint as the existing demo recording in
[`RECORDING-DEMO.md`](RECORDING-DEMO.md)).

Once recorded, drop the file in `docs/assets/v0.6.0-pulse.mp4`
(and the GIF version at `docs/assets/v0.6.0-pulse.gif`) and
update the embeds in `README.md`, `docs/index.html`, and
`docs/about.html`. Those embed points are already prepared with
TODO markers — see the placeholders in the v0.6.0 callout blocks.
