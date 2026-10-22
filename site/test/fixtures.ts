import { FIELDS, type RecordRow } from '@/lib/record';

/**
 * t0 (2026-10-22) as first reported, before the gold-set size and bible-llm's
 * baseline were read from the run: rates rounded to three places, everything
 * unreported null. The committed record now carries the run's full values;
 * this stays as the 2-row fixture with nulls where a ratio or rate must be
 * withheld.
 */
export const SEED_JSONL = [
    '{"ts": "2026-10-22", "project": "rfnode-guide", "version": null, "git_sha": null, "hit_at_1": 0.667, "hit_at_5": 0.750, "mrr": 0.688, "avg_ctx_tok": null, "ratio_vs_indexed": 60.3, "baseline_src": "measured", "baseline_tok": 52218, "gold_n": null, "nodes": 618, "synapse_edges": null, "index_age_h": null, "builds_7d": null, "mean_build_s": null, "saved_tokens_cum": null, "median_query_s": 0.095}',
    '{"ts": "2026-10-22", "project": "bible-llm", "version": null, "git_sha": null, "hit_at_1": 0.417, "hit_at_5": 0.833, "mrr": null, "avg_ctx_tok": null, "ratio_vs_indexed": 273.0, "baseline_src": "measured", "baseline_tok": null, "gold_n": null, "nodes": 1941, "synapse_edges": null, "index_age_h": null, "builds_7d": null, "mean_build_s": null, "saved_tokens_cum": null, "median_query_s": 0.094}',
].join('\n');

const EMPTY = Object.fromEntries([...FIELDS, 'gold_n', 'baseline_tok'].map((k) => [k, null])) as unknown as RecordRow;

/** A row with every field null except the ones given. */
export function row(fields: Partial<RecordRow> & Pick<RecordRow, 'ts' | 'project'>): RecordRow {
    return { ...EMPTY, ...fields };
}

export const jsonl = (rows: object[]) => rows.map((r) => JSON.stringify(r)).join('\n');

/**
 * rfnode-guide's t0 (gold set of 12, as recorded), then a second month that
 * drops on hit@1, MRR and ratio under a new version. The second run is
 * hypothetical: there isn't one yet.
 */
export const TWO_RUNS = jsonl([
    row({ ts: '2026-10-22', project: 'rfnode-guide', version: '4.20.0', hit_at_1: 0.667, hit_at_5: 0.75, mrr: 0.688, ratio_vs_indexed: 60.3, baseline_src: 'measured', baseline_tok: 52218, gold_n: 12, nodes: 618, median_query_s: 0.095 }),
    row({ ts: '2026-11-20', project: 'rfnode-guide', version: '4.21.0', hit_at_1: 0.583, hit_at_5: 0.75, mrr: 0.66, ratio_vs_indexed: 58.9, baseline_src: 'measured', baseline_tok: 52990, gold_n: 12, nodes: 640, median_query_s: 0.097 }),
]);

/** Six months of one project with most fields null and one synthetic baseline. */
export const NULL_HEAVY = jsonl([
    row({ ts: '2026-05-01', project: 'p', hit_at_5: 0.5, gold_n: 10, baseline_src: 'measured' }),
    row({ ts: '2026-06-01', project: 'p', hit_at_5: 0.6, gold_n: 10, baseline_src: 'measured' }),
    row({ ts: '2026-07-01', project: 'p', baseline_src: 'measured' }),
    row({ ts: '2026-08-01', project: 'p', hit_at_5: 0.7, gold_n: 10, baseline_src: 'measured' }),
    row({ ts: '2026-09-01', project: 'p', hit_at_5: 0.9, ratio_vs_indexed: 41.8, gold_n: 10, baseline_src: 'naive-50k', baseline_tok: 50000 }),
    row({ ts: '2026-10-01', project: 'p', hit_at_5: null, gold_n: 10, baseline_src: 'measured' }),
    row({ ts: '2026-11-01', project: 'p', hit_at_5: 0.8, gold_n: null, baseline_src: 'measured' }),
]);

export const NARRATIVE = `# 2026-10 — performance record

## A. Site

First month on the record. See [the raw rows](https://github.com/dfrostar/neuralmind) and \`neuralmind eval .\`.

- **hit@5** is the headline.
- <script>alert(1)</script> stays text.

## B. LinkedIn

Our first month of public numbers.
#retrieval

## C. What we are working on

- [moved] Top-1 ranking on bible-llm,
  where most misses are.
- [stalled] Gold sets are still small.

## D. Integrity

SECRET-INTEGRITY-NOTE: t0 was re-run once after a cold cache.
`;
