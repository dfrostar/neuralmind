/**
 * The longitudinal performance record: rows of `benchmarks/ai9970/record.jsonl`
 * and the monthly narratives beside it, parsed, validated and gated.
 *
 * Pure: no filesystem, so the gates can be tested on fixtures. `performance.ts`
 * reads the files and calls into here at build time.
 *
 * The honest-render rules live here as functions, not as copy, so a component
 * cannot show a number without going through them:
 *
 * - `isPublishable`: a row whose `baseline_src` is not exactly "measured" is
 *   withheld whole. The page shows how many were withheld and why.
 * - `ratioView`: a ratio renders only beside its measured baseline, in tokens.
 * - `rateView`: a hit rate renders only with its gold-set size and the misses
 *   counted from it; a small gold set is flagged.
 * - `regressions`: a drop from the project's previous run is reported, so the
 *   row is highlighted rather than left out.
 *
 * Nothing here interpolates: a null stays null all the way to the page.
 */

import claims from '../../claims.json';

export const MEASURED = 'measured';

/**
 * Below this many questions a rate is flagged "small sample". The site already
 * calls the public benchmark's 40 queries a small sample (site/claims.json), so
 * the line sits above 40.
 */
export const SMALL_SAMPLE_N = 50;

/** The fields of the data contract, in the order the record writes them. */
export const FIELDS = [
    'ts',
    'project',
    'version',
    'git_sha',
    'hit_at_1',
    'hit_at_5',
    'mrr',
    'avg_ctx_tok',
    'ratio_vs_indexed',
    'baseline_src',
    'nodes',
    'synapse_edges',
    'index_age_h',
    'builds_7d',
    'mean_build_s',
    'saved_tokens_cum',
    'median_query_s',
] as const;

/**
 * Added to the contract so the rules above can be met: `neuralmind eval`
 * reports both (`n_questions`, `baseline_tokens`) but the original row shape
 * dropped them. A row may leave them out; that reads as null.
 */
export const OPTIONAL_FIELDS = ['gold_n', 'baseline_tok'] as const;

export interface RecordRow {
    /** ISO 8601 date or date-time of the run. */
    ts: string;
    project: string;
    version: string | null;
    git_sha: string | null;
    hit_at_1: number | null;
    hit_at_5: number | null;
    mrr: number | null;
    avg_ctx_tok: number | null;
    ratio_vs_indexed: number | null;
    baseline_src: string | null;
    nodes: number | null;
    synapse_edges: number | null;
    index_age_h: number | null;
    builds_7d: number | null;
    mean_build_s: number | null;
    saved_tokens_cum: number | null;
    median_query_s: number | null;
    /** Gold-set size: the number of questions the rates are over. */
    gold_n: number | null;
    /** The measured baseline the ratio divides, in tokens. */
    baseline_tok: number | null;
}

const RATES = ['hit_at_1', 'hit_at_5', 'mrr'] as const;
const COUNTS = ['nodes', 'synapse_edges', 'builds_7d', 'saved_tokens_cum', 'gold_n', 'baseline_tok'] as const;
const NON_NEGATIVE = ['avg_ctx_tok', 'ratio_vs_indexed', 'index_age_h', 'mean_build_s', 'median_query_s'] as const;
const STRINGS = ['version', 'git_sha', 'baseline_src'] as const;

const TS_RE = /^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?)?$/;
const PROJECT_RE = /^[A-Za-z0-9._-]+$/;

function fail(where: string, message: string): never {
    throw new Error(`${where}: ${message}`);
}

/** Digits after the decimal point, as the number is written: 0.75 -> 2, 0.667 -> 3. */
function decimals(value: number): number {
    const text = String(value);
    if (text.includes('e-')) return Number(text.split('e-')[1]);
    const dot = text.indexOf('.');
    return dot === -1 ? 0 : text.length - dot - 1;
}

