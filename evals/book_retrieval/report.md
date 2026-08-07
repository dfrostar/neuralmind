# Book Retrieval Eval Report v2 — N-15 IR Metrics + RAGAS

**Book:** Underground  
**Queries:** 30  

## Aggregates

| Metric | Value |
|--------|-------|
| recall@5 | 0.327 |
| MRR | 0.733 |
| nDCG@5 | 0.530 |
| hit_rate | 1.000 |
| mean_faithfulness | 0.010 |
| avg_token_reduction | 248.2x |

## Per-Shape Breakdown

### causal (11 queries)

- recall@5: 0.318
- MRR: 0.818
- hit_rate: 1.000
- faithfulness: 0.009

### entity (9 queries)

- recall@5: 0.322
- MRR: 0.667
- hit_rate: 1.000
- faithfulness: 0.000

### precise (7 queries)

- recall@5: 0.343
- MRR: 0.714
- hit_rate: 1.000
- faithfulness: 0.014

### temporal (2 queries)

- recall@5: 0.300
- MRR: 0.500
- hit_rate: 1.000
- faithfulness: 0.000

### thematic (1 queries)

- recall@5: 0.400
- MRR: 1.000
- hit_rate: 1.000
- faithfulness: 0.100

## Per-Query Breakdown

- [✓] **wank-worm-origin** — recall@5=0.20, mrr=1.00, faith=0.00
- [✓] **wank-australian-origin** — recall@5=0.30, mrr=0.50, faith=0.00
- [✓] **span-network** — recall@5=0.30, mrr=0.50, faith=0.00
- [✓] **citibank-hack** — recall@5=0.40, mrr=1.00, faith=0.00
- [✓] **par-fugitive** — recall@5=0.30, mrr=0.50, faith=0.00
- [✓] **phoenix-style** — recall@5=0.40, mrr=1.00, faith=0.00
- [✓] **pad-gandalf-worms** — recall@5=0.40, mrr=1.00, faith=0.10
- [✓] **anthrax-profile** — recall@5=0.30, mrr=1.00, faith=0.00
- [✓] **telephone-exchange-hazard** — recall@5=0.40, mrr=1.00, faith=0.00
- [✓] **operation-weather-afp** — recall@5=0.20, mrr=1.00, faith=0.00
- [✓] **force-realm-bbs** — recall@5=0.30, mrr=0.50, faith=0.00
- [✓] **altos-chat** — recall@5=0.40, mrr=1.00, faith=0.00
- [✓] **midnight-oil-connection** — recall@5=0.30, mrr=0.50, faith=0.00
- [✓] **freekers** — recall@5=0.30, mrr=0.50, faith=0.00
- [✓] **x25-networks** — recall@5=0.30, mrr=1.00, faith=0.10
- [✓] **eugene-spafford** — recall@5=0.40, mrr=1.00, faith=0.00
- [✓] **three-realm-hackers** — recall@5=0.30, mrr=0.50, faith=0.00
- [✓] **rtm-worm** — recall@5=0.30, mrr=0.50, faith=0.00
- [✓] **2600-hertz** — recall@5=0.30, mrr=0.50, faith=0.00
- [✓] **computer-misuse-act** — recall@5=0.30, mrr=0.50, faith=0.00
- [✓] **handles-purpose** — recall@5=0.40, mrr=1.00, faith=0.00
- [✓] **first-creation** — recall@5=0.30, mrr=0.50, faith=0.00
- [✓] **oilz-worm-variant** — recall@5=0.30, mrr=0.50, faith=0.00
- [✓] **underground-evolution** — recall@5=0.30, mrr=0.50, faith=0.00
- [✓] **deccnet-security** — recall@5=0.40, mrr=1.00, faith=0.00
- [✓] **hacker-motivations** — recall@5=0.30, mrr=0.50, faith=0.00
- [✓] **galileo-controversy** — recall@5=0.30, mrr=0.50, faith=0.00
- [✓] **rmit-hacking-hub** — recall@5=0.40, mrr=1.00, faith=0.00
- [✓] **secretservice-methods** — recall@5=0.30, mrr=0.50, faith=0.00
- [✓] **telsa-not-telstra** — recall@5=0.40, mrr=1.00, faith=0.10
