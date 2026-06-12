# Changelog

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