/**
 * Hits implied by a rate over `n` questions, or null when the rate is not a
 * whole count of `n` at the precision it is written to. 0.667 of 12 is 8;
 * 0.625 of 12 is 7.5, which no run produces (0.6 could be 7 of 12, rounded).
 */
export function impliedHits(rate: number, n: number): number | null {
    const hits = Math.round(rate * n);
    const tolerance = n * 0.5 * 10 ** -decimals(rate) + 1e-9;
    return Math.abs(rate * n - hits) <= tolerance ? hits : null;
}

/**
 * Check one parsed row against the contract and its own arithmetic. Throws
 * with the line number on anything malformed, so a bad row fails the build
 * instead of rendering.
 */
export function validateRow(raw: unknown, where: string): RecordRow {
    if (typeof raw !== 'object' || raw === null || Array.isArray(raw)) fail(where, 'not a JSON object');
    const obj = raw as Record<string, unknown>;
    const known = new Set<string>([...FIELDS, ...OPTIONAL_FIELDS]);
    for (const key of Object.keys(obj)) {
        if (!known.has(key)) fail(where, `unknown field "${key}" (the contract is in benchmarks/ai9970/README.md)`);
    }
    for (const key of FIELDS) {
        if (!(key in obj)) fail(where, `missing field "${key}" (write null when it was not recorded)`);
    }
    const row = { gold_n: null, baseline_tok: null, ...obj } as RecordRow;

    if (typeof row.ts !== 'string' || !TS_RE.test(row.ts) || Number.isNaN(Date.parse(row.ts))) {
        fail(where, `ts must be an ISO 8601 date or date-time, got ${JSON.stringify(row.ts)}`);
    }
    if (typeof row.project !== 'string' || !PROJECT_RE.test(row.project)) {
        fail(where, `project must be a repo name, got ${JSON.stringify(row.project)}`);
    }
    for (const key of STRINGS) {
        const v = row[key];
        if (v !== null && (typeof v !== 'string' || v.trim() === '')) fail(where, `${key} must be a non-empty string or null`);
    }
    for (const key of RATES) {
        const v = row[key];
        if (v !== null && (typeof v !== 'number' || !(v >= 0 && v <= 1))) fail(where, `${key} must be in [0, 1] or null`);
    }
    for (const key of COUNTS) {
        const v = row[key];
        if (v !== null && (!Number.isInteger(v) || (v as number) < 0)) fail(where, `${key} must be a whole number or null`);
    }
    for (const key of NON_NEGATIVE) {
        const v = row[key];
        if (v !== null && (typeof v !== 'number' || !Number.isFinite(v) || v < 0)) fail(where, `${key} must be a number ≥ 0 or null`);
    }
    if (row.gold_n === 0) fail(where, 'gold_n is 0: a rate over no questions is not a measurement');

    // The rates' own arithmetic. A row that breaks it was mistyped.
    if (row.hit_at_1 !== null && row.hit_at_5 !== null && row.hit_at_1 > row.hit_at_5) {
        fail(where, 'hit_at_1 is above hit_at_5');
    }
    if (row.hit_at_1 !== null && row.mrr !== null && row.mrr + 0.0005 < row.hit_at_1) {
        fail(where, 'mrr is below hit_at_1 (every rank-1 hit adds 1 to the mean)');
    }
    if (row.gold_n !== null) {
        for (const key of ['hit_at_1', 'hit_at_5'] as const) {
            const v = row[key];
            if (v !== null && impliedHits(v, row.gold_n) === null) {
                fail(where, `${key} ${v} is not a whole number of hits out of gold_n ${row.gold_n}`);
            }
        }
    }
    // The ratio is the baseline over the mean context; when the row has all
    // three, they must agree to the ratio's one decimal.
    if (row.ratio_vs_indexed !== null && row.baseline_tok !== null && row.avg_ctx_tok) {
        const recomputed = row.baseline_tok / row.avg_ctx_tok;
        if (Math.abs(recomputed - row.ratio_vs_indexed) > 0.051 + row.ratio_vs_indexed * 1e-3) {
            fail(
                where,
                `ratio_vs_indexed ${row.ratio_vs_indexed} disagrees with baseline_tok / avg_ctx_tok = ${recomputed.toFixed(2)}`,
            );
        }
    }
    return row;
}

