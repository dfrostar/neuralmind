# NeuralMind v4.14.0 — measure whether the synapse layer helps on your own repo, and releases you can verify

**Type:** Minor release | **Themes:** check the learning instead of taking it on trust; check that the NeuralMind you install is the one this repository built

A field user put NeuralMind to an adversarial review. The retrieval demos
showed the right symbols coming back, but nothing showed the synapse layer
making retrieval better over time, and the store had sat at 0 transitions for
two months. That was a fair hit. The CI synapse gate is directional and runs on
a ~500-line fixture; nothing published shows the layer paying off on a real
codebase. This release adds the measurement, closes one of the reasons a store
stays at 0 transitions, and makes the public pages say what is and isn't shown.

NIST doesn't certify software against its Secure Software Development
Framework (SP 800-218). A US federal agency buying software asks the producer
to attest to it on CISA's Secure Software Development Attestation Form, signed
by an officer of the company. Until now the repository was missing parts of
the evidence behind that signature. Releases weren't signed or attested,
nothing scanned the code or the installed dependencies on each change, and the
"not affected" decisions on dependency advisories existed only as prose in
SECURITY.md. This release adds that evidence.

---

## What changed

### `neuralmind eval . --synapse-ab`

- Runs your `.neuralmind.eval.yaml` questions twice, read-only: with synapse
  recall on, then off (`NEURALMIND_SYNAPSE_INJECT=0` for the second run only).
  Each run sets the switch itself, so a shell that already exports
  `NEURALMIND_SYNAPSE_INJECT=0` still gets a real "on" run, and its value is
  restored afterwards.
- Under the usual summary it prints the "off" hit@1, hit@5 and MRR, how many
  questions synapse recall moved up or down, hit@5 won and lost with an exact
  McNemar p-value, and the size of the layer it read:

  ```
  NeuralMind eval — shop (12 questions, read-only)
    hit@1 50% · hit@5 83% · MRR 0.64
    ...
    synapse recall off: hit@1 42% · hit@5 83% · MRR 0.60
    synapse recall moved 2 question(s) up, 0 down, 10 unchanged · hit@5 0 won / 0 lost (exact McNemar p = 1.00)
    synapse layer read: 3,612 edges, seeded and learned (usage-learned: 41 LTP edges, 12 transitions)
  ```

  (illustrative).
- **What it measures.** The switch turns off the whole synapse layer, and that
  layer holds two kinds of edge: the call and import edges every build seeds
  from the code graph, and what usage taught it. So one run measures both
  together, and a fresh build can already show a difference. The usage-learned
  part is what the LTP-edge and transition counts track (seeding adds neither).
- The comparison is stored in `.neuralmind/eval_history.jsonl` with the run,
  and `neuralmind eval . --report` adds a **Synapse recall on vs off** table,
  one row per A/B run, with the edge, LTP-edge and transition counts beside
  the on and off scores. Whether the gap grows as LTP edges and transitions
  grow is the usage-learning signal. `--json` includes it as `synapse_ab`.

### The Hermes plugin learns transitions from reads

- It recorded only `write_file` and `patch`, so a Hermes session that read its
  way through a codebase taught the store nothing about the order.
- A successful `read_file` of a file inside the served project now records a
  transition step, as Claude Code's Read hook does
  (`neuralmind _hook read-activity`).
- The path is normalized first, so `src/a.py` and `sub/../src/a.py` are one
  file, not two with a false step between them.
- Reads outside the project, such as Hermes's own config or another
  repository, are never recorded. `NEURALMIND_NO_LEARN=1` turns it off with
  the rest of the learning.

### Public pages say what isn't measured

- `bench/public/results.json` already had a ripgrep baseline (keywords, top
  five files opened whole). The site, README, `docs/benchmarks/public.md` and
  the about page now quote it beside the whole-file figure: **31–67× fewer
  tokens, and ripgrep found the gold file on 32 of 40**. They also say that an
  agent reading only the matching lines pays less than this baseline, and that
  this isn't measured.
- New disclosures: task outcomes (time to fix, error rate) are not measured,
  and the synapse gate is directional, on a ~500-line fixture. Nothing
  published shows the layer paying off on a real codebase.
- `site/claims.json` registers the new figures and the two disclosures, and
  `tests/test_site_claims.py` recomputes the ripgrep range and found count from
  `bench/public/results.json`.

### Releases you can verify (NIST SP 800-218)

- **Container images are signed.** Each `ghcr.io/dfrostar/neuralmind` image is
  signed with cosign by the release workflow. The signing is keyless: the
  signature is bound to the workflow's GitHub OIDC identity and recorded in
  Sigstore's public transparency log, so there's no signing key to hold or
  leak.
- **Every artifact carries build provenance.** The image, the wheel and the
  sdist get GitHub build-provenance attestations naming the workflow, commit
  and runner that built them. PyPI already received PEP 740 attestations from
  trusted publishing.
- **The release checks itself.** Before `:latest` moves, the release workflow
  runs the same `cosign verify` and `gh attestation verify` commands it
  documents. An image that doesn't verify never becomes the default pull.

### Scanning on every change

- **bandit** runs on the package. High severity fails the change, and the full
  report goes to the repository's code scanning alongside CodeQL. The one
  high-severity exception is the SHA-256-pinned model archive's extraction,
  marked `# nosec B202` with its reason.
