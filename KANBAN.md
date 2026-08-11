# NeuralMind Refactor — Code Quality Sprint

## In Progress
- [ ] **K1**: Replace bare `except Exception` with logger + re-raise on critical paths (core.py, embedder.py)

## Ready
- [ ] **K2**: Add config schema validation (pydantic/dataclass) — fail fast on malformed TOML
- [ ] **K3**: Extract NeuralMind god-object — Builder, Querier, SynapseClient
- [ ] **K4**: Inject LLM provider + business matcher into SynapseStore
- [ ] **K5**: Extract Chroma lifecycle into repository pattern

## Done
- (none)

## Notes
- Scope: 5 architectural improvements from code evaluation
- Constraint: must not regress 56/56 synapse tests
- Run tests after each fix: `cd /home/dtfrost5/projects/neuralmind && source venv/bin/activate && python -m pytest tests/ -q`