/** Parse the JSONL text, one row per non-blank line, oldest first. */
export function parseRecord(text: string, file = 'record.jsonl'): RecordRow[] {
    const rows: RecordRow[] = [];
    const seen = new Set<string>();
    text.split('\n').forEach((line, i) => {
        if (!line.trim()) return;
        const where = `${file}:${i + 1}`;
        let raw: unknown;
        try {
            raw = JSON.parse(line);
        } catch {
            fail(where, 'not valid JSON');
        }
        const row = validateRow(raw, where);
        const key = `${row.project}@${row.ts}`;
        if (seen.has(key)) fail(where, `a second row for ${row.project} at ${row.ts}`);
        seen.add(key);
        rows.push(row);
    });
    return rows.sort((a, b) => Date.parse(a.ts) - Date.parse(b.ts) || a.project.localeCompare(b.project));
}

// --------------------------------------------------------------------------
// Gates
// --------------------------------------------------------------------------

/** The "measured only" gate. Exact match: "naive-50k", null, "Measured" all fail. */
export function isMeasured(baselineSrc: unknown): boolean {
    return baselineSrc === MEASURED;
}

/** Whether any of a row may be published. */
export function isPublishable(row: RecordRow): boolean {
    return isMeasured(row.baseline_src);
}

export type Withheld = { shown: false; reason: string };

export type RatioView = { shown: true; ratio: number; baselineTok: number } | Withheld;

/** A ratio and its baseline, or why it is not shown. */
export function ratioView(row: RecordRow): RatioView {
    if (row.ratio_vs_indexed === null) return { shown: false, reason: 'not recorded' };
    if (!isMeasured(row.baseline_src)) {
        return { shown: false, reason: `baseline is ${row.baseline_src ?? 'not recorded'}, not measured` };
    }
    if (row.baseline_tok === null) return { shown: false, reason: 'baseline size not recorded' };
    return { shown: true, ratio: row.ratio_vs_indexed, baselineTok: row.baseline_tok };
}

export type RateView =
    | { shown: true; value: number; n: number; hits: number | null; misses: number | null; small: boolean }
    | Withheld;

/**
 * A rate with its gold-set size, or why it is not shown. `hits` and `misses`
 * are counted for hit rates; MRR has no miss count (`counted: false`), since a
 * question found past the fifth file still adds to it.
 */
export function rateView(value: number | null, n: number | null, counted = true): RateView {
    if (value === null) return { shown: false, reason: 'not recorded' };
    if (n === null) return { shown: false, reason: 'gold-set size not recorded' };
    const hits = counted ? impliedHits(value, n) : null;
    return { shown: true, value, n, hits, misses: hits === null ? null : n - hits, small: n < SMALL_SAMPLE_N };
}

export type Metric = 'hit_at_1' | 'hit_at_5' | 'mrr' | 'ratio_vs_indexed';

export const METRIC_LABELS: Record<Metric, string> = {
    hit_at_1: 'hit@1',
    hit_at_5: 'hit@5',
    mrr: 'MRR',
    ratio_vs_indexed: 'vs indexed code',
};

/** The value a metric shows for a row, or null when it is withheld. */
export function shownValue(row: RecordRow, metric: Metric): number | null {
    if (!isPublishable(row)) return null;
    if (metric === 'ratio_vs_indexed') {
        const v = ratioView(row);
        return v.shown ? v.ratio : null;
    }
    const v = rateView(row[metric], row.gold_n, metric !== 'mrr');
    return v.shown ? v.value : null;
}

export interface Regression {
    metric: Metric;
    from: number;
    to: number;
}

