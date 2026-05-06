# Enterprise use cases

> **Reality check first:** every claim below assumes your codebase, language coverage, and workload match what NeuralMind handles well. Read [HONEST-ASSESSMENT.md](HONEST-ASSESSMENT.md) before pitching this internally — overpromising hurts adoption.

NeuralMind addresses specific pain points for organizations operating
AI coding assistants at scale. The framing below is a starting point
for internal conversations; the actual numbers come from running
`neuralmind benchmark .` on your codebase.

## Regulated industries (finance, healthcare, legal, government)

**Challenge:** AI tools can't be trusted if they can't explain decisions.

**What NeuralMind offers:**
- Every recommendation is traceable to extracted code (auditable, not guessed at).
- Runs 100% on-premise — no cloud, no data transfer, zero exfiltration risk.
- Compatible with GDPR, HIPAA, SOC 2, and ISO 27001 deployment patterns. (NeuralMind itself isn't certified; the architecture supports certification of the deployment.)
- Explainability by design — you can see which code fed each decision.

## Proprietary / sensitive code

**Challenge:** Sending code to external APIs or SaaS models is a legal no-go.

**What NeuralMind offers:**
- All processing stays on your hardware or internal network.
- Uses local ChromaDB storage; no ChromaDB cloud.
- No API keys, no authentication to external vendors.
- Process trade secrets, algorithms, and confidential code without external dependencies.

## Large organizations scaling AI coding assistant spend

**Challenge:** $50K+/month aggregate LLM bills across hundreds of developers.

**What NeuralMind offers:**
- Per-query token reduction that compounds across the team's query volume.
- Explicit benchmarking (`neuralmind benchmark`) to show ROI to finance.
- Measurable savings: baseline vs. optimized (in dollars at your model's pricing).
- Build the index once, share across teams.

**Caveat:** end-to-end cost reduction is typically 3–10×, not the 40–70× retrieval-stage figure. Plan budget conversations against the realistic number. See [HONEST-ASSESSMENT.md](HONEST-ASSESSMENT.md#what-40-70x-reduction-actually-means).

## Internal platform teams & shared infrastructure

**Challenge:** Different teams query the same codebase; results are inconsistent.

**What NeuralMind offers:**
- Build the index once → share across all teams.
- Cooccurrence learning adapts to your org's query patterns (`neuralmind learn`).
- Reproducible context for every question against the same index version.
- Single source of truth for "how does this system work?"

## Offline / disconnected development

**Challenge:** Regulated environments, air-gapped networks, unreliable connectivity.

**What NeuralMind offers:**
- No internet required after the initial install.
- Pre-build the index on a connected machine, ship it via source control or internal artifact storage.
- Works in submarines, rural offices, flight-mode development.
- No API rate limiting or external service outages.

---

## Before you pitch this internally

Three things to do first so the pitch survives scrutiny:

1. **Run `neuralmind benchmark . --contribute` on the actual repo** the team works on. Use those numbers, not the README's headline range.
2. **Read [HONEST-ASSESSMENT.md](HONEST-ASSESSMENT.md)** so you can answer the "what doesn't this help with?" question before someone in the meeting asks it.
3. **Pilot with one team for two weeks** before a wider rollout. Multi-language monorepos, generated code, and unusual project structures can drop retrieval quality below the headline numbers.

For deployment-architecture details (where artifacts live, how to refresh indexes in CI, what happens during a graphify upgrade), see [DEPLOYMENT-GUIDE.md](DEPLOYMENT-GUIDE.md).
