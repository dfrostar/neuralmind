# 60-second screencast script — NeuralMind v0.7.0

Three beats. Sixty seconds total. The job of this clip is to flip
the v0.7.0 pitch from a list of five install commands into a single
visual claim: **same canvas, every install path.**

The previous release's screencast
([`SCREENCAST-v0.6.0.md`](SCREENCAST-v0.6.0.md)) introduced the live
activity feed; this one assumes the viewer already knows what the
canvas does, and only proves "it's reachable however you install
NeuralMind."

---

## Format

- **Length:** 60 seconds, hard cut.
- **Aspect:** 16:9 for LinkedIn / X / blog embed; 9:16 vertical
  re-cut for mobile-first surfaces.
- **Resolution:** 1920×1080 minimum; capture at retina/2× if
  possible — terminals look much sharper.
- **Audio:** No voice-over. Text overlays for narration.
- **Terminal theme:** Dark background, monospace font ≥ 18pt. The
  install commands have to be legible at thumbnail size.
- **Browser theme:** Dark; canvas readable in thumbnails.

## Beat 1 — pipx install + verify (0:00–0:20)

**Visual:** Full-screen terminal. No editor, no browser yet.

Type and run, with enough pause for the viewer to read each line:

```bash
pipx install neuralmind
```

Wait for the "installed package neuralmind" line. Then:

```bash
neuralmind --help
```

Hero detail: the command works from a directory with no `venv`
activated. Show the prompt (`~/scratch $ `) so it's obvious this is
a clean shell.

**Text overlay (top third):**

> One command. Global CLI. No venv to activate.

**Cut at:** the help output's last line, before the next prompt.

## Beat 2 — docker run, same package (0:20–0:40)

**Visual:** Cut to a fresh terminal pane. Type:

```bash
docker run --rm \
  -v "$PWD:/project:ro" \
  ghcr.io/dfrostar/neuralmind \
  neuralmind --help
```

(If GHCR auto-publish isn't live yet by recording time, build
locally with `docker build -t neuralmind:dev .` and substitute the
image tag — the visual claim is the same.)

The output is the **same `--help` text** as Beat 1. That's the
intentional reveal: different install path, same package.

**Text overlay (bottom third):**

> Same package. Zero Python on the host.

**Cut at:** the help output's last line.

## Beat 3 — same canvas, side by side (0:40–1:00)

**THIS IS THE MONEY SHOT.** Beats 1 and 2 prove the CLI runs;
this beat proves the *experience* is identical.

**Visual:** Split-screen. Two browser windows, both showing
`neuralmind serve` running on the same demo project.

- **Left:** `neuralmind serve .` from Beat 1's pipx install.
  URL bar shows `127.0.0.1:8765/?token=…`.
- **Right:** `docker run -p 8765:8765 ghcr.io/dfrostar/neuralmind
  neuralmind serve /project --host 0.0.0.0 --no-auth`. URL bar
  shows `127.0.0.1:8765/`. (Run on a different host port — e.g.
  `-p 8766:8765` — and show the second browser pointed there if
  you want both visible simultaneously.)

**On-screen action:**

1. In the editor (offscreen, or briefly cut to), make a one-line
   change to a file in the demo project and save.
2. Cut back to the split — **both canvases pulse on the same
   node** within ~1s. The activity feeds in the sidebars both
   light up with the same `file_activity` event.

The pulse-rings are the v0.6.0 hero. The new claim here is
*duplicated* pulse-rings: same brain, two install paths, same
visual proof.

**Text overlay (timed to the first pulse):**

> Same brain. Whichever way you install.
> NeuralMind v0.7.0 — `pip` / `pipx` / `uv` / Docker / source.

**End frame (last 3 seconds):**

Static frame. NeuralMind logo bottom-left. URL bottom-right:

> github.com/dfrostar/neuralmind

## Pitfalls / things to avoid

- **Don't show all five install commands on screen.** Two is the
  cap — pipx and docker. The README has all five; the screencast
  proves the *equivalence*, which only needs two endpoints of the
  range.
- **Don't show uv or pip in their own beats.** They look identical
  to pipx on screen (one line, one progress bar) and dilute the
  pipx-vs-docker contrast. Mention them in the text overlay only.
- **Don't show `python -c "import neuralmind"`** — it's the
  verification command from the README but it's a single boring
  line and chews 5 seconds. `neuralmind --help` is the more
  visually-impressive equivalent for the screencast.
- **Don't open the Dockerfile on screen.** Same trap as v0.6.0's
  events.jsonl — internals don't earn screen time. The
  Dockerfile's value is that it exists; viewers can read it on
  GitHub.
- **Don't post without the v0.6.0 screencast having landed first.**
  Beat 3's payoff depends on the viewer already knowing what the
  pulse-rings mean. If your audience is new to NeuralMind, either
  splice in 5s from the v0.6.0 clip or skip the v0.7.0 screencast
  and post the v0.6.0 one again with the v0.7.0 LinkedIn copy.

## Recording checklist

- [ ] Demo project pre-built (`graphify update .` and `neuralmind
      build .` already run).
- [ ] `pipx` already on the recording machine (don't burn 5
      seconds installing pipx itself; that's not the story).
- [ ] Docker image either pulled (if GHCR is live) or built
      locally and tagged `ghcr.io/dfrostar/neuralmind`.
- [ ] Two browser windows pre-positioned for the Beat 3 split.
- [ ] Editor open on a file with one obvious one-line edit
      already staged in muscle memory.
- [ ] Screen recording app set to capture at 60fps if possible
      (the pulse animation looks dramatically better at 60fps).
- [ ] Run-through twice off-camera so the docker pull/build time
      doesn't leak into the take.

## Post-production

- Hard cuts only. No fades. Each beat starts at second 0/20/40.
- Color-grade the terminal slightly warmer than default — pure
  white text on pure black tests as sterile in thumbnails.
- The first frame of beat 3 (both canvases mid-pulse) is your
  **thumbnail candidate**. Export a still and use as the LinkedIn
  / YouTube thumbnail. Two pulse-rings side-by-side is the most
  thumb-stopping single frame in the clip.

## Distribution

- LinkedIn — native video upload preferred over embed. Use the
  Draft v0.7.0–A caption from
  [`LINKEDIN-POST-DRAFT.md`](LINKEDIN-POST-DRAFT.md).
- X / Twitter — 60s fits in a single tweet. Lead with the
  two-canvases thumbnail.
- README — embed the asciinema-style version (terminal-only beats
  1 + 2) at the top of the README, above the existing
  30-second-proof block. Browser-based beat 3 doesn't asciinema
  cleanly; show it as a separate animated PNG/GIF or as the full
  60s embed on the release page.
- Blog / about page — embed the full 60s in the "What's new in
  v0.7.0" callout.
