# Review a client's codebase you've never seen

> Goal: a consultancy engineer lands on a client repository on day one, with a
> deadline and a coding agent, and leaves with a review the client can act on
> and evidence the client's own security review will accept. Everything below
> runs on the engineer's machine; by default NeuralMind sends no telemetry and
> transmits no repository content off it.

**Who this is for:** a 2–15 person software consultancy whose engineers
rotate between client codebases, several engagements a year. The reviewer is
usually not the author. Some clients are regulated.

**Existing use cases it draws together:** [review before
push](review-before-push.md), [blast radius before a
rename](blast-radius-before-a-rename.md), [decision
provenance](decision-provenance.md), [verify a release](verify-a-release.md)
and the [CMMC CUI enclave](cmmc-cui-enclave.md) walkthrough.

## Day one: orient on a stranger's repository

```bash
pip install neuralmind
cd client-repo
neuralmind scan-for-secrets . --strict   # credentials, before anything is indexed
neuralmind build . --redact-secrets      # the code graph, the index, structural seeds
neuralmind doctor .           # what's wired, what isn't, before you rely on it
neuralmind install-hooks .    # Claude Code: related files at each prompt
```

The hook is how NeuralMind reaches the agent on an unfamiliar repository. In
the task-outcome studies the agent never chose to call the MCP tools; the
prompt-time block was the channel that worked, so install the hooks, not only
the server ([the studies](../benchmarks/public.md)).

Then ask the questions you'd otherwise grep for:

```bash
neuralmind search . "where are inbound webhooks verified"
neuralmind query . "how does a request get from the router to the database"
neuralmind skeleton src/billing/invoices.py     # functions and call graph, not the file
```

What the numbers behind this say, and don't: on four public repositories the
index found the gold file on 40 of 40 pre-registered queries, and on a
150-question eval put a gold file in the top five on 93.3%, with every miss
published. On 12 held-out tasks in a million-line repository, the prompt-time block
named a file the fix touched on 4 of 12, in offline replays; the tasks were
held out, the repository was not (five other tasks from it had tuned the
ranking). The second number is closer to your day one than the first. The
first is on [/benchmark](https://neuralmind.uk/benchmark/); the second is in
[the replay report](https://github.com/dfrostar/neuralmind/blob/main/bench/task_outcome/hermes-agent-test-ranking/README.md).

## The review: what the client will act on

Before recommending a change, see what it reaches:

```bash
neuralmind impact . RequestSigner.verify     # callers, importers, subclasses
```

Before you push, ask what your diff may have forgotten:

```bash
neuralmind review .                          # files coupled to the ones you changed
neuralmind drift .                           # a changed symbol that skips what its peers do
```

`review` spreads activation from your changed files through the synapse
graph. On a repository you've just indexed, that graph holds only the
structural seeds the build wrote (calls, imports, inheritance); the "edited
together" associations the command describes accumulate with use. `drift`
needs only the code graph. Whether either beats the `git log` and the import
graph you already have is being measured on real commits of public
repositories, pre-registered in a separate pull request
(`REVIEW-DRIFT-EVAL-SPEC.md`); the result will be published whichever way it
comes out, and this page will link it when it lands.

Record what you learned where the next engineer will find it:

```bash
git commit -m "fix: verify webhook signatures before parsing

Decision: signatures are checked in `verify_signature` in `src/router.py`,
  not in the handlers, so a new handler can't skip it.
  Subjects: `verify_signature`, `src/router.py`."
neuralmind why verify_signature              # recall it later, by the symbol
```

Subjects come from the backticked names or a `Subjects:` line, and a wrapped
line must be indented; `why` matches a subject, not the rationale. The client
keeps the trailers in their history whether or not they keep NeuralMind.

## Regulated clients: the evidence their review asks for

A client in a regulated sector will ask what the tool does with their code
and whether it can be installed inside their boundary.

- [Verify the release](verify-a-release.md) you're installing: image
  signature, build provenance, SBOM and VEX, and what each proves.
- `neuralmind data-locations .` lists every place NeuralMind keeps the
  client's data on your machine, and how to remove it at the end of the
  engagement.
- `neuralmind scan-for-secrets . --strict`, run on day one before the first
  build, reports credentials before they reach the index, a commit or the
  agent's context, and `build --redact-secrets` scrubs what it finds from the
  indexed text. Run the scan again before each commit.
- For a defense contractor's CUI code, follow the [CMMC CUI
  enclave](cmmc-cui-enclave.md) walkthrough: `security.profile: cui` turns the
  posture on as one setting and `neuralmind hardening` checks the host.
- [Which NIST documents apply](../compliance/NIST.md) depends on who your
  client is; the table there says which, and what stays the client's.

NeuralMind holds no certification. What it offers is evidence a reviewer can
check, and a tool that runs where the code already is.

## At the end of the engagement

```bash
neuralmind savings .          # what the index saved the agent, labelled an estimate
neuralmind data-locations .   # then remove the index and the audit log
```

Your agent's model provider is the one party that sees the client's code
slices. NeuralMind reduces how much goes out; it can't change where it goes.
For CUI, the provider must meet DFARS 252.204-7012 regardless of the tool.