const METRICS = ['hit_at_1', 'hit_at_5', 'mrr', 'ratio_vs_indexed'] as const;

/** Each metric's most recent shown value across `runs`, oldest first. */
export function lastShown(runs: RecordRow[]): Partial<Record<Metric, number>> {
    const out: Partial<Record<Metric, number>> = {};
    for (const run of runs) {
        for (const metric of METRICS) {
            const v = shownValue(run, metric);
            if (v !== null) out[metric] = v;
        }
    }
    return out;
}

/**
 * Metrics that fell in `row` from the last earlier run that showed them. A
 * run with a blank in between is skipped over, not compared against, so a
 * drop can't hide behind a month that didn't record the metric. Only shown
 * values are compared: a withheld one can't leak through a highlight.
 */
export function regressions(earlier: Partial<Record<Metric, number>>, row: RecordRow): Regression[] {
    const out: Regression[] = [];
    for (const metric of METRICS) {
        const from = earlier[metric];
        const to = shownValue(row, metric);
        if (from !== undefined && to !== null && to < from) out.push({ metric, from, to });
    }
    return out;
}

export interface ProjectRun {
    row: RecordRow;
    /** Set when the version differs from the last published run that recorded one. */
    versionBump: { from: string; to: string } | null;
    regressions: Regression[];
    /** Set when the gold set changed size since the last run that recorded it. */
    goldChanged: { from: number; to: number } | null;
}

export interface ProjectHistory {
    project: string;
    runs: ProjectRun[];
    /** Rows withheld whole, by reason, e.g. { "baseline is naive-50k": 2 }. */
    withheld: Record<string, number>;
}

/** Group rows by project (first-seen order), gate them, and mark bumps and drops. */
export function histories(rows: RecordRow[]): ProjectHistory[] {
    const byProject = new Map<string, RecordRow[]>();
    for (const row of rows) {
        if (!byProject.has(row.project)) byProject.set(row.project, []);
        byProject.get(row.project)!.push(row);
    }
    return [...byProject].map(([project, all]) => {
        const withheld: Record<string, number> = {};
        const published: ProjectRun[] = [];
        for (const row of all) {
            if (!isPublishable(row)) {
                const reason = `baseline ${row.baseline_src ?? 'not recorded'}`;
                withheld[reason] = (withheld[reason] ?? 0) + 1;
                continue;
            }
            const earlier = published.map((r) => r.row);
            const prevVersion = earlier.findLast((r) => r.version !== null)?.version ?? null;
            const prevGold = earlier.findLast((r) => r.gold_n !== null)?.gold_n ?? null;
            published.push({
                row,
                versionBump:
                    prevVersion && row.version && prevVersion !== row.version ? { from: prevVersion, to: row.version } : null,
                regressions: regressions(lastShown(earlier), row),
                goldChanged:
                    prevGold !== null && row.gold_n !== null && prevGold !== row.gold_n
                        ? { from: prevGold, to: row.gold_n }
                        : null,
            });
        }
        return { project, runs: published, withheld };
    });
}

export interface SeriesPoint {
    /** Run time, ms since the epoch. */
    t: number;
    /** The shown value; null when not recorded or withheld. Never filled in. */
    v: number | null;
    /** The version this run bumped to, when it did. */
    bump: string | null;
    regressed: boolean;
}

/** One metric over a project's published runs, for a sparkline. */
export function series(history: ProjectHistory, metric: Metric): SeriesPoint[] {
    return history.runs.map((run) => ({
        t: Date.parse(run.row.ts),
        v: shownValue(run.row, metric),
        bump: run.versionBump?.to ?? null,
        regressed: run.regressions.some((r) => r.metric === metric),
    }));
}

// --------------------------------------------------------------------------
// Narratives
// --------------------------------------------------------------------------

export const NARRATIVE_FILE_RE = /^(\d{4})-(\d{2})\.md$/;

export type WorkTag = 'moved' | 'stalled';

