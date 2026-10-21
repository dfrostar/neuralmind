# Hermes plugin debut on the Nous Research Discord — 2026-10-21

The Discord version of the [Reddit debut](./2026-10-15-hermes-reddit-debut.md)
for the NeuralMind **Hermes-Agent plugin**. It says the same things and uses the
same figures. The difference is the format: one message under Discord's
2,000-character limit, written for people who already use Hermes. It's drafted
in this repo so `tests/test_docs_claims.py` checks its claims.

## Before posting

- [ ] **Pick the channel by the server's rules, not by habit.** The August
      venue note names `#agent` as where Hermes discussion happens. Read the
      server's rules and pinned messages first. If there's a showcase or
      projects channel, post there instead, and don't cross-post the same
      message to several channels.
- [ ] **Check the message fits.** The body below is 1,921 characters, under 2,000
      (the limit without Nitro). Paste it as is: Discord renders the bold,
      bullets and code block.
- [ ] **Attach the demo** if you've recorded it (see the Reddit doc's "Demo to
      record"). A screenshot of the recall block does more on Discord than the
      text does.
- [ ] Same as Reddit: **don't mention the Hermes MCP catalog entry**
      (NousResearch/hermes-agent#97207) unless you've checked its state that
      day, and re-run the benchmark if the numbers might have moved.
- [ ] **Answer in a thread.** Open a thread on your own message for questions,
      so the channel doesn't fill up. The Reddit doc's "Replies to prepare"
      table works here too.

---

## Message (1,921 characters; the limit is 2,000)

**NeuralMind plugin for Hermes: codebase memory on every turn, no tool call**

Hi all, I build NeuralMind (MIT-licensed core, runs locally) and just shipped a Hermes plugin for it. I'd like feedback from people using Hermes on real repos.

Hermes could already use NeuralMind over MCP, but only when the model chose to call it. The plugin hooks `pre_llm_call` and `post_tool_call` instead:
- **Every turn:** appends the files matching your message (with symbols and line numbers), the files linked to them, and recorded decisions from git trailers. It goes on the user message, so the prompt cache isn't invalidated. If nothing matches, nothing is added.
- **First turn of a session:** a short recap of your last session in that repo.
- **As you work:** successful `write_file`/`patch` calls and `read_file` calls inside the project are recorded, so files you work on together get linked.

```
pip install -U neuralmind
neuralmind build /path/to/repo
neuralmind install-hermes-plugin
```
Or `hermes plugins install dfrostar/neuralmind#neuralmind/hermes_plugin --enable`. Tested with Hermes 0.21.5 and later. In Desktop or ACP sessions, pin a project or set `NEURALMIND_PROJECT`.

**Numbers, misses included:** the right file was in the context for 40 of 40 pre-registered queries across requests, click, flask and rich, at 51–242x fewer tokens than pasting whole files. That's a small sample: a 150-question eval misses 10. A bare vector lookup costs fewer tokens and ranks the right file higher on 2 of the 4 repos.

The index is local and there's no telemetry. The first build downloads the embedding model (SHA256-checked) unless you pre-seed it.

Not recorded yet: edits made through `terminal`, and subagent or cron turns.

Repo: <https://github.com/dfrostar/neuralmind>
Walkthrough: <https://docs.neuralmind.uk/use-cases/hermes-agent.html>

Does the per-turn block help, or is it noise? I can tune when it shows up.

---

## Notes on the format

- The links are wrapped in `<…>` so Discord doesn't unfurl two embeds under
  the message. Drop the brackets on the repo link if you want its card.
- Without a heading, the bold first line works as the title.
- Pinned users: if someone installed with a path before, a re-run without one
  keeps the pin. Point them to `neuralmind install-hermes-plugin --unpin` in
  the thread rather than lengthening the message.

## Claim sources

Every claim above also appears in the Reddit post, which cites its sources in
its "Claim sources" table. Additions specific to this version:

| Claim | Source |
|---|---|
| Tested with Hermes 0.21.5 and later | `neuralmind/hermes_plugin/plugin.yaml` (`requires_hermes: ">=0.21.5"`) |
| `read_file` recorded only inside the project | `docs/use-cases/hermes-agent.md` §4 |
| MIT-licensed core | `LICENSE` (excludes `neuralmind/tier2/`) |
