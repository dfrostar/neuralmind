# NeuralMind Refactor — Code Quality Sprint

## In Progress
- [ ] **K3**: Extract NeuralMind god-object — Builder, Querier, SynapseClient

## Ready
- [ ] **K4**: Inject LLM provider + business matcher into SynapseStore
- [ ] **K5**: Extract Chroma lifecycle into repository pattern

## Done
- [x] **K1**: Replace bare `except Exception` with logger + re-raise on critical paths
- [x] **K2**: Add config schema validation (dataclass)

## Notes
- Scope: 5 architectural improvements from code evaluation
- Constraint: must not regress 120+ synapse/config/embedder tests
- Run tests after each fix: `cd /home/dtfrost5/projects/neuralmind && source venv/bin/activate && python -m pytest tests/test_synapses.py tests/test_config.py tests/test_local_client.py tests/test_embedder.py -q`