- **pip-audit** audits what users install, meaning the default install plus
  the `chromadb` extra, in its own environment. Any advisory fails the change
  unless the VEX document below marks it not affected.

### Dependency decisions as data (VEX)

- **`security/neuralmind.openvex.json`** records, in OpenVEX, the four
  ChromaDB advisories SECURITY.md has argued are unreachable. ChromaDB is an
  opt-in extra, and NeuralMind uses only its local `PersistentClient`. Give it
  to a VEX-aware scanner (Grype or Trivy `--vex`) with the release SBOM, and
  those advisories show as not affected rather than open.
- The CI gate ignores exactly what the VEX lists (`scripts/vex_ignores.py`),
  so the published decision and the gate can't disagree.
  `tests/test_vex.py` fails if an entry isn't argued in SECURITY.md or drifts
  from the advisories `chromadb-cve-watch.yml` watches.

### The SSDF mapping

- **[`docs/compliance/SSDF.md`](../compliance/SSDF.md)** maps every SP 800-218
  practice (PO, PS, PW, RV) to the evidence in the repository. It also says
  which parts a repository can't show, such as account 2FA and repository
  settings, which the attesting officer confirms directly.

### Where NeuralMind stands on NIST, in one place

- **[`docs/compliance/NIST.md`](../compliance/NIST.md)** says which NIST
  documents apply to which buyer, where NeuralMind stands on each (FIPS 140-3,
  SP 800-218, SP 800-171/CMMC, SP 800-53, the AI RMF), what's planned next,
  and what stays yours. NIST doesn't certify software; the page says what each
  buyer actually asks for.

## What the agent actually sees

Nothing changes in hook output, MCP tools or response fields. An agent, or the
person running it, can check the synapse layer instead of trusting it:
`neuralmind eval . --synapse-ab --json` returns the on and off metrics side by
side. Under Hermes, a session that only reads files now builds transitions, so
`neuralmind next` has something to say about what usually follows.

The release-signing, scanning and VEX changes add nothing at runtime: they
change how NeuralMind is built and published, not how it runs.

## Per-agent expectations

| Agent | What changes |
|---|---|
| Claude Code (hooks + MCP) | Nothing at runtime; `eval --synapse-ab` is a CLI command you run |
| Cursor / Cline / Continue (MCP) | Same |
| Hermes-Agent plugin | A `read_file` of a file inside the project records a transition step, one background `neuralmind _hook read-activity` call per read |
| Generic MCP client | Same as Claude Code |

## Upgrading

- `eval --synapse-ab` is opt-in; a plain `neuralmind eval .` and its history
  rows are unchanged.
- Under Hermes, each `read_file` inside the project starts one short background
  NeuralMind process, as each edit already did. The plugin is a copy, so after
  `pip install -U neuralmind` re-run `neuralmind install-hermes-plugin` to pick
  it up.
- The release-signing, scanning and VEX changes need no action, and there is
  no index format change.
- To verify what you installed, see
  [SSDF.md §2](../compliance/SSDF.md#2-how-to-verify-a-release-yourself).
  Releases before v4.14.0 have no signature or attestations to verify.
- Air-gapped installs can verify the wheel's provenance on the connected
  machine before transfer; see the
  [air-gapped walkthrough](../use-cases/air-gapped.md).

## Reproduce

```bash
pytest tests/test_measurement_v450.py -k "synapse_ab or SynapseAB" -v
pytest tests/test_hermes_plugin.py -k read -v
pytest tests/test_hooks.py -k read_activity -v
pytest tests/test_site_claims.py -v

pytest tests/test_vex.py -v

# The CI gates, locally
pip install bandit pip-audit
bandit -q -r neuralmind --severity-level high
python -m venv /tmp/audit && /tmp/audit/bin/pip install -e ".[chromadb]"
PIPAPI_PYTHON_LOCATION=/tmp/audit/bin/python \
  pip-audit --skip-editable $(python scripts/vex_ignores.py)

# A published image (v4.14.0 and later)
cosign verify ghcr.io/dfrostar/neuralmind:v4.14.0 \
  --certificate-identity-regexp '^https://github\.com/dfrostar/neuralmind/\.github/workflows/docker-publish\.yml@refs/(heads/main|tags/v[0-9]+\.[0-9]+\.[0-9]+)$' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
gh attestation verify oci://ghcr.io/dfrostar/neuralmind:v4.14.0 --repo dfrostar/neuralmind \
  --cert-identity-regex '^https://github\.com/dfrostar/neuralmind/\.github/workflows/docker-publish\.yml@refs/(heads/main|tags/v[0-9]+\.[0-9]+\.[0-9]+)$'
```

## Related

- [Does NeuralMind earn its place on your repo?](../use-cases/does-it-earn-its-place.md) — replay past incidents as gold questions, and A/B the synapse layer
- [Measure retrieval on your own repo](../use-cases/measure-retrieval-on-your-repo.md)
- [CLI reference: `eval`](../wiki/CLI-Reference.md)
- [The public benchmark](../benchmarks/public.md)
- [Secure Software Development (SSDF) evidence](../compliance/SSDF.md)
- [Compliance Summary](../COMPLIANCE-SUMMARY.md)
- [Vulnerability Management Policy](../VULNERABILITY-MANAGEMENT-POLICY.md)
- [SECURITY.md — Verifying a Release](../../SECURITY.md#verifying-a-release)
- [NIST: what applies, where it stands, what's next](../compliance/NIST.md)
