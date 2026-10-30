/**
 * Every measured number the site renders, read at build time from the files
 * that hold it — never retyped into a component.
 *
 * - `site/claims.json` is canon for which figures the site may quote and what
 *   kind of evidence each one is. `ratio()` / `ratioRange()` throw when asked
 *   for a value it doesn't list, so a ratio a page renders through here fails
 *   `next build`, not just `tests/test_site_claims.py`.
 * - `bench/public/results.json` is the committed public-benchmark run that
 *   `tests/test_site_claims.py` already recomputes the headline from. The
 *   per-repo tables and found counts come from it directly, and each per-repo
 *   ratio is checked against claims.json on the way out, so a regenerated run
 *   that changes a ratio breaks the build until claims.json is updated with
 *   it — the "commit the raw data and update claims.json in the same change"
 *   rule, enforced.
 * - `bench/retrieval/on-v4.12/results.json` is the 150-question retrieval
 *   eval's raw output; its hit rate and misses are counted, not quoted.
 *
 * Server-only: these imports are large, and only server components (every
 * page here is statically exported) may import this module.
 */
import claims from '../../claims.json';
import publicRun from '../../../bench/public/results.json';
import retrievalRun from '../../../bench/retrieval/on-v4.12/results.json';
import type { EvidenceLevel } from '@/components/ui/EvidenceBadge';

export const GITHUB_URL = 'https://github.com/dfrostar/neuralmind';
export const blob = (path: string) => `${GITHUB_URL}/blob/main/${path}`;

type RatioEntry = (typeof claims.ratios)[number];
type HeadlineEntry = (typeof claims.non_ratio_headline_claims)[number];

export interface Figure {
    /** As the page prints it, e.g. "51–242×". */
    text: string;
    evidence: EvidenceLevel;
    source: string;
    reproduce: string;
}

function entriesFor(value: number): RatioEntry[] {
    return claims.ratios.filter((e) => e.value === value);
}

function only(value: number): RatioEntry {
    const found = entriesFor(value);
    if (found.length === 0) {
        throw new Error(`${value}× is not in site/claims.json — add the measurement there first, then the copy.`);
    }
    return found[0];
}

/** "51.2×", "48.8×", "4.0×" — the value as claims.json records it. */
export function ratio(value: number, digits = value % 1 === 0 ? 0 : 1): Figure {
    const e = only(value);
    return {
        text: `${value.toFixed(digits)}×`,
        evidence: e.evidence as EvidenceLevel,
        source: e.source,
        reproduce: e.reproduce,
    };
}

/** "51–242×". Both ends must be listed, from the same source and evidence level. */
export function ratioRange(lo: number, hi: number): Figure {
    const a = only(lo);
    const b = only(hi);
    if (a.source !== b.source || a.evidence !== b.evidence) {
        throw new Error(`${lo}–${hi}× joins two claims.json entries with different sources or evidence levels.`);
    }
    return { text: `${lo}–${hi}×`, evidence: a.evidence as EvidenceLevel, source: a.source, reproduce: a.reproduce };
}

/** A non-ratio claim, found by a phrase from its `claim` text. */
export function headline(phrase: string): Figure & { claim: string } {
    const matches = claims.non_ratio_headline_claims.filter((c: HeadlineEntry) => c.claim.includes(phrase));
    if (matches.length !== 1) {
        throw new Error(`"${phrase}" matches ${matches.length} non_ratio_headline_claims entries in site/claims.json; expected one.`);
    }
    const c = matches[0];
    return { text: c.claim, claim: c.claim, evidence: c.evidence as EvidenceLevel, source: c.source, reproduce: c.reproduce };
}

/**
 * The task-outcome pilot: Claude Code with and without NeuralMind on 20
 * pre-registered bug-fix tasks. A null result, published with the retrieval
 * wins rather than below them. `figures` is recomputed from
 * bench/task_outcome/pilot/ by tests/test_site_claims.py.
 */