export interface WorkItem {
    tag: WorkTag;
    text: string;
}

/**
 * A month's narrative. Every block is published: A on /performance, B at
 * /performance/linkedin.txt, C on /performance. Integrity notes are not a
 * block: they live in the private repo (`INTEGRITY_NOTES`), because this repo
 * and everything committed to it is public on GitHub.
 */
export interface Narrative {
    month: string;
    /** Block A: Markdown subset rendered inline on /performance. */
    site: string | null;
    /** Block B: plain text served at /performance/linkedin.txt. */
    linkedin: string | null;
    /** Block C: areas for improvement, each tagged. */
    working: WorkItem[];
}

/** Where integrity notes go instead, from site/claims.json. */
export const INTEGRITY_NOTES = claims.longitudinal_record.integrity_notes;

const BLOCK_RE = /^##\s+([A-Z])\b/;
const ANY_HEADING_RE = /^\s{0,3}#{1,6}(\s|$)/;
const ITEM_RE = /^- \[([a-z]+)\]\s+(.+)$/;

/**
 * Split a narrative into blocks A–C by its `## A` … `## C` headings. Any other
 * heading is an error rather than content, so nothing can sit in a published
 * block under a heading of its own; one that looks like integrity notes (a
 * `## D` block, or a heading naming integrity) says where those go.
 */
export function parseNarrative(fileName: string, text: string): Narrative {
    const m = NARRATIVE_FILE_RE.exec(fileName);
    if (!m || Number(m[2]) < 1 || Number(m[2]) > 12) fail(fileName, 'narratives are named YYYY-MM.md');
    const blocks: Partial<Record<'A' | 'B' | 'C', string[]>> = {};
    let current: 'A' | 'B' | 'C' | null = null;
    text.split('\n').forEach((line, i) => {
        const where = `${fileName}:${i + 1}`;
        if (ANY_HEADING_RE.test(line) && (/integrity/i.test(line) || /^##\s+D\b/.test(line))) {
            fail(where, `integrity notes are not committed to this public repo; keep them in ${INTEGRITY_NOTES}`);
        }
        const block = BLOCK_RE.exec(line);
        if (block) {
            const letter = block[1];
            if (letter !== 'A' && letter !== 'B' && letter !== 'C') fail(where, `unknown block "${letter}" (A–C only)`);
            if (blocks[letter]) fail(where, `block ${letter} appears twice`);
            current = letter;
            blocks[letter] = [];
            return;
        }
        if (ANY_HEADING_RE.test(line)) {
            // The title line above the first block is the only other heading allowed.
            if (current === null && /^#\s/.test(line)) return;
            fail(where, 'only the ## A–C block headings may appear in a narrative');
        }
        if (current !== null) blocks[current]!.push(line);
    });

    const body = (lines?: string[]) => {
        const joined = (lines ?? []).join('\n').trim();
        return joined === '' ? null : joined;
    };

    const working: WorkItem[] = [];
    for (const line of blocks.C ?? []) {
        if (!line.trim()) continue;
        const item = ITEM_RE.exec(line);
        if (item) {
            const tag = item[1];
            if (tag !== 'moved' && tag !== 'stalled') fail(fileName, `block C tag [${tag}] is not [moved] or [stalled]`);
            working.push({ tag, text: item[2].trim() });
        } else if (/^\s+\S/.test(line) && working.length) {
            working[working.length - 1].text += ` ${line.trim()}`;
        } else {
            fail(fileName, `block C lines are "- [moved] …" or "- [stalled] …", got ${JSON.stringify(line)}`);
        }
    }

    return { month: `${m[1]}-${m[2]}`, site: body(blocks.A), linkedin: body(blocks.B), working };
}

/** The most recent month's narrative, or null when none is committed. */
export function latestNarrative(narratives: Narrative[]): Narrative | null {
    return [...narratives].sort((a, b) => a.month.localeCompare(b.month)).at(-1) ?? null;
}
