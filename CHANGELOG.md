# Changelog

## [1.5.0](https://github.com/dfrostar/neuralmind/compare/v1.11.0...v1.5.0) (2026-08-01)


### ⚠ BREAKING CHANGES

* NeuralMind.__init__ no longer accepts the enable_reranking keyword and instances no longer expose an enable_reranking attribute. The parameter had been deprecated and ignored since v0.25.0; the synapse layer supersedes the reranker it once gated.

### Features

* `neuralmind probe` queries by docstring/rationale + review hardening ([#292](https://github.com/dfrostar/neuralmind/issues/292)) ([bd45e5c](https://github.com/dfrostar/neuralmind/commit/bd45e5ca3b04d881a8090f906500616f9c07bbff))
* add DocEvolver for data-driven JSDoc optimization + self-review fixes ([874ea90](https://github.com/dfrostar/neuralmind/commit/874ea90f5cdfe64e55af363cc63e546c29df8c8f))
* add Java to the built-in tree-sitter backend ([#246](https://github.com/dfrostar/neuralmind/issues/246)) ([6a35145](https://github.com/dfrostar/neuralmind/commit/6a351456714696afe4d2fae7bc6d6a536b61d891))
* add neuralmind probe — label-free retrieval self-test on your own codebase ([b51bffc](https://github.com/dfrostar/neuralmind/commit/b51bffcbf5e054554d3cbd5ac4e99cd63b043bea)), closes [#241](https://github.com/dfrostar/neuralmind/issues/241)
* add Rust to the built-in tree-sitter backend ([#245](https://github.com/dfrostar/neuralmind/issues/245)) ([b4a0e63](https://github.com/dfrostar/neuralmind/commit/b4a0e6366b5218061278df8ee2954ab0acf8090f))
* C and C++ language extractors ([#257](https://github.com/dfrostar/neuralmind/issues/257)) ([f09635e](https://github.com/dfrostar/neuralmind/commit/f09635e1da347dbbf4edf64e980f39810293540b))
* C# extractor — eighth language behind the tree-sitter seam ([#267](https://github.com/dfrostar/neuralmind/issues/267)) ([f16f5b6](https://github.com/dfrostar/neuralmind/commit/f16f5b674ffb6c32d7022803fc4334144b556411))
* **C4:** CI-gated tuner promotion via QualityHarness ([80186b9](https://github.com/dfrostar/neuralmind/commit/80186b943f629c97af94837d352150931bf0f2de))
* complete the v0.43.0 trio — cohesion outlier detection + neuralmind gaps ([#343](https://github.com/dfrostar/neuralmind/issues/343)) ([a8c334a](https://github.com/dfrostar/neuralmind/commit/a8c334a2ad04d5d53a38d586ede85e76400f20af))
* **D3:** judge transcripts loader + generator ([346c8e5](https://github.com/dfrostar/neuralmind/commit/346c8e5e792f14be935abd10c31f1eb1edd7a31c))
* decision provenance — recall why code is the way it is ([#340](https://github.com/dfrostar/neuralmind/issues/340)) ([cc7c64d](https://github.com/dfrostar/neuralmind/commit/cc7c64d9f4b79688c5ddd9dee74d188640561e46))
* dollar-cost reporting for `neuralmind savings` (--cost) ([#353](https://github.com/dfrostar/neuralmind/issues/353)) ([bb8e89b](https://github.com/dfrostar/neuralmind/commit/bb8e89b48901eca179be8c4a2abb57686a0260f7))
* **E1:** contribution-quality scoring — ContributionQualityScorer + team_memory wiring ([7db0214](https://github.com/dfrostar/neuralmind/commit/7db0214ca2df44a8e7adc79cc802d66cc62c84de))
* **E2:** quality-weighted merge semantics with decay-on-conflict ([0288486](https://github.com/dfrostar/neuralmind/commit/02884861fe0d43f61569cfcbf17e91762bd2f9a6))
* **E3:** peer review gate wired into team memory import ([00948b9](https://github.com/dfrostar/neuralmind/commit/00948b94ef4152f64d887a96dbe86335ad696e76))
* **E3:** peer review gate wired into team memory import ([7bcd85a](https://github.com/dfrostar/neuralmind/commit/7bcd85ae0dbbd442110daf9808908d999ccaee6b))
* **E4:** staleness detection wired into team memory + sleep + CLI ([764d16f](https://github.com/dfrostar/neuralmind/commit/764d16f5e0969d9a57e3d9e1a06cd45b5881b603))
* **eval:** PRD 2 retrieval-quality harness — 19-query golden set, polyglot coverage, category breakdown ([a3e8c75](https://github.com/dfrostar/neuralmind/commit/a3e8c752ec94eeee6c3981da4bf410162c70e2df))
* expand public benchmark corpus with flask + rich ([#271](https://github.com/dfrostar/neuralmind/issues/271)) ([df397b7](https://github.com/dfrostar/neuralmind/commit/df397b7de7df1b7fb9a07b95bb9c9995bb0d6868))
* **G4:** incremental re-extraction + dangling edge prune ([4318fd6](https://github.com/dfrostar/neuralmind/commit/4318fd6c8fb4c35b755f92b1abe84d44a3e931c3))
* G5 structural gap detection — betweenness centrality + bridge analysis ([9e3d542](https://github.com/dfrostar/neuralmind/commit/9e3d542e69ce29259e83b63a5481ac0d35120ea8))
* hybrid BM25 search, explicit feedback MCP tool, CI auto-index action (v0.38.0) ([706f2c1](https://github.com/dfrostar/neuralmind/commit/706f2c1d333e75ba1374407f51f31449b68c5c1b))
* index OpenAPI, SQL DDL, and Protobuf schema artifacts (v0.40.0) ([#296](https://github.com/dfrostar/neuralmind/issues/296)) ([3b3c1d3](https://github.com/dfrostar/neuralmind/commit/3b3c1d3a33393087c0ca5fae391eada98618b681))
* **license:** v0.55.0 — anti-tamper DI, TAMPERED status, clock-skew activation ([c9450ef](https://github.com/dfrostar/neuralmind/commit/c9450ef72377fc7305f6a53634a761f304fcbf44))
* **licensing:** add clickwrap EULA to onboarding flow ([631afc2](https://github.com/dfrostar/neuralmind/commit/631afc29d0500428a2957d305d9003131c786036))
* **licensing:** add Team license issuance, revocation, renewal, and partner management ([8a790a3](https://github.com/dfrostar/neuralmind/commit/8a790a3251eb99f2a706bf96be2b390ffcc744cd))
* **licensing:** CLI integration, license agreement, and tests ([1cb2a2e](https://github.com/dfrostar/neuralmind/commit/1cb2a2e372ec8b223dc628c3c7ee8707b21107c6))
* **licensing:** DeepSeek V4 Pro + Flash QA fixes ([fdcadcf](https://github.com/dfrostar/neuralmind/commit/fdcadcfb9a2131a790f0d18e5fc7f9c3c478b2fb))
* live codebase-memory-mcp head-to-head in the public benchmark ([#259](https://github.com/dfrostar/neuralmind/issues/259)) ([54a93c5](https://github.com/dfrostar/neuralmind/commit/54a93c5a0fe51662ddb3ab2f3377c94b0efeb3bb))
* make the default install ChromaDB-free (turbovec/ONNX) ([#251](https://github.com/dfrostar/neuralmind/issues/251)) ([23dac89](https://github.com/dfrostar/neuralmind/commit/23dac89f3c751321e2788e7bdd516c1390e0471c))
* memory namespaces & branch isolation for the synapse layer (PRD 4) ([e8bfafd](https://github.com/dfrostar/neuralmind/commit/e8bfafd5539dc6b0746403a78c68f3b613c1c6dd))
* neuralmind benchmark --public — honest, reproducible benchmark vs alternatives ([#254](https://github.com/dfrostar/neuralmind/issues/254)) ([d1c76ed](https://github.com/dfrostar/neuralmind/commit/d1c76ed2e81c4b35dfefcf5fd3dd2dc824a230bf))
* neuralmind_compliance_report MCP tool for live validated saving reports ([99d0485](https://github.com/dfrostar/neuralmind/commit/99d048501636049a43a286fc17e25fa7ec438b8e))
* opt-in LLM-judged answerability arm for the public benchmark ([#264](https://github.com/dfrostar/neuralmind/issues/264)) ([3d6ec92](https://github.com/dfrostar/neuralmind/commit/3d6ec92ae354e760909d75371607bdeb50db3d0e))
* PHP extractor — tenth language behind the tree-sitter seam ([#270](https://github.com/dfrostar/neuralmind/issues/270)) ([12f19b5](https://github.com/dfrostar/neuralmind/commit/12f19b59dde16f5f497efbd5024f65e26f6ccc9e))
* retire the learned_patterns reranker — the synapse layer is the single learning signal ([#230](https://github.com/dfrostar/neuralmind/issues/230)) ([730eb8b](https://github.com/dfrostar/neuralmind/commit/730eb8b204ddd15e80017e51a2202338559b1756)), closes [#143](https://github.com/dfrostar/neuralmind/issues/143)
* reuse-vs-rewrite feedback loop + structured relevance sidecar (v0.41.0) ([8fcc2e7](https://github.com/dfrostar/neuralmind/commit/8fcc2e796a5c194a92ecaffe12e9b884dd2aed5b))
* Ruby extractor — ninth language behind the tree-sitter seam ([#269](https://github.com/dfrostar/neuralmind/issues/269)) ([4bddb75](https://github.com/dfrostar/neuralmind/commit/4bddb75e0648408e2cf0baf6d71e836bdb0eae86))
* **savings:** mark --cost dollar figures as estimates, disclose basis ([#356](https://github.com/dfrostar/neuralmind/issues/356)) ([05904ae](https://github.com/dfrostar/neuralmind/commit/05904ae24a50d868094f5040fcc0ca0005a0abb5))
* **savings:** serve the savings report from the MCP server and daemon ([3b243d0](https://github.com/dfrostar/neuralmind/commit/3b243d0aafe33241eb3b7691ca9f00ffa7980dab))
* **security:** real Ed25519 keypair, Privacy Policy, Stripe webhook security, lessons learned ([51f0f28](https://github.com/dfrostar/neuralmind/commit/51f0f28b27ef3b17c882c704ed5f652a515256fb))
* self-improvement engine phases 1-2 — selector auto-tuning from the synapse signal ([#233](https://github.com/dfrostar/neuralmind/issues/233)) ([e11e8fb](https://github.com/dfrostar/neuralmind/commit/e11e8fbf4e84405a463294039304c9b4c908965d))
* structural code-graph edge layer (calls/inherits/imports) ([#320](https://github.com/dfrostar/neuralmind/issues/320)) ([f6da1c8](https://github.com/dfrostar/neuralmind/commit/f6da1c86ed45c6a4ee5d4303ae92ad55d62f8d4e))
* **synapse:** seed synapses from structural graph edges ([e1187ee](https://github.com/dfrostar/neuralmind/commit/e1187ee3c0c61b810202fe35ecc726f31677ba17))
* team memory — agents inherit the team's learned associations ([#252](https://github.com/dfrostar/neuralmind/issues/252)) ([c42085e](https://github.com/dfrostar/neuralmind/commit/c42085e18b8427a95bdaabbd1eff66daa28f2486))
* **tier1:** structural edges persistence, time-based half-life decay, migration version check ([a3d9aa1](https://github.com/dfrostar/neuralmind/commit/a3d9aa1749c48a43a651454352f07f1583ddc4e6))
* **tier2:** free tier auto-provisioning + upgrade path ([b231ddc](https://github.com/dfrostar/neuralmind/commit/b231ddc90022022ce6e5feb4d58257af1fdaf3af))
* **tier2:** Team tier 9/user/mo — governance, audit, license, seats, self-hosted ([655b50f](https://github.com/dfrostar/neuralmind/commit/655b50fbd018669919b3abaa30c4f05984ae95c2))
* **tier2:** vendor skip, single backend, honest-first README, dead code cleanup ([768107d](https://github.com/dfrostar/neuralmind/commit/768107ddb3bab51aa61e8cafda2a3b124ca2b8ba))
* **type-verifier:** add cross-language type inference (TypeScript, Go, Rust) ([5ba24e0](https://github.com/dfrostar/neuralmind/commit/5ba24e0e9335b8ab21ecd6f890f8fe16d7a7bc56))
* **type-verifier:** add static type verification layer and cold-start synapse hardening ([2463adf](https://github.com/dfrostar/neuralmind/commit/2463adf20e5db5851fce05f2b034d42b25c49461))
* v0.40.0 — dry-run build, deletion decay, --explain, review, savings dashboard ([5a28ee7](https://github.com/dfrostar/neuralmind/commit/5a28ee7e311a72d5c524044f624945fc834335c9))
* **v0.50.0:** metrics CLI, /api/metrics endpoint, team memory integration test ([9cf79b2](https://github.com/dfrostar/neuralmind/commit/9cf79b25ac3c785e28fa1d73322417d2fb433109))
* **v0.52.0:** impact tool — reverse-dependency blast-radius lookup ([f3d2a81](https://github.com/dfrostar/neuralmind/commit/f3d2a811a57a9c1dbffa807d75076fda96b422f8))
* **v0.56.0:** team license portal + activate signature validation ([62a9daf](https://github.com/dfrostar/neuralmind/commit/62a9daf117681d3234342539077357613071b091))
* **v0.57.0:** seat governance hardening + free-tier bypass ([addd273](https://github.com/dfrostar/neuralmind/commit/addd27393bde9dbdecd065dc4bdcafa2a8ed1a7f))
* **v1.7.0:** free-tier auto-provision on wakeup + upgrade CTA + default tier fix ([3202355](https://github.com/dfrostar/neuralmind/commit/320235518e73dfa78eb4235c5227704c5c54203e))
* v2.0 sprint — Wave 1-3 features (G1, G2, G4, G5, G7) ([2da0f29](https://github.com/dfrostar/neuralmind/commit/2da0f2968912f603ef44f4f3b49213e5748dcf07))
* VS Code native extension, BM25 hybrid search, explicit feedback, CI auto-index (v0.38.0) ([981d8f8](https://github.com/dfrostar/neuralmind/commit/981d8f8098c149369d80bc30c937c51fc1c8412f))
* Wave 1 execution — D quality harness, B1 IR migration, G1 dynamic imports ([13a927b](https://github.com/dfrostar/neuralmind/commit/13a927b23f568ef589514d422d50266e038bd1a4))
* **wave2:** C1/A1/A2/B2/B3/G2 — fitness, traces, entity resolution, sparse, rerank, SCIP ([b85548d](https://github.com/dfrostar/neuralmind/commit/b85548d7e27b61cc09a8b3b577b6045fd2b64e2c))
* **wave3:** C2/C3/A3/A4/B4/F1/F2 — expanded param space, population tuner, learned decay, sleep consolidation, summarization, MCP HTTP, shared daemon memory ([0f5823c](https://github.com/dfrostar/neuralmind/commit/0f5823c4f7af1e06497194d9a0d10b90f33c61a4))
* **wave4:** C4/G3/G4/E1/E2/E3/E4/F3/F4/D3/D4 — modularity, team memory flywheel, CI-gated promotion, incremental extraction, backpressure, per-language fixtures ([b40efb0](https://github.com/dfrostar/neuralmind/commit/b40efb0da917f350638b2a0cb4412df40a91a61c))
* **wave5:** tuner faithfulness + incremental extraction wiring ([e179ed8](https://github.com/dfrostar/neuralmind/commit/e179ed8f5142fd131d86c517f99f11a9e66d926d))


### Bug Fixes

* 3 critical bugs from code review before v2.0.0 ([60fcfd8](https://github.com/dfrostar/neuralmind/commit/60fcfd8b63d06001c066dbd7e16606dd80cc3471))
* add .nojekyll to disable GitHub Pages Jekyll build ([5740b4b](https://github.com/dfrostar/neuralmind/commit/5740b4b50e7b5ad8be2b3d49fc8147789f5b6f23))
* add .nojekyll to docs/ to disable GitHub Pages Jekyll build ([09fb6b9](https://github.com/dfrostar/neuralmind/commit/09fb6b9edaf70126178a0bfb8bd7d2c22a127f76))
* add missing os import in doc_evolver ([186b83d](https://github.com/dfrostar/neuralmind/commit/186b83de82aa01c4ab70294e14ee14ecf7c6e9fe))
* adopt pr-fix-board branch (all audits applied) ([2d90dc9](https://github.com/dfrostar/neuralmind/commit/2d90dc937cae8ece60b7c92656937084f797fa00))
* align SCIP env var between scip_backend.py and precision.py ([1f4de21](https://github.com/dfrostar/neuralmind/commit/1f4de21c39e41f62a9a39cd9d2bc3f5eb9f1452f))
* batch reinforce, concurrency test, auth-enabled server tests ([6cdfbcb](https://github.com/dfrostar/neuralmind/commit/6cdfbcbe8222f5b7bb008ea7624c46c595d2ec5a))
* bump + test_deterministic ([4225f5d](https://github.com/dfrostar/neuralmind/commit/4225f5d56711fad2c29c664ac7d13bddc7fbe9e1))
* bump version to 0.51.2 ([3be58e7](https://github.com/dfrostar/neuralmind/commit/3be58e73312de6e7fde3076aefcf505ad87714f8))
* **ci:** address Codex review — action install path, SBOM-to-site deploy, stray release notes ([11eb071](https://github.com/dfrostar/neuralmind/commit/11eb071993ce53defaf108665ca150fcce8d2b1e))
* **ci:** complete lint sweep — all ruff errors patched ([c0af90e](https://github.com/dfrostar/neuralmind/commit/c0af90e71a3707a183bcfb37d1fa39fac856b039))
* **ci:** compliance-check action must install the checked-out source ([0d3aa24](https://github.com/dfrostar/neuralmind/commit/0d3aa24b84e77b9a7c14a338b388a248c054717a))
* **ci:** let compliance-check post its PR comment, and never fail on it ([5250165](https://github.com/dfrostar/neuralmind/commit/5250165bba0ba0bc86aa26934da6f8e59a419d7c))
* **ci:** lint cleanup + tests package breakage ([5098300](https://github.com/dfrostar/neuralmind/commit/509830051d6f43f1b14a963d146499e82819e7fa))
* **ci:** patch stale test assertions post-wave4 cleanup ([be71e16](https://github.com/dfrostar/neuralmind/commit/be71e16f2d2a6ba4d615d3a61a17405360b91eb8))
* **ci:** restore CI green — lint + test infra patches ([1e6980d](https://github.com/dfrostar/neuralmind/commit/1e6980d58599ac66e519f773dead52f4267ceb30))
* **D3:** DeepSeek QA patches — 4 issues ([366858e](https://github.com/dfrostar/neuralmind/commit/366858e4311c68529833ce371095cc3e357fa9a4))
* DeepSeek QA patches — Waves 4-6 modules ([1ff56cc](https://github.com/dfrostar/neuralmind/commit/1ff56cce5791cc1156ded52ecb023b510d3acde1))
* **deepseek:** Tier 2 security + correctness patches across all 6 modules ([ab2737e](https://github.com/dfrostar/neuralmind/commit/ab2737ea4d145cdc76bc85f45bfb039c86dfe68b))
* demo index gate, honest pricing page, and commercial-terms alignment ([#410](https://github.com/dfrostar/neuralmind/issues/410)) ([fc82505](https://github.com/dfrostar/neuralmind/commit/fc825055bcaf59c9ca6d1e535d0c7c86971e3063))
* DocEvolver subprocess path resolution + query parsing ([74067fa](https://github.com/dfrostar/neuralmind/commit/74067fa66a63bca4fe05887f5853a004c2a60bdf))
* **docs-site:** remove docs/.nojekyll — it disabled the wiki entirely ([0f550d5](https://github.com/dfrostar/neuralmind/commit/0f550d5eb50a78aac120e02017db6cb3ea47439d))
* force UTF-8 stdout/stderr in CLI to avoid Windows cp1252 crash ([#242](https://github.com/dfrostar/neuralmind/issues/242)) ([68361ec](https://github.com/dfrostar/neuralmind/commit/68361ecf16dfd83b726f48f7b148fabd05fe4fb4))
* **format:** ruff format turbovec_backend.py ([6cc8965](https://github.com/dfrostar/neuralmind/commit/6cc8965fee2ee7bd2f6de6b7a03c4034218fc89a))
* **G4/DeepSeek:** ignore-set drift patch + rationale_for comment ([b8002d1](https://github.com/dfrostar/neuralmind/commit/b8002d1f9f1260ffed2411957888ff2a8579a30a))
* G5 performance — approximate betweenness for large graphs ([f141c61](https://github.com/dfrostar/neuralmind/commit/f141c6186c1960248079dc394843c5397e7f1ea2))
* **g5:** deepseek qa patches — Gap ordering, Louvain fallback, dead code, docstring ([a6666d7](https://github.com/dfrostar/neuralmind/commit/a6666d7bd10fd058002471d023965dccb61554dc))
* **license:** restore 'never' expiry guard in _is_expired — free licenses were always EXPIRED ([249fa1a](https://github.com/dfrostar/neuralmind/commit/249fa1a2a5e6fe603bb4734d06d1e5f33fa27c9a))
* **licensing:** DeepSeek QA critical + high fixes ([b06a3ee](https://github.com/dfrostar/neuralmind/commit/b06a3ee6afcbdec193415990a1615b58fc8cc764))
* **lint:** reapply ruff N806 fixes post-PR367 merge ([3229a05](https://github.com/dfrostar/neuralmind/commit/3229a05298274ede6260787cbf82519a01b6a3f5))
* make every neuralmind.uk proof link work + unblock the release pipeline ([#395](https://github.com/dfrostar/neuralmind/issues/395)) ([4af00ba](https://github.com/dfrostar/neuralmind/commit/4af00baf34e9797f204117795cd7aef43a9eaf63))
* make the test suite Windows-green and restore full Windows support ([#228](https://github.com/dfrostar/neuralmind/issues/228)) ([aeea6ac](https://github.com/dfrostar/neuralmind/commit/aeea6ac8bd972779f9b7ff2e3e802f0ba0a286e5))
* MCP auth bypass, token persistence, cache cleanup, env var lazy load ([0db7d2c](https://github.com/dfrostar/neuralmind/commit/0db7d2c97d2c2d87d99216c199548d8508972801))
* MCP server hang under concurrent SQLite write contention ([#363](https://github.com/dfrostar/neuralmind/issues/363)) ([8592aa7](https://github.com/dfrostar/neuralmind/commit/8592aa7ab744514f868c23dbcf851438e5231e13))
* **modularity/DeepSeek:** patch 3 WARNINGs — remove dead code, dedup Phase 2 edges, fix falsy fallback ([3b5e67a](https://github.com/dfrostar/neuralmind/commit/3b5e67a49c06419fe187646ace0466103f6ffeec))
* **modularity/G3:** resolution param + O(n·k) Louvain + community wiring into build_graph ([78efd06](https://github.com/dfrostar/neuralmind/commit/78efd06f6e23c04f3ae30f325036304cb4c76aff))
* **modularity+tests:** stale test_communities_are_per_file + Black drift on modularity.py ([88e4339](https://github.com/dfrostar/neuralmind/commit/88e43398278797cdffd4c9ba161efa7acdfdeb7d))
* namespace-aware learned-decay update in reinforce(); deterministic stickiness test ([#389](https://github.com/dfrostar/neuralmind/issues/389)) ([96509bc](https://github.com/dfrostar/neuralmind/commit/96509bc32083c619224734fd46d5577003130350))
* neuralmind savings now reads audit_events.jsonl (always written) ([8c2c3e2](https://github.com/dfrostar/neuralmind/commit/8c2c3e228859fed7a4235e36624671258200573d))
* patch 2 CRITICAL findings from DeepSeek QA review ([3bc0317](https://github.com/dfrostar/neuralmind/commit/3bc03177b5d392207bf7997300736d09a59237bf))
* patch 3 CRITICAL findings from DeepSeek QA ([836031b](https://github.com/dfrostar/neuralmind/commit/836031b195ed98a71e32290ecc646a0f33a1b217))
* patch 5 critical + 6 warning findings from deepseek retrospective ([7de6dc2](https://github.com/dfrostar/neuralmind/commit/7de6dc28f5fac0b2701755e0ffc6070cc3a59e8f))
* patch BUSINESS-CASE.md model bugs + housekeeping (Phase 3 & 5) ([49f1403](https://github.com/dfrostar/neuralmind/commit/49f1403a414e813d635c9f1837c5d1af40d5cadc))
* patch WARNING findings from DeepSeek QA ([6ac26d1](https://github.com/dfrostar/neuralmind/commit/6ac26d1574112ef5885859559f257b6abe91b6cb))
* re-resolve memory namespace when a warm process crosses a git checkout ([df61fbf](https://github.com/dfrostar/neuralmind/commit/df61fbfb12a7bd0fe1fad6f6b5ef944883d0daea))
* restore transaction atomicity in synapse reinforce/decay + honor auth=False ([#319](https://github.com/dfrostar/neuralmind/issues/319)) ([7e48303](https://github.com/dfrostar/neuralmind/commit/7e48303fbadbfeaa938b66138d44a445c12e3e81))
* ruff format drift + sync manifest to 0.51.2 ([ac1136f](https://github.com/dfrostar/neuralmind/commit/ac1136f82909b018c215683e55eeb1275f2c8245))
* ruff N806 (MAX_EDGES→max_edges) + doctor test stale assertion ([e19f51c](https://github.com/dfrostar/neuralmind/commit/e19f51ce493d4fd49c1b96b29233664a57ac762d))
* **ruff:** sort imports in tier2/license.py (I001) ([da86e68](https://github.com/dfrostar/neuralmind/commit/da86e689d1409fb70c3bb2fbf01ffcad95915981))
* schema migration — add half_life_days BEFORE CREATE INDEX ([eff06dd](https://github.com/dfrostar/neuralmind/commit/eff06dd5d532b2ecd1586a35de092b03a7b08a51))
* **site:** current version on every release + verified PyPI/SBOM links again ([902866d](https://github.com/dfrostar/neuralmind/commit/902866d4c53373d98e9f5a171014605d100deb5d))
* **site:** nav label 'Team' -&gt; 'Teams' ([a401fe8](https://github.com/dfrostar/neuralmind/commit/a401fe8a423e7c9c9028a65f2adaddd2bf76487a))
* stop suggesting graphify update as the fix for a missing graph ([#223](https://github.com/dfrostar/neuralmind/issues/223)) ([9d327d7](https://github.com/dfrostar/neuralmind/commit/9d327d779d03d4397a62efd5930902ec2563f1f2))
* **test:** +Inf clamps to hi, not lo — assertion was wrong ([7bffcba](https://github.com/dfrostar/neuralmind/commit/7bffcba653f43abbff503f644adbed1dc4302b33))
* **tests:** skip tuner_faithfulness/v049_patches when chromadb missing ([a22e2e4](https://github.com/dfrostar/neuralmind/commit/a22e2e40736bf9d07af3d0c939ec014e5fda1fc1))
* **tests:** test_deterministic self-contained to avoid pollution ([1815e07](https://github.com/dfrostar/neuralmind/commit/1815e072c2623b178e7808eb956804595cd3a4e9))
* **tests:** update ephemeral decay tests for time-based half-life model ([a128b77](https://github.com/dfrostar/neuralmind/commit/a128b771ebb59576930d13c69ad2a54972e4d098))
* **test:** update MCP tool count to 17 for neuralmind_structural_gaps ([73c615c](https://github.com/dfrostar/neuralmind/commit/73c615cc418ba9330d7e513cc6e1741604112feb))
* **tier1:** remove dead code, make decay_node time-based, align docs with impl ([3a5aaf0](https://github.com/dfrostar/neuralmind/commit/3a5aaf054ecf75da1523c5bfe30ef336ead0ad12))
* **type-verifier:** support both 'edges' and 'links' graph formats, extract func names from labels ([8de5a72](https://github.com/dfrostar/neuralmind/commit/8de5a72bd6cc0d3fce4b41952ee973382fda05da))
* **type-verifier:** thread-pool, AST cache, any severity, func index, persist batch ([0d4633e](https://github.com/dfrostar/neuralmind/commit/0d4633ed6cf25e6bf20b81ca0c5f93d210be95d8))
* **v0.49.1:** patch 4 CRITICAL + 5 WARNING DeepSeek findings ([c01c7f7](https://github.com/dfrostar/neuralmind/commit/c01c7f798917d7bdec8eae37f5a5baf767fac809))
* **v0.49.2:** apply DeepSeek patches — prune dangling edges, remove dead code, fix axis independence ([fd113f7](https://github.com/dfrostar/neuralmind/commit/fd113f7f870d744c0986a67c029a9e71826a1aa9))
* **v1.7.0:** DeepSeek QA — --json contamination + atomic license write ([337148d](https://github.com/dfrostar/neuralmind/commit/337148dd4534d26af419bc0505dca6949066a0f3))
* **Wave 12:** DeepSeek QA 3 CRITICAL + 2 WARNING patched ([dca7352](https://github.com/dfrostar/neuralmind/commit/dca735289fc14f59b778fa05bb22b958538c3074))
* **Wave 12:** two CRITICAL DeepSeek findings actually patched now ([0fcbee1](https://github.com/dfrostar/neuralmind/commit/0fcbee1a91f25023cee107f8161ca7635e07c736))
* **wave12:** DeepSeek QA patches — 1 CRITICAL + 7 WARNING ([930e2df](https://github.com/dfrostar/neuralmind/commit/930e2dfe9bea3806189c42392bcbd182d3e3d8a1))
* **Wave18:** wire cmd_learn → ingest_document, v1.11.0 ([#411](https://github.com/dfrostar/neuralmind/issues/411)) ([f2f3318](https://github.com/dfrostar/neuralmind/commit/f2f331828e97963cbf5d922cc6373d76e2c369b4))
* **wave3:** patch 4 critical + 8 warning findings from deepseek post-implementation review ([8833603](https://github.com/dfrostar/neuralmind/commit/8833603c1a81b037891da7fbf73da1288bd8fbd0))
* **wave4:** clean deferred warnings — remove dead CI keys, phantom CI params, thread hysteresis through PromotionVerdict ([0af2faa](https://github.com/dfrostar/neuralmind/commit/0af2faa379012ec5dfdf65ef0e10ff23552c6dfa))
* **wave4:** clean up deferred warnings from DeepSeek QA ([8690f76](https://github.com/dfrostar/neuralmind/commit/8690f76c5db179d153325991c3cdec5687d805bb))
* **wave4:** patch 3 CRITICAL + 6 WARNING findings from DeepSeek batch 1 ([0e8dfa5](https://github.com/dfrostar/neuralmind/commit/0e8dfa5454476bfc1f2f1efe1c9606b178cf6402))


### Documentation

* add "US-based" signal to docs-site footers ([#335](https://github.com/dfrostar/neuralmind/issues/335)) ([6143688](https://github.com/dfrostar/neuralmind/commit/614368808e618dde5e7a424b82c443c1137be83e))
* add Book Content QA System draft docs (BRD/TRD/PRD/requirements/dev prompt) ([f021336](https://github.com/dfrostar/neuralmind/commit/f02133687d45c48b3bc1615e3d47a1c74599f368))
* add contact channel and free AI-spend assessment offer ([#324](https://github.com/dfrostar/neuralmind/issues/324)) ([001842c](https://github.com/dfrostar/neuralmind/commit/001842c15eefe3e429971f40f82c7cd03c168690))
* add context engineering stack comparative guide ([2cc7894](https://github.com/dfrostar/neuralmind/commit/2cc7894b6602f498ab8478d6e3f87c37937a0c91))
* add context engineering stack comparative guide (NeuralMind + Ponytail + Headroom) ([8c8cdae](https://github.com/dfrostar/neuralmind/commit/8c8cdae3aa8ec317b5d3e4325508c93c424ebe75))
* add Google Search Console site-verification file ([#237](https://github.com/dfrostar/neuralmind/issues/237)) ([ef2294d](https://github.com/dfrostar/neuralmind/commit/ef2294d67a2f74c0a76a72e8f36b573042c5e72b))
* add release notes for v1.9.1 (type intelligence & synapse hardening) ([b28d237](https://github.com/dfrostar/neuralmind/commit/b28d237f06055608bf55e0d7866e74cb4618622d))
* add session prompts, Wave 6 docs, code standards, module template ([6b7c9e2](https://github.com/dfrostar/neuralmind/commit/6b7c9e2db94f6959a99c06662972a2e4515daa44))
* add the Headroom comparison and fix the sitemap to same-host URLs ([#236](https://github.com/dfrostar/neuralmind/issues/236)) ([67eaee0](https://github.com/dfrostar/neuralmind/commit/67eaee0bebf52562e475bcf970c04dcfd8ca9fd4))
* add TRINODE.md positioning note + state the memory write policy ([#311](https://github.com/dfrostar/neuralmind/issues/311)) ([eb78133](https://github.com/dfrostar/neuralmind/commit/eb7813380e121c91c3dad1aed35521a9699a74c1))
* add upgrade check to session routine + Wave 4 prompt ([13257b0](https://github.com/dfrostar/neuralmind/commit/13257b0250909e38d519d69e5aee3f5b2cedac73))
* audit fixes for v0.46.0 release ([00f09f7](https://github.com/dfrostar/neuralmind/commit/00f09f7de7d7a308752320c43236f321db1ba3e3))
* bump GraphQL roadmap target v0.41.0 → v0.42.0 ([#301](https://github.com/dfrostar/neuralmind/issues/301)) ([ac5a186](https://github.com/dfrostar/neuralmind/commit/ac5a186c55aced406b7bb4952483770d3ded7c09))
* **C4:** CI-gated tuner promotion design — QualityHarness gate ([fd84ca7](https://github.com/dfrostar/neuralmind/commit/fd84ca72e03380ab244966c320d8cb128bb309b4))
* close the recurring critique — limits page, runnable benchmarks/, SWE-bench retrieval harness, security refresh + coverage scorecard ([#303](https://github.com/dfrostar/neuralmind/issues/303)) ([cf1898d](https://github.com/dfrostar/neuralmind/commit/cf1898dcc7406892630b4d59dfc73923c1a036f6))
* commercial license + consulting agreement + cfo pitch deck ([8ca7790](https://github.com/dfrostar/neuralmind/commit/8ca77904f103290d90593071ee19464751cc8b08))
* correct marketing claims and point SEO at neuralmind.uk ([#321](https://github.com/dfrostar/neuralmind/issues/321)) ([8604cf5](https://github.com/dfrostar/neuralmind/commit/8604cf550326e967d2cf91634456537f6731e96a))
* correct version attribution — v0.43.0 provenance-only, cohesion + gaps are v0.44.0 ([#352](https://github.com/dfrostar/neuralmind/issues/352)) ([efe4adb](https://github.com/dfrostar/neuralmind/commit/efe4adb3c2ed7e47504b45c2d755d438514def29))
* defensive publication — quality-weighted merge with conflict-driven decay ([db0cfe5](https://github.com/dfrostar/neuralmind/commit/db0cfe5ee343877e42a9483009c7d2905c8d8f08))
* disclosed-maker launch kit under docs/launch/ ([#263](https://github.com/dfrostar/neuralmind/issues/263)) ([e3a054c](https://github.com/dfrostar/neuralmind/commit/e3a054c1c34a8464bcc1149cfc42bfc777acb98b))
* enrich schema.org JSON-LD on docs pages (SEO) ([#272](https://github.com/dfrostar/neuralmind/issues/272)) ([15d0854](https://github.com/dfrostar/neuralmind/commit/15d0854edfe2b7289edaec093688f18c5d7c14e1))
* enterprise competition + monetization plan (open-core licensing brief) ([#349](https://github.com/dfrostar/neuralmind/issues/349)) ([839f944](https://github.com/dfrostar/neuralmind/commit/839f944cf73f36bee2dac3661cfb546b30383305))
* fix audit-log path drift (docs described a file that doesn't exist) ([#332](https://github.com/dfrostar/neuralmind/issues/332)) ([bfff339](https://github.com/dfrostar/neuralmind/commit/bfff339fb466b3c738dd4be048afd811b7c2624e))
* fix benchmark release notes link to local file ([7f248e5](https://github.com/dfrostar/neuralmind/commit/7f248e5103364353450ce9c474d7fa04abfdc9b1))
* fix DeepSeek doc sweep — 5 issues ([c172486](https://github.com/dfrostar/neuralmind/commit/c1724864315a4b7537d3d1b61952030533e4a469))
* fix release notes links to point to marketing repo ([e2c96da](https://github.com/dfrostar/neuralmind/commit/e2c96da60e8a3bc8041c0e04eed84f8696df6b82))
* **G3:** add BRD, TRD, test plan (governance gap closure) ([fd44988](https://github.com/dfrostar/neuralmind/commit/fd449889576af7fff1495da44539b3a4090ee82d))
* G5 — complete 6-docs-per-wave gate ([8fc3ebf](https://github.com/dfrostar/neuralmind/commit/8fc3ebf769c322b032ffb29d29dcc3acac56e6b2))
* G5 structural gap detection — BRD + TRD + test plan ([28b8188](https://github.com/dfrostar/neuralmind/commit/28b818816020076c23f68404d0df6f6a11e2fa97))
* **handoff:** refresh session handoff for v0.40 + next-session roadmap ([#298](https://github.com/dfrostar/neuralmind/issues/298)) ([21883bf](https://github.com/dfrostar/neuralmind/commit/21883bfb0701e60d58d1ac277d48b8788d0103d4))
* mark v0.23.0 as the latest release on the landing page ([#224](https://github.com/dfrostar/neuralmind/issues/224)) ([bc95bb2](https://github.com/dfrostar/neuralmind/commit/bc95bb230b1f9a754787cdabfa245139ee58def5))
* mark v0.25.0 as the latest release on the landing page ([#231](https://github.com/dfrostar/neuralmind/issues/231)) ([ba353cf](https://github.com/dfrostar/neuralmind/commit/ba353cf6fa1be9f382bc1a3e7f68763c24a9469f))
* mark v0.26.0 as the latest release on the landing page ([#234](https://github.com/dfrostar/neuralmind/issues/234)) ([9ccb12a](https://github.com/dfrostar/neuralmind/commit/9ccb12a2443c801c664a4fc007d6979a41369848))
* marketing measurement framework + rebuild verification ([2bfbc04](https://github.com/dfrostar/neuralmind/commit/2bfbc04e1a2ebdcc03322e6776c962b9d12d68e9))
* modernize guides to the no-graphify flow, fix all broken links ([#222](https://github.com/dfrostar/neuralmind/issues/222)) ([bdcadc5](https://github.com/dfrostar/neuralmind/commit/bdcadc51268a964c6e2901a1f72cae0a6e7a6749))
* move docs site to docs.neuralmind.uk subdomain ([#331](https://github.com/dfrostar/neuralmind/issues/331)) ([3cca46e](https://github.com/dfrostar/neuralmind/commit/3cca46e1ad22b37f04324341625ee2307fdfec63))
* NeuralMind ↔ OpenHuman concept note ([08a6310](https://github.com/dfrostar/neuralmind/commit/08a6310bfaa0a096ac1974add257b1125e3dc579))
* organize v1.7.0 marketing campaign folder ([0b498f6](https://github.com/dfrostar/neuralmind/commit/0b498f66e6c21f97efdc48e7c1c3f5ceefb68ad1))
* **pilot:** corrected BRD and golden queries template ([#285](https://github.com/dfrostar/neuralmind/issues/285)) ([ab87c44](https://github.com/dfrostar/neuralmind/commit/ab87c44c64a44303a3afc261b5e31f96be4fd82f))
* position NeuralMind as four data-backed benefits, not just token reduction ([#261](https://github.com/dfrostar/neuralmind/issues/261)) ([b5db037](https://github.com/dfrostar/neuralmind/commit/b5db03759418a0deb9ce4dddc62e45fffda30cbf))
* **PRD:** Session-scoped memory — namespaces for orchestrated agents ([1b0ff83](https://github.com/dfrostar/neuralmind/commit/1b0ff83072a615ec71bc1cc9881a21d12c0c8f71))
* publish real-world rebuild field report (48.8×, synapse edges 36→135) ([#390](https://github.com/dfrostar/neuralmind/issues/390)) ([53f00ca](https://github.com/dfrostar/neuralmind/commit/53f00cae04cdb89367faa999c3addfc808260435))
* purge forbidden absolute privacy claims (+CI guard) & document git-worktree workflow ([#316](https://github.com/dfrostar/neuralmind/issues/316)) ([#333](https://github.com/dfrostar/neuralmind/issues/333)) ([9e30754](https://github.com/dfrostar/neuralmind/commit/9e3075402c644089c22edcb6bf5309d5b097afe5))
* purge retired claims — 40-70× → 12-50×, +6.5pt → +11.6pt, NIST 800-171 → 800-53 ([10575e5](https://github.com/dfrostar/neuralmind/commit/10575e5d9c3d60435e2e905d225a2f3c44cf58f3))
* README comparisons row, SEO meta tags, and unified-stack use-case walkthrough ([f1c6c2e](https://github.com/dfrostar/neuralmind/commit/f1c6c2e725d68f53ef1fa6273da6427d8b266ef6))
* README comparisons row, SEO meta tags, and unified-stack use-case walkthrough ([7804163](https://github.com/dfrostar/neuralmind/commit/78041635da401390bb1493021055d0f8f6d50af7))
* **readme:** surface the savings report command in quick start ([4d4bbb8](https://github.com/dfrostar/neuralmind/commit/4d4bbb80ec40627e84215deb1b10b57e955ac5b4))
* redesign benchmarks dashboard and wiki pages to match site design system ([#327](https://github.com/dfrostar/neuralmind/issues/327)) ([ba4e588](https://github.com/dfrostar/neuralmind/commit/ba4e588a54460469fe085741af681f5e8404f83b))
* reflect v2.0 completion in HONEST-ASSESSMENT + README ([7e9b383](https://github.com/dfrostar/neuralmind/commit/7e9b383b08a612035e3e450fff256b32bf4e8061))
* refresh benchmark chart [skip ci] ([90a8c99](https://github.com/dfrostar/neuralmind/commit/90a8c99ea921ee1acb2f21f55545ebb1677a4f05))
* refresh benchmark chart [skip ci] ([50a9153](https://github.com/dfrostar/neuralmind/commit/50a91537e066237c94d6a220c1c9306847229fa4))
* refresh benchmark chart [skip ci] ([5fc6e0e](https://github.com/dfrostar/neuralmind/commit/5fc6e0e4d39a8375a72b402d506c974176d3f13d))
* refresh benchmark chart [skip ci] ([fdd9f5b](https://github.com/dfrostar/neuralmind/commit/fdd9f5bae45a5a5005e9a07abdd3ab2f20613866))
* refresh benchmark chart [skip ci] ([1cbcabb](https://github.com/dfrostar/neuralmind/commit/1cbcabbc50ba9c69e1004abf7588cffb754a273a))
* refresh benchmark chart [skip ci] ([bf124ab](https://github.com/dfrostar/neuralmind/commit/bf124abc73352c005c69c7da1d9a025273346603))
* refresh benchmark chart [skip ci] ([e168e5e](https://github.com/dfrostar/neuralmind/commit/e168e5e3b5bd91c1484319b66d588471da9707e9))
* refresh launch handoff to v0.37.0 state ([#275](https://github.com/dfrostar/neuralmind/issues/275)) ([ad5cbb0](https://github.com/dfrostar/neuralmind/commit/ad5cbb0d35153b56e0de6cd6454080d5a07fee16))
* refresh launch handoff with next-session checklist ([#265](https://github.com/dfrostar/neuralmind/issues/265)) ([fe86fd6](https://github.com/dfrostar/neuralmind/commit/fe86fd6b85c703115e7c86cea59c1b69d9a0cb18))
* refresh SEO structured data and sitemap to v0.38.0 state ([#288](https://github.com/dfrostar/neuralmind/issues/288)) ([8716b70](https://github.com/dfrostar/neuralmind/commit/8716b7077ed0fa029880cf4351b9a2606f09973a))
* rename v0.40.0 → v0.39.0 across all public-facing surfaces ([#295](https://github.com/dfrostar/neuralmind/issues/295)) ([1107da8](https://github.com/dfrostar/neuralmind/commit/1107da813bd5dafd408327c97c8d798ca9f9590a))
* restore archival release notes v0.3.2–v0.45.0 to repo root ([38f36e5](https://github.com/dfrostar/neuralmind/commit/38f36e51606dc37e6acc69f5d4c72f7338d9511d))
* rewrite README to 214 lines, add community files, fix stale versions ([2ad797f](https://github.com/dfrostar/neuralmind/commit/2ad797fbb27cc7ad2c278bf9f61909319f55b72b))
* rewrite Reranker TRD to match actual rerank.py code ([cb37102](https://github.com/dfrostar/neuralmind/commit/cb37102cb3c0f2f298b164fcb2ca117e6f04eacc))
* rewrite ROADMAP.md — mark shipped through v1.8.0, delete stale items, add near-term next ([06dd6f7](https://github.com/dfrostar/neuralmind/commit/06dd6f7a7b4e193269e5c79578b095bc886bc572))
* roadmap v0.54.0 + Wave 9 license enforcement architecture ([09ad608](https://github.com/dfrostar/neuralmind/commit/09ad6081e645082ecd502d5deda3359fe5a333da))
* **roadmap:** language expansion, impact tool, broader agent installs ([d5992b2](https://github.com/dfrostar/neuralmind/commit/d5992b2de4e0d69794e61f0caf45027e621e8092))
* route internal docs to marketing repo ([0bf971f](https://github.com/dfrostar/neuralmind/commit/0bf971faded54b415cd4586c513c5a61a099f5e2))
* SEO refresh — right-size meta tags, fix sitemap, add llms.txt ([#310](https://github.com/dfrostar/neuralmind/issues/310)) ([ed5e653](https://github.com/dfrostar/neuralmind/commit/ed5e653576966c604f547418579f189724e350b4))
* **site:** rationalize and dismiss all 23 dependabot alerts ([713897d](https://github.com/dfrostar/neuralmind/commit/713897d1f0eeb1a9768e5018dd51328884eda33c))
* SOC 2 readiness package — BRD, TRD, Test Plan, 7 policies, .gitignore fix ([b9e6cb0](https://github.com/dfrostar/neuralmind/commit/b9e6cb048547920bc81d9df8e81100bc492dcfb7))
* Tier 2 (Team) — BRD, TRD, Test Plan, DeepSeek QA, Kickoff Prompt ([5fa2672](https://github.com/dfrostar/neuralmind/commit/5fa26723bc1e5e5acd0618eff3ea85103003172f))
* umbrella v0.37.0 release notes + Release-As 0.37.0 ([#273](https://github.com/dfrostar/neuralmind/issues/273)) ([f2821be](https://github.com/dfrostar/neuralmind/commit/f2821be8af0d83a04dfe2572e6c1349e7e450f27))
* update future-proofing planning artifacts ([#313](https://github.com/dfrostar/neuralmind/issues/313)) ([de29fcf](https://github.com/dfrostar/neuralmind/commit/de29fcfcc952eba3fc6afaacb59bd74a400b20eb))
* update ROADMAP for v0.48.0 (v2.0 complete) ([b48b2d4](https://github.com/dfrostar/neuralmind/commit/b48b2d46e8cfb3463232c459f75a92f96cca76d3))
* update Wave 4 BRD/TRD/session prompt for C4 ship ([0f9f722](https://github.com/dfrostar/neuralmind/commit/0f9f7226ef61d5c491f1169740a330b9cce47820))
* v0.47.0 audit fixes — synapse metric, turbovec default, graphify removal ([9562291](https://github.com/dfrostar/neuralmind/commit/9562291a3c29ae736b9031962cc5c8f8149b9a0a))
* v0.48.0 — update README, CHANGELOG, HONEST-ASSESSMENT, LinkedIn outreach for v2.0 completion ([0a3be83](https://github.com/dfrostar/neuralmind/commit/0a3be832030eb903803fac815f58c392c38ca17d))
* v0.52.0 public docs + SEO refresh — impact tool, wiki backfill, LinkedIn messaging ([d4dac49](https://github.com/dfrostar/neuralmind/commit/d4dac494a941a89850a2ae196ccf0e1a9a4de27a))
* v1.11.0 propagation — about.html, CLI-Reference wiki ([2a741a8](https://github.com/dfrostar/neuralmind/commit/2a741a868f85440a19ea9bf4df2117f3273d1c5d))
* **v1.7.0:** marketing index + release notes + sitemap ([a8de112](https://github.com/dfrostar/neuralmind/commit/a8de1127237ddd42f48ba496f309098cfb2fbd0e))
* **v1.7.0:** marketing kit + LinkedIn about refresh + Codex outreach ([4fcf992](https://github.com/dfrostar/neuralmind/commit/4fcf992350ad13899de418cc323bc7c62d2fec11))
* **v1.7.0:** Phase 2 — Tier2 Operator Guide, Upgrade Guide, onboarding CLI ref, wakeup memory opt-in ([a445b9e](https://github.com/dfrostar/neuralmind/commit/a445b9ec49409b4ac19b6e56cf6a826f15017f7b))
* v1.7.2 release notes + public surface update ([fa2122c](https://github.com/dfrostar/neuralmind/commit/fa2122cf4860ffe02e05d48d5f2af6a929f5388b))
* v1.9.0 post-release cleanup — release notes, README banner, CLI reference, ROADMAP, __version_info__, DocEvolver failure-path tests ([ed458b8](https://github.com/dfrostar/neuralmind/commit/ed458b83b4e050c9c72b700a651343388e152595))
* v1.9.0 roadmap update + session prompt ([50b488b](https://github.com/dfrostar/neuralmind/commit/50b488b4f5efc71d14c68550c30c4c232e7bceab))
* Wave 12 DeepSeek QA final sweep report ([b183654](https://github.com/dfrostar/neuralmind/commit/b183654ce097a2b043a0a00692f4223e1d6f5953))
* Wave 12 post-build assessment — retrieval quality, discoverability ([dd10e2a](https://github.com/dfrostar/neuralmind/commit/dd10e2a746c277ac2ef2cd8b8ad03b734bcb8383))
* Wave 12 QA report — 3 CRITICAL + 9 WARNING patched ([d1686d6](https://github.com/dfrostar/neuralmind/commit/d1686d67777e4dcac3ceb6f0fc83d8e1f1a538c5))
* Wave 12 session prompt for Wave 4 kickoff ([fc88900](https://github.com/dfrostar/neuralmind/commit/fc889004292652fb97159b4845aea22c6742ce2d))
* wave 3 brd and trd ([52973c6](https://github.com/dfrostar/neuralmind/commit/52973c61047890553b788c075ddfddc2ad0dae19))
* wave 3 handoff ([6745a64](https://github.com/dfrostar/neuralmind/commit/6745a648f429530a0b94289a89894989ef5a3dfd))
* Wave 4 BRD/TRD — v2.0 future-proofing plan complete ([e9e4218](https://github.com/dfrostar/neuralmind/commit/e9e42186dd2b855f6af27a37621985671aa3351f))
* Wave 4 session prompt v10.0 — F3 COMPLETE, F4 next ([ea3042f](https://github.com/dfrostar/neuralmind/commit/ea3042f7a98be1e3e48a41436cebba53aa8d717a))
* Wave 4 session prompt v11.0 — F4 COMPLETE, G3 next ([bce9963](https://github.com/dfrostar/neuralmind/commit/bce9963546d1009bb5b56bf09e09b5ead34fecfe))
* Wave 4 session prompt v5.0 — E1 next ([17980c2](https://github.com/dfrostar/neuralmind/commit/17980c2cf3851cfa87d9df3cd1ef26cf8b62e3c5))
* **Wave 4:** BRD, TRD, session prompt, and standardized session routine ([859cb57](https://github.com/dfrostar/neuralmind/commit/859cb574643e35e2518b55db6139340828c6ac21))
* Wave 5-6 module docstring audit + governance arg docs ([b8d87d0](https://github.com/dfrostar/neuralmind/commit/b8d87d01fdc8e502b5ea72d0c6d264e91920ecc5))
* **WAVE4:** mark G3 shipped in BRD/TRD, update §3.10 to actual implementation ([2fd99b1](https://github.com/dfrostar/neuralmind/commit/2fd99b12ab4abf9887cdf1f98b1f3b7a3adfbb7f))
* **WAVE4:** next session prompt — G3+G4 implemented, release blocked on repo rules ([5a3118d](https://github.com/dfrostar/neuralmind/commit/5a3118d7758a053f8d06c4952454ce7df85c3a9c))
* **WAVE4:** v12.0 session prompt + G3 QA report (G3 → DONE, G4 next) ([2240187](https://github.com/dfrostar/neuralmind/commit/2240187f13f2862421faab296b4fc3d10cc5436e))
* **WAVE4:** v13.0 session prompt — G3 complete, DeepSeek QA clean, v1.4.0 released ([5bd6cf7](https://github.com/dfrostar/neuralmind/commit/5bd6cf7862d244ad4a2033752eff6813cb40ebbe))


### Miscellaneous Chores

* release as v0.31.0 (roll 0.30.0 into 0.31.0) ([#256](https://github.com/dfrostar/neuralmind/issues/256)) ([4cc955b](https://github.com/dfrostar/neuralmind/commit/4cc955b02941b4cbe674208f76575c93f8cf5c39))
* **release:** retarget release-please to 1.5.0 ([bad2f4a](https://github.com/dfrostar/neuralmind/commit/bad2f4ade8ec7079a280b48ec9acb1e0c7a832fe))


### Code Refactoring

* split core.py, remove deprecated enable_reranking, fix IR aliasing ([#318](https://github.com/dfrostar/neuralmind/issues/318)) ([40f7593](https://github.com/dfrostar/neuralmind/commit/40f759318239afb66472495fe08581bd9451bcd6))

## [1.10.1](https://github.com/dfrostar/neuralmind/compare/v1.10.0...v1.10.1) (2026-07-30)


### Bug Fixes

* **type-verifier:** support both 'edges' and 'links' graph formats, extract func names from labels ([f0a1ad2](https://github.com/dfrostar/neuralmind/commit/f0a1ad251213360cb29c085d86a7feb55bcf7611))
* **type-verifier:** thread-pool, AST cache, any severity, func index, persist batch ([6314504](https://github.com/dfrostar/neuralmind/commit/631450478b139a77a1f04fe3db3a499a719e57fd))

## [1.10.0](https://github.com/dfrostar/neuralmind/compare/v1.9.1...v1.10.0) (2026-07-30)


### Features

* neuralmind_compliance_report MCP tool for live validated saving reports ([6739513](https://github.com/dfrostar/neuralmind/commit/6739513efab5fcde06c7fe61665f70130a963970))
* **savings:** serve the savings report from the MCP server and daemon ([ca3463e](https://github.com/dfrostar/neuralmind/commit/ca3463e2944927b8c0042f6f4df32aca0b8a87fb))
* **type-verifier:** add cross-language type inference (TypeScript, Go, Rust) ([125ae58](https://github.com/dfrostar/neuralmind/commit/125ae58286b2a0a7077d0fce119266dd95fc3523))
* **type-verifier:** add static type verification layer and cold-start synapse hardening ([f87dabc](https://github.com/dfrostar/neuralmind/commit/f87dabcbd91f3f7df019df71e6c86008e027f078))
* v2.0 sprint — Wave 1-3 features (G1, G2, G4, G5, G7) ([4b53f2d](https://github.com/dfrostar/neuralmind/commit/4b53f2d4e12231641d1fa96cec79b7655b9f769c))


### Bug Fixes

* 3 critical bugs from code review before v2.0.0 ([d86c9d2](https://github.com/dfrostar/neuralmind/commit/d86c9d2f7b8c808ab2edcc5dd9c5235fef559a89))
* align SCIP env var between scip_backend.py and precision.py ([b5b291a](https://github.com/dfrostar/neuralmind/commit/b5b291aaf1528c4f7c2119b6fc0e7b9f2f23ca6f))
* **ci:** address Codex review — action install path, SBOM-to-site deploy, stray release notes ([42332f8](https://github.com/dfrostar/neuralmind/commit/42332f8a4506b9f9704ec1166cb19d22f963ab08))
* **ci:** compliance-check action must install the checked-out source ([e4b0535](https://github.com/dfrostar/neuralmind/commit/e4b0535f7528cb2a8eff36974e070d448447fad0))
* **ci:** let compliance-check post its PR comment, and never fail on it ([8245083](https://github.com/dfrostar/neuralmind/commit/8245083b4427df933672065e0d82183fa82955d2))
* **docs-site:** remove docs/.nojekyll — it disabled the wiki entirely ([705d261](https://github.com/dfrostar/neuralmind/commit/705d26178346b84bb2d7360000d5967c1f8efb13))
* neuralmind savings now reads audit_events.jsonl (always written) ([08ef7d3](https://github.com/dfrostar/neuralmind/commit/08ef7d3a56d7494a0b6a8e3ce4eb1b1f68670e90))
* **site:** current version on every release + verified PyPI/SBOM links again ([757c4ea](https://github.com/dfrostar/neuralmind/commit/757c4ea317ffd3e6934b7eb1cbfc1a879a462e31))
* **site:** nav label 'Team' -&gt; 'Teams' ([b5f3ad0](https://github.com/dfrostar/neuralmind/commit/b5f3ad0126f028b24234eabbff5b44626a31ec46))


### Reverts

* remove CMMC bridge docs from NeuralMind repo — belongs in separate track (CMMC 2.0 + LLM) ([d6452d3](https://github.com/dfrostar/neuralmind/commit/d6452d3de62562b0ebee4fa7f77d59ad9416070c))


### Documentation

* add release notes for v1.9.1 (type intelligence & synapse hardening) ([2b61178](https://github.com/dfrostar/neuralmind/commit/2b61178292f2fb182e4ca0699f8368f545270b14))
* **readme:** surface the savings report command in quick start ([3bdf552](https://github.com/dfrostar/neuralmind/commit/3bdf552677e445462799b39bde326d58176460ca))
* rewrite README to 214 lines, add community files, fix stale versions ([2b062bf](https://github.com/dfrostar/neuralmind/commit/2b062bfce3c690434c89a114d53f79e4c4cfb95f))
* rewrite Reranker TRD to match actual rerank.py code ([9e2633b](https://github.com/dfrostar/neuralmind/commit/9e2633b8f24ce293b20f7ac49b6a2b17512c6f31))

## [1.9.1](https://github.com/dfrostar/neuralmind/compare/v1.9.0...v1.9.1) (2026-07-28)


### Documentation

* add Book Content QA System draft docs (BRD/TRD/PRD/requirements/dev prompt) ([0269181](https://github.com/dfrostar/neuralmind/commit/02691819b95dd2091c14a782aeb52f4cb30daca1))
* v1.9.0 post-release cleanup — release notes, README banner, CLI reference, ROADMAP, __version_info__, DocEvolver failure-path tests ([c37e688](https://github.com/dfrostar/neuralmind/commit/c37e68849b2c7797d963f459b1a9889e21a3cc61))

## [1.9.0](https://github.com/dfrostar/neuralmind/compare/v1.8.0...v1.9.0) (2026-07-28)


### Features

* G5 structural gap detection — betweenness centrality + bridge analysis ([638a72e](https://github.com/dfrostar/neuralmind/commit/638a72eefede04dca8d0b68c2918187ae978dbfc))


### Bug Fixes

* G5 performance — approximate betweenness for large graphs ([85e242f](https://github.com/dfrostar/neuralmind/commit/85e242f277dba52de02003f4f5d97dd6928595d1))
* **g5:** deepseek qa patches — Gap ordering, Louvain fallback, dead code, docstring ([acf14e2](https://github.com/dfrostar/neuralmind/commit/acf14e29f77c7542e5f025fd94f75dfab387b289))
* **test:** update MCP tool count to 17 for neuralmind_structural_gaps ([438aec6](https://github.com/dfrostar/neuralmind/commit/438aec649c70e6f9f25e597b0e45bb802be26f35))


### Documentation

* G5 — complete 6-docs-per-wave gate ([9b88c4b](https://github.com/dfrostar/neuralmind/commit/9b88c4ba89a6e1f81358c4955e429c4063752a65))
* G5 structural gap detection — BRD + TRD + test plan ([34f0650](https://github.com/dfrostar/neuralmind/commit/34f06500a2705270c013df33e61da81abe085d57))
* rewrite ROADMAP.md — mark shipped through v1.8.0, delete stale items, add near-term next ([dc1c08a](https://github.com/dfrostar/neuralmind/commit/dc1c08af2b63621b42835d8610355aa727bccfa4))
* SOC 2 readiness package — BRD, TRD, Test Plan, 7 policies, .gitignore fix ([214ea87](https://github.com/dfrostar/neuralmind/commit/214ea87024ed697ebb3075f00c83a4c9533e9ff3))
* v1.9.0 roadmap update + session prompt ([64a3fb4](https://github.com/dfrostar/neuralmind/commit/64a3fb4a4d1c4782006c46e35cab3aee849708a1))

## [1.8.0](https://github.com/dfrostar/neuralmind/compare/v1.7.1...v1.8.0) (2026-07-27)


### Features

* add DocEvolver for data-driven JSDoc optimization + self-review fixes ([41d407f](https://github.com/dfrostar/neuralmind/commit/41d407ff1295192237b56ffc817bb5e3f781d25c))


### Bug Fixes

* add .nojekyll to disable GitHub Pages Jekyll build ([20947f7](https://github.com/dfrostar/neuralmind/commit/20947f7ba2a0fffb9c930a2d00cec6260a3c2388))
* add .nojekyll to docs/ to disable GitHub Pages Jekyll build ([221f1b8](https://github.com/dfrostar/neuralmind/commit/221f1b8c77b04b7302363a6c8e936ebab5427766))
* add missing os import in doc_evolver ([ed9b2f8](https://github.com/dfrostar/neuralmind/commit/ed9b2f8e991468623b9cf0257a7ba914887264bc))
* **format:** ruff format turbovec_backend.py ([77015c4](https://github.com/dfrostar/neuralmind/commit/77015c4234c5de67f126a4ceebd1533fe4931699))


### Documentation

* refresh benchmark chart [skip ci] ([3c3e7c9](https://github.com/dfrostar/neuralmind/commit/3c3e7c953889093620e9c272b18a8a329e11e13a))
* v1.7.2 release notes + public surface update ([663d708](https://github.com/dfrostar/neuralmind/commit/663d7085891ef556253121ebd24dc2f9323f5c31))

## [1.5.0](https://github.com/dfrostar/neuralmind/compare/v1.4.0...v1.5.0) (2026-07-21)


### ⚠ BREAKING CHANGES

* NeuralMind.__init__ no longer accepts the enable_reranking keyword and instances no longer expose an enable_reranking attribute. The parameter had been deprecated and ignored since v0.25.0; the synapse layer supersedes the reranker it once gated.

### Features

* `neuralmind probe` queries by docstring/rationale + review hardening ([#292](https://github.com/dfrostar/neuralmind/issues/292)) ([745169a](https://github.com/dfrostar/neuralmind/commit/745169a18b53b3678d2c6b329d974617d8f38859))
* add Java to the built-in tree-sitter backend ([#246](https://github.com/dfrostar/neuralmind/issues/246)) ([42c9516](https://github.com/dfrostar/neuralmind/commit/42c9516dfad772f958933672f86c0252d70738c1))
* add neuralmind probe — label-free retrieval self-test on your own codebase ([4dceb99](https://github.com/dfrostar/neuralmind/commit/4dceb99c57c3551630fa0a0b27f643e1a08c0713)), closes [#241](https://github.com/dfrostar/neuralmind/issues/241)
* add Obsidian-style graph-view UI (`neuralmind serve`) ([f6d4cbd](https://github.com/dfrostar/neuralmind/commit/f6d4cbd4c2fd3b489c4e7e8d623c45736c5349da))
* add Rust to the built-in tree-sitter backend ([#245](https://github.com/dfrostar/neuralmind/issues/245)) ([6eea233](https://github.com/dfrostar/neuralmind/commit/6eea23333af8f464d3a151d9979869b91cd4f766))
* **backend:** built-in tree-sitter graph backend — `neuralmind build` with no graphify ([#187](https://github.com/dfrostar/neuralmind/issues/187)) ([c297898](https://github.com/dfrostar/neuralmind/commit/c29789840918706a1cb2e70a10e961c786d2f18f))
* **backend:** ChromaDB-free embeddings — owned MiniLM embedder ([#207](https://github.com/dfrostar/neuralmind/issues/207)) ([9be4762](https://github.com/dfrostar/neuralmind/commit/9be47626dedcdd14cb2235f950b555300ee9f0e5))
* **backend:** default to turbovec when available, with chroma fallback ([#214](https://github.com/dfrostar/neuralmind/issues/214)) ([9be320f](https://github.com/dfrostar/neuralmind/commit/9be320f909747b7c3b58a3c55b240f418f37d799))
* **backend:** experimental TurboVec (TurboQuant) vector backend [POC, [#204](https://github.com/dfrostar/neuralmind/issues/204)] ([#205](https://github.com/dfrostar/neuralmind/issues/205)) ([e37d4c7](https://github.com/dfrostar/neuralmind/commit/e37d4c7f66e3c70b116443f3a7e4f57c71f5be86))
* **backend:** incremental per-file graph updates wired to the watcher ([#193](https://github.com/dfrostar/neuralmind/issues/193)) ([1777747](https://github.com/dfrostar/neuralmind/commit/177774726edc3f4e51e699d4b586955636881199))
* **backend:** multi-language built-in backend — TypeScript + Go extractors ([#189](https://github.com/dfrostar/neuralmind/issues/189)) ([2dfc255](https://github.com/dfrostar/neuralmind/commit/2dfc255a2171ee91b1fe7555de6b89dc904a985e))
* **backend:** optional SCIP precision pass for compiler-accurate edges ([#191](https://github.com/dfrostar/neuralmind/issues/191)) ([d457231](https://github.com/dfrostar/neuralmind/commit/d45723130be78879c7f80da0f2cef4bbf4271494))
* **bench:** TurboVec vs ChromaDB memory/latency benchmark toolkit ([#211](https://github.com/dfrostar/neuralmind/issues/211)) ([e5fb19b](https://github.com/dfrostar/neuralmind/commit/e5fb19baaaa72a475b230ce72ddce6a9fcd88419))
* C and C++ language extractors ([#257](https://github.com/dfrostar/neuralmind/issues/257)) ([424faf9](https://github.com/dfrostar/neuralmind/commit/424faf95d010948fcca10381c9e081d3cc75185f))
* C# extractor — eighth language behind the tree-sitter seam ([#267](https://github.com/dfrostar/neuralmind/issues/267)) ([d5b5c65](https://github.com/dfrostar/neuralmind/commit/d5b5c6534321efe6409934f32ab16c56006e4b78))
* **C4:** CI-gated tuner promotion via QualityHarness ([7e7ff98](https://github.com/dfrostar/neuralmind/commit/7e7ff989b2982d76bae82329c8bfe11cf099f873))
* **ci:** CycloneDX SBOM generation + release-asset attachment ([#120](https://github.com/dfrostar/neuralmind/issues/120)) ([f5f671d](https://github.com/dfrostar/neuralmind/commit/f5f671d8756ea83ec0761f6c960c1dbfa26bdb5b))
* **ci:** GHCR multi-platform image auto-build on tag push ([#120](https://github.com/dfrostar/neuralmind/issues/120)) ([a2b708e](https://github.com/dfrostar/neuralmind/commit/a2b708e39be25891a6285ec648e8d0dbffadcccf))
* **ci:** v0.9 enterprise-ready — GHCR auto-build, SBOM, air-gapped doc, compliance one-pager ([#129](https://github.com/dfrostar/neuralmind/issues/129)) ([eb5969f](https://github.com/dfrostar/neuralmind/commit/eb5969f371fe062dfabb4803f913017b2359b231))
* **cli:** neuralmind doctor — install health check + friendlier first-run error ([#169](https://github.com/dfrostar/neuralmind/issues/169)) ([2b0509b](https://github.com/dfrostar/neuralmind/commit/2b0509bb03a9a6e210d3f8bf3990d6b47a89edd9))
* complete the v0.43.0 trio — cohesion outlier detection + neuralmind gaps ([#343](https://github.com/dfrostar/neuralmind/issues/343)) ([c0cfa24](https://github.com/dfrostar/neuralmind/commit/c0cfa24f226470a125c0b832f99a2eb7c8457c33))
* **compressors:** show what was dropped + `neuralmind last` recovery cache ([#149](https://github.com/dfrostar/neuralmind/issues/149)) ([561f8ef](https://github.com/dfrostar/neuralmind/commit/561f8eff221770eaf324ca239f8888935230b5dd))
* **D3:** judge transcripts loader + generator ([e232b15](https://github.com/dfrostar/neuralmind/commit/e232b152a39f40e714ff086cfab672e2e28d3748))
* decision provenance — recall why code is the way it is ([#340](https://github.com/dfrostar/neuralmind/issues/340)) ([9961562](https://github.com/dfrostar/neuralmind/commit/9961562b0e351e56e98753d051b83a73999e4ccc))
* dollar-cost reporting for `neuralmind savings` (--cost) ([#353](https://github.com/dfrostar/neuralmind/issues/353)) ([5eb60f6](https://github.com/dfrostar/neuralmind/commit/5eb60f67a8523e85843c07fcf42ad2781adfd345))
* **E1:** contribution-quality scoring — ContributionQualityScorer + team_memory wiring ([2969e38](https://github.com/dfrostar/neuralmind/commit/2969e3873cbbbde136b5d3b55cc4dcdf24a9e527))
* **E1:** contribution-quality scoring — ContributionQualityScorer + team_memory wiring ([c7d5a86](https://github.com/dfrostar/neuralmind/commit/c7d5a860a9201b029057c4cb4b933e8db1be6c95))
* **E2:** quality-weighted merge semantics with decay-on-conflict ([43d4ef4](https://github.com/dfrostar/neuralmind/commit/43d4ef4c84e06b820ffb68a251029a5b4a1c2684))
* **E3:** peer review gate wired into team memory import ([485687f](https://github.com/dfrostar/neuralmind/commit/485687faf77ca8d63fa9d91f023e98e5efbaeaa3))
* **E3:** peer review gate wired into team memory import ([f1f4913](https://github.com/dfrostar/neuralmind/commit/f1f4913736944dc8e0a6415cd46039e616ec0fc6))
* **E4:** staleness detection wired into team memory + sleep + CLI ([3fe5a61](https://github.com/dfrostar/neuralmind/commit/3fe5a610087c8b2bf98dae4dd5f96520ceb71ba7))
* **ecosystem:** Agent Zero MCP integration + a0-plugins submission draft ([b016f28](https://github.com/dfrostar/neuralmind/commit/b016f2809350e21651fea3b4305435703cad2829))
* **eval:** PRD 2 retrieval-quality harness — 19-query golden set, polyglot coverage, category breakdown ([4672b96](https://github.com/dfrostar/neuralmind/commit/4672b96f76c9487000a005fbb006556e17447de1))
* **evals:** faithfulness A/B harness + report (E1.2-E1.4) ([#182](https://github.com/dfrostar/neuralmind/issues/182)) ([c7da2b1](https://github.com/dfrostar/neuralmind/commit/c7da2b169f4a69405ca5e1c7f220bd903a7ea0d9))
* **evals:** faithfulness eval foundation — query+gold-fact set + offline judge skeleton (E1.1) ([#177](https://github.com/dfrostar/neuralmind/issues/177)) ([90be7aa](https://github.com/dfrostar/neuralmind/commit/90be7aa80c02442044b0d0584f2062332c488090))
* **evals:** onboarding-lift eval (E1.5) — measure the learned-synapse uplift ([#199](https://github.com/dfrostar/neuralmind/issues/199)) ([e53782e](https://github.com/dfrostar/neuralmind/commit/e53782ec5f5075450a6efb2c0f1ee5d5caeb661f))
* expand public benchmark corpus with flask + rich ([#271](https://github.com/dfrostar/neuralmind/issues/271)) ([3ce219f](https://github.com/dfrostar/neuralmind/commit/3ce219f990560efb902d48b99b12292ca363034f))
* **G4:** incremental re-extraction + dangling edge prune ([0a1feb8](https://github.com/dfrostar/neuralmind/commit/0a1feb8840ab94976fe2734557b7b32f26b2363e))
* hybrid BM25 search, explicit feedback MCP tool, CI auto-index action (v0.38.0) ([438bacd](https://github.com/dfrostar/neuralmind/commit/438bacd8d40ea97101c548f924dbd894586e3c7f))
* index OpenAPI, SQL DDL, and Protobuf schema artifacts (v0.40.0) ([#296](https://github.com/dfrostar/neuralmind/issues/296)) ([a482ffd](https://github.com/dfrostar/neuralmind/commit/a482ffd0df10a5267674f5edd5a721a4b0443e44))
* **install:** add Dockerfile and PyPI keywords for v0.6.1 ([#118](https://github.com/dfrostar/neuralmind/issues/118)) ([fd51773](https://github.com/dfrostar/neuralmind/commit/fd5177301b79ebc93d11f088a531f4063bd28342))
* **license:** v0.55.0 — anti-tamper DI, TAMPERED status, clock-skew activation ([8bc2990](https://github.com/dfrostar/neuralmind/commit/8bc29907560fa6d27e813bf74017db60ef8a4cf7))
* live codebase-memory-mcp head-to-head in the public benchmark ([#259](https://github.com/dfrostar/neuralmind/issues/259)) ([888291d](https://github.com/dfrostar/neuralmind/commit/888291df67e3d5e3db6c3152e5928c42c92a0270))
* make the default install ChromaDB-free (turbovec/ONNX) ([#251](https://github.com/dfrostar/neuralmind/issues/251)) ([5edf090](https://github.com/dfrostar/neuralmind/commit/5edf090c28a84c4416efb0685f70b330f9797650))
* **mcp:** one-command MCP setup — auto-detect + register with agents ([#195](https://github.com/dfrostar/neuralmind/issues/195)) ([40c3209](https://github.com/dfrostar/neuralmind/commit/40c3209a22d3b519b8c5b07732fcc79e1f61ee4f))
* memory namespaces & branch isolation for the synapse layer (PRD 4) ([8fae289](https://github.com/dfrostar/neuralmind/commit/8fae28975779bcfe2491443a47b9a8f6929e6de4))
* neuralmind benchmark --public — honest, reproducible benchmark vs alternatives ([#254](https://github.com/dfrostar/neuralmind/issues/254)) ([f8eca9b](https://github.com/dfrostar/neuralmind/commit/f8eca9bd7a651941f4f6d55f16c31d446339fdf2))
* Obsidian-style graph view (`neuralmind serve`) + editor jump, auth, layout persistence ([14a654e](https://github.com/dfrostar/neuralmind/commit/14a654e5be6977540c868e2c400b37b876895605))
* opt-in LLM-judged answerability arm for the public benchmark ([#264](https://github.com/dfrostar/neuralmind/issues/264)) ([f6e8cd7](https://github.com/dfrostar/neuralmind/commit/f6e8cd7c182808c30476bb88ec60e1f3c719fb7f))
* PHP extractor — tenth language behind the tree-sitter seam ([#270](https://github.com/dfrostar/neuralmind/issues/270)) ([f33b87c](https://github.com/dfrostar/neuralmind/commit/f33b87c83686d2ffc3f6fc95eb731826a63b6462))
* polyglot retrieval-quality fixtures — TypeScript + Go ([#173](https://github.com/dfrostar/neuralmind/issues/173) E2.2/E2.3) ([#178](https://github.com/dfrostar/neuralmind/issues/178)) ([f7d7b53](https://github.com/dfrostar/neuralmind/commit/f7d7b53bc209f2a5561beaf6cfb3a653c788a15e))
* retire the learned_patterns reranker — the synapse layer is the single learning signal ([#230](https://github.com/dfrostar/neuralmind/issues/230)) ([d00f46c](https://github.com/dfrostar/neuralmind/commit/d00f46c29b2dacaff1af8577278a2eb13cff90c6)), closes [#143](https://github.com/dfrostar/neuralmind/issues/143)
* reuse-vs-rewrite feedback loop + structured relevance sidecar (v0.41.0) ([a27dc57](https://github.com/dfrostar/neuralmind/commit/a27dc57adf888d79a82ecb2cf56f0131c20465b0))
* Ruby extractor — ninth language behind the tree-sitter seam ([#269](https://github.com/dfrostar/neuralmind/issues/269)) ([b27c7d7](https://github.com/dfrostar/neuralmind/commit/b27c7d7ec47c0d9b96eed3a9725cb4eca9aa0bfd))
* **savings:** mark --cost dollar figures as estimates, disclose basis ([#356](https://github.com/dfrostar/neuralmind/issues/356)) ([a8ce708](https://github.com/dfrostar/neuralmind/commit/a8ce708b81c7da74fb06ee343512d3e7e5688f78))
* **security:** real Ed25519 keypair, Privacy Policy, Stripe webhook security, lessons learned ([01fc1f0](https://github.com/dfrostar/neuralmind/commit/01fc1f0c4db6b5d38f82bc8b014dcadf44577a8c))
* self-improvement engine phases 1-2 — selector auto-tuning from the synapse signal ([#233](https://github.com/dfrostar/neuralmind/issues/233)) ([d1d622f](https://github.com/dfrostar/neuralmind/commit/d1d622fcd9721893143a001b016ccf4225701d06))
* **serve:** /healthz endpoint + systemd/launchd/Windows templates for v0.8 ([3f22efe](https://github.com/dfrostar/neuralmind/commit/3f22efecffa4d9af072d6a5f2b7ab0a5517cb698))
* **serve:** Cmd/Ctrl-K and '/' jump to search, Esc clears ([1f844a5](https://github.com/dfrostar/neuralmind/commit/1f844a5d0675d359d2d85c64e82b7873c900b849))
* **serve:** Cmd/Ctrl-K and '/' jump to search, Esc clears ([374fbbc](https://github.com/dfrostar/neuralmind/commit/374fbbc4895d73a9b19d7d78dc2f434a13935b09))
* **serve:** Cmd/Ctrl-K and '/' jump to search, Esc clears ([#109](https://github.com/dfrostar/neuralmind/issues/109)) ([1f844a5](https://github.com/dfrostar/neuralmind/commit/1f844a5d0675d359d2d85c64e82b7873c900b849))
* **serve:** cross-process activity stream via JSONL bridge ([806ceba](https://github.com/dfrostar/neuralmind/commit/806cebaa1637c630a80e75c1e866570d1e0b7b11))
* **serve:** cross-process activity stream via JSONL bridge ([7fce097](https://github.com/dfrostar/neuralmind/commit/7fce097c5272976625bf2d5828cc5b9bb70ad428))
* **serve:** cross-process activity stream via JSONL bridge ([#112](https://github.com/dfrostar/neuralmind/issues/112)) ([806ceba](https://github.com/dfrostar/neuralmind/commit/806cebaa1637c630a80e75c1e866570d1e0b7b11))
* **serve:** edge tooltips + min-weight synapse slider ([5c7ce5c](https://github.com/dfrostar/neuralmind/commit/5c7ce5cca56a4e6fe99f80443754f7a08b6d1854))
* **serve:** edge tooltips + min-weight synapse slider ([a595a38](https://github.com/dfrostar/neuralmind/commit/a595a38f26d01d43f73a566e8b788dc4eca55324))
* **serve:** edge tooltips + min-weight synapse slider ([#106](https://github.com/dfrostar/neuralmind/issues/106)) ([5c7ce5c](https://github.com/dfrostar/neuralmind/commit/5c7ce5cca56a4e6fe99f80443754f7a08b6d1854))
* **serve:** editor jump, auth token, first-run guidance, layout persistence ([b716f46](https://github.com/dfrostar/neuralmind/commit/b716f466da52f354136fbf0c134362dc3d48fb27))
* **serve:** live activity feed - SSE stream of synapse + file events ([#110](https://github.com/dfrostar/neuralmind/issues/110)) ([ea9fa26](https://github.com/dfrostar/neuralmind/commit/ea9fa2683a523a51cf3e31a651e93ddba722bd2a))
* **serve:** live activity feed — SSE stream of synapse + file events ([ea9fa26](https://github.com/dfrostar/neuralmind/commit/ea9fa2683a523a51cf3e31a651e93ddba722bd2a))
* **serve:** live activity feed — SSE stream of synapse + file events ([1712e61](https://github.com/dfrostar/neuralmind/commit/1712e61184388e800b17e0ff00df235de6203457))
* **serve:** local-graph depth slider (1-3 hops) ([#111](https://github.com/dfrostar/neuralmind/issues/111)) ([6760c3b](https://github.com/dfrostar/neuralmind/commit/6760c3b7f5043864dd5b08d4a0f9facd798e2382))
* **serve:** local-graph depth slider (1–3 hops) ([6760c3b](https://github.com/dfrostar/neuralmind/commit/6760c3b7f5043864dd5b08d4a0f9facd798e2382))
* **serve:** local-graph depth slider (1–3 hops) ([d5d8d0a](https://github.com/dfrostar/neuralmind/commit/d5d8d0a3569d21eaf07614dc580e09873478b369))
* **serve:** replay-last-query overlay closes the trust gap ([0802429](https://github.com/dfrostar/neuralmind/commit/0802429cd9491610c8cb11ab8fd51c98dab43ee2))
* **serve:** replay-last-query overlay closes the trust gap ([3f08e6b](https://github.com/dfrostar/neuralmind/commit/3f08e6b61c8d8674548be5f9fa828714c8cc5923))
* **serve:** visible pin glyph, Pin/Unpin button, Unpin-all ([987e6dc](https://github.com/dfrostar/neuralmind/commit/987e6dc713d6f097fc79c2c536501529e58d658d))
* **serve:** visible pin glyph, Pin/Unpin button, Unpin-all ([5894259](https://github.com/dfrostar/neuralmind/commit/5894259e42dac25da7b9e6b96fa1d5274375c07a))
* **serve:** visible pin glyph, Pin/Unpin button, Unpin-all ([#108](https://github.com/dfrostar/neuralmind/issues/108)) ([987e6dc](https://github.com/dfrostar/neuralmind/commit/987e6dc713d6f097fc79c2c536501529e58d658d))
* structural code-graph edge layer (calls/inherits/imports) ([#320](https://github.com/dfrostar/neuralmind/issues/320)) ([e3d33a2](https://github.com/dfrostar/neuralmind/commit/e3d33a2c57dbc3b60ebd2c3d171e9fb099897a07))
* **synapses:** directional transitions — learn what comes next ([#153](https://github.com/dfrostar/neuralmind/issues/153)) ([0fb3ee7](https://github.com/dfrostar/neuralmind/commit/0fb3ee7d607aac5962014b1837b50a5aa5d741b8))
* **synapse:** seed synapses from structural graph edges ([2049bbb](https://github.com/dfrostar/neuralmind/commit/2049bbb09f55e27acc721126b40d7d4b32532e83))
* team memory — agents inherit the team's learned associations ([#252](https://github.com/dfrostar/neuralmind/issues/252)) ([18aac97](https://github.com/dfrostar/neuralmind/commit/18aac97f0b7ae069a524b400f22f6fe38baa0a70))
* **tier1:** structural edges persistence, time-based half-life decay, migration version check ([ed43dfa](https://github.com/dfrostar/neuralmind/commit/ed43dfae975542d987e2d31107d9fe0b598b3c1d))
* **tier2:** free tier auto-provisioning + upgrade path ([1202845](https://github.com/dfrostar/neuralmind/commit/1202845354bdbcebdcbad2ed7b3726c9bfd53c76))
* **tier2:** Team tier 9/user/mo — governance, audit, license, seats, self-hosted ([2fb2fc2](https://github.com/dfrostar/neuralmind/commit/2fb2fc2e69a40cfc623f02a1f0c9ef9ed7312ea1))
* **tier2:** vendor skip, single backend, honest-first README, dead code cleanup ([241ca2b](https://github.com/dfrostar/neuralmind/commit/241ca2b96915840d110644cf9a36318250f4eb1b))
* v0.40.0 — dry-run build, deletion decay, --explain, review, savings dashboard ([e92a9f5](https://github.com/dfrostar/neuralmind/commit/e92a9f5577b041e8ee666f89e1c478c0f633aea0))
* **v0.50.0:** metrics CLI, /api/metrics endpoint, team memory integration test ([f31037a](https://github.com/dfrostar/neuralmind/commit/f31037a8ed9262c98fc0cc41c6a271bf4dafb2c5))
* **v0.52.0:** impact tool — reverse-dependency blast-radius lookup ([63a0f3f](https://github.com/dfrostar/neuralmind/commit/63a0f3f4a7c536714cb59fec498ea9180f7e2b2e))
* **v0.56.0:** team license portal + activate signature validation ([a61fee2](https://github.com/dfrostar/neuralmind/commit/a61fee219a01b5d12c9c4b36a45eba322a4cb24d))
* **v0.57.0:** seat governance hardening + free-tier bypass ([4029895](https://github.com/dfrostar/neuralmind/commit/4029895887fa80e14c5e8beceaea5e3372733149))
* versioned IR (PRD 1) + quality harness (PRD 2) + debug traces (PRD 3) + local daemon (PRD 5) ([#217](https://github.com/dfrostar/neuralmind/issues/217)) ([a62e635](https://github.com/dfrostar/neuralmind/commit/a62e6353a9dcd799c8cb3dfee321ac194c69be9a))
* VS Code native extension, BM25 hybrid search, explicit feedback, CI auto-index (v0.38.0) ([716c422](https://github.com/dfrostar/neuralmind/commit/716c4224ead33593d436359addacb4932a40c08f))
* Wave 1 execution — D quality harness, B1 IR migration, G1 dynamic imports ([ffce05c](https://github.com/dfrostar/neuralmind/commit/ffce05c56111ab29636106b564dc567c9c506dfe))
* **wave2:** C1/A1/A2/B2/B3/G2 — fitness, traces, entity resolution, sparse, rerank, SCIP ([74961be](https://github.com/dfrostar/neuralmind/commit/74961beebc7711c9cdb437f11ed52bde48ff11f0))
* **wave3:** C2/C3/A3/A4/B4/F1/F2 — expanded param space, population tuner, learned decay, sleep consolidation, summarization, MCP HTTP, shared daemon memory ([d94f40c](https://github.com/dfrostar/neuralmind/commit/d94f40c4ba89f993556c0e31b7024ea4de353ebe))
* **wave4:** C4/G3/G4/E1/E2/E3/E4/F3/F4/D3/D4 — modularity, team memory flywheel, CI-gated promotion, incremental extraction, backpressure, per-language fixtures ([c30050e](https://github.com/dfrostar/neuralmind/commit/c30050e370fd991d16d3fb668ad730a2a02805da))
* **wave5:** tuner faithfulness + incremental extraction wiring ([0467588](https://github.com/dfrostar/neuralmind/commit/0467588d09a9d7375d8ab1bfc4a0d08c9c309d0c))


### Bug Fixes

* adopt pr-fix-board branch (all audits applied) ([dab5a00](https://github.com/dfrostar/neuralmind/commit/dab5a00daaca5c186372090ce7a3bb958c390d1f))
* batch reinforce, concurrency test, auth-enabled server tests ([2eec7a8](https://github.com/dfrostar/neuralmind/commit/2eec7a8633bfb21090aef1a9825529b68ce593f3))
* bump + test_deterministic ([811b02c](https://github.com/dfrostar/neuralmind/commit/811b02c71d26e84306bf24c71b1e386e929aef85))
* bump version to 0.51.2 ([8d4048c](https://github.com/dfrostar/neuralmind/commit/8d4048cd9ea81eafb2c05c6f08d0d3ab4d1d6271))
* **ci:** complete lint sweep — all ruff errors patched ([e96b805](https://github.com/dfrostar/neuralmind/commit/e96b805f12e6886cb7a4701a7967437e5fc28931))
* **ci:** docker-publish version tag missing on workflow_dispatch ([#140](https://github.com/dfrostar/neuralmind/issues/140)) ([81da081](https://github.com/dfrostar/neuralmind/commit/81da081eee532c9fc4880ac5cc06943e27369673))
* **ci:** lint cleanup + tests package breakage ([76c8668](https://github.com/dfrostar/neuralmind/commit/76c8668924a0f501a54651fba9b80b2d293679d9))
* **ci:** patch stale test assertions post-wave4 cleanup ([5a13c16](https://github.com/dfrostar/neuralmind/commit/5a13c163c6d100e9aedf8c82504173266bdc84e6))
* **ci:** restore CI green — lint + test infra patches ([e19e631](https://github.com/dfrostar/neuralmind/commit/e19e631dfc636b240028dd3e7054cdedea971d3c))
* **ci:** use PAT for release-please so tag pushes trigger release.yml ([#126](https://github.com/dfrostar/neuralmind/issues/126)) ([d6fd9d9](https://github.com/dfrostar/neuralmind/commit/d6fd9d954b0f35aa4df44f8ac56d30250e1a8184))
* **ci:** use PAT for release-please so tag pushes trigger release.yml ([#98](https://github.com/dfrostar/neuralmind/issues/98)) ([81baac9](https://github.com/dfrostar/neuralmind/commit/81baac94345847fb91080e86f8f33b7efc62536c))
* **D3:** DeepSeek QA patches — 4 issues ([6de7ceb](https://github.com/dfrostar/neuralmind/commit/6de7ceb13277b40f153b465bca0d6d7f04c0f17f))
* DeepSeek QA patches — Waves 4-6 modules ([5d46e46](https://github.com/dfrostar/neuralmind/commit/5d46e463d204bccc994b81d2d110c21022c44257))
* **deepseek:** Tier 2 security + correctness patches across all 6 modules ([59bdfc3](https://github.com/dfrostar/neuralmind/commit/59bdfc37bb56c13e38f0d1a3af79517f4db4374f))
* **docker:** install graphifyy + pre-wheel transitive deps in builder ([b6297bd](https://github.com/dfrostar/neuralmind/commit/b6297bdc0809d8c76a52e926f7ace2b85fa1ebb8))
* **event_log:** keep reopen-at-start across failed open + missing-file ([db1816b](https://github.com/dfrostar/neuralmind/commit/db1816b0bab88afd8e64f6e4736620ad1bb4b1d4))
* **event_log:** reopen rotated logs from offset 0 ([#115](https://github.com/dfrostar/neuralmind/issues/115)) ([9b0ecd8](https://github.com/dfrostar/neuralmind/commit/9b0ecd819b4da0cd576f96823a1ec69cd7a1402d))
* force UTF-8 stdout/stderr in CLI to avoid Windows cp1252 crash ([#242](https://github.com/dfrostar/neuralmind/issues/242)) ([2db260a](https://github.com/dfrostar/neuralmind/commit/2db260a27260e14f07e5314c96071d8b60ce6b66))
* **G4/DeepSeek:** ignore-set drift patch + rationale_for comment ([d6c4f1f](https://github.com/dfrostar/neuralmind/commit/d6c4f1f7e5fbd0da1bf133c668171be68dbf0e85))
* **lint:** reapply ruff N806 fixes post-PR367 merge ([06ee806](https://github.com/dfrostar/neuralmind/commit/06ee806cc92ecd3488a037d3105f2370cb27dabb))
* make every neuralmind.uk proof link work + unblock the release pipeline ([#395](https://github.com/dfrostar/neuralmind/issues/395)) ([2fe0d85](https://github.com/dfrostar/neuralmind/commit/2fe0d8507280090b939a2bc6d088fba4a04e3787))
* make the test suite Windows-green and restore full Windows support ([#228](https://github.com/dfrostar/neuralmind/issues/228)) ([bd3daad](https://github.com/dfrostar/neuralmind/commit/bd3daadd6db1746edf4365ff99dea21cfa5d0350))
* MCP auth bypass, token persistence, cache cleanup, env var lazy load ([a0dd1f5](https://github.com/dfrostar/neuralmind/commit/a0dd1f568d891878beabfaea30a5262859140ac2))
* MCP server hang under concurrent SQLite write contention ([#363](https://github.com/dfrostar/neuralmind/issues/363)) ([2bff051](https://github.com/dfrostar/neuralmind/commit/2bff051738248c50d3318fe8b6531c8474009382))
* **modularity/DeepSeek:** patch 3 WARNINGs — remove dead code, dedup Phase 2 edges, fix falsy fallback ([f953001](https://github.com/dfrostar/neuralmind/commit/f953001227b738082f11faf4a2b9c048d2bd8644))
* **modularity/G3:** resolution param + O(n·k) Louvain + community wiring into build_graph ([3c65481](https://github.com/dfrostar/neuralmind/commit/3c654810c065fd5bc5d4d72c439dd45d91aa000e))
* **modularity+tests:** stale test_communities_are_per_file + Black drift on modularity.py ([a80f34a](https://github.com/dfrostar/neuralmind/commit/a80f34aed85f05e7f9e2cca13918956d30a02351))
* namespace-aware learned-decay update in reinforce(); deterministic stickiness test ([#389](https://github.com/dfrostar/neuralmind/issues/389)) ([82e6be7](https://github.com/dfrostar/neuralmind/commit/82e6be7221895c2276183cdc2074f8e594ad2c60))
* patch 2 CRITICAL findings from DeepSeek QA review ([1d05b6c](https://github.com/dfrostar/neuralmind/commit/1d05b6c335e496da19538205cd4c9b5a96769693))
* patch 5 critical + 6 warning findings from deepseek retrospective ([f45c2b0](https://github.com/dfrostar/neuralmind/commit/f45c2b0a4f11f0d75178949ed1e4f719f616654c))
* re-resolve memory namespace when a warm process crosses a git checkout ([32cd1e0](https://github.com/dfrostar/neuralmind/commit/32cd1e0c8af3ff13c64b8ab8e15510697c768fef))
* restore transaction atomicity in synapse reinforce/decay + honor auth=False ([#319](https://github.com/dfrostar/neuralmind/issues/319)) ([6457cf7](https://github.com/dfrostar/neuralmind/commit/6457cf71eda9092bae63c7c097c7da8d78aaa6d6))
* ruff format drift + sync manifest to 0.51.2 ([469b4c0](https://github.com/dfrostar/neuralmind/commit/469b4c021d40779a05dde2dd5f14f7a1add042c4))
* ruff N806 (MAX_EDGES→max_edges) + doctor test stale assertion ([2e51920](https://github.com/dfrostar/neuralmind/commit/2e519204810ad5cbd6cecc8c3713065cee21219b))
* **ruff:** sort imports in tier2/license.py (I001) ([2a8a26a](https://github.com/dfrostar/neuralmind/commit/2a8a26a185775b13ba1240dcb9fc40b34b56edcc))
* **serve:** address PR [#101](https://github.com/dfrostar/neuralmind/issues/101) review — graphify cmd, canvas sizing, race, a11y ([e3f5cdf](https://github.com/dfrostar/neuralmind/commit/e3f5cdffea8b9ac9ce1778e0fb20b7a05e69177e))
* **serve:** address PR [#105](https://github.com/dfrostar/neuralmind/issues/105) Copilot review — consent, races, a11y, tests ([37e1706](https://github.com/dfrostar/neuralmind/commit/37e17061e9e34c9308fc402d7663b5db50d31f7b))
* **serve:** address PR [#110](https://github.com/dfrostar/neuralmind/issues/110) review ([6afc5da](https://github.com/dfrostar/neuralmind/commit/6afc5daf5344d0bb4b09f6359942292a053909ee))
* **serve:** allowlist Popen path against precomputed safe set ([d4d5eb9](https://github.com/dfrostar/neuralmind/commit/d4d5eb993daab7ae602b61a21c07edcabd3113d0))
* **serve:** atomic append for recent_queries.jsonl — close cross-process race ([4b453b8](https://github.com/dfrostar/neuralmind/commit/4b453b8c7313d1901bf2fca97e30b787c3e0744b))
* **serve:** make depth slider truly inert when local graph is off ([b6a42a0](https://github.com/dfrostar/neuralmind/commit/b6a42a08afbd62ce34c27d02feb5d8b57bf1b1b0))
* stop suggesting graphify update as the fix for a missing graph ([#223](https://github.com/dfrostar/neuralmind/issues/223)) ([045008f](https://github.com/dfrostar/neuralmind/commit/045008fafc26eb2e64d4ad0dae0f598541831af8))
* **systemd:** use ReadWritePaths instead of invalid ProtectHome=read-write ([d7cfbd6](https://github.com/dfrostar/neuralmind/commit/d7cfbd6c7b1778c5808fff68e326aa9f8a6eddbc))
* **test:** +Inf clamps to hi, not lo — assertion was wrong ([039dda2](https://github.com/dfrostar/neuralmind/commit/039dda2ab2ed64b5645de183f1b9a9f4f72b1ebb))
* **tests:** skip tuner_faithfulness/v049_patches when chromadb missing ([271b236](https://github.com/dfrostar/neuralmind/commit/271b2364196cdcd7ea79ee4e36dcbf32ce5a788a))
* **tests:** test_deterministic self-contained to avoid pollution ([c4a9d16](https://github.com/dfrostar/neuralmind/commit/c4a9d16e664154986b667343f7c976758108be54))
* **tests:** update ephemeral decay tests for time-based half-life model ([111e83e](https://github.com/dfrostar/neuralmind/commit/111e83e9ff3752d0c59dcd4b563dd18385aac321))
* **tier1:** remove dead code, make decay_node time-based, align docs with impl ([34639cc](https://github.com/dfrostar/neuralmind/commit/34639cc3e7f214e21767a9fdc809e2cf054f7c1a))
* **v0.49.1:** patch 4 CRITICAL + 5 WARNING DeepSeek findings ([fa4b42b](https://github.com/dfrostar/neuralmind/commit/fa4b42b6b6830d9d96fd77790f4f3e41b48f47be))
* **v0.49.2:** apply DeepSeek patches — prune dangling edges, remove dead code, fix axis independence ([cc53555](https://github.com/dfrostar/neuralmind/commit/cc5355557d4f4ccf24d6475c44c7daec1c247412))
* **v0.8:** address Copilot review — XML validity, --no-browser, Windows time limit, healthcheck ([6e91bd5](https://github.com/dfrostar/neuralmind/commit/6e91bd586c2ad239e3b0c4ed2f8ceb72f3d3294d))
* **v0.9:** address Copilot review — case-safe + stable-only :latest + SBOM race + air-gapped TL;DR ([fdf8b4e](https://github.com/dfrostar/neuralmind/commit/fdf8b4e2900479b628bfe8e7f60bc41b67a668cf))
* **Wave 12:** DeepSeek QA 3 CRITICAL + 2 WARNING patched ([b2ad291](https://github.com/dfrostar/neuralmind/commit/b2ad291fab664987ed008839b5da8001fa1c8ed6))
* **Wave 12:** two CRITICAL DeepSeek findings actually patched now ([1d6384c](https://github.com/dfrostar/neuralmind/commit/1d6384cd78d45bed3d412048d8998a1b37a4a310))
* **wave12:** DeepSeek QA patches — 1 CRITICAL + 7 WARNING ([b82ab8d](https://github.com/dfrostar/neuralmind/commit/b82ab8d7467823126c162713ff0ce7b9e565a561))
* **wave3:** patch 4 critical + 8 warning findings from deepseek post-implementation review ([6d945ac](https://github.com/dfrostar/neuralmind/commit/6d945acf87df7e615cec945f32cf68b5babf68f8))
* **wave4:** clean deferred warnings — remove dead CI keys, phantom CI params, thread hysteresis through PromotionVerdict ([39aa5e7](https://github.com/dfrostar/neuralmind/commit/39aa5e75fba445400a1e8d00e4952b17ab2ee403))
* **wave4:** clean up deferred warnings from DeepSeek QA ([b2e3846](https://github.com/dfrostar/neuralmind/commit/b2e384657581ce72cd44354f6d1058a33c99d057))
* **wave4:** patch 3 CRITICAL + 6 WARNING findings from DeepSeek batch 1 ([98bd5fd](https://github.com/dfrostar/neuralmind/commit/98bd5fdc47bf00ea697ae4f31608df1a404b2fe8))


### Performance Improvements

* **turbovec:** skip numpy→list→numpy round-trip when indexing ([#212](https://github.com/dfrostar/neuralmind/issues/212)) ([e3e8914](https://github.com/dfrostar/neuralmind/commit/e3e89145610c14a598f8f60bd59be921ea2c46a3))


### Documentation

* add "US-based" signal to docs-site footers ([#335](https://github.com/dfrostar/neuralmind/issues/335)) ([83acb6f](https://github.com/dfrostar/neuralmind/commit/83acb6fa999e649a963af7448cf4dc56c0a27390))
* add contact channel and free AI-spend assessment offer ([#324](https://github.com/dfrostar/neuralmind/issues/324)) ([1475c45](https://github.com/dfrostar/neuralmind/commit/1475c45ab082058588e97d33f44efced86a78d13))
* add context engineering stack comparative guide ([5a21b39](https://github.com/dfrostar/neuralmind/commit/5a21b39ec0e796d9902bd581cb6f5dfb1bfcb596))
* add context engineering stack comparative guide (NeuralMind + Ponytail + Headroom) ([005ceba](https://github.com/dfrostar/neuralmind/commit/005ceba9e7746c6f6607d23c573e8306c10535d4))
* add Google Search Console site-verification file ([#237](https://github.com/dfrostar/neuralmind/issues/237)) ([c26c0ad](https://github.com/dfrostar/neuralmind/commit/c26c0ad1844a9afb12e97d78f81009fb0bbc20d3))
* add serve CLI ref + graph-view SEO keywords ([897b109](https://github.com/dfrostar/neuralmind/commit/897b1096680bd56f29a5d9d678b0f24f8b0e0bef))
* add session prompts, Wave 6 docs, code standards, module template ([485bfeb](https://github.com/dfrostar/neuralmind/commit/485bfeba6e62e7b87919fdb2de185a5ab2eb4260))
* add the Headroom comparison and fix the sitemap to same-host URLs ([#236](https://github.com/dfrostar/neuralmind/issues/236)) ([040a8ef](https://github.com/dfrostar/neuralmind/commit/040a8efd8d63d9f610e2f6cfc355836f3b1ec97e))
* add TRINODE.md positioning note + state the memory write policy ([#311](https://github.com/dfrostar/neuralmind/issues/311)) ([89d8b39](https://github.com/dfrostar/neuralmind/commit/89d8b39dc8dcbd515e37b0e70eb56c303dbb01b1))
* add upgrade check to session routine + Wave 4 prompt ([502cd41](https://github.com/dfrostar/neuralmind/commit/502cd411b5fbfa4193786ec3cb15d7ebc068a697))
* address Copilot review on [#132](https://github.com/dfrostar/neuralmind/issues/132) — wording precision + companion-page consistency ([3b11fd5](https://github.com/dfrostar/neuralmind/commit/3b11fd51d15b15e9e68a3fc75ddd8ec76b2f4111))
* announce graph view in README, landing, and about pages ([f27ff98](https://github.com/dfrostar/neuralmind/commit/f27ff986726132928b4b1f0859caa5435ed5604f))
* audit fixes for v0.46.0 release ([4f73a15](https://github.com/dfrostar/neuralmind/commit/4f73a157c4e72d73fa48d1a1df6e97266c1544c6))
* **benchmarks:** interactive community-benchmark dashboard at /benchmarks/ ([#158](https://github.com/dfrostar/neuralmind/issues/158)) ([7d4723b](https://github.com/dfrostar/neuralmind/commit/7d4723bcb10c371e60ce783e8d8fc2efae4eba7b))
* bump GraphQL roadmap target v0.41.0 → v0.42.0 ([#301](https://github.com/dfrostar/neuralmind/issues/301)) ([d641459](https://github.com/dfrostar/neuralmind/commit/d641459a63780e70ecadb2617d5cf824e1d01437))
* **C4:** CI-gated tuner promotion design — QualityHarness gate ([0295db3](https://github.com/dfrostar/neuralmind/commit/0295db300fc3b03c20d99ff9edcc1be5b6e4fc40))
* **claude.md:** list event_bus + server in layout ([6368fdb](https://github.com/dfrostar/neuralmind/commit/6368fdbebc20122fb965b098a81719cc7ccdc551))
* close the recurring critique — limits page, runnable benchmarks/, SWE-bench retrieval harness, security refresh + coverage scorecard ([#303](https://github.com/dfrostar/neuralmind/issues/303)) ([c5f9b4f](https://github.com/dfrostar/neuralmind/commit/c5f9b4faf7a53f14294365b0764fdcdde0ee00fc))
* commercial license + consulting agreement + cfo pitch deck ([94bce64](https://github.com/dfrostar/neuralmind/commit/94bce647d000da5c02c35f7f55aa2101745b4713))
* **compliance:** NIST + SOC 2 + GDPR one-pager + v0.9.0 release notes ([#120](https://github.com/dfrostar/neuralmind/issues/120)) ([5ac1c2d](https://github.com/dfrostar/neuralmind/commit/5ac1c2d7382173a80a9325ad7de69803a3fd7835))
* **contributing:** refresh bump-patch-for-minor-pre-major guidance ([0cc241d](https://github.com/dfrostar/neuralmind/commit/0cc241d95b3d2991a0e099167b1dc7562d6fc90c))
* correct marketing claims and point SEO at neuralmind.uk ([#321](https://github.com/dfrostar/neuralmind/issues/321)) ([1fe0cc6](https://github.com/dfrostar/neuralmind/commit/1fe0cc6c491d37d85e9920f1750c13fca618181d))
* correct replay overlay file path per [#107](https://github.com/dfrostar/neuralmind/issues/107) review ([7590e19](https://github.com/dfrostar/neuralmind/commit/7590e19f3cbef3592f4e8626faedfc7b4e238eac))
* correct v0.5.4 release labels in about page ([5b489cf](https://github.com/dfrostar/neuralmind/commit/5b489cf7998fb5da643474ea91e3557f877aeece))
* correct v0.5.4 release labels in about page ([ed1da09](https://github.com/dfrostar/neuralmind/commit/ed1da090e97f007dece26c0f03e04f9c3ef52827))
* correct version attribution — v0.43.0 provenance-only, cohesion + gaps are v0.44.0 ([#352](https://github.com/dfrostar/neuralmind/issues/352)) ([5160c3b](https://github.com/dfrostar/neuralmind/commit/5160c3ba7e937d7f1be93e837ad154773f1853c7))
* defensive publication — quality-weighted merge with conflict-driven decay ([31aac0e](https://github.com/dfrostar/neuralmind/commit/31aac0e7b39592ef249173ef97365e1d1e38851f))
* disclosed-maker launch kit under docs/launch/ ([#263](https://github.com/dfrostar/neuralmind/issues/263)) ([948f732](https://github.com/dfrostar/neuralmind/commit/948f73257203176c4831bd8a59637ed1147864ca))
* enrich schema.org JSON-LD on docs pages (SEO) ([#272](https://github.com/dfrostar/neuralmind/issues/272)) ([19b3eb5](https://github.com/dfrostar/neuralmind/commit/19b3eb500cd9ff58a94a2924527d8b2eb13c3a94))
* enterprise competition + monetization plan (open-core licensing brief) ([#349](https://github.com/dfrostar/neuralmind/issues/349)) ([844afb7](https://github.com/dfrostar/neuralmind/commit/844afb71a1ed21090a55cc280186d3f05975ba0e))
* establish a standard documentation process ([#176](https://github.com/dfrostar/neuralmind/issues/176)) ([9e4d014](https://github.com/dfrostar/neuralmind/commit/9e4d01415b78415b9f47d8b6316407a03c6ced93))
* fix audit-log path drift (docs described a file that doesn't exist) ([#332](https://github.com/dfrostar/neuralmind/issues/332)) ([0d6efd5](https://github.com/dfrostar/neuralmind/commit/0d6efd5f1b22911b7aaa43c9d8211319a337defb))
* fix benchmark release notes link to local file ([241d465](https://github.com/dfrostar/neuralmind/commit/241d465d6f0305578fb0ccc1d9e3bbb0abd1bce5))
* fix DeepSeek doc sweep — 5 issues ([793884d](https://github.com/dfrostar/neuralmind/commit/793884d3ce023a37bb2f97f8485e07d520f42663))
* fix release notes links to point to marketing repo ([a0c3fce](https://github.com/dfrostar/neuralmind/commit/a0c3fce29c6781fa06f1abb617af377c71f65bed))
* **G3:** add BRD, TRD, test plan (governance gap closure) ([47c288b](https://github.com/dfrostar/neuralmind/commit/47c288b06eec02d0e59a8cdc217204fa9cacf0a9))
* **handoff:** refresh session handoff for v0.40 + next-session roadmap ([#298](https://github.com/dfrostar/neuralmind/issues/298)) ([e3c2e15](https://github.com/dfrostar/neuralmind/commit/e3c2e156c49b5b564158f3faf5e70bd2c75bd4c6))
* **install:** build-locally Docker, dedupe pip line, scope verify snippet ([4796afc](https://github.com/dfrostar/neuralmind/commit/4796afc295c6b6d5bfadb5dd2708251322086766))
* **install:** five-path install matrix in README, wiki, comparisons ([#118](https://github.com/dfrostar/neuralmind/issues/118)) ([a4f0b9f](https://github.com/dfrostar/neuralmind/commit/a4f0b9febcc0d5a5449186a4ac8c54e89d366334))
* mark v0.23.0 as the latest release on the landing page ([#224](https://github.com/dfrostar/neuralmind/issues/224)) ([f72ff10](https://github.com/dfrostar/neuralmind/commit/f72ff10f9cb2b9d5c96eb14154f9d1ac59674875))
* mark v0.25.0 as the latest release on the landing page ([#231](https://github.com/dfrostar/neuralmind/issues/231)) ([edb5b05](https://github.com/dfrostar/neuralmind/commit/edb5b05d84a34b7d7a9ab0cd47f915ad07056cda))
* mark v0.26.0 as the latest release on the landing page ([#234](https://github.com/dfrostar/neuralmind/issues/234)) ([cbea018](https://github.com/dfrostar/neuralmind/commit/cbea01850ca476d1bce2f2fde0b2f6a82cb524e0))
* marketing measurement framework + rebuild verification ([fb22089](https://github.com/dfrostar/neuralmind/commit/fb22089462e61b96d11bc7d42ef383888beb62bb))
* **marketing:** v0.6.1 LinkedIn drafts, screencast script, NotebookLM pack ([#118](https://github.com/dfrostar/neuralmind/issues/118)) ([7cba04a](https://github.com/dfrostar/neuralmind/commit/7cba04a77d9f0c5aa055cbe019181b845da483cc))
* modernize guides to the no-graphify flow, fix all broken links ([#222](https://github.com/dfrostar/neuralmind/issues/222)) ([ba7e4d0](https://github.com/dfrostar/neuralmind/commit/ba7e4d0852fd22a2fe68558f0178a6f87e82a69e))
* move docs site to docs.neuralmind.uk subdomain ([#331](https://github.com/dfrostar/neuralmind/issues/331)) ([af5c26d](https://github.com/dfrostar/neuralmind/commit/af5c26d60e2239f3bbff1da7d3e1170c1e3fdde5))
* NeuralMind ↔ OpenHuman concept note ([1cf4595](https://github.com/dfrostar/neuralmind/commit/1cf45958e9e1747116e7d71402184a664c523720))
* next-release plan + eval-first roadmap announcement (v0.13→v0.16) ([#170](https://github.com/dfrostar/neuralmind/issues/170)) ([8d87d2b](https://github.com/dfrostar/neuralmind/commit/8d87d2bd16210c8d5810db85c0fa4b3c8455c913))
* **pilot:** corrected BRD and golden queries template ([#285](https://github.com/dfrostar/neuralmind/issues/285)) ([bfd34b3](https://github.com/dfrostar/neuralmind/commit/bfd34b30b397bfbfb3a98bf1489d407809bf86e9))
* **plan:** session accomplishments + E1.5 onboarding-lift eval handoff ([#197](https://github.com/dfrostar/neuralmind/issues/197)) ([86c6eba](https://github.com/dfrostar/neuralmind/commit/86c6eba9208ae25b2ed380e68d80b4dd3dba148d))
* position NeuralMind as four data-backed benefits, not just token reduction ([#261](https://github.com/dfrostar/neuralmind/issues/261)) ([d56d0bc](https://github.com/dfrostar/neuralmind/commit/d56d0bcb8a22ceb4bab80959bb83c384979cf6c4))
* **PRD:** Session-scoped memory — namespaces for orchestrated agents ([a8c23b6](https://github.com/dfrostar/neuralmind/commit/a8c23b6decff63ef5a71bedf250981f8bb3a5016))
* propagate v0.6.1 install matrix across README, wiki, Pages, ROADMAP ([fceea6b](https://github.com/dfrostar/neuralmind/commit/fceea6bb8b835646ccb2efe671f01be056776a4c))
* propagate v0.8.0 + v0.9.0 across README, wiki, Pages, ROADMAP ([fbf0fd3](https://github.com/dfrostar/neuralmind/commit/fbf0fd3946c41782e265a2bb7ac5834d06d4197e))
* propagate v0.8.0 + v0.9.0 across README, wiki, Pages, ROADMAP ([#132](https://github.com/dfrostar/neuralmind/issues/132)) ([fdfa35e](https://github.com/dfrostar/neuralmind/commit/fdfa35efdc8f73687047fb7727e13ec19bc58db2))
* purge forbidden absolute privacy claims (+CI guard) & document git-worktree workflow ([#316](https://github.com/dfrostar/neuralmind/issues/316)) ([#333](https://github.com/dfrostar/neuralmind/issues/333)) ([cae4a3c](https://github.com/dfrostar/neuralmind/commit/cae4a3c889c3ad80eadc87807458532a8319e7f9))
* README comparisons row, SEO meta tags, and unified-stack use-case walkthrough ([dad3298](https://github.com/dfrostar/neuralmind/commit/dad32984f835a2df9fa31d414176c88bd723c456))
* README comparisons row, SEO meta tags, and unified-stack use-case walkthrough ([540d3ad](https://github.com/dfrostar/neuralmind/commit/540d3ad26fbdf07b5c2808b2c4cf23c276fb82e1))
* redesign benchmarks dashboard and wiki pages to match site design system ([#327](https://github.com/dfrostar/neuralmind/issues/327)) ([801f34c](https://github.com/dfrostar/neuralmind/commit/801f34c5f56d9e1b7fb6b6abe3fc2dca68c61e79))
* redesign landing page — fix versions, links, quickstart, positioning ([#220](https://github.com/dfrostar/neuralmind/issues/220)) ([2602bf8](https://github.com/dfrostar/neuralmind/commit/2602bf83b014c4339de851b0d82f92214e2e9773))
* reflect v2.0 completion in HONEST-ASSESSMENT + README ([1d02b66](https://github.com/dfrostar/neuralmind/commit/1d02b6615d6e8f48146fc11d77dd2b8cfd448a74))
* reframe README + PyPI around persistent memory ([#154](https://github.com/dfrostar/neuralmind/issues/154)) ([33e50fa](https://github.com/dfrostar/neuralmind/commit/33e50fab66332d39d311ebe2e65c40faa079f4c0))
* refresh benchmark chart [skip ci] ([aa226e0](https://github.com/dfrostar/neuralmind/commit/aa226e0edbe4193f5e84ed0af6a332d5f0949fb8))
* refresh benchmark chart [skip ci] ([c421d10](https://github.com/dfrostar/neuralmind/commit/c421d10eca81b0c1f3b776ab5497e8237c92f6a3))
* refresh benchmark chart [skip ci] ([d1b62c0](https://github.com/dfrostar/neuralmind/commit/d1b62c0e13aa6515559c22bbdc4b838d63713603))
* refresh benchmark chart [skip ci] ([27cb48c](https://github.com/dfrostar/neuralmind/commit/27cb48c00b262226a1db7dcdc33428b79904e453))
* refresh benchmark chart [skip ci] ([8e4fc98](https://github.com/dfrostar/neuralmind/commit/8e4fc98f5b6d5bfbdd4107614f7ffd181970892c))
* refresh benchmark chart [skip ci] ([a2f20db](https://github.com/dfrostar/neuralmind/commit/a2f20dbeecd4eea806d7b4591588f1b0402ce486))
* refresh benchmark chart [skip ci] ([8ff1e0d](https://github.com/dfrostar/neuralmind/commit/8ff1e0df86f0ca5827731e216be99ebf942ce3ec))
* refresh benchmark chart [skip ci] ([b640818](https://github.com/dfrostar/neuralmind/commit/b6408181bc16512e5ce1d053fa9e61447548492c))
* refresh benchmark chart [skip ci] ([80a0216](https://github.com/dfrostar/neuralmind/commit/80a021628a5a6262e390cdea767003fe94622ce5))
* refresh benchmark chart [skip ci] ([4c8550e](https://github.com/dfrostar/neuralmind/commit/4c8550e7b6e7cecb51245da8eb7f7ccfc4755e1f))
* refresh launch handoff to v0.37.0 state ([#275](https://github.com/dfrostar/neuralmind/issues/275)) ([8dff2c1](https://github.com/dfrostar/neuralmind/commit/8dff2c1221bdca6779908669b095ed3abc140d3a))
* refresh launch handoff with next-session checklist ([#265](https://github.com/dfrostar/neuralmind/issues/265)) ([3fd424a](https://github.com/dfrostar/neuralmind/commit/3fd424a987f53069fe1aa939fe813aa6f9858fb0))
* refresh roadmap + landing pages with current graph-view plan ([31adc09](https://github.com/dfrostar/neuralmind/commit/31adc099f12e5b61e8984746b3b4f764c148662f))
* refresh roadmap + landing pages with current graph-view plan ([b9f2c80](https://github.com/dfrostar/neuralmind/commit/b9f2c8012b4421250fd3b9450f43fc2f25445e3e))
* refresh roadmap + landing pages with current graph-view plan ([#107](https://github.com/dfrostar/neuralmind/issues/107)) ([31adc09](https://github.com/dfrostar/neuralmind/commit/31adc099f12e5b61e8984746b3b4f764c148662f))
* refresh SEO structured data and sitemap to v0.38.0 state ([#288](https://github.com/dfrostar/neuralmind/issues/288)) ([82cb1e2](https://github.com/dfrostar/neuralmind/commit/82cb1e27372bc3cbdba12d10521e7bd9a562e9b5))
* **release:** address PR [#124](https://github.com/dfrostar/neuralmind/issues/124) review — v0.7→v0.8 forward refs ([c3477f1](https://github.com/dfrostar/neuralmind/commit/c3477f1d36523d79e4ba6cc508a25c0ddad3a1f7))
* **release:** rename v0.6.1 → v0.7.0 to match release-please ([#124](https://github.com/dfrostar/neuralmind/issues/124)) ([0c8fa0a](https://github.com/dfrostar/neuralmind/commit/0c8fa0a7b295ae2f4621d5210746c3190cf9a5b6))
* **release:** rename v0.6.1 → v0.7.0 to match release-please version ([3ce2da2](https://github.com/dfrostar/neuralmind/commit/3ce2da23b5b52cfffbf5c0b0bb79d9b47c02aa66))
* rename v0.40.0 → v0.39.0 across all public-facing surfaces ([#295](https://github.com/dfrostar/neuralmind/issues/295)) ([08f8f82](https://github.com/dfrostar/neuralmind/commit/08f8f82aa45ac0ab2706981d42be2776e50ad451))
* restore archival release notes v0.3.2–v0.45.0 to repo root ([8e8ff48](https://github.com/dfrostar/neuralmind/commit/8e8ff48ff96940cd481bc0c530d9a21a052d6982))
* roadmap v0.54.0 + Wave 9 license enforcement architecture ([9bcbc71](https://github.com/dfrostar/neuralmind/commit/9bcbc71f85eec8c7e4bd163fc355e68793bab117))
* **roadmap:** language expansion, impact tool, broader agent installs ([47df6e2](https://github.com/dfrostar/neuralmind/commit/47df6e21b85841b00d00b81f27919665c2ec5407))
* route internal docs to marketing repo ([8b942ea](https://github.com/dfrostar/neuralmind/commit/8b942ea15505118d9d21f24ceba1b08a64390e06))
* **security:** document chromadb CVE-2026-45829 has no fixed release ([#201](https://github.com/dfrostar/neuralmind/issues/201)) ([722d41c](https://github.com/dfrostar/neuralmind/commit/722d41c27e8ba305c0a116b5b1f213a108ff25de))
* SEO refresh — right-size meta tags, fix sitemap, add llms.txt ([#310](https://github.com/dfrostar/neuralmind/issues/310)) ([c2ebbde](https://github.com/dfrostar/neuralmind/commit/c2ebbde180448238611882b7953d5a78a1e3730b))
* showcase measured results — Benchmarks page, use cases, metrics ([#208](https://github.com/dfrostar/neuralmind/issues/208)) ([615c69b](https://github.com/dfrostar/neuralmind/commit/615c69bb2dc9fc562e88cc65a135b5c5f0a41b7f))
* **site:** rationalize and dismiss all 23 dependabot alerts ([17e61b8](https://github.com/dfrostar/neuralmind/commit/17e61b8beff2efd1f22cd0436e85a871336da79a))
* Tier 2 (Team) — BRD, TRD, Test Plan, DeepSeek QA, Kickoff Prompt ([331d9f1](https://github.com/dfrostar/neuralmind/commit/331d9f1422e7f22ccdc5d7d798222d8a3141cd7d))
* umbrella v0.37.0 release notes + Release-As 0.37.0 ([#273](https://github.com/dfrostar/neuralmind/issues/273)) ([f9c19ea](https://github.com/dfrostar/neuralmind/commit/f9c19ea078967df804d0a915d1db4224a905d3b4))
* update future-proofing planning artifacts ([#313](https://github.com/dfrostar/neuralmind/issues/313)) ([4cc98a8](https://github.com/dfrostar/neuralmind/commit/4cc98a863fd99f859efb5d017956ca3a0ab92e6b))
* update ROADMAP for v0.48.0 (v2.0 complete) ([fa5d825](https://github.com/dfrostar/neuralmind/commit/fa5d8255b3d7d38836488d815a5f8f489f48027f))
* update Wave 4 BRD/TRD/session prompt for C4 ship ([50ac2eb](https://github.com/dfrostar/neuralmind/commit/50ac2eb8fbe54db844e04a78eb6d4df6d8c07a86))
* **use-cases:** air-gapped install walkthrough ([#120](https://github.com/dfrostar/neuralmind/issues/120)) ([a40f1f9](https://github.com/dfrostar/neuralmind/commit/a40f1f9873b837917a2fd3720a11388b6d4a5316))
* v0.13.0 launch pass — release notes, banners, SEO, wiki, sitemap ([#180](https://github.com/dfrostar/neuralmind/issues/180)) ([e995804](https://github.com/dfrostar/neuralmind/commit/e9958043025fe45222b32e81d5e241fc40501e26))
* v0.14.0 launch pass — neuralmind eval + faithfulness measurement ([#184](https://github.com/dfrostar/neuralmind/issues/184)) ([ba7fe52](https://github.com/dfrostar/neuralmind/commit/ba7fe5258acc4cb6a1665305c6dd79c5cf439661))
* v0.47.0 audit fixes — synapse metric, turbovec default, graphify removal ([79f6879](https://github.com/dfrostar/neuralmind/commit/79f68792f413b92952df93c5fd814258f4b6b11b))
* v0.48.0 — update README, CHANGELOG, HONEST-ASSESSMENT, LinkedIn outreach for v2.0 completion ([e7de4c5](https://github.com/dfrostar/neuralmind/commit/e7de4c56c3e162846d5634acc5da736806a81876))
* v0.52.0 public docs + SEO refresh — impact tool, wiki backfill, LinkedIn messaging ([13256e5](https://github.com/dfrostar/neuralmind/commit/13256e54545cf3b143dc7a12e6b767c6be9d8064))
* **v0.6.0:** release notes, polish, multi-agent + notebooklm pack ([930dcca](https://github.com/dfrostar/neuralmind/commit/930dccaef284ae7a0e4f2d490dbb0dc52fda08a7))
* **v0.6.0:** release notes, polish, multi-agent + notebooklm pack ([c84cd93](https://github.com/dfrostar/neuralmind/commit/c84cd93541b8c59127652e50783a1af3f81465a2))
* **v0.6.0:** release notes, polish, multi-agent + notebooklm pack ([#113](https://github.com/dfrostar/neuralmind/issues/113)) ([930dcca](https://github.com/dfrostar/neuralmind/commit/930dccaef284ae7a0e4f2d490dbb0dc52fda08a7))
* Wave 12 DeepSeek QA final sweep report ([55f1195](https://github.com/dfrostar/neuralmind/commit/55f119588ee6e831d217072831c90a262ed719c4))
* Wave 12 post-build assessment — retrieval quality, discoverability ([15e9a7c](https://github.com/dfrostar/neuralmind/commit/15e9a7c048ff84ef003ef6d8e23f93343adf12d9))
* Wave 12 QA report — 3 CRITICAL + 9 WARNING patched ([fc100c5](https://github.com/dfrostar/neuralmind/commit/fc100c579a65e5b603565d50c51bb5b310c0effa))
* Wave 12 session prompt for Wave 4 kickoff ([bcc59f0](https://github.com/dfrostar/neuralmind/commit/bcc59f0f8c5a05a60ca684634050f4201e997e6a))
* wave 3 brd and trd ([cca22fc](https://github.com/dfrostar/neuralmind/commit/cca22fc322ee1929c013dc3c0a99f7f3f1f28fc1))
* wave 3 handoff ([397fb0c](https://github.com/dfrostar/neuralmind/commit/397fb0c32c878c0d29ea8fb2dfbd02a8c6f41a3e))
* Wave 4 BRD/TRD — v2.0 future-proofing plan complete ([23c49ff](https://github.com/dfrostar/neuralmind/commit/23c49ffff1cd4a429be4e4cd35ae8be9665ec6ac))
* Wave 4 session prompt v10.0 — F3 COMPLETE, F4 next ([e7eb973](https://github.com/dfrostar/neuralmind/commit/e7eb97340eafa1e5e94e7091bc4ccdd7cfa3dc3b))
* Wave 4 session prompt v11.0 — F4 COMPLETE, G3 next ([4572f0f](https://github.com/dfrostar/neuralmind/commit/4572f0f4eeb8476f3c0099cf9b76bbfbad47a2e1))
* Wave 4 session prompt v5.0 — E1 next ([890bc2c](https://github.com/dfrostar/neuralmind/commit/890bc2c67cde191b5cf1775c91eb87f5c89a69a9))
* **Wave 4:** BRD, TRD, session prompt, and standardized session routine ([f216a74](https://github.com/dfrostar/neuralmind/commit/f216a741f950e926cb86ccff4a011f9a4d54549c))
* Wave 5-6 module docstring audit + governance arg docs ([d4c0584](https://github.com/dfrostar/neuralmind/commit/d4c0584d0a69c784f6c98d29554796e2a93febd9))
* **WAVE4:** mark G3 shipped in BRD/TRD, update §3.10 to actual implementation ([4e2afbc](https://github.com/dfrostar/neuralmind/commit/4e2afbcf22e303059c457c8c6acd63c66e9c9cfa))
* **WAVE4:** next session prompt — G3+G4 implemented, release blocked on repo rules ([53bf43a](https://github.com/dfrostar/neuralmind/commit/53bf43aff9394e368d7314d91be6cd5528d4eb19))
* **WAVE4:** v12.0 session prompt + G3 QA report (G3 → DONE, G4 next) ([74e5740](https://github.com/dfrostar/neuralmind/commit/74e5740f2edec4b5a6c79c733bdd7df56660db7b))
* **WAVE4:** v13.0 session prompt — G3 complete, DeepSeek QA clean, v1.4.0 released ([68aee7a](https://github.com/dfrostar/neuralmind/commit/68aee7ae77f60f284053c0092a0560bf41a8b964))


### Miscellaneous Chores

* release as v0.31.0 (roll 0.30.0 into 0.31.0) ([#256](https://github.com/dfrostar/neuralmind/issues/256)) ([e70e157](https://github.com/dfrostar/neuralmind/commit/e70e157da924d1f44704b4da52ec391afb41b7dc))
* **release:** Release-As 0.8.0 override for always-on ([#128](https://github.com/dfrostar/neuralmind/issues/128)) ([aa1a026](https://github.com/dfrostar/neuralmind/commit/aa1a026360f06bd0e262eec4a13f6f567e4cba73))
* **release:** retarget release-please to 1.5.0 ([8ddfaa2](https://github.com/dfrostar/neuralmind/commit/8ddfaa2e21367bc3883102255c1a18d7f53a32eb))
* trigger v0.8.0 release with always-on work ([16c967b](https://github.com/dfrostar/neuralmind/commit/16c967be8d20330a4e566ade5392403f9f0b5066))


### Code Refactoring

* split core.py, remove deprecated enable_reranking, fix IR aliasing ([#318](https://github.com/dfrostar/neuralmind/issues/318)) ([82dd633](https://github.com/dfrostar/neuralmind/commit/82dd633f29761fcf50978656e5d43d88a133b56c))

## [1.4.0](https://github.com/dfrostar/neuralmind/compare/v1.3.0...v1.4.0) (2026-07-20)


### Features

* **E3:** peer review gate wired into team memory import ([485687f](https://github.com/dfrostar/neuralmind/commit/485687faf77ca8d63fa9d91f023e98e5efbaeaa3))
* **E4:** staleness detection wired into team memory + sleep + CLI ([3fe5a61](https://github.com/dfrostar/neuralmind/commit/3fe5a610087c8b2bf98dae4dd5f96520ceb71ba7))


### Bug Fixes

* **ruff:** sort imports in tier2/license.py (I001) ([2a8a26a](https://github.com/dfrostar/neuralmind/commit/2a8a26a185775b13ba1240dcb9fc40b34b56edcc))
* **Wave 12:** DeepSeek QA 3 CRITICAL + 2 WARNING patched ([b2ad291](https://github.com/dfrostar/neuralmind/commit/b2ad291fab664987ed008839b5da8001fa1c8ed6))
* **Wave 12:** two CRITICAL DeepSeek findings actually patched now ([1d6384c](https://github.com/dfrostar/neuralmind/commit/1d6384cd78d45bed3d412048d8998a1b37a4a310))


### Documentation

* defensive publication — quality-weighted merge with conflict-driven decay ([31aac0e](https://github.com/dfrostar/neuralmind/commit/31aac0e7b39592ef249173ef97365e1d1e38851f))
* marketing measurement framework + rebuild verification ([fb22089](https://github.com/dfrostar/neuralmind/commit/fb22089462e61b96d11bc7d42ef383888beb62bb))
* Wave 12 DeepSeek QA final sweep report ([55f1195](https://github.com/dfrostar/neuralmind/commit/55f119588ee6e831d217072831c90a262ed719c4))
* Wave 12 QA report — 3 CRITICAL + 9 WARNING patched ([fc100c5](https://github.com/dfrostar/neuralmind/commit/fc100c579a65e5b603565d50c51bb5b310c0effa))
* Wave 4 session prompt v10.0 — F3 COMPLETE, F4 next ([e7eb973](https://github.com/dfrostar/neuralmind/commit/e7eb97340eafa1e5e94e7091bc4ccdd7cfa3dc3b))
* Wave 4 session prompt v11.0 — F4 COMPLETE, G3 next ([4572f0f](https://github.com/dfrostar/neuralmind/commit/4572f0f4eeb8476f3c0099cf9b76bbfbad47a2e1))

## [1.3.0](https://github.com/dfrostar/neuralmind/compare/v1.2.0...v1.3.0) (2026-07-20)


### Features

* **E3:** peer review gate wired into team memory import ([f1f4913](https://github.com/dfrostar/neuralmind/commit/f1f4913736944dc8e0a6415cd46039e616ec0fc6))


### Documentation

* fix DeepSeek doc sweep — 5 issues ([793884d](https://github.com/dfrostar/neuralmind/commit/793884d3ce023a37bb2f97f8485e07d520f42663))

## [1.2.0](https://github.com/dfrostar/neuralmind/compare/v1.1.1...v1.2.0) (2026-07-20)


### Features

* **C4:** CI-gated tuner promotion via QualityHarness ([7e7ff98](https://github.com/dfrostar/neuralmind/commit/7e7ff989b2982d76bae82329c8bfe11cf099f873))
* **D3:** judge transcripts loader + generator ([e232b15](https://github.com/dfrostar/neuralmind/commit/e232b152a39f40e714ff086cfab672e2e28d3748))
* **E1:** contribution-quality scoring — ContributionQualityScorer + team_memory wiring ([2969e38](https://github.com/dfrostar/neuralmind/commit/2969e3873cbbbde136b5d3b55cc4dcdf24a9e527))
* **E1:** contribution-quality scoring — ContributionQualityScorer + team_memory wiring ([c7d5a86](https://github.com/dfrostar/neuralmind/commit/c7d5a860a9201b029057c4cb4b933e8db1be6c95))
* **E2:** quality-weighted merge semantics with decay-on-conflict ([43d4ef4](https://github.com/dfrostar/neuralmind/commit/43d4ef4c84e06b820ffb68a251029a5b4a1c2684))


### Bug Fixes

* **D3:** DeepSeek QA patches — 4 issues ([6de7ceb](https://github.com/dfrostar/neuralmind/commit/6de7ceb13277b40f153b465bca0d6d7f04c0f17f))
* **wave12:** DeepSeek QA patches — 1 CRITICAL + 7 WARNING ([b82ab8d](https://github.com/dfrostar/neuralmind/commit/b82ab8d7467823126c162713ff0ce7b9e565a561))


### Documentation

* add upgrade check to session routine + Wave 4 prompt ([502cd41](https://github.com/dfrostar/neuralmind/commit/502cd411b5fbfa4193786ec3cb15d7ebc068a697))
* **C4:** CI-gated tuner promotion design — QualityHarness gate ([0295db3](https://github.com/dfrostar/neuralmind/commit/0295db300fc3b03c20d99ff9edcc1be5b6e4fc40))
* **PRD:** Session-scoped memory — namespaces for orchestrated agents ([a8c23b6](https://github.com/dfrostar/neuralmind/commit/a8c23b6decff63ef5a71bedf250981f8bb3a5016))
* refresh benchmark chart [skip ci] ([aa226e0](https://github.com/dfrostar/neuralmind/commit/aa226e0edbe4193f5e84ed0af6a332d5f0949fb8))
* update Wave 4 BRD/TRD/session prompt for C4 ship ([50ac2eb](https://github.com/dfrostar/neuralmind/commit/50ac2eb8fbe54db844e04a78eb6d4df6d8c07a86))
* Wave 4 session prompt v5.0 — E1 next ([890bc2c](https://github.com/dfrostar/neuralmind/commit/890bc2c67cde191b5cf1775c91eb87f5c89a69a9))
* **Wave 4:** BRD, TRD, session prompt, and standardized session routine ([f216a74](https://github.com/dfrostar/neuralmind/commit/f216a741f950e926cb86ccff4a011f9a4d54549c))

## [1.1.1](https://github.com/dfrostar/neuralmind/compare/v1.1.0...v1.1.1) (2026-07-20)


### Documentation

* Wave 12 post-build assessment — retrieval quality, discoverability ([15e9a7c](https://github.com/dfrostar/neuralmind/commit/15e9a7c048ff84ef003ef6d8e23f93343adf12d9))
* Wave 12 session prompt for Wave 4 kickoff ([bcc59f0](https://github.com/dfrostar/neuralmind/commit/bcc59f0f8c5a05a60ca684634050f4201e997e6a))

## [1.1.0](https://github.com/dfrostar/neuralmind/compare/v1.0.0...v1.1.0) (2026-07-20)


### Features

* **license:** v0.55.0 — anti-tamper DI, TAMPERED status, clock-skew activation ([8bc2990](https://github.com/dfrostar/neuralmind/commit/8bc29907560fa6d27e813bf74017db60ef8a4cf7))
* **security:** real Ed25519 keypair, Privacy Policy, Stripe webhook security, lessons learned ([01fc1f0](https://github.com/dfrostar/neuralmind/commit/01fc1f0c4db6b5d38f82bc8b014dcadf44577a8c))
* **tier2:** free tier auto-provisioning + upgrade path ([1202845](https://github.com/dfrostar/neuralmind/commit/1202845354bdbcebdcbad2ed7b3726c9bfd53c76))
* **v0.56.0:** team license portal + activate signature validation ([a61fee2](https://github.com/dfrostar/neuralmind/commit/a61fee219a01b5d12c9c4b36a45eba322a4cb24d))
* **v0.57.0:** seat governance hardening + free-tier bypass ([4029895](https://github.com/dfrostar/neuralmind/commit/4029895887fa80e14c5e8beceaea5e3372733149))


### Bug Fixes

* DeepSeek QA patches — Waves 4-6 modules ([5d46e46](https://github.com/dfrostar/neuralmind/commit/5d46e463d204bccc994b81d2d110c21022c44257))
* ruff N806 (MAX_EDGES→max_edges) + doctor test stale assertion ([2e51920](https://github.com/dfrostar/neuralmind/commit/2e519204810ad5cbd6cecc8c3713065cee21219b))
* **test:** +Inf clamps to hi, not lo — assertion was wrong ([039dda2](https://github.com/dfrostar/neuralmind/commit/039dda2ab2ed64b5645de183f1b9a9f4f72b1ebb))


### Documentation

* add session prompts, Wave 6 docs, code standards, module template ([485bfeb](https://github.com/dfrostar/neuralmind/commit/485bfeba6e62e7b87919fdb2de185a5ab2eb4260))
* roadmap v0.54.0 + Wave 9 license enforcement architecture ([9bcbc71](https://github.com/dfrostar/neuralmind/commit/9bcbc71f85eec8c7e4bd163fc355e68793bab117))
* Wave 5-6 module docstring audit + governance arg docs ([d4c0584](https://github.com/dfrostar/neuralmind/commit/d4c0584d0a69c784f6c98d29554796e2a93febd9))

## [0.53.0](https://github.com/dfrostar/neuralmind/compare/v0.52.0...v0.53.0) (2026-07-19)


### Features

* **tier2:** free tier auto-provisioning + upgrade path ([1202845](https://github.com/dfrostar/neuralmind/commit/1202845354bdbcebdcbad2ed7b3726c9bfd53c76))
* **tier2:** Team tier 9/user/mo — governance, audit, license, seats, self-hosted ([2fb2fc2](https://github.com/dfrostar/neuralmind/commit/2fb2fc2e69a40cfc623f02a1f0c9ef9ed7312ea1))


### Bug Fixes

* **deepseek:** Tier 2 security + correctness patches across all 6 modules ([59bdfc3](https://github.com/dfrostar/neuralmind/commit/59bdfc37bb56c13e38f0d1a3af79517f4db4374f))


### Documentation

* fix benchmark release notes link to local file ([241d465](https://github.com/dfrostar/neuralmind/commit/241d465d6f0305578fb0ccc1d9e3bbb0abd1bce5))
* restore archival release notes v0.3.2–v0.45.0 to repo root ([8e8ff48](https://github.com/dfrostar/neuralmind/commit/8e8ff48ff96940cd481bc0c530d9a21a052d6982))
* Tier 2 (Team) — BRD, TRD, Test Plan, DeepSeek QA, Kickoff Prompt ([331d9f1](https://github.com/dfrostar/neuralmind/commit/331d9f1422e7f22ccdc5d7d798222d8a3141cd7d))
* v0.52.0 public docs + SEO refresh — impact tool, wiki backfill, LinkedIn messaging ([13256e5](https://github.com/dfrostar/neuralmind/commit/13256e54545cf3b143dc7a12e6b767c6be9d8064))

## [0.52.0](https://github.com/dfrostar/neuralmind/compare/v0.51.3...v0.52.0) (2026-07-19)


### Features

* **v0.52.0:** impact tool — reverse-dependency blast-radius lookup ([63a0f3f](https://github.com/dfrostar/neuralmind/commit/63a0f3f4a7c536714cb59fec498ea9180f7e2b2e))

## [0.51.3](https://github.com/dfrostar/neuralmind/compare/v0.51.2...v0.51.3) (2026-07-19)


### Bug Fixes

* ruff format drift + sync manifest to 0.51.2 ([469b4c0](https://github.com/dfrostar/neuralmind/commit/469b4c021d40779a05dde2dd5f14f7a1add042c4))

## [0.49.5](https://github.com/dfrostar/neuralmind/compare/v0.49.4...v0.49.5) (2026-07-18)


### Bug Fixes

* **lint:** reapply ruff N806 fixes post-PR367 merge ([06ee806](https://github.com/dfrostar/neuralmind/commit/06ee806cc92ecd3488a037d3105f2370cb27dabb))

## [0.49.4](https://github.com/dfrostar/neuralmind/compare/v0.49.3...v0.49.4) (2026-07-18)


### Bug Fixes

* **ci:** complete lint sweep — all ruff errors patched ([e96b805](https://github.com/dfrostar/neuralmind/commit/e96b805f12e6886cb7a4701a7967437e5fc28931))

## [0.49.3](https://github.com/dfrostar/neuralmind/compare/v0.49.2...v0.49.3) (2026-07-18)


### Bug Fixes

* **ci:** complete lint sweep — all ruff errors patched ([e96b805](https://github.com/dfrostar/neuralmind/commit/e96b805f12e6886cb7a4701a7967437e5fc28931))
* **ci:** lint cleanup + tests package breakage ([76c8668](https://github.com/dfrostar/neuralmind/commit/76c8668924a0f501a54651fba9b80b2d293679d9))
* **ci:** patch stale test assertions post-wave4 cleanup ([5a13c16](https://github.com/dfrostar/neuralmind/commit/5a13c163c6d100e9aedf8c82504173266bdc84e6))
* **ci:** restore CI green — lint + test infra patches ([e19e631](https://github.com/dfrostar/neuralmind/commit/e19e631dfc636b240028dd3e7054cdedea971d3c))

## [0.48.0](https://github.com/dfrostar/neuralmind/compare/v0.47.1...v0.48.0) (2026-07-17)


### Features — Wave 4 completes NeuralMind v2.0

> **v2.0 is complete.** Four waves, 26 workstreams, 7 buckets. The future-proofing plan v2.0 is fully implemented.

* **CI-gated tuner promotion (C4)**: wraps the population tuner (C3) with a fixture-evaluated promotion gate — runs `neuralmind benchmark --tuner-ci`, promotes only if fitness beats incumbent by hysteresis margin
* **Modularity clustering (G3)**: Louvain clustering over structural edges replaces balanced-per-file communities; `detect_structural_communities()` returns architecturally-boundary communities for L2
* **Incremental re-extraction (G4)**: `IncrementalExtractor` tracks file content hashes; builds re-extract symbols and callers/importers from changed files only
* **Contribution-quality scoring (E1)**: `ContributionQualityScorer` scores edges by reinforcement frequency + recency − conflict rate; gates promotion to `shared` namespace
* **Quality-weighted merge semantics (E2)**: `QualityWeightedMerger` resolves conflicting edges from two contributors by quality score instead of last-write-wins
* **Peer review gate (E3)**: `PeerReviewGate` auto-promotes high-quality edges, flags marginal ones for review, rejects very-low-quality edges
* **Team staleness detection (E4)**: `TeamStalenessDetector` applies accelerated decay to team edges with no reinforcement in N days (30/14 day thresholds)
* **Tool-use metrics pipeline (F3)**: `MetricsCollector` logs per-query latency, retrieval reuse rate, tool success rate, token cost to bounded JSONL files under `.neuralmind/metrics/`
* **Backpressure + circuit breakers (F4)**: `ProjectBackpressure`, `CircuitBreaker`, `ProjectLock` for graceful degradation under concurrent daemon/query/watch
* **Judge transcripts (D3)**: populated `bench/public/judge/` with fixture queries and reference answers for offline `--judge` evaluation
* **Per-language fixtures (D4)**: registered C#, Ruby, PHP suites in `evals/quality/runner.py` — 10-language golden-query coverage (128 queries across 10 fixtures)


### Writes

* **New modules**: `neuralmind/ci_tuner.py`, `neuralmind/modularity.py`, `neuralmind/incremental_extract.py`, `neuralmind/contribution_scoring.py`, `neuralmind/merge_semantics.py`, `neuralmind/peer_review.py`, `neuralmind/team_staleness.py`, `neuralmind/metrics_pipeline.py`, `neuralmind/backpressure.py`, `neuralmind/judge_transcripts.py`


### Tests

* 38 new tests across 8 test files; all 1374 tests pass

## [0.47.1](https://github.com/dfrostar/neuralmind/compare/v0.47.0...v0.47.1) (2026-07-17)


### Bug Fixes

* **ci**: black formatting drift across 16 files — no logic changes, purely formatting. Re-releases v0.47.0 content with clean lint gate.

## [0.47.0](https://github.com/dfrostar/neuralmind/compare/v0.46.2...v0.47.0) (2026-07-17)


### Features

* **quality harness (D)**: RAGAS-axis offline judge at `neuralmind/ragas.py` — faithfulness, context precision, context recall, answer relevance. Faithfulness is stdlib-only and CI-gated; cosine columns use injectable `embed_fn` for model-free CI ([7948edc](https://github.com/dfrostar/neuralmind/commit/7948edc))
* **quality harness (D)**: nDCG@k and hit-rate@k metrics added to `neuralmind/quality.py` alongside MRR, answerability, precision/recall — per-language fixtures for 7 languages registered in `evals/quality/runner.py`
* **IR migration (B1)**: embedder now reads `.neuralmind/index_ir.json` as the canonical source with `graphify-out/graph.json` mtime-fallback. The IR is no longer write-only archival — it's the live read path. All three backends (GraphEmbedder, TurboVecEmbedder, InMemoryEmbeddingBackend) + `core.py` + `server.py` updated
* **dynamic import resolution (G1)**: `add_edge` gains `confidence_score` param; Python/TS/Ruby dynamic import resolvers emit deterministic edges for string-literal imports (confidence 1.0), variable-const lookups (0.8), and synthetic `ext__` nodes for unresolvable dynamics (0.2). `SCHEMA_VERSION` 1→2

### Tests

* 14 IR migration tests in `tests/test_ir_load.py`; 12 dynamic import tests in `tests/test_graphgen.py`; 11 new RAGAS + nDCG + hit-rate tests in `tests/test_quality_harness.py`

## [0.46.2](https://github.com/dfrostar/neuralmind/compare/v0.46.0...v0.46.2) (2026-07-17)


### Bug Fixes

* **mcp_server.py**: run MCP tool handler via `asyncio.to_thread()` to keep the asyncio event loop free during SQLite lock contention — prevents MCP timeout hangs when two `neuralmind-mcp` processes target the same project ([a8c2063](https://github.com/dfrostar/neuralmind/commit/a8c2063))
* **synapses.py**: raise SQLite busy timeout from 5s to 30s so transient write contention resolves without failing writes under concurrent access


### Tests

* **test_mcp_server.py**: verify SynapseStore busy timeout is 30s — regression guard for #363

## [0.46.0](https://github.com/dfrostar/neuralmind/compare/v0.45.0...v0.46.0) (2026-07-17)


### Features

* **synapse:** seed synapses from structural graph edges — `seed_from_structural()` persists weighted code-to-code synapses derived from the structural_edges table on every build, so the learned-association layer starts with real architectural signal instead of waiting weeks for co-activation to accumulate. Seeded edges land in `shared` namespace (60-day half-life), weights are log-scaled by call_count and capped at 0.60. Wired into `core.py build()` after `persist_structural_edges()` with fail-open pattern. ([2049bbb](https://github.com/dfrostar/neuralmind/commit/2049bbb))


### Documentation

* audit fixes for v0.46.0 release — archive stale NEXT-RELEASE-PLAN.md (v0.13→v0.16, project at v0.45), bump ROADMAP.md banner to v0.45.0, correct README synapse A/B claim (+12pts → +11.6pts, 71.7%→83.3%), remove unverifiable +6.5pts claim, fix HONEST-ASSESSMENT.md install instructions (graphifyy optional since v0.15) ([4f73a15](https://github.com/dfrostar/neuralmind/commit/4f73a15))
* fix stale `test_doctor.py` assertions — `test_backend_check_reports_auto_resolution` and `test_backend_check_treats_null_config_as_auto` expected "graph" in detail but v0.29+ resolves auto to turbovec; updated to match `doctor._check_backend` actual output

## [0.45.0](https://github.com/dfrostar/neuralmind/compare/v0.44.0...v0.45.0) (2026-07-16)


### Features

* dollar-cost reporting for `neuralmind savings` (--cost) ([#353](https://github.com/dfrostar/neuralmind/issues/353)) ([5eb60f6](https://github.com/dfrostar/neuralmind/commit/5eb60f67a8523e85843c07fcf42ad2781adfd345))

## [0.44.0](https://github.com/dfrostar/neuralmind/compare/v0.43.0...v0.44.0) (2026-07-16)


### Features

* complete the v0.43.0 trio — cohesion outlier detection + neuralmind gaps ([#343](https://github.com/dfrostar/neuralmind/issues/343)) ([c0cfa24](https://github.com/dfrostar/neuralmind/commit/c0cfa24f226470a125c0b832f99a2eb7c8457c33))


### Documentation

* correct version attribution — v0.43.0 provenance-only, cohesion + gaps are v0.44.0 ([#352](https://github.com/dfrostar/neuralmind/issues/352)) ([5160c3b](https://github.com/dfrostar/neuralmind/commit/5160c3ba7e937d7f1be93e837ad154773f1853c7))
* enterprise competition + monetization plan (open-core licensing brief) ([#349](https://github.com/dfrostar/neuralmind/issues/349)) ([844afb7](https://github.com/dfrostar/neuralmind/commit/844afb71a1ed21090a55cc280186d3f05975ba0e))

## [0.43.0](https://github.com/dfrostar/neuralmind/compare/v0.42.1...v0.43.0) (2026-07-15)


### Features

* decision provenance — recall why code is the way it is ([#340](https://github.com/dfrostar/neuralmind/issues/340)) ([9961562](https://github.com/dfrostar/neuralmind/commit/9961562b0e351e56e98753d051b83a73999e4ccc))

## [0.42.1](https://github.com/dfrostar/neuralmind/compare/v0.42.0...v0.42.1) (2026-07-13)


### Documentation

* add "US-based" signal to docs-site footers ([#335](https://github.com/dfrostar/neuralmind/issues/335)) ([83acb6f](https://github.com/dfrostar/neuralmind/commit/83acb6fa999e649a963af7448cf4dc56c0a27390))
* add contact channel and free AI-spend assessment offer ([#324](https://github.com/dfrostar/neuralmind/issues/324)) ([1475c45](https://github.com/dfrostar/neuralmind/commit/1475c45ab082058588e97d33f44efced86a78d13))
* add TRINODE.md positioning note + state the memory write policy ([#311](https://github.com/dfrostar/neuralmind/issues/311)) ([89d8b39](https://github.com/dfrostar/neuralmind/commit/89d8b39dc8dcbd515e37b0e70eb56c303dbb01b1))
* correct marketing claims and point SEO at neuralmind.uk ([#321](https://github.com/dfrostar/neuralmind/issues/321)) ([1fe0cc6](https://github.com/dfrostar/neuralmind/commit/1fe0cc6c491d37d85e9920f1750c13fca618181d))
* fix audit-log path drift (docs described a file that doesn't exist) ([#332](https://github.com/dfrostar/neuralmind/issues/332)) ([0d6efd5](https://github.com/dfrostar/neuralmind/commit/0d6efd5f1b22911b7aaa43c9d8211319a337defb))
* move docs site to docs.neuralmind.uk subdomain ([#331](https://github.com/dfrostar/neuralmind/issues/331)) ([af5c26d](https://github.com/dfrostar/neuralmind/commit/af5c26d60e2239f3bbff1da7d3e1170c1e3fdde5))
* purge forbidden absolute privacy claims (+CI guard) & document git-worktree workflow ([#316](https://github.com/dfrostar/neuralmind/issues/316)) ([#333](https://github.com/dfrostar/neuralmind/issues/333)) ([cae4a3c](https://github.com/dfrostar/neuralmind/commit/cae4a3c889c3ad80eadc87807458532a8319e7f9))
* redesign benchmarks dashboard and wiki pages to match site design system ([#327](https://github.com/dfrostar/neuralmind/issues/327)) ([801f34c](https://github.com/dfrostar/neuralmind/commit/801f34c5f56d9e1b7fb6b6abe3fc2dca68c61e79))
* refresh benchmark chart [skip ci] ([c421d10](https://github.com/dfrostar/neuralmind/commit/c421d10eca81b0c1f3b776ab5497e8237c92f6a3))

## [0.42.0](https://github.com/dfrostar/neuralmind/compare/v0.41.0...v0.42.0) (2026-07-12)


### ⚠ BREAKING CHANGES

* NeuralMind.__init__ no longer accepts the enable_reranking keyword and instances no longer expose an enable_reranking attribute. The parameter had been deprecated and ignored since v0.25.0; the synapse layer supersedes the reranker it once gated.

### Features

* structural code-graph edge layer (calls/inherits/imports) ([#320](https://github.com/dfrostar/neuralmind/issues/320)) ([e3d33a2](https://github.com/dfrostar/neuralmind/commit/e3d33a2c57dbc3b60ebd2c3d171e9fb099897a07))


### Bug Fixes

* adopt pr-fix-board branch (all audits applied) ([dab5a00](https://github.com/dfrostar/neuralmind/commit/dab5a00daaca5c186372090ce7a3bb958c390d1f))
* batch reinforce, concurrency test, auth-enabled server tests ([2eec7a8](https://github.com/dfrostar/neuralmind/commit/2eec7a8633bfb21090aef1a9825529b68ce593f3))
* MCP auth bypass, token persistence, cache cleanup, env var lazy load ([a0dd1f5](https://github.com/dfrostar/neuralmind/commit/a0dd1f568d891878beabfaea30a5262859140ac2))
* restore transaction atomicity in synapse reinforce/decay + honor auth=False ([#319](https://github.com/dfrostar/neuralmind/issues/319)) ([6457cf7](https://github.com/dfrostar/neuralmind/commit/6457cf71eda9092bae63c7c097c7da8d78aaa6d6))


### Documentation

* bump GraphQL roadmap target v0.41.0 → v0.42.0 ([#301](https://github.com/dfrostar/neuralmind/issues/301)) ([d641459](https://github.com/dfrostar/neuralmind/commit/d641459a63780e70ecadb2617d5cf824e1d01437))
* close the recurring critique — limits page, runnable benchmarks/, SWE-bench retrieval harness, security refresh + coverage scorecard ([#303](https://github.com/dfrostar/neuralmind/issues/303)) ([c5f9b4f](https://github.com/dfrostar/neuralmind/commit/c5f9b4faf7a53f14294365b0764fdcdde0ee00fc))
* commercial license + consulting agreement + cfo pitch deck ([94bce64](https://github.com/dfrostar/neuralmind/commit/94bce647d000da5c02c35f7f55aa2101745b4713))
* refresh benchmark chart [skip ci] ([d1b62c0](https://github.com/dfrostar/neuralmind/commit/d1b62c0e13aa6515559c22bbdc4b838d63713603))
* SEO refresh — right-size meta tags, fix sitemap, add llms.txt ([#310](https://github.com/dfrostar/neuralmind/issues/310)) ([c2ebbde](https://github.com/dfrostar/neuralmind/commit/c2ebbde180448238611882b7953d5a78a1e3730b))
* update future-proofing planning artifacts ([#313](https://github.com/dfrostar/neuralmind/issues/313)) ([4cc98a8](https://github.com/dfrostar/neuralmind/commit/4cc98a863fd99f859efb5d017956ca3a0ab92e6b))


### Code Refactoring

* split core.py, remove deprecated enable_reranking, fix IR aliasing ([#318](https://github.com/dfrostar/neuralmind/issues/318)) ([82dd633](https://github.com/dfrostar/neuralmind/commit/82dd633f29761fcf50978656e5d43d88a133b56c))

## [0.41.0](https://github.com/dfrostar/neuralmind/compare/v0.40.0...v0.41.0) (2026-06-29)


### Features

* reuse-vs-rewrite feedback loop + structured relevance sidecar (v0.41.0) ([a27dc57](https://github.com/dfrostar/neuralmind/commit/a27dc57adf888d79a82ecb2cf56f0131c20465b0))


### Documentation

* **handoff:** refresh session handoff for v0.40 + next-session roadmap ([#298](https://github.com/dfrostar/neuralmind/issues/298)) ([e3c2e15](https://github.com/dfrostar/neuralmind/commit/e3c2e156c49b5b564158f3faf5e70bd2c75bd4c6))

## [0.40.0](https://github.com/dfrostar/neuralmind/compare/v0.39.0...v0.40.0) (2026-06-29)


### Features

* index OpenAPI, SQL DDL, and Protobuf schema artifacts (v0.40.0) ([#296](https://github.com/dfrostar/neuralmind/issues/296)) ([a482ffd](https://github.com/dfrostar/neuralmind/commit/a482ffd0df10a5267674f5edd5a721a4b0443e44))

## [0.39.0](https://github.com/dfrostar/neuralmind/compare/v0.38.0...v0.39.0) (2026-06-29)


### Features

* `neuralmind probe` queries by docstring/rationale + review hardening ([#292](https://github.com/dfrostar/neuralmind/issues/292)) ([745169a](https://github.com/dfrostar/neuralmind/commit/745169a18b53b3678d2c6b329d974617d8f38859))
* add neuralmind probe — label-free retrieval self-test on your own codebase ([4dceb99](https://github.com/dfrostar/neuralmind/commit/4dceb99c57c3551630fa0a0b27f643e1a08c0713)), closes [#241](https://github.com/dfrostar/neuralmind/issues/241)
* v0.40.0 — dry-run build, deletion decay, --explain, review, savings dashboard ([e92a9f5](https://github.com/dfrostar/neuralmind/commit/e92a9f5577b041e8ee666f89e1c478c0f633aea0))
* VS Code native extension, BM25 hybrid search, explicit feedback, CI auto-index (v0.38.0) ([716c422](https://github.com/dfrostar/neuralmind/commit/716c4224ead33593d436359addacb4932a40c08f))


### Documentation

* NeuralMind ↔ OpenHuman concept note ([1cf4595](https://github.com/dfrostar/neuralmind/commit/1cf45958e9e1747116e7d71402184a664c523720))
* **pilot:** corrected BRD and golden queries template ([#285](https://github.com/dfrostar/neuralmind/issues/285)) ([bfd34b3](https://github.com/dfrostar/neuralmind/commit/bfd34b30b397bfbfb3a98bf1489d407809bf86e9))
* refresh benchmark chart [skip ci] ([27cb48c](https://github.com/dfrostar/neuralmind/commit/27cb48c00b262226a1db7dcdc33428b79904e453))
* refresh SEO structured data and sitemap to v0.38.0 state ([#288](https://github.com/dfrostar/neuralmind/issues/288)) ([82cb1e2](https://github.com/dfrostar/neuralmind/commit/82cb1e27372bc3cbdba12d10521e7bd9a562e9b5))
* rename v0.40.0 → v0.39.0 across all public-facing surfaces ([#295](https://github.com/dfrostar/neuralmind/issues/295)) ([08f8f82](https://github.com/dfrostar/neuralmind/commit/08f8f82aa45ac0ab2706981d42be2776e50ad451))
* **roadmap:** language expansion, impact tool, broader agent installs ([47df6e2](https://github.com/dfrostar/neuralmind/commit/47df6e21b85841b00d00b81f27919665c2ec5407))

## [0.38.0](https://github.com/dfrostar/neuralmind/compare/v0.37.0...v0.38.0) (2026-06-27)


### Features

* hybrid BM25 search, explicit feedback MCP tool, CI auto-index action (v0.38.0) ([438bacd](https://github.com/dfrostar/neuralmind/commit/438bacd8d40ea97101c548f924dbd894586e3c7f))


### Documentation

* refresh benchmark chart [skip ci] ([8e4fc98](https://github.com/dfrostar/neuralmind/commit/8e4fc98f5b6d5bfbdd4107614f7ffd181970892c))
* refresh launch handoff to v0.37.0 state ([#275](https://github.com/dfrostar/neuralmind/issues/275)) ([8dff2c1](https://github.com/dfrostar/neuralmind/commit/8dff2c1221bdca6779908669b095ed3abc140d3a))

## [0.37.0](https://github.com/dfrostar/neuralmind/compare/v0.34.0...v0.37.0) (2026-06-20)


### Features

* C# extractor — eighth language behind the tree-sitter seam ([#267](https://github.com/dfrostar/neuralmind/issues/267)) ([d5b5c65](https://github.com/dfrostar/neuralmind/commit/d5b5c6534321efe6409934f32ab16c56006e4b78))
* expand public benchmark corpus with flask + rich ([#271](https://github.com/dfrostar/neuralmind/issues/271)) ([3ce219f](https://github.com/dfrostar/neuralmind/commit/3ce219f990560efb902d48b99b12292ca363034f))
* PHP extractor — tenth language behind the tree-sitter seam ([#270](https://github.com/dfrostar/neuralmind/issues/270)) ([f33b87c](https://github.com/dfrostar/neuralmind/commit/f33b87c83686d2ffc3f6fc95eb731826a63b6462))
* Ruby extractor — ninth language behind the tree-sitter seam ([#269](https://github.com/dfrostar/neuralmind/issues/269)) ([b27c7d7](https://github.com/dfrostar/neuralmind/commit/b27c7d7ec47c0d9b96eed3a9725cb4eca9aa0bfd))


### Documentation

* enrich schema.org JSON-LD on docs pages (SEO) ([#272](https://github.com/dfrostar/neuralmind/issues/272)) ([19b3eb5](https://github.com/dfrostar/neuralmind/commit/19b3eb500cd9ff58a94a2924527d8b2eb13c3a94))
* umbrella v0.37.0 release notes + Release-As 0.37.0 ([#273](https://github.com/dfrostar/neuralmind/issues/273)) ([f9c19ea](https://github.com/dfrostar/neuralmind/commit/f9c19ea078967df804d0a915d1db4224a905d3b4))

## [0.34.0](https://github.com/dfrostar/neuralmind/compare/v0.33.0...v0.34.0) (2026-06-20)


### Features

* opt-in LLM-judged answerability arm for the public benchmark ([#264](https://github.com/dfrostar/neuralmind/issues/264)) ([f6e8cd7](https://github.com/dfrostar/neuralmind/commit/f6e8cd7c182808c30476bb88ec60e1f3c719fb7f))


### Documentation

* disclosed-maker launch kit under docs/launch/ ([#263](https://github.com/dfrostar/neuralmind/issues/263)) ([948f732](https://github.com/dfrostar/neuralmind/commit/948f73257203176c4831bd8a59637ed1147864ca))
* position NeuralMind as four data-backed benefits, not just token reduction ([#261](https://github.com/dfrostar/neuralmind/issues/261)) ([d56d0bc](https://github.com/dfrostar/neuralmind/commit/d56d0bcb8a22ceb4bab80959bb83c384979cf6c4))
* refresh launch handoff with next-session checklist ([#265](https://github.com/dfrostar/neuralmind/issues/265)) ([3fd424a](https://github.com/dfrostar/neuralmind/commit/3fd424a987f53069fe1aa939fe813aa6f9858fb0))

## [0.33.0](https://github.com/dfrostar/neuralmind/compare/v0.32.0...v0.33.0) (2026-06-19)


### Features

* live codebase-memory-mcp head-to-head in the public benchmark ([#259](https://github.com/dfrostar/neuralmind/issues/259)) ([888291d](https://github.com/dfrostar/neuralmind/commit/888291df67e3d5e3db6c3152e5928c42c92a0270))

## [0.32.0](https://github.com/dfrostar/neuralmind/compare/v0.31.0...v0.32.0) (2026-06-19)


### Features

* C and C++ language extractors ([#257](https://github.com/dfrostar/neuralmind/issues/257)) ([424faf9](https://github.com/dfrostar/neuralmind/commit/424faf95d010948fcca10381c9e081d3cc75185f))

## [0.31.0](https://github.com/dfrostar/neuralmind/compare/v0.29.0...v0.31.0) (2026-06-19)


### Features

* neuralmind benchmark --public — honest, reproducible benchmark vs alternatives ([#254](https://github.com/dfrostar/neuralmind/issues/254)) ([f8eca9b](https://github.com/dfrostar/neuralmind/commit/f8eca9bd7a651941f4f6d55f16c31d446339fdf2))
* team memory — agents inherit the team's learned associations ([#252](https://github.com/dfrostar/neuralmind/issues/252)) ([18aac97](https://github.com/dfrostar/neuralmind/commit/18aac97f0b7ae069a524b400f22f6fe38baa0a70))


### Miscellaneous Chores

* release as v0.31.0 (roll 0.30.0 into 0.31.0) ([#256](https://github.com/dfrostar/neuralmind/issues/256)) ([e70e157](https://github.com/dfrostar/neuralmind/commit/e70e157da924d1f44704b4da52ec391afb41b7dc))

## [0.29.0](https://github.com/dfrostar/neuralmind/compare/v0.28.0...v0.29.0) (2026-06-18)


### Features

* make the default install ChromaDB-free (turbovec/ONNX) ([#251](https://github.com/dfrostar/neuralmind/issues/251)) ([5edf090](https://github.com/dfrostar/neuralmind/commit/5edf090c28a84c4416efb0685f70b330f9797650))


### Documentation

* README comparisons row, SEO meta tags, and unified-stack use-case walkthrough ([dad3298](https://github.com/dfrostar/neuralmind/commit/dad32984f835a2df9fa31d414176c88bd723c456))
* README comparisons row, SEO meta tags, and unified-stack use-case walkthrough ([540d3ad](https://github.com/dfrostar/neuralmind/commit/540d3ad26fbdf07b5c2808b2c4cf23c276fb82e1))

## [0.28.0](https://github.com/dfrostar/neuralmind/compare/v0.27.0...v0.28.0) (2026-06-18)


### Features

* add Java to the built-in tree-sitter backend ([#246](https://github.com/dfrostar/neuralmind/issues/246)) ([42c9516](https://github.com/dfrostar/neuralmind/commit/42c9516dfad772f958933672f86c0252d70738c1))

## [0.27.0](https://github.com/dfrostar/neuralmind/compare/v0.26.0...v0.27.0) (2026-06-18)


### Features

* add Rust to the built-in tree-sitter backend ([#245](https://github.com/dfrostar/neuralmind/issues/245)) ([6eea233](https://github.com/dfrostar/neuralmind/commit/6eea23333af8f464d3a151d9979869b91cd4f766))


### Bug Fixes

* force UTF-8 stdout/stderr in CLI to avoid Windows cp1252 crash ([#242](https://github.com/dfrostar/neuralmind/issues/242)) ([2db260a](https://github.com/dfrostar/neuralmind/commit/2db260a27260e14f07e5314c96071d8b60ce6b66))


### Documentation

* add context engineering stack comparative guide ([5a21b39](https://github.com/dfrostar/neuralmind/commit/5a21b39ec0e796d9902bd581cb6f5dfb1bfcb596))
* add context engineering stack comparative guide (NeuralMind + Ponytail + Headroom) ([005ceba](https://github.com/dfrostar/neuralmind/commit/005ceba9e7746c6f6607d23c573e8306c10535d4))
* add Google Search Console site-verification file ([#237](https://github.com/dfrostar/neuralmind/issues/237)) ([c26c0ad](https://github.com/dfrostar/neuralmind/commit/c26c0ad1844a9afb12e97d78f81009fb0bbc20d3))
* add the Headroom comparison and fix the sitemap to same-host URLs ([#236](https://github.com/dfrostar/neuralmind/issues/236)) ([040a8ef](https://github.com/dfrostar/neuralmind/commit/040a8efd8d63d9f610e2f6cfc355836f3b1ec97e))
* mark v0.26.0 as the latest release on the landing page ([#234](https://github.com/dfrostar/neuralmind/issues/234)) ([cbea018](https://github.com/dfrostar/neuralmind/commit/cbea01850ca476d1bce2f2fde0b2f6a82cb524e0))
* refresh benchmark chart [skip ci] ([a2f20db](https://github.com/dfrostar/neuralmind/commit/a2f20dbeecd4eea806d7b4591588f1b0402ce486))

## [0.26.0](https://github.com/dfrostar/neuralmind/compare/v0.25.0...v0.26.0) (2026-06-12)


### Features

* self-improvement engine phases 1-2 — selector auto-tuning from the synapse signal ([#233](https://github.com/dfrostar/neuralmind/issues/233)) ([d1d622f](https://github.com/dfrostar/neuralmind/commit/d1d622fcd9721893143a001b016ccf4225701d06))


### Documentation

* mark v0.25.0 as the latest release on the landing page ([#231](https://github.com/dfrostar/neuralmind/issues/231)) ([edb5b05](https://github.com/dfrostar/neuralmind/commit/edb5b05d84a34b7d7a9ab0cd47f915ad07056cda))

## [0.25.0](https://github.com/dfrostar/neuralmind/compare/v0.24.0...v0.25.0) (2026-06-12)


### Features

* retire the learned_patterns reranker — the synapse layer is the single learning signal ([#230](https://github.com/dfrostar/neuralmind/issues/230)) ([d00f46c](https://github.com/dfrostar/neuralmind/commit/d00f46c29b2dacaff1af8577278a2eb13cff90c6)), closes [#143](https://github.com/dfrostar/neuralmind/issues/143)


### Bug Fixes

* make the test suite Windows-green and restore full Windows support ([#228](https://github.com/dfrostar/neuralmind/issues/228)) ([bd3daad](https://github.com/dfrostar/neuralmind/commit/bd3daadd6db1746edf4365ff99dea21cfa5d0350))

## [0.24.0](https://github.com/dfrostar/neuralmind/compare/v0.23.0...v0.24.0) (2026-06-11)


### Features

* memory namespaces & branch isolation for the synapse layer (PRD 4) ([8fae289](https://github.com/dfrostar/neuralmind/commit/8fae28975779bcfe2491443a47b9a8f6929e6de4))


### Bug Fixes

* re-resolve memory namespace when a warm process crosses a git checkout ([32cd1e0](https://github.com/dfrostar/neuralmind/commit/32cd1e0c8af3ff13c64b8ab8e15510697c768fef))


### Documentation

* mark v0.23.0 as the latest release on the landing page ([#224](https://github.com/dfrostar/neuralmind/issues/224)) ([f72ff10](https://github.com/dfrostar/neuralmind/commit/f72ff10f9cb2b9d5c96eb14154f9d1ac59674875))

## [0.23.0](https://github.com/dfrostar/neuralmind/compare/v0.22.0...v0.23.0) (2026-06-11)


### Features

* versioned IR (PRD 1) + quality harness (PRD 2) + debug traces (PRD 3) + local daemon (PRD 5) ([#217](https://github.com/dfrostar/neuralmind/issues/217)) ([a62e635](https://github.com/dfrostar/neuralmind/commit/a62e6353a9dcd799c8cb3dfee321ac194c69be9a))


### Bug Fixes

* stop suggesting graphify update as the fix for a missing graph ([#223](https://github.com/dfrostar/neuralmind/issues/223)) ([045008f](https://github.com/dfrostar/neuralmind/commit/045008fafc26eb2e64d4ad0dae0f598541831af8))


### Documentation

* modernize guides to the no-graphify flow, fix all broken links ([#222](https://github.com/dfrostar/neuralmind/issues/222)) ([ba7e4d0](https://github.com/dfrostar/neuralmind/commit/ba7e4d0852fd22a2fe68558f0178a6f87e82a69e))
* redesign landing page — fix versions, links, quickstart, positioning ([#220](https://github.com/dfrostar/neuralmind/issues/220)) ([2602bf8](https://github.com/dfrostar/neuralmind/commit/2602bf83b014c4339de851b0d82f92214e2e9773))
* refresh benchmark chart [skip ci] ([8ff1e0d](https://github.com/dfrostar/neuralmind/commit/8ff1e0df86f0ca5827731e216be99ebf942ce3ec))

## [0.22.0](https://github.com/dfrostar/neuralmind/compare/v0.21.0...v0.22.0) (2026-06-07)


### Features

* **backend:** default to turbovec when available, with chroma fallback ([#214](https://github.com/dfrostar/neuralmind/issues/214)) ([9be320f](https://github.com/dfrostar/neuralmind/commit/9be320f909747b7c3b58a3c55b240f418f37d799))
* **bench:** TurboVec vs ChromaDB memory/latency benchmark toolkit ([#211](https://github.com/dfrostar/neuralmind/issues/211)) ([e5fb19b](https://github.com/dfrostar/neuralmind/commit/e5fb19baaaa72a475b230ce72ddce6a9fcd88419))


### Performance Improvements

* **turbovec:** skip numpy→list→numpy round-trip when indexing ([#212](https://github.com/dfrostar/neuralmind/issues/212)) ([e3e8914](https://github.com/dfrostar/neuralmind/commit/e3e89145610c14a598f8f60bd59be921ea2c46a3))


### Documentation

* showcase measured results — Benchmarks page, use cases, metrics ([#208](https://github.com/dfrostar/neuralmind/issues/208)) ([615c69b](https://github.com/dfrostar/neuralmind/commit/615c69bb2dc9fc562e88cc65a135b5c5f0a41b7f))

## [0.21.0](https://github.com/dfrostar/neuralmind/compare/v0.20.1...v0.21.0) (2026-06-07)


### Features

* **backend:** ChromaDB-free embeddings — owned MiniLM embedder ([#207](https://github.com/dfrostar/neuralmind/issues/207)) ([9be4762](https://github.com/dfrostar/neuralmind/commit/9be47626dedcdd14cb2235f950b555300ee9f0e5))
* **backend:** experimental TurboVec (TurboQuant) vector backend [POC, [#204](https://github.com/dfrostar/neuralmind/issues/204)] ([#205](https://github.com/dfrostar/neuralmind/issues/205)) ([e37d4c7](https://github.com/dfrostar/neuralmind/commit/e37d4c7f66e3c70b116443f3a7e4f57c71f5be86))

## [0.20.1](https://github.com/dfrostar/neuralmind/compare/v0.20.0...v0.20.1) (2026-06-07)


### Documentation

* **security:** document chromadb CVE-2026-45829 has no fixed release ([#201](https://github.com/dfrostar/neuralmind/issues/201)) ([722d41c](https://github.com/dfrostar/neuralmind/commit/722d41c27e8ba305c0a116b5b1f213a108ff25de))

## [0.20.0](https://github.com/dfrostar/neuralmind/compare/v0.19.0...v0.20.0) (2026-06-06)


### Features

* **evals:** onboarding-lift eval (E1.5) — measure the learned-synapse uplift ([#199](https://github.com/dfrostar/neuralmind/issues/199)) ([e53782e](https://github.com/dfrostar/neuralmind/commit/e53782ec5f5075450a6efb2c0f1ee5d5caeb661f))


### Documentation

* **plan:** session accomplishments + E1.5 onboarding-lift eval handoff ([#197](https://github.com/dfrostar/neuralmind/issues/197)) ([86c6eba](https://github.com/dfrostar/neuralmind/commit/86c6eba9208ae25b2ed380e68d80b4dd3dba148d))

## [0.19.0](https://github.com/dfrostar/neuralmind/compare/v0.18.0...v0.19.0) (2026-06-05)


### Features

* **mcp:** one-command MCP setup — auto-detect + register with agents ([#195](https://github.com/dfrostar/neuralmind/issues/195)) ([40c3209](https://github.com/dfrostar/neuralmind/commit/40c3209a22d3b519b8c5b07732fcc79e1f61ee4f))

## [0.18.0](https://github.com/dfrostar/neuralmind/compare/v0.17.0...v0.18.0) (2026-06-05)


### Features

* **backend:** incremental per-file graph updates wired to the watcher ([#193](https://github.com/dfrostar/neuralmind/issues/193)) ([1777747](https://github.com/dfrostar/neuralmind/commit/177774726edc3f4e51e699d4b586955636881199))

## [0.17.0](https://github.com/dfrostar/neuralmind/compare/v0.16.0...v0.17.0) (2026-06-05)


### Features

* **backend:** optional SCIP precision pass for compiler-accurate edges ([#191](https://github.com/dfrostar/neuralmind/issues/191)) ([d457231](https://github.com/dfrostar/neuralmind/commit/d45723130be78879c7f80da0f2cef4bbf4271494))

## [0.16.0](https://github.com/dfrostar/neuralmind/compare/v0.15.0...v0.16.0) (2026-06-05)


### Features

* **backend:** multi-language built-in backend — TypeScript + Go extractors ([#189](https://github.com/dfrostar/neuralmind/issues/189)) ([2dfc255](https://github.com/dfrostar/neuralmind/commit/2dfc255a2171ee91b1fe7555de6b89dc904a985e))

## [0.15.0](https://github.com/dfrostar/neuralmind/compare/v0.14.0...v0.15.0) (2026-06-05)


### Features

* **backend:** built-in tree-sitter graph backend — `neuralmind build` with no graphify ([#187](https://github.com/dfrostar/neuralmind/issues/187)) ([c297898](https://github.com/dfrostar/neuralmind/commit/c29789840918706a1cb2e70a10e961c786d2f18f))

## [0.14.0](https://github.com/dfrostar/neuralmind/compare/v0.13.1...v0.14.0) (2026-06-05)


### Features

* **evals:** faithfulness A/B harness + report (E1.2-E1.4) ([#182](https://github.com/dfrostar/neuralmind/issues/182)) ([c7da2b1](https://github.com/dfrostar/neuralmind/commit/c7da2b169f4a69405ca5e1c7f220bd903a7ea0d9))


### Documentation

* v0.14.0 launch pass — neuralmind eval + faithfulness measurement ([#184](https://github.com/dfrostar/neuralmind/issues/184)) ([ba7fe52](https://github.com/dfrostar/neuralmind/commit/ba7fe5258acc4cb6a1665305c6dd79c5cf439661))

## [0.13.1](https://github.com/dfrostar/neuralmind/compare/v0.13.0...v0.13.1) (2026-06-05)


### Documentation

* v0.13.0 launch pass — release notes, banners, SEO, wiki, sitemap ([#180](https://github.com/dfrostar/neuralmind/issues/180)) ([e995804](https://github.com/dfrostar/neuralmind/commit/e9958043025fe45222b32e81d5e241fc40501e26))

## [0.13.0](https://github.com/dfrostar/neuralmind/compare/v0.12.0...v0.13.0) (2026-06-05)


### Features

* **evals:** faithfulness eval foundation — query+gold-fact set + offline judge skeleton (E1.1) ([#177](https://github.com/dfrostar/neuralmind/issues/177)) ([90be7aa](https://github.com/dfrostar/neuralmind/commit/90be7aa80c02442044b0d0584f2062332c488090))
* polyglot retrieval-quality fixtures — TypeScript + Go ([#173](https://github.com/dfrostar/neuralmind/issues/173) E2.2/E2.3) ([#178](https://github.com/dfrostar/neuralmind/issues/178)) ([f7d7b53](https://github.com/dfrostar/neuralmind/commit/f7d7b53bc209f2a5561beaf6cfb3a653c788a15e))


### Documentation

* establish a standard documentation process ([#176](https://github.com/dfrostar/neuralmind/issues/176)) ([9e4d014](https://github.com/dfrostar/neuralmind/commit/9e4d01415b78415b9f47d8b6316407a03c6ced93))

## [0.12.0](https://github.com/dfrostar/neuralmind/compare/v0.11.1...v0.12.0) (2026-06-04)


### Features

* **cli:** neuralmind doctor — install health check + friendlier first-run error ([#169](https://github.com/dfrostar/neuralmind/issues/169)) ([2b0509b](https://github.com/dfrostar/neuralmind/commit/2b0509bb03a9a6e210d3f8bf3990d6b47a89edd9))


### Documentation

* next-release plan + eval-first roadmap announcement (v0.13→v0.16) ([#170](https://github.com/dfrostar/neuralmind/issues/170)) ([8d87d2b](https://github.com/dfrostar/neuralmind/commit/8d87d2bd16210c8d5810db85c0fa4b3c8455c913))
* refresh benchmark chart [skip ci] ([b640818](https://github.com/dfrostar/neuralmind/commit/b6408181bc16512e5ce1d053fa9e61447548492c))

## [0.11.1](https://github.com/dfrostar/neuralmind/compare/v0.11.0...v0.11.1) (2026-06-01)


### Documentation

* **benchmarks:** interactive community-benchmark dashboard at /benchmarks/ ([#158](https://github.com/dfrostar/neuralmind/issues/158)) ([7d4723b](https://github.com/dfrostar/neuralmind/commit/7d4723bcb10c371e60ce783e8d8fc2efae4eba7b))
* reframe README + PyPI around persistent memory ([#154](https://github.com/dfrostar/neuralmind/issues/154)) ([33e50fa](https://github.com/dfrostar/neuralmind/commit/33e50fab66332d39d311ebe2e65c40faa079f4c0))

## [0.11.0](https://github.com/dfrostar/neuralmind/compare/v0.10.0...v0.11.0) (2026-05-27)


### Features

* **synapses:** directional transitions — learn what comes next ([#153](https://github.com/dfrostar/neuralmind/issues/153)) ([0fb3ee7](https://github.com/dfrostar/neuralmind/commit/0fb3ee7d607aac5962014b1837b50a5aa5d741b8))


### Bug Fixes

* **ci:** docker-publish version tag missing on workflow_dispatch ([#140](https://github.com/dfrostar/neuralmind/issues/140)) ([81da081](https://github.com/dfrostar/neuralmind/commit/81da081eee532c9fc4880ac5cc06943e27369673))


### Documentation

* refresh benchmark chart [skip ci] ([80a0216](https://github.com/dfrostar/neuralmind/commit/80a021628a5a6262e390cdea767003fe94622ce5))

## [0.10.0](https://github.com/dfrostar/neuralmind/compare/v0.9.0...v0.10.0) (2026-05-24)


### Features

* **compressors:** show what was dropped + `neuralmind last` recovery cache ([#149](https://github.com/dfrostar/neuralmind/issues/149)) ([561f8ef](https://github.com/dfrostar/neuralmind/commit/561f8eff221770eaf324ca239f8888935230b5dd))


### Documentation

* propagate v0.8.0 + v0.9.0 across README, wiki, Pages, ROADMAP ([#132](https://github.com/dfrostar/neuralmind/issues/132)) ([fdfa35e](https://github.com/dfrostar/neuralmind/commit/fdfa35efdc8f73687047fb7727e13ec19bc58db2))
* refresh benchmark chart [skip ci] ([4c8550e](https://github.com/dfrostar/neuralmind/commit/4c8550e7b6e7cecb51245da8eb7f7ccfc4755e1f))

## [0.9.0](https://github.com/dfrostar/neuralmind/compare/v0.8.0...v0.9.0) (2026-05-18)


### Features

* **ci:** v0.9 enterprise-ready — GHCR auto-build, SBOM, air-gapped doc, compliance one-pager ([#129](https://github.com/dfrostar/neuralmind/issues/129)) ([eb5969f](https://github.com/dfrostar/neuralmind/commit/eb5969f371fe062dfabb4803f913017b2359b231))

## [0.8.0](https://github.com/dfrostar/neuralmind/compare/v0.7.0...v0.8.0) (2026-05-18)


### Bug Fixes

* **ci:** use PAT for release-please so tag pushes trigger release.yml ([#126](https://github.com/dfrostar/neuralmind/issues/126)) ([d6fd9d9](https://github.com/dfrostar/neuralmind/commit/d6fd9d954b0f35aa4df44f8ac56d30250e1a8184))
* **ci:** use PAT for release-please so tag pushes trigger release.yml ([#98](https://github.com/dfrostar/neuralmind/issues/98)) ([81baac9](https://github.com/dfrostar/neuralmind/commit/81baac94345847fb91080e86f8f33b7efc62536c))


### Miscellaneous Chores

* **release:** Release-As 0.8.0 override for always-on ([#128](https://github.com/dfrostar/neuralmind/issues/128)) ([aa1a026](https://github.com/dfrostar/neuralmind/commit/aa1a026360f06bd0e262eec4a13f6f567e4cba73))
* trigger v0.8.0 release with always-on work ([16c967b](https://github.com/dfrostar/neuralmind/commit/16c967be8d20330a4e566ade5392403f9f0b5066))

## [0.7.0](https://github.com/dfrostar/neuralmind/compare/v0.6.0...v0.7.0) (2026-05-17)


### Features

* **ecosystem:** Agent Zero MCP integration + a0-plugins submission draft ([b016f28](https://github.com/dfrostar/neuralmind/commit/b016f2809350e21651fea3b4305435703cad2829))
* **install:** add Dockerfile and PyPI keywords for v0.6.1 ([#118](https://github.com/dfrostar/neuralmind/issues/118)) ([fd51773](https://github.com/dfrostar/neuralmind/commit/fd5177301b79ebc93d11f088a531f4063bd28342))


### Bug Fixes

* **docker:** install graphifyy + pre-wheel transitive deps in builder ([b6297bd](https://github.com/dfrostar/neuralmind/commit/b6297bdc0809d8c76a52e926f7ace2b85fa1ebb8))
* **event_log:** keep reopen-at-start across failed open + missing-file ([db1816b](https://github.com/dfrostar/neuralmind/commit/db1816b0bab88afd8e64f6e4736620ad1bb4b1d4))
* **event_log:** reopen rotated logs from offset 0 ([#115](https://github.com/dfrostar/neuralmind/issues/115)) ([9b0ecd8](https://github.com/dfrostar/neuralmind/commit/9b0ecd819b4da0cd576f96823a1ec69cd7a1402d))


### Documentation

* **install:** build-locally Docker, dedupe pip line, scope verify snippet ([4796afc](https://github.com/dfrostar/neuralmind/commit/4796afc295c6b6d5bfadb5dd2708251322086766))
* **install:** five-path install matrix in README, wiki, comparisons ([#118](https://github.com/dfrostar/neuralmind/issues/118)) ([a4f0b9f](https://github.com/dfrostar/neuralmind/commit/a4f0b9febcc0d5a5449186a4ac8c54e89d366334))
* **marketing:** v0.6.1 LinkedIn drafts, screencast script, NotebookLM pack ([#118](https://github.com/dfrostar/neuralmind/issues/118)) ([7cba04a](https://github.com/dfrostar/neuralmind/commit/7cba04a77d9f0c5aa055cbe019181b845da483cc))
* propagate v0.6.1 install matrix across README, wiki, Pages, ROADMAP ([fceea6b](https://github.com/dfrostar/neuralmind/commit/fceea6bb8b835646ccb2efe671f01be056776a4c))
* **release:** address PR [#124](https://github.com/dfrostar/neuralmind/issues/124) review — v0.7→v0.8 forward refs ([c3477f1](https://github.com/dfrostar/neuralmind/commit/c3477f1d36523d79e4ba6cc508a25c0ddad3a1f7))
* **release:** rename v0.6.1 → v0.7.0 to match release-please ([#124](https://github.com/dfrostar/neuralmind/issues/124)) ([0c8fa0a](https://github.com/dfrostar/neuralmind/commit/0c8fa0a7b295ae2f4621d5210746c3190cf9a5b6))
* **release:** rename v0.6.1 → v0.7.0 to match release-please version ([3ce2da2](https://github.com/dfrostar/neuralmind/commit/3ce2da23b5b52cfffbf5c0b0bb79d9b47c02aa66))

## [0.6.0](https://github.com/dfrostar/neuralmind/compare/v0.5.4...v0.6.0) (2026-05-15)


### Features

* **serve:** Cmd/Ctrl-K and '/' jump to search, Esc clears ([1f844a5](https://github.com/dfrostar/neuralmind/commit/1f844a5d0675d359d2d85c64e82b7873c900b849))
* **serve:** Cmd/Ctrl-K and '/' jump to search, Esc clears ([374fbbc](https://github.com/dfrostar/neuralmind/commit/374fbbc4895d73a9b19d7d78dc2f434a13935b09))
* **serve:** Cmd/Ctrl-K and '/' jump to search, Esc clears ([#109](https://github.com/dfrostar/neuralmind/issues/109)) ([1f844a5](https://github.com/dfrostar/neuralmind/commit/1f844a5d0675d359d2d85c64e82b7873c900b849))
* **serve:** cross-process activity stream via JSONL bridge ([806ceba](https://github.com/dfrostar/neuralmind/commit/806cebaa1637c630a80e75c1e866570d1e0b7b11))
* **serve:** cross-process activity stream via JSONL bridge ([7fce097](https://github.com/dfrostar/neuralmind/commit/7fce097c5272976625bf2d5828cc5b9bb70ad428))
* **serve:** cross-process activity stream via JSONL bridge ([#112](https://github.com/dfrostar/neuralmind/issues/112)) ([806ceba](https://github.com/dfrostar/neuralmind/commit/806cebaa1637c630a80e75c1e866570d1e0b7b11))
* **serve:** edge tooltips + min-weight synapse slider ([5c7ce5c](https://github.com/dfrostar/neuralmind/commit/5c7ce5cca56a4e6fe99f80443754f7a08b6d1854))
* **serve:** edge tooltips + min-weight synapse slider ([a595a38](https://github.com/dfrostar/neuralmind/commit/a595a38f26d01d43f73a566e8b788dc4eca55324))
* **serve:** edge tooltips + min-weight synapse slider ([#106](https://github.com/dfrostar/neuralmind/issues/106)) ([5c7ce5c](https://github.com/dfrostar/neuralmind/commit/5c7ce5cca56a4e6fe99f80443754f7a08b6d1854))
* **serve:** live activity feed - SSE stream of synapse + file events ([#110](https://github.com/dfrostar/neuralmind/issues/110)) ([ea9fa26](https://github.com/dfrostar/neuralmind/commit/ea9fa2683a523a51cf3e31a651e93ddba722bd2a))
* **serve:** live activity feed — SSE stream of synapse + file events ([ea9fa26](https://github.com/dfrostar/neuralmind/commit/ea9fa2683a523a51cf3e31a651e93ddba722bd2a))
* **serve:** live activity feed — SSE stream of synapse + file events ([1712e61](https://github.com/dfrostar/neuralmind/commit/1712e61184388e800b17e0ff00df235de6203457))
* **serve:** local-graph depth slider (1-3 hops) ([#111](https://github.com/dfrostar/neuralmind/issues/111)) ([6760c3b](https://github.com/dfrostar/neuralmind/commit/6760c3b7f5043864dd5b08d4a0f9facd798e2382))
* **serve:** local-graph depth slider (1–3 hops) ([6760c3b](https://github.com/dfrostar/neuralmind/commit/6760c3b7f5043864dd5b08d4a0f9facd798e2382))
* **serve:** local-graph depth slider (1–3 hops) ([d5d8d0a](https://github.com/dfrostar/neuralmind/commit/d5d8d0a3569d21eaf07614dc580e09873478b369))
* **serve:** replay-last-query overlay closes the trust gap ([0802429](https://github.com/dfrostar/neuralmind/commit/0802429cd9491610c8cb11ab8fd51c98dab43ee2))
* **serve:** replay-last-query overlay closes the trust gap ([3f08e6b](https://github.com/dfrostar/neuralmind/commit/3f08e6b61c8d8674548be5f9fa828714c8cc5923))
* **serve:** visible pin glyph, Pin/Unpin button, Unpin-all ([987e6dc](https://github.com/dfrostar/neuralmind/commit/987e6dc713d6f097fc79c2c536501529e58d658d))
* **serve:** visible pin glyph, Pin/Unpin button, Unpin-all ([5894259](https://github.com/dfrostar/neuralmind/commit/5894259e42dac25da7b9e6b96fa1d5274375c07a))
* **serve:** visible pin glyph, Pin/Unpin button, Unpin-all ([#108](https://github.com/dfrostar/neuralmind/issues/108)) ([987e6dc](https://github.com/dfrostar/neuralmind/commit/987e6dc713d6f097fc79c2c536501529e58d658d))


### Bug Fixes

* **serve:** address PR [#105](https://github.com/dfrostar/neuralmind/issues/105) Copilot review — consent, races, a11y, tests ([37e1706](https://github.com/dfrostar/neuralmind/commit/37e17061e9e34c9308fc402d7663b5db50d31f7b))
* **serve:** address PR [#110](https://github.com/dfrostar/neuralmind/issues/110) review ([6afc5da](https://github.com/dfrostar/neuralmind/commit/6afc5daf5344d0bb4b09f6359942292a053909ee))
* **serve:** atomic append for recent_queries.jsonl — close cross-process race ([4b453b8](https://github.com/dfrostar/neuralmind/commit/4b453b8c7313d1901bf2fca97e30b787c3e0744b))
* **serve:** make depth slider truly inert when local graph is off ([b6a42a0](https://github.com/dfrostar/neuralmind/commit/b6a42a08afbd62ce34c27d02feb5d8b57bf1b1b0))


### Documentation

* add serve CLI ref + graph-view SEO keywords ([897b109](https://github.com/dfrostar/neuralmind/commit/897b1096680bd56f29a5d9d678b0f24f8b0e0bef))
* **claude.md:** list event_bus + server in layout ([6368fdb](https://github.com/dfrostar/neuralmind/commit/6368fdbebc20122fb965b098a81719cc7ccdc551))
* **contributing:** refresh bump-patch-for-minor-pre-major guidance ([0cc241d](https://github.com/dfrostar/neuralmind/commit/0cc241d95b3d2991a0e099167b1dc7562d6fc90c))
* correct replay overlay file path per [#107](https://github.com/dfrostar/neuralmind/issues/107) review ([7590e19](https://github.com/dfrostar/neuralmind/commit/7590e19f3cbef3592f4e8626faedfc7b4e238eac))
* correct v0.5.4 release labels in about page ([5b489cf](https://github.com/dfrostar/neuralmind/commit/5b489cf7998fb5da643474ea91e3557f877aeece))
* refresh roadmap + landing pages with current graph-view plan ([31adc09](https://github.com/dfrostar/neuralmind/commit/31adc099f12e5b61e8984746b3b4f764c148662f))
* refresh roadmap + landing pages with current graph-view plan ([b9f2c80](https://github.com/dfrostar/neuralmind/commit/b9f2c8012b4421250fd3b9450f43fc2f25445e3e))
* refresh roadmap + landing pages with current graph-view plan ([#107](https://github.com/dfrostar/neuralmind/issues/107)) ([31adc09](https://github.com/dfrostar/neuralmind/commit/31adc099f12e5b61e8984746b3b4f764c148662f))
* **v0.6.0:** release notes, polish, multi-agent + notebooklm pack ([930dcca](https://github.com/dfrostar/neuralmind/commit/930dccaef284ae7a0e4f2d490dbb0dc52fda08a7))
* **v0.6.0:** release notes, polish, multi-agent + notebooklm pack ([c84cd93](https://github.com/dfrostar/neuralmind/commit/c84cd93541b8c59127652e50783a1af3f81465a2))
* **v0.6.0:** release notes, polish, multi-agent + notebooklm pack ([#113](https://github.com/dfrostar/neuralmind/issues/113)) ([930dcca](https://github.com/dfrostar/neuralmind/commit/930dccaef284ae7a0e4f2d490dbb0dc52fda08a7))

## [0.5.4](https://github.com/dfrostar/neuralmind/compare/v0.5.3...v0.5.4) (2026-05-15)


### Features

* add Obsidian-style graph-view UI (`neuralmind serve`) ([f6d4cbd](https://github.com/dfrostar/neuralmind/commit/f6d4cbd4c2fd3b489c4e7e8d623c45736c5349da))
* Obsidian-style graph view (`neuralmind serve`) + editor jump, auth, layout persistence ([14a654e](https://github.com/dfrostar/neuralmind/commit/14a654e5be6977540c868e2c400b37b876895605))
* **serve:** editor jump, auth token, first-run guidance, layout persistence ([b716f46](https://github.com/dfrostar/neuralmind/commit/b716f466da52f354136fbf0c134362dc3d48fb27))


### Bug Fixes

* **serve:** address PR [#101](https://github.com/dfrostar/neuralmind/issues/101) review — graphify cmd, canvas sizing, race, a11y ([e3f5cdf](https://github.com/dfrostar/neuralmind/commit/e3f5cdffea8b9ac9ce1778e0fb20b7a05e69177e))
* **serve:** allowlist Popen path against precomputed safe set ([d4d5eb9](https://github.com/dfrostar/neuralmind/commit/d4d5eb993daab7ae602b61a21c07edcabd3113d0))


### Documentation

* announce graph view in README, landing, and about pages ([f27ff98](https://github.com/dfrostar/neuralmind/commit/f27ff986726132928b4b1f0859caa5435ed5604f))

## [0.5.3](https://github.com/dfrostar/neuralmind/compare/v0.5.2...v0.5.3) (2026-05-12)


### Features

* ship portable SKILL.md so OpenClaw / Agent Zero / Hermes can drive NeuralMind ([2a833db](https://github.com/dfrostar/neuralmind/commit/2a833db127c9c52a102c0c5c40e8498d2dbf2714))


### Documentation

* add dedicated Hermes-Agent block to the skill section ([34a3f64](https://github.com/dfrostar/neuralmind/commit/34a3f64b59cecf6816be38fe1e68ab1bdda8a92c))
* add RELEASE_NOTES_v0.5.3.md ([e0efad4](https://github.com/dfrostar/neuralmind/commit/e0efad4267eda8bb654c3caeef20eb4208724fb8))
* address Copilot review on PR [#96](https://github.com/dfrostar/neuralmind/issues/96); fix preexisting black lint ([c89db50](https://github.com/dfrostar/neuralmind/commit/c89db505f4eb690718f9510d3259554be93d8d19))
* refresh benchmark chart [skip ci] ([ea2fb05](https://github.com/dfrostar/neuralmind/commit/ea2fb05f88f33f15768f1a0006c7c54e319c1937))
* ship portable SKILL.md for OpenClaw and Agent Zero ([bb8554a](https://github.com/dfrostar/neuralmind/commit/bb8554a35f4424df51c0c103471410ed18bb3b91))

## [0.5.2](https://github.com/dfrostar/neuralmind/compare/v0.5.1...v0.5.2) (2026-05-08)

### Features

* **demo:** bundle sample fixture so `pip install neuralmind && neuralmind demo` works ([#92](https://github.com/dfrostar/neuralmind/pull/92))

### Documentation

* fact-based business case + honest assessment + README slim ([#91](https://github.com/dfrostar/neuralmind/pull/91))

## [0.5.1](https://github.com/dfrostar/neuralmind/compare/v0.5.0...v0.5.1) (2026-05-04)


### Bug Fixes

* **release:** make github-release job idempotent on existing Release ([b44656d](https://github.com/dfrostar/neuralmind/commit/b44656d7ab51f7116118c827bc3d18006ef1cbe8))
* **release:** survive immutable Releases, attach artifacts at create time ([2542542](https://github.com/dfrostar/neuralmind/commit/25425428d584b639e9a27768afce1a3cc6e0a8ce))

## [0.5.0] - 2026-05-03

### Changed

- **MCP server bundled by default.** The `mcp` package moved from the
  `[mcp]` optional extra to a base dependency. `pip install neuralmind`
  now ships `neuralmind-mcp` ready to run, closing the long-standing
  "Connection closed" footgun where users followed the README Quick
  Start, wired up an MCP host (Claude Desktop, Claude Code, Cursor,
  Cline, Continue, Hermes-Agent, OpenClaw…), and hit an immediate
  `import mcp` failure because the SDK was gated.

### Backwards Compatibility

- The `[mcp]` extra is preserved as an empty no-op. Existing
  `pip install "neuralmind[mcp]"` commands in user docs, blog posts,
  and CI configs keep resolving cleanly with no warnings; pip just
  installs the base package (which now contains the MCP SDK).
- `neuralmind[all]` continues to resolve via `[mcp,dev]` because both
  extras still exist as keys in `pyproject.toml`.
- No code or API changes. Anyone already on the `[mcp]` install path
  is unaffected; anyone on the plain `pip install neuralmind` path now
  gets MCP support out of the box.

### Documentation

- Document release-please troubleshooting in `CONTRIBUTING.md` — covers
  the "no Release PR appears" GitHub setting trap (filed as #81),
  capitalized `Fix:`/`Feat:` commits being ignored by Conventional
  Commits parsing, and the `Release-As:` empty-commit override for
  forcing minor bumps before v1.0.
- Sweep the wiki (Installation, Setup-Guide, Home, Usage-Guide, FAQ),
  `USAGE.md`, `docs/DEPLOYMENT-GUIDE.md`, `docs/VERSION-STRATEGY.md`,
  and the landing + about pages to drop the now-stale `[mcp]` extra
  recommendations. The intentional backwards-compat / "legacy alias"
  notes that explain the preserved empty stub are kept.
- Refresh the about/landing roadmap. v0.5.0 is described as the
  packaging-only bundled-MCP release (matching what this entry actually
  ships); auto-watcher launch (#78), synapse import/export (#79), and
  retrieval-quality benchmark (#80) are listed as separate v0.5.x /
  v0.6.0 follow-on work, not as part of v0.5.0. PostgreSQL pgvector
  and observability dashboard remain on the v0.6.0+ track.
- Fix the stale "v0.4.2 (Current)" claim on `docs/index.html` (current
  was v0.4.0 — v0.4.2 was never cut).

## [0.4.0] - 2026-05-03

### Added

#### Brain-like Synapse Layer
- **`SynapseStore`** (`neuralmind/synapses.py`) — SQLite-backed weighted
  graph over code nodes; persists at `<project>/.neuralmind/synapses.db`.
  - Hebbian `reinforce()` strengthens edges between co-activated nodes.
  - Multiplicative `decay()` ages unused weights; weak edges are pruned.
  - Long-term potentiation: edges crossing an activation threshold get
    a weight floor and slower decay.
  - Spreading activation `spread(seeds, depth, top_k)` for usage-based
    recall, complementing vector search.
  - Hub normalization prevents runaway central nodes from dominating.

#### File Activity Watcher
- **`FileActivityWatcher`** (`neuralmind/watcher.py`) — debounces edits
  into co-activation batches; backed by `watchdog` when present, polling
  fallback otherwise.
- **`neuralmind watch`** CLI — foreground daemon that wires the watcher
  into the synapse store with periodic decay ticks.

#### Claude Code Lifecycle Hooks
- `install-hooks` now registers four events instead of one:
  - `SessionStart` — warm store, run decay tick, export memory.
  - `UserPromptSubmit` — spread activation from prompt; inject ranked
    neighbors as `additionalContext`.
  - `PreCompact` — normalize hub nodes before context compaction.
  - `PostToolUse` — (existing) Read/Bash/Grep compression.
- Idempotent — strip + re-add for all five managed events.

#### Memory Export
- **`neuralmind/synapse_memory.py`** — renders the synapse graph as
  markdown with strongest pairs (LTP-tagged) and top hubs.
- Writes `<project>/.neuralmind/SYNAPSE_MEMORY.md` always; also writes
  `~/.claude/projects/<slug>/memory/synapse-activations.md` when Claude
  Code's auto-memory directory exists for the project.

#### MCP Tools
- `neuralmind_synaptic_neighbors(query, depth, top_k)` — spreading
  activation recall.
- `neuralmind_synapse_stats()` — edge counts, LTP edges, top hubs.
- `neuralmind_synapse_decay()` — manual decay tick.
- `neuralmind_export_synapse_memory()` — write the markdown export.

#### Public API
- `NeuralMind.activate(node_ids, strength)` — feed an activation signal
  into the synapse layer.
- `NeuralMind.activate_files(file_paths, strength)` — resolve paths to
  node ids and reinforce.
- `NeuralMind.synaptic_neighbors(query, depth, top_k)` — spreading
  activation retrieval.
- `NeuralMind.synapses` property — direct access to the `SynapseStore`.
- `NeuralMind.__init__` gained `enable_synapses=True`.

### Changed

#### Performance
- **3× fewer embedder round trips per query.** `ContextSelector` now
  caches one search per query and slices results for L2, L3, hybrid
  highlights, and synapse reinforcement.
- `ContextResult.top_search_hits` exposes the cached hits so downstream
  consumers reuse them instead of re-querying.

#### Documentation
- Added `CLAUDE.md` with architecture map and `@.neuralmind/SYNAPSE_MEMORY.md`
  import for dogfooding.
- Gitignored generated synapse artifacts (`synapses.db`, WAL/SHM,
  `SYNAPSE_MEMORY.md`).

### Environment Variables
- `NEURALMIND_SYNAPSE_INJECT=0` — disable prompt-time recall injection.
- `NEURALMIND_SYNAPSE_EXPORT=0` — disable session-start memory export.

### Tests
- 50 new tests across the synapse layer, stdlib-only so they run
  without the full ChromaDB dep set.

### Backwards Compatibility
- All additions are opt-in or default-on with safe behavior.
- No migrations required. Synapse DB is created on first use.
- `ContextResult.top_search_hits` defaults to `[]`; existing callers
  ignore it.

---

## [0.3.4] - 2026-04-20

### Documentation

- **CLI Reference** — Corrected all CLI flag documentation to match the actual implementation
  - Removed non-existent `--verbose`, `--export`, `--db-path`, `--type`, `--community`, `--queries` flags
  - Renamed `--limit` to `--n` for the `search` command (matches implementation)
  - Removed unsupported `--quiet` flag from `build` examples in Usage and Integration guides
- **Installation Guide** — Added missing `toml>=0.10` core dependency; fixed `python -m neuralmind` references to use the installed `neuralmind` entry point
- **Troubleshooting** — Fixed `python -m neuralmind` reference and removed non-existent `--verbose` option from examples
- **Setup Guide** — Created missing `docs/wiki/Setup-Guide.md`, fixing broken link referenced in Home and README
- **README** — Updated "What's New" to reflect the full v0.3.x feature set including 0.3.3 stability fixes

### Changed
- Version bumped from 0.3.3.2 → 0.3.4 for this documentation polish release

---

## [0.3.3.2] - 2026-04-20

### Fixed
- **Version sync for smoke test** — Fixed hardcoded __version__ in __init__.py to match pyproject.toml
  - Smoke test was failing due to version mismatch between package metadata and runtime

---

## [0.3.3.1] - 2026-04-20

### Fixed
- **Test expectations** — Fixed all remaining test expectations for embedder stat counting
  - `test_embed_nodes_force_reembeds` corrected to expect updated count

---

## [0.3.3] - 2026-04-20

### Fixed
- **Incremental embedding stat counting** — Fixed bug where `force=True` re-embed incorrectly counted all nodes as "added"
  - Now correctly distinguishes between "added" (new) and "updated" (existing) nodes
  - Critical for accurate build statistics and incremental updates
  
- **Test expectations** — Updated `test_build_force_reembeds_all` to expect correct behavior
  - Existing nodes on force rebuild now correctly reported as "updated"
  - Integration test marked as skipped in restricted network environments

### Quality Improvements
- Improved embed_nodes logic for accurate stat reporting

---

## [0.3.2] - 2026-04-20

### Added

#### Cooccurrence-Based Reranking (v0.3.2)
- **Reranker integration** — Applies learned module patterns to improve search relevance
  - `CooccurrenceIndex` class loads learned patterns from JSON
  - `SemanticReranker` class applies patterns to search results
  - Lazy-loads reranker in context selector for zero overhead if patterns unavailable
  - Boost factor (0-1) amplifies semantic relevance by up to 30%
  
- **Learning pipeline** — Analyzes query history to discover module relationships
  - `neuralmind learn .` command builds cooccurrence patterns from events
  - Extracts module pairs that frequently appear together
  - Saves patterns to `.neuralmind/learned_patterns.json`
  - Shows top patterns and statistics to user

- **Seamless integration** — Automatic reranking in retrieval pipeline
  - L2 context tracks loaded modules for reranker context
  - L3 search automatically reranks results if patterns available
  - Displays reranker boost scores in search output
  - Enable/disable via `enable_reranking` flag (default: enabled)

### Changed
- **NeuralMind class** — Added `enable_reranking` parameter for control
- **ContextSelector** — Integrated reranking into L3 search pipeline
- **CLI** — `learn` command now functional (was scaffold)

### Quality Improvements
- 30 new tests for reranker classes and functions
- 8 tests for pattern learning and cooccurrence analysis
- 3 tests for learn CLI command integration
- 7 integration tests for context selector + reranker pipeline
- Token savings measurement foundation

---

## [0.3.1] - 2026-04-20

### Added
- **EmbeddingBackend abstraction layer** — Decouples ChromaDB from core logic
  - New abstract base class enables backend swaps and mocking
  - Improves testability (no ChromaDB overhead in tests)
  - Future-proofs architecture for Pinecone/Weaviate integration

- **Comprehensive integration tests** — 14 tests validating 4-layer retrieval pipeline
  - End-to-end retrieval pipeline tests
  - Query-aware context validation
  - Token reduction verification
  - Community detection and file skeleton tests
  - Incremental embedding validation

### Changed
- **GraphEmbedder** — Now implements EmbeddingBackend interface
  - Adds `clear()` and `close()` methods
  - Maintains full backward compatibility
  
### Fixed
- Version string sync (__init__.py was v0.2.0, now v0.3.1)
- Wiki navigation updated to highlight new guides

### Quality Improvements
- Better code organization with clear abstractions
- Improved documentation discoverability
- Foundation for swappable embedding backends

---

## [0.3.0] - 2026-04-20

### Added

#### Brain-Like Learning (v0.3.0)
- **Local-first memory infrastructure** — JSONL storage for query patterns (project + global scopes)
- **Opt-in consent system** — One-time TTY-only prompt, respects env vars (`NEURALMIND_MEMORY=0`, `NEURALMIND_LEARNING=0`)
- **Memory logging** — Implicit tracking of queries and retrieved modules
- **CLI commands**:
  - `neuralmind learn .` — Scaffold command, safe no-op when learning disabled
  - `neuralmind stats --memory` — Show memory statistics (v0.3.1+)
  - `neuralmind memory reset` — Clear learned patterns anytime
- **Comprehensive documentation** (`docs/brain_like_learning.md`)
  - Why learning matters (repeated queries, context fatigue)
  - Before/after examples showing token improvements
  - Privacy-first design (100% local, no telemetry)
  - Role-based examples (developers, data scientists, DevOps, onboarding)
  - Troubleshooting guide

#### Setup & Documentation
- **Setup-Guide** (`docs/wiki/Setup-Guide.md`) — Complete first-time setup for all platforms
  - 30-second minimal setup
  - Platform decision tree
  - Version requirements and compatibility matrix
  - Cost breakdown (token savings per platform)
  - Performance expectations and optimization
- **Wiki navigation updates** — Learning and Setup-Guide as primary links
- **README updates** — Feature overview and learning guide link

### Changed
- **Memory module** (`neuralmind/memory.py`) — New persistence layer for query patterns
- **Core module** — Integration of memory logging into `NeuralMind.query()`
- **CLI** — New memory commands and options
- **PyPI metadata** — Keywords include brain-like-learning, continual-learning, copilot, cursor

### Coming in v0.3.1+
- Cooccurrence-based reranking algorithm
- Active `neuralmind learn .` execution (not just scaffold)
- Token savings measurement
- Memory decay and freshness controls

---

## [0.2.2] - 2026-04-15

### Fixed
- CI: Declare toml dependency to fix collection failures
- Release CI: Gate GitHub release on PyPI install/import smoke test

### Changed
- CI: Migrate workflow action pins to Node 24-compatible majors

---

## Earlier Versions

See [GitHub Releases](https://github.com/dfrostar/neuralmind/releases) for v0.2.1 and earlier.
