import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { RateValue } from '@/components/performance/Gated';
import { Prose, WorkingOn } from '@/components/performance/Narrative';
import ProfileCard from '@/components/performance/ProfileCard';
import RecordTable from '@/components/performance/RecordTable';
import Sparkline from '@/components/performance/Sparkline';
import { histories, parseNarrative, parseRecord, rateView, series, type ProjectHistory } from '@/lib/record';
import { NARRATIVE, NULL_HEAVY, SEED_JSONL, TWO_RUNS } from './fixtures';

const byProject = (text: string) => Object.fromEntries(histories(parseRecord(text)).map((h) => [h.project, h]));
const count = (html: string, needle: string) => html.split(needle).length - 1;

const table = (h: ProjectHistory) => renderToStaticMarkup(<RecordTable history={h} />);
const spark = (h: ProjectHistory, metric: 'hit_at_1' | 'hit_at_5' | 'ratio_vs_indexed') =>
    renderToStaticMarkup(
        <Sparkline
            points={series(h, metric)}
            label={metric}
            domain={metric === 'ratio_vs_indexed' ? undefined : [0, 1]}
            format={String}
        />,
    );

describe('RecordTable', () => {
    it('t0 seed: shows the measured ratio with its baseline, withholds rates without a gold-set size', () => {
        const seed = byProject(SEED_JSONL);
        const rf = table(seed['rfnode-guide']);
        expect(rf).toContain('60.3×');
        expect(rf).toContain('vs 52,218 measured tokens');
        expect(count(rf, 'not shown: gold-set size not recorded')).toBe(3); // hit@1, hit@5, MRR
        expect(rf).not.toContain('0.667');
        expect(rf).toContain('0.095 s');

        const bible = table(seed['bible-llm']);
        expect(bible).toContain('not shown: baseline size not recorded');
        expect(bible).not.toContain('273');
        expect(bible).not.toContain('0.417');
        expect(rf + bible).not.toContain('is-regressed');
    });

    it('two runs: highlights the drop in place and marks the version bump', () => {
        const html = table(byProject(TWO_RUNS)['rfnode-guide']);
        expect(count(html, 'class="is-regressed"')).toBe(1);
        expect(html).toContain('data-regressed="hit_at_1 mrr ratio_vs_indexed"');
        expect(html).toContain('↓ from 0.667');
        expect(html).toContain('↓ from 60.3×');
        expect(html).toContain('data-bump="4.21.0"');
        // Both runs' rates carry their gold-set size, misses and the small-sample badge.
        expect(html).toContain('8 of 12 · 4 missed');
        expect(html).toContain('7 of 12 · 5 missed');
        expect(count(html, 'Small sample')).toBe(6); // 3 rates × 2 runs
    });

    it('null-heavy: blanks stay blank and the synthetic-baseline run is counted, not shown', () => {
        const html = table(byProject(NULL_HEAVY).p);
        expect(count(html, '<tr')).toBe(1 + 6); // head + six published runs
        expect(html).not.toContain('2026-09-01');
        expect(html).not.toContain('41.8');
        expect(html).not.toContain('0.900');
        expect(html).toContain('Not shown: 1 run (baseline naive-50k)');
        expect(html).toContain('not shown: gold-set size not recorded'); // November
    });

    it('shows no small-sample badge on a large gold set', () => {
        expect(renderToStaticMarkup(<RateValue view={rateView(0.75, 60)} />)).not.toContain('Small sample');
        expect(renderToStaticMarkup(<RateValue view={rateView(0.75, 12)} />)).toContain('Small sample');
    });
});

