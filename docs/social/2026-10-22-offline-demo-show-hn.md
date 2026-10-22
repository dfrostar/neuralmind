# Show HN draft — 2026-10-22: `neuralmind demo`, offline after `pip install`

**Draft, ready to post:** v4.21.0 is on PyPI (the offline demo shipped in
v4.19.0; v4.21.0 makes it run on Intel macOS and Windows ARM).

A "Show HN" post for developers, built around the lowest-friction way to try
NeuralMind. Drafted here so `tests/test_docs_claims.py` vets it before it is
posted. Hacker News readers check numbers, so every figure is from
`site/claims.json` and the misses are in the post.

## Before posting

- [x] The demo crashed on Intel macOS and Windows ARM (no turbovec wheel;
      ChromaDB is installed instead). Fixed in v4.21.0: there it now builds
      the sample with ChromaDB, downloading the model once. It still isn't
      offline there, so keep the platform caveat in the post.
- [x] Post only once v4.21.0 or later is on PyPI (it is, as of 2026-10-22).
- [ ] In a fresh virtualenv on a machine with no `~/.cache/neuralmind`, run
      `pip install neuralmind && neuralmind demo` with the network off after
      the install. It should finish without downloading the model. Paste its
      real output into the first comment, not this draft.
- [ ] Post on a weekday morning US time; reply to every question in the first
      two hours.
- [ ] Don't lead with cost savings: the task-outcome pilot found none (see
      the post).

## Title

Show HN: NeuralMind – a local code index for coding agents, with a demo that runs offline

## Post text

NeuralMind builds a local index of your codebase (a code graph plus
embeddings) and gives a coding agent the code that answers its question,
instead of the agent pasting or grepping its way through files. It works
through MCP and through Claude Code's hooks.

To try it without pointing it at your own code:

    pip install neuralmind
    neuralmind demo

It runs three questions against a small sample project bundled with the
package and prints what an agent would get for each, in tokens, next to
pasting every source file. As of this week it needs no model download: the
sample's vector index and its three questions' embeddings ship in the package,
so it ranks exactly as it would with the embedding model, on a plane or behind
a proxy that blocks model downloads. That holds on Linux, Apple Silicon macOS
and 64-bit Windows, where the default install includes the turbovec index; on
Intel macOS and Windows ARM the install uses ChromaDB instead and the demo
downloads the model once.

The numbers we can back up, with the misses:

- Public benchmark (40 pre-registered queries on open-source repos): the right
  file on 40 of 40, against 32 of 40 for ripgrep keyword search, at 31–67×
  fewer tokens.
- A larger 150-question retrieval eval: 93.3% top-five. The 10 misses are
  published.
- A pre-registered 20-task pilot running Claude Code with and without
  NeuralMind found no difference: 18 of 20 tasks solved in both arms, and a
  median per-task cost change of +0.0% (95% CI −5.2% to +8.6%). Twenty tasks
  can't rule out an effect inside that interval. The agent
  never called NeuralMind's tools; better retrieval doesn't help an agent that
  doesn't ask for it. That's what we're working on next.

NeuralMind runs on your machine. It sends no telemetry and transmits no
repository content off your machine; the agent still sends what it selects to
its model.

https://github.com/dfrostar/neuralmind · benchmarks and raw data:
https://neuralmind.uk/benchmark

## Fact check

| Claim | Source |
|---|---|
| Demo bundles the vector index and question embeddings; no model download | `docs/wiki/CLI-Reference.md#demo`, `tests/test_cli.py::TestCLIDemoOffline` |
| Only on Linux, Apple Silicon macOS and 64-bit Windows | `pyproject.toml` turbovec / chromadb platform markers |
| Elsewhere the demo builds with ChromaDB and downloads the model once | `docs/releases/RELEASE_NOTES_v4.21.0.md`, `neuralmind/cli.py::cmd_demo` |
| Ranks exactly as with the model | `scripts/build_demo_index.py --check` in `ci-benchmark.yml` compares top-5 rankings |
| 40 of 40 vs ripgrep's 32 of 40, 31–67× | `bench/public/results.json`, `site/claims.json` |
| 93.3% top-five, 10 misses | `bench/retrieval/on-v4.12/results.json`, `site/claims.json` |
| Pilot: 18 of 20 in both arms, +0.0% (95% CI −5.2% to +8.6%); agent never called the MCP tools | `bench/task_outcome/pilot/report.txt`, `site/claims.json` |
| Sends no telemetry and transmits no repository content off the machine | `docs/SECURITY-GUIDE.md`, the wording `tests/test_docs_claims.py` prescribes |