export const taskOutcomePilot = (() => {
    const c = claims.non_ratio_headline_claims.find((e) => e.source === 'bench/task_outcome/pilot/report.txt');
    if (!c || !('figures' in c) || !('spec' in c)) {
        throw new Error('site/claims.json has no task-outcome pilot entry (source bench/task_outcome/pilot/report.txt).');
    }
    return {
        claim: c.claim,
        evidence: c.evidence as EvidenceLevel,
        source: c.source,
        spec: c.spec as string,
        reproduce: c.reproduce,
        figures: c.figures as {
            date: string;
            tasks: number;
            seeds: number;
            runs: number;
            model: string;
            claude_code: string;
            neuralmind: string;
            tasks_solved: { baseline: number; neuralmind: number };
            runs_solved: { baseline: number; neuralmind: number };
            cost_per_solved_task_usd: { baseline: number; neuralmind: number };
            median_cost_change: string;
            cost_change_ci95: string;
            wilcoxon_p: number;
            median_turns: { baseline: number; neuralmind: number };
            median_explore_calls_before_first_edit: { baseline: number; neuralmind: number };
            mcp_tools_listed: number;
            mcp_tool_calls: number;
            claim_supported: boolean;
        },
    };
})();

/**
 * The exploratory rerun after the pilot: the neuralmind arm again, with
 * v4.21.0's MCP server instructions and six-tool list, against the pilot's
 * baseline. Not pre-registered. `figures` is recomputed from
 * bench/task_outcome/exploratory-agent-uptake/ by tests/test_site_claims.py.
 */
export const taskOutcomeRerun = (() => {
    const c = claims.non_ratio_headline_claims.find(
        (e) => e.source === 'bench/task_outcome/exploratory-agent-uptake/report.txt',
    );
    if (!c || !('figures' in c)) {
        throw new Error(
            'site/claims.json has no exploratory-rerun entry (source bench/task_outcome/exploratory-agent-uptake/report.txt).',
        );
    }
    return {
        claim: c.claim,
        evidence: c.evidence as EvidenceLevel,
        source: c.source,
        reproduce: c.reproduce,
        figures: c.figures as {
            date: string;
            tasks: number;
            seeds: number;
            runs: number;
            neuralmind_reported: string;
            neuralmind_commit: string;
            released_in: string;
            mcp_tools_listed: number;
            mcp_tool_calls: number;
            median_cost_change: string;
            cost_change_ci95: string;
            wilcoxon_p: number;
            tasks_solved: { baseline: number; neuralmind: number };
            median_explore_calls_before_first_edit: { baseline: number; neuralmind: number };
            claim_supported: boolean;
        },
    };
})();

/** Every `disclosure` entry: what the site states is not measured. */
export const disclosures = claims.non_ratio_headline_claims
    .filter((c) => c.evidence === 'disclosure')
    .map((c) => ({ claim: c.claim, source: c.source, reproduce: c.reproduce }));

export const evidenceLevels = claims._evidence_levels;

/** Every ratio value claims.json lists, for pages that must render all of them. */
export const claimedRatios = claims.ratios.map((e) => e.value);

/**
 * The non-ratio claims meant as copy: not the disclosures (pages render those
 * through `disclosures`) and not the entries whose note says they are canon
 * for the data but must not be quoted, like the public run's perfect recall.
 */
export const quotableClaims = claims.non_ratio_headline_claims
    .filter((c) => c.evidence !== 'disclosure' && !('note' in c && /must NOT headline/.test(c.note ?? '')))
    .map((c) => ({ claim: c.claim, evidence: c.evidence as EvidenceLevel, source: c.source, reproduce: c.reproduce }));

// ---------------------------------------------------------------------------
// The public benchmark (bench/public/results.json)
// ---------------------------------------------------------------------------

type Summary = { n: number; mean_recall: number; found_rate: number; mean_tokens: number; mean_mrr: number };
type QueryResult = { context_files: string[]; tokens: number; found: boolean; gold_files: string[]; reciprocal_rank: number };

const BACKENDS = ['full-file', 'ripgrep', 'embedding-rag', 'neuralmind'] as const;
export type Backend = (typeof BACKENDS)[number];