describe('Sparkline', () => {
    it('t0 seed: one point where a value is shown, a gap tick where it is not', () => {
        const rf = byProject(SEED_JSONL)['rfnode-guide'];
        const ratio = spark(rf, 'ratio_vs_indexed');
        expect(count(ratio, 'data-point=')).toBe(1);
        expect(count(ratio, 'data-segment=')).toBe(0);
        const hit1 = spark(rf, 'hit_at_1');
        expect(count(hit1, 'data-point=')).toBe(0);
        expect(count(hit1, 'data-gap=')).toBe(1);
        expect(hit1).toContain('no value shown yet');
    });

    it('two runs: one segment, the drop drawn in the warning colour, the bump marked', () => {
        const svg = spark(byProject(TWO_RUNS)['rfnode-guide'], 'hit_at_1');
        expect(count(svg, 'data-segment="2"')).toBe(1);
        expect(count(svg, 'data-point=')).toBe(2);
        expect(count(svg, 'fill-warn')).toBe(1);
        expect(svg).toContain('data-bump="4.21.0"');
    });

    it('null-heavy: never draws a line across a null', () => {
        const svg = spark(byProject(NULL_HEAVY).p, 'hit_at_5');
        // 0.5, 0.6, null, 0.7, null, null: one two-point segment, a lone point, three gaps.
        expect(count(svg, 'data-segment=')).toBe(1);
        expect(count(svg, 'data-segment="2"')).toBe(1);
        expect(count(svg, 'data-point=')).toBe(3);
        expect(count(svg, 'data-gap=')).toBe(3);
        expect(svg).not.toContain('data-point="0.9"');
    });

    it('a rate axis is fixed at 0–1, so the same value sits at the same height', () => {
        const low = byProject(TWO_RUNS)['rfnode-guide'];
        const a = spark(low, 'hit_at_5');
        const y = [...a.matchAll(/data-point="0.75"[^>]*cy="([\d.]+)"/g)].map((m) => m[1]);
        expect(new Set(y).size).toBe(1);
    });
});

describe('ProfileCard', () => {
    it('says "not recorded" rather than filling in the repo shape', () => {
        const html = renderToStaticMarkup(
            <ProfileCard
                history={byProject(SEED_JSONL)['rfnode-guide']}
                shape={null}
                hardware="single RTX 5000 Ada 16GB dev box"
                method="neuralmind eval ."
                evidence="field-report"
            />,
        );
        expect(html).toContain('not recorded');
        expect(html).toContain('618 nodes');
        expect(html).toContain('single RTX 5000 Ada 16GB dev box');
        expect(html).toContain('60.3×');
    });
});

describe('narrative blocks', () => {
    const n = parseNarrative('2026-10.md', NARRATIVE);

    it('renders block A as elements: https links kept, markup printed as text', () => {
        const html = renderToStaticMarkup(<Prose markdown={n.site!} />);
        expect(html).toContain('<a href="https://github.com/dfrostar/neuralmind"');
        expect(html).toContain('<code');
        expect(html).toContain('<strong');
        expect(html).not.toContain('<script>');
        expect(html).toContain('&lt;script&gt;');
    });

    it('drops a link to anything but https:// or a site path', () => {
        const html = renderToStaticMarkup(<Prose markdown="[x](javascript:alert(1))" />);
        expect(html).not.toContain('<a');
    });

    it('tags block C items', () => {
        const html = renderToStaticMarkup(<WorkingOn items={n.working} />);
        expect(html).toContain('data-tag="moved"');
        expect(html).toContain('data-tag="stalled"');
    });
});

describe('/performance/linkedin.txt', () => {
    it('serves block B verbatim and nothing from the other blocks', async () => {
        vi.resetModules();
        vi.doMock('@/lib/performance', () => ({
            performanceRecord: () => ({ narrative: parseNarrative('2026-10.md', NARRATIVE) }),
        }));
        const { GET } = await import('@/app/performance/linkedin.txt/route');
        const body = await GET().text();
        expect(body).toBe('Our first month of public numbers.\n#retrieval\n');
        expect(body).not.toContain('First month on the record');
        expect(body).not.toContain('Gold sets are still small');
        vi.doUnmock('@/lib/performance');
    });

    it('is empty when no narrative is committed', async () => {
        vi.resetModules();
        vi.doMock('@/lib/performance', () => ({ performanceRecord: () => ({ narrative: null }) }));
        const { GET } = await import('@/app/performance/linkedin.txt/route');
        expect(await GET().text()).toBe('');
        vi.doUnmock('@/lib/performance');
    });
});
