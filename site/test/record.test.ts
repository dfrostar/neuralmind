import { mkdirSync, mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { assertNoIntegrityNotes, loadNarratives, performanceRecord } from '@/lib/performance';
import {
    INTEGRITY_NOTES,
    compatibleHits,
    histories,
    impliedHits,
    latestTs,
    isMeasured,
    isPublishable,
    latestNarrative,
    parseNarrative,
    parseRecord,
    rateView,
    ratioView,
    series,
} from '@/lib/record';
import { NARRATIVE, NULL_HEAVY, SEED_JSONL, TWO_RUNS, jsonl, row } from './fixtures';

describe('the "measured only" gate', () => {
    it.each([['naive-50k'], ['synthetic'], ['estimated'], [null], [''], ['Measured'], [' measured'], ['measured ']])(
        'rejects baseline_src %j',
        (src) => {
            expect(isMeasured(src)).toBe(false);
            const r = row({ ts: '2026-10-22', project: 'p', ratio_vs_indexed: 41.8, baseline_src: src, baseline_tok: 50000 });
            expect(isPublishable(r)).toBe(false);
            expect(ratioView(r).shown).toBe(false);
        },
    );

    it('accepts exactly "measured"', () => {
        expect(isMeasured('measured')).toBe(true);
    });

    it('withholds a synthetic-baseline row whole and counts it', () => {
        const [h] = histories(parseRecord(NULL_HEAVY));
        expect(h.runs.map((r) => r.row.ts)).not.toContain('2026-09-01');
        expect(h.withheld).toEqual({ 'baseline naive-50k': 1 });
        // Its hit@5 (0.9) is in no series either.
        expect(series(h, 'hit_at_5').map((p) => p.v)).not.toContain(0.9);
    });

    it('shows a measured ratio only beside its baseline size', () => {
        const [rf, bible] = histories(parseRecord(SEED_JSONL)).sort((a, b) => b.project.localeCompare(a.project));
        expect(ratioView(rf.runs[0].row)).toEqual({ shown: true, ratio: 60.3, baselineTok: 52218 });
        expect(ratioView(bible.runs[0].row)).toEqual({ shown: false, reason: 'baseline size not recorded' });
    });
});

describe('rates', () => {
    it('need a gold-set size, and count misses from it', () => {
        expect(rateView(0.667, null)).toEqual({ shown: false, reason: 'gold-set size not recorded' });
        expect(rateView(0.667, 12)).toMatchObject({ shown: true, hits: 8, misses: 4, n: 12, small: true });
        expect(rateView(0.75, 60)).toMatchObject({ hits: 45, misses: 15, small: false });
        // MRR has no miss count.
        expect(rateView(0.688, 12, false)).toMatchObject({ shown: true, hits: null, misses: null });
    });

    it('impliedHits respects the precision a rate is written to', () => {
        expect(impliedHits(0.667, 12)).toBe(8);
        expect(impliedHits(0.75, 12)).toBe(9);
        expect(impliedHits(0.417, 12)).toBe(5);
        expect(impliedHits(0.625, 12)).toBeNull(); // 7.5 hits
        // One decimal is coarse enough that 0.6 may be 7 of 12 rounded.
        expect(impliedHits(0.6, 12)).toBe(7);
    });
});

describe('hit counts', () => {
    it('are inferred only when one whole number fits the rate', () => {
        // 28/50 to 32/50 all round to 0.6: printing "30 of 50" would invent a count.
        expect(compatibleHits(0.6, 50)).toEqual([28, 29, 30, 31, 32]);
        expect(impliedHits(0.6, 50)).toBeNull();
        expect(rateView(0.6, 50)).toMatchObject({ shown: true, hits: null, misses: null });
        expect(compatibleHits(0.6667, 12)).toEqual([8]);
        expect(compatibleHits(0.625, 12)).toEqual([]);
    });

    it('reject a row whose rate fits several counts', () => {
        const r = row({ ts: '2026-10-22', project: 'p', hit_at_1: 0.6, hit_at_5: 0.62, gold_n: 50, baseline_src: 'measured' });
        expect(() => parseRecord(jsonl([r]))).toThrow(/hit_at_1 0.6 fits 28–32 hits out of gold_n 50; write it to more decimal places/);
        expect(() => parseRecord(jsonl([{ ...r, hit_at_1: 0.56 }]))).not.toThrow();
    });
});

describe('the ratio check', () => {
    // bible-llm's t0: 180,906 tokens over a mean of 662.7, recorded as 273.0.
    const base = row({ ts: '2026-10-22', project: 'p', ratio_vs_indexed: 273.0, baseline_src: 'measured', baseline_tok: 180906, avg_ctx_tok: 662.7 });

    it('accepts the ratio the producer would round to', () => {
        expect(() => parseRecord(jsonl([base]))).not.toThrow();
        expect(() => parseRecord(jsonl([{ ...base, ratio_vs_indexed: 60.3, baseline_tok: 52218, avg_ctx_tok: 866.2 }]))).not.toThrow();
    });

    it.each([[273.3], [273.1], [272.8]])('rejects %s, which no mean rounding to 662.7 gives', (ratio) => {
        expect(() => parseRecord(jsonl([{ ...base, ratio_vs_indexed: ratio }]))).toThrow(/disagrees with baseline_tok \/ avg_ctx_tok/);
    });

    it('rejects a ratio over zero context tokens', () => {
        expect(() => parseRecord(jsonl([{ ...base, avg_ctx_tok: 0 }]))).toThrow(/avg_ctx_tok is 0/);
    });
});

describe('latestTs', () => {
    it('orders by time, not by string', () => {
        expect(latestTs(['2026-10-23T00:15:00+02:00', '2026-10-22T23:00:00Z'])).toBe('2026-10-22T23:00:00Z');
        expect(latestTs(['2026-10-22', '2026-11-20'])).toBe('2026-11-20');
        expect(latestTs([])).toBeNull();
    });
});

describe('parseRecord', () => {
    it('loads the t0 seed with its nulls intact', () => {
        const rows = parseRecord(SEED_JSONL);
        expect(rows).toHaveLength(2);
        const bible = rows.find((r) => r.project === 'bible-llm')!;
        expect(bible.mrr).toBeNull();
        expect(bible.gold_n).toBeNull();
        expect(bible.ratio_vs_indexed).toBe(273.0);
    });

    it('reads a row without the two added fields as null', () => {
        const r = JSON.parse(SEED_JSONL.split('\n')[0]);
        delete r.gold_n;
        delete r.baseline_tok;
        expect(parseRecord(JSON.stringify(r))[0]).toMatchObject({ gold_n: null, baseline_tok: null });
    });

    it.each([
        ['an unknown field', { hit_at1: 0.5 }, /unknown field "hit_at1"/],
        ['a rate above 1', { hit_at_5: 1.2 }, /hit_at_5 must be in \[0, 1\]/],
        ['hit@1 above hit@5', { hit_at_1: 0.9, hit_at_5: 0.5 }, /hit_at_1 is above hit_at_5/],
        ['MRR below hit@1', { hit_at_1: 0.5, mrr: 0.4 }, /mrr is below hit_at_1/],
        ['a rate that is no whole count of gold_n', { hit_at_1: 0.625, gold_n: 12 }, /not a whole number of hits/],
        ['a ratio its own fields contradict', { ratio_vs_indexed: 60.3, baseline_tok: 52218, avg_ctx_tok: 500 }, /disagrees/],
        ['a bad timestamp', { ts: 'last tuesday' }, /ts must be an ISO 8601/],
        ['a day past the end of its month', { ts: '2026-04-31' }, /ts must be an ISO 8601/],
        ['February 30', { ts: '2026-02-30T03:38:39' }, /ts must be an ISO 8601/],
        ['February 29 outside a leap year', { ts: '2026-02-29' }, /ts must be an ISO 8601/],
        ['an hour past 23', { ts: '2026-10-22T25:00' }, /ts must be an ISO 8601/],
        ['a fractional node count', { nodes: 61.8 }, /nodes must be a whole number/],
    ])('rejects %s', (_label, change, message) => {
        const r = { ...JSON.parse(SEED_JSONL.split('\n')[0]), ...change };
        expect(() => parseRecord(JSON.stringify(r))).toThrow(message);
    });

    it('accepts a real leap day and a date-time with a zone', () => {
        for (const ts of ['2028-02-29', '2026-10-22T03:38:39', '2026-10-22T03:38:39+01:00']) {
            const r = { ...JSON.parse(SEED_JSONL.split('\n')[0]), ts };
            expect(parseRecord(JSON.stringify(r))[0].ts).toBe(ts);
        }
    });

    it('rejects a missing field rather than guessing it', () => {
        const r = JSON.parse(SEED_JSONL.split('\n')[0]);
        delete r.synapse_edges;
        expect(() => parseRecord(JSON.stringify(r), 'record.jsonl')).toThrow(/record.jsonl:1: missing field "synapse_edges"/);
    });

    it('rejects a duplicate run', () => {
        const line = SEED_JSONL.split('\n')[0];
        expect(() => parseRecord(`${line}\n${line}`)).toThrow(/a second row for rfnode-guide/);
    });
});

describe('histories', () => {
    it('marks a drop and a version bump, keeping the row', () => {
        const [h] = histories(parseRecord(TWO_RUNS));
        expect(h.runs).toHaveLength(2);
        expect(h.runs[1].versionBump).toEqual({ from: '4.20.0', to: '4.21.0' });
        expect(h.runs[1].regressions.map((r) => r.metric)).toEqual(['hit_at_1', 'mrr', 'ratio_vs_indexed']);
        expect(h.runs[0].regressions).toEqual([]);
    });

    it('compares a drop against the last run that showed the metric, across a blank', () => {
        const rows = parseRecord(
            jsonl([
                row({ ts: '2026-01-01', project: 'p', hit_at_5: 0.6, gold_n: 10, baseline_src: 'measured' }),
                row({ ts: '2026-02-01', project: 'p', baseline_src: 'measured' }),
                row({ ts: '2026-03-01', project: 'p', hit_at_5: 0.5, gold_n: 10, baseline_src: 'measured' }),
            ]),
        );
        const [h] = histories(rows);
        expect(h.runs[2].regressions).toEqual([{ metric: 'hit_at_5', from: 0.6, to: 0.5 }]);
    });

    it('never fills a null in a series', () => {
        const [h] = histories(parseRecord(NULL_HEAVY));
        expect(series(h, 'hit_at_5').map((p) => p.v)).toEqual([0.5, 0.6, null, 0.7, null, null]);
    });
});

describe('narratives', () => {
    it('parses blocks A–C', () => {
        const n = parseNarrative('2026-10.md', NARRATIVE);
        expect(n.month).toBe('2026-10');
        expect(n.site).toContain('First month on the record');
        expect(n.linkedin).toBe('Our first month of public numbers.\n#retrieval');
        expect(n.working).toEqual([
            { tag: 'moved', text: 'Top-1 ranking on bible-llm, where most misses are.' },
            { tag: 'stalled', text: 'Gold sets are still small.' },
        ]);
        expect(Object.keys(n).sort()).toEqual(['linkedin', 'month', 'site', 'working']);
    });

    it.each([
        ['a heading nested in a block', `${NARRATIVE}\n### Aside\n`, /only the ## A–C/],
        ['an unknown block', `${NARRATIVE}\n## E. Extra\n`, /unknown block "E"/],
        ['a repeated block', `${NARRATIVE}\n## A. Again\n`, /block A appears twice/],
        ['an untagged C item', NARRATIVE.replace('- [stalled]', '- '), /block C lines are/],
        ['an unknown C tag', NARRATIVE.replace('[stalled]', '[shipped]'), /\[shipped\] is not/],
    ])('rejects %s', (_label, text, message) => {
        expect(() => parseNarrative('2026-10.md', text)).toThrow(message);
    });

    it.each([
        ['a block D', `${NARRATIVE}\n## D. Integrity\n\nt0 was re-run once.\n`],
        ['a bare D heading', `${NARRATIVE}\n## D\n`],
        ['an integrity heading at any level', `${NARRATIVE}\n### Integrity notes\n`],
        ['an integrity title', `# 2026-10 integrity\n\n## A. Site\n\nText.\n`],
    ])('sends %s to the private repo instead of parsing it', (_label, text) => {
        expect(() => parseNarrative('2026-10.md', text)).toThrow(
            new RegExp(`not committed to this public repo; keep them in ${INTEGRITY_NOTES.replace(/[.*+?^${}()|[\]\\/]/g, '\\$&')}`),
        );
    });

    it('names the private repo for integrity notes', () => {
        expect(INTEGRITY_NOTES).toContain('dfrostar/neuralmind-marketing');
    });

    it('reads only YYYY-MM.md files and picks the latest month', () => {
        const dir = mkdtempSync(path.join(tmpdir(), 'narratives-'));
        writeFileSync(path.join(dir, 'TEMPLATE.md'), '## Z\nnot a narrative');
        writeFileSync(path.join(dir, '2026-10.md'), NARRATIVE);
        writeFileSync(path.join(dir, '2026-11.md'), '## A. Site\n\nNovember.\n');
        const all = loadNarratives(dir);
        expect(all.map((n) => n.month).sort()).toEqual(['2026-10', '2026-11']);
        expect(latestNarrative(all)?.site).toBe('November.');
    });
});

describe('assertNoIntegrityNotes', () => {
    const tree = (files: Record<string, string>) => {
        const root = mkdtempSync(path.join(tmpdir(), 'record-'));
        for (const [rel, text] of Object.entries(files)) {
            mkdirSync(path.dirname(path.join(root, rel)), { recursive: true });
            writeFileSync(path.join(root, rel), text);
        }
        return { root, narratives: path.join(root, 'narratives') };
    };

    it('passes a clean record', () => {
        const { root, narratives } = tree({ 'record.jsonl': '', 'narratives/2026-10.md': NARRATIVE, 'narratives/TEMPLATE.md': '## A\nText.' });
        expect(() => assertNoIntegrityNotes(root, narratives)).not.toThrow();
    });

    it.each([
        ['a file named for integrity notes among the narratives', { 'narratives/integrity-notes.md': 'Re-ran once.' }, /integrity-notes.md: named for integrity notes/],
        ['one anywhere else under the record', { 'raw/2026-10-integrity.json': '{}' }, /2026-10-integrity.json: named for integrity notes/],
        ['an integrity heading in the template, which the loader never reads', { 'narratives/TEMPLATE.md': '## A\n## D. Integrity\n' }, /TEMPLATE.md:2: an integrity heading/],
    ])('fails the build on %s', (_label, files, message) => {
        const { root, narratives } = tree({ 'record.jsonl': '', 'narratives/2026-10.md': NARRATIVE, ...files });
        expect(() => assertNoIntegrityNotes(root, narratives)).toThrow(message);
    });
});

describe('the committed record', () => {
    it('loads, and every project in it has a profile', () => {
        const record = performanceRecord();
        expect(record.projects.length).toBeGreaterThan(0);
        for (const p of record.projects) expect(record.profile.projects).toHaveProperty(p.project);
    });
});