const fmt = new Intl.NumberFormat('en-US');
const pct = (v: number) => `${Math.round(v * 100)}%`;

export interface RepoResult {
    name: string;
    sha: string;
    queries: number;
    /** NeuralMind vs pasting every source file, checked against claims.json. */
    ratio: Figure;
    rows: { backend: Backend; recall: string; found: string; tokens: string; mrr: string }[];
}

const repos = publicRun.repos as unknown as {
    name: string;
    commit: string;
    n_queries: number;
    summary: Record<Backend, Summary>;
    queries: { query_id: string; results: Record<Backend, QueryResult> }[];
}[];

export const publicBenchmark = (() => {
    const found: Record<Backend, number> = { 'full-file': 0, ripgrep: 0, 'embedding-rag': 0, neuralmind: 0 };
    let total = 0;
    const perRepo: RepoResult[] = repos.map((r) => {
        for (const b of BACKENDS) found[b] += Math.round(r.summary[b].found_rate * r.summary[b].n);
        total += r.summary.neuralmind.n;
        const nm = r.summary.neuralmind;
        return {
            name: r.name,
            sha: r.commit.slice(0, 10),
            queries: r.n_queries,
            ratio: ratio(Math.round((r.summary['full-file'].mean_tokens / nm.mean_tokens) * 10) / 10, 1),
            rows: BACKENDS.map((b) => {
                const s = r.summary[b];
                return {
                    backend: b,
                    recall: s.mean_recall.toFixed(2),
                    found: pct(s.found_rate),
                    tokens: fmt.format(Math.round(s.mean_tokens)),
                    mrr: s.mean_mrr.toFixed(2),
                };
            }),
        };
    });
    const tokens = (b: Backend) => repos.map((r) => Math.round(r.summary[b].mean_tokens));
    return {
        repos: perRepo,
        repoNames: perRepo.map((r) => r.name),
        total,
        /** "40 of 40" */
        found: (b: Backend) => `${found[b]} of ${total}`,
        tokenRange: (b: Backend) => `${fmt.format(Math.min(...tokens(b)))}–${fmt.format(Math.max(...tokens(b)))}`,
        tokenizer: publicRun.tokenizer,
    };
})();

/** One query's result for two backends: the homepage's side-by-side. */
export function publicQuery(repo: string, queryId: string) {
    const r = repos.find((x) => x.name === repo);
    const q = r?.queries.find((x) => x.query_id === queryId);
    if (!r || !q) throw new Error(`${repo}/${queryId} is not in bench/public/results.json`);
    const side = (b: Backend) => ({
        files: q.results[b].context_files,
        tokens: fmt.format(q.results[b].tokens),
        found: q.results[b].found,
        /** Rank of the first gold file; null when none is in the context. */
        rank: q.results[b].reciprocal_rank > 0 ? Math.round(1 / q.results[b].reciprocal_rank) : null,
    });
    return { repo, sha: r.commit.slice(0, 10), gold: q.results.neuralmind.gold_files, neuralmind: side('neuralmind'), ripgrep: side('ripgrep') };
}

// ---------------------------------------------------------------------------
// The 150-question retrieval eval (bench/retrieval/on-v4.12/results.json)
// ---------------------------------------------------------------------------

export const retrievalEval = (() => {
    const runs = Object.entries(retrievalRun.results).map(([name, configs]) => ({
        name,
        ...(configs as { baseline: { n: number; ranks: (number | null)[]; avg_tokens: number } }).baseline,
    }));
    const questions = runs.reduce((n, r) => n + r.n, 0);
    const hits = runs.reduce((n, r) => n + r.ranks.filter((k) => k !== null && k <= 5).length, 0);
    const claim = headline('150-question retrieval eval');
    return {
        questions,
        repos: runs.length,
        misses: questions - hits,
        /** "93.3%" */
        hitAt5: `${((hits / questions) * 100).toFixed(1)}%`,
        evidence: claim.evidence,
        source: claim.source,
        reproduce: claim.reproduce,
    };
})();
