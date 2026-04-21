# NeuralMind Benchmark Fixture

A small but realistic Python web-application stub used as a hermetic fixture
for the self-benchmarking suite.

## Why this fixture?

- Large enough to have **cross-file relationships** (auth depends on users + JWT,
  billing depends on users, api wires everything together)
- Small enough that every CI run is fast (~500 lines total across ~10 files)
- Realistic enough that NeuralMind's semantic retrieval has something to
  meaningfully compress
- Fully static — no runtime dependencies required for indexing

## Layout

```
sample_project/
├── auth/            # login, JWT verification
├── billing/         # Stripe charges, invoices
├── users/           # User model + CRUD
├── api/             # HTTP route wiring
└── db/              # Connection pool
```

## Regenerating the knowledge graph

If you modify these files, rebuild the graph used by the benchmark:

```bash
pip install graphifyy
cd tests/fixtures/sample_project
graphify update .
cd ../../..
neuralmind build tests/fixtures/sample_project --force
```

CI does this automatically — you only need to regenerate locally for faster
iteration.
