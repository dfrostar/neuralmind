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
 * - `bench/exploration-share/2026-11-01/*.summary.json` are the exploration-share
 *   field report's aggregates; its shares are computed from them and checked
 *   against the claims.json entry, so a re-run that moves one breaks the build
 *   until the entry is updated with it.
 *
 * Server-only: these imports are large, and only server components (every
 * page here is statically exported) may import this module.
 */
import claims from '../../claims.json';
import publicRun from '../../../bench/public/results.json';
import retrievalRun from '../../../bench/retrieval/on-v4.12/results.json';
import explorationClaudeCode from '../../../bench/exploration-share/2026-11-01/claude-code.summary.json';
import explorationClaudeCodePass3 from '../../../bench/exploration-share/2026-11-01/claude-code.summary.pass3.json';
import explorationClaudeCodePass4 from '../../../bench/exploration-share/2026-11-01/claude-code.summary.pass4.json';
import explorationHermes from '../../../bench/exploration-share/2026-11-01/hermes.summary.json';
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

// ---------------------------------------------------------------------------
// The exploration-share field report (bench/exploration-share/2026-11-01/)
// ---------------------------------------------------------------------------

const EXPLORATION_DIR = 'bench/exploration-share/2026-11-01';

/** The slice of a summary group this page reads. */
interface ShareGroup {
    sessions: number;
    prompt_tokens_billed: number;
    billed_tokens: { exploration: number };
    /** The spec's headline: billed exploration tokens over the estimated (recorded) context. */
    exploration_share_billed: number;
    exploration_share_median_session: number;
    calibration_est_over_billed: number;
}

interface ShareRowFigures {
    sessions: number;
    billed_prompt_tokens: number;
    share_of_recorded_context_pct: number;
    share_of_billed_prompt_pct: number;
    median_session_pct: number;
    calibration_pct: number;
}

interface ShareFigures {
    since: string;
    until: string;
    tokenizer: string;
    thresholds_pct: number[];
    claude_code_interactive: ShareRowFigures;
    hermes_interactive: ShareRowFigures;
    hermes_benchmark: { sessions: number; share_of_recorded_context_pct: number };
    /** The Claude Code headline at passes 3, 4 and the current one. */
    claude_code_headline_by_pass_pct: number[];
    /** What the last classifier fixes move the pooled shares by on identical sessions (spec, pass 5). */
    classifier_effect_points: { recorded_context: number; billed_prompt: number };
    /** What moves a reading between runs: which sessions a run can read (report, pass 5). */
    session_set_drift_points: number;
}

const FRACTION_WORDS: [number, string][] = [
    [0.1, 'a tenth'],
    [0.2, 'a fifth'],
    [0.25, 'a quarter'],
    [1 / 3, 'a third'],
    [0.5, 'half'],
];

/** "a fifth" for 0.196: the copy's rounding in words, refused when no word is within three points. */
function aboutFraction(v: number): string {
    const [target, words] = FRACTION_WORDS.reduce((best, f) => (Math.abs(f[0] - v) < Math.abs(best[0] - v) ? f : best));
    if (Math.abs(target - v) > 3 / 100) {
        throw new Error(`${(v * 100).toFixed(1)}% is not about any fraction the exploration-share copy names; reword it.`);
    }
    return words;
}

/**
 * What share of the prompt tokens an agent's sessions were billed for was
 * exploration (reading and searching code): one developer's two machines, a
 * field report, pre-registered in docs/specs/EXPLORATION-SHARE-SPEC.md.
 *
 * Every share is computed here from the committed summaries and compared with
 * the `figures` in the claims.json entry, to the digit the page prints. They
 * are the same numbers read twice on purpose: a regenerated summary that moves
 * one fails `next build` until the entry (the canon) is updated, and
 * tests/test_site_claims.py recomputes them again without this module.
 */
export const explorationShare = (() => {
    const c = claims.non_ratio_headline_claims.find((e) => e.source === `${EXPLORATION_DIR}/README.md`);
    if (!c || !('figures' in c) || !('spec' in c)) {
        throw new Error(`site/claims.json has no exploration-share entry (source ${EXPLORATION_DIR}/README.md).`);
    }
    const quoted = c.figures as unknown as ShareFigures;

    const group = (run: { groups: unknown }, key: string): ShareGroup => {
        const g = (run.groups as Record<string, ShareGroup>)[key];
        if (!g) throw new Error(`${EXPLORATION_DIR} has no ${key} group.`);
        return g;
    };
    const percent = (what: string, computed: number, claimed: number): string => {
        if ((computed * 100).toFixed(1) !== claimed.toFixed(1)) {
            throw new Error(
                `Exploration share, ${what}: the summaries give ${(computed * 100).toFixed(1)}% but site/claims.json says ${claimed.toFixed(1)}%. Update the entry first, then the copy.`,
            );
        }
        return `${claimed.toFixed(1)}%`;
    };
    const row = (what: string, g: ShareGroup, q: ShareRowFigures) => {
        if (g.sessions !== q.sessions || g.prompt_tokens_billed !== q.billed_prompt_tokens) {
            throw new Error(`Exploration share, ${what}: sessions or billed tokens differ from site/claims.json.`);
        }
        const ofBilled = g.billed_tokens.exploration / g.prompt_tokens_billed;
        return {
            sessions: fmt.format(g.sessions),
            billedTokens: fmt.format(g.prompt_tokens_billed),
            /** Exploration tool results over everything the transcript records: the spec's headline. */
            ofContext: percent(`${what} of recorded context`, g.exploration_share_billed, q.share_of_recorded_context_pct),
            /** The same exploration over what the provider billed. */
            ofBilled: percent(`${what} of billed prompt`, ofBilled, q.share_of_billed_prompt_pct),
            median: percent(`${what} median per session`, g.exploration_share_median_session, q.median_session_pct),
            /** Transcript-estimated context over billed prompt. */
            calibration: percent(`${what} calibration`, g.calibration_est_over_billed, q.calibration_pct),
            /** Unrounded, for the sentence that says them in words. */
            fractions: { ofContext: g.exploration_share_billed, ofBilled },
        };
    };

    const bench = group(explorationHermes, 'hermes/benchmark');
    if (bench.sessions !== quoted.hermes_benchmark.sessions) {
        throw new Error('Exploration share, benchmark harness: session count differs from site/claims.json.');
    }
    const claudeCode = row('Claude Code interactive', group(explorationClaudeCode, 'claude-code/interactive'), quoted.claude_code_interactive);
    const [lowLine, highLine] = quoted.thresholds_pct;
    // The headline's history, read from the pass 3 and pass 4 summaries beside the current one.
    const history = [
        group(explorationClaudeCodePass3, 'claude-code/interactive'),
        group(explorationClaudeCodePass4, 'claude-code/interactive'),
        group(explorationClaudeCode, 'claude-code/interactive'),
    ].map((g, i) => percent(`Claude Code headline, pass ${i + 3}`, g.exploration_share_billed, quoted.claude_code_headline_by_pass_pct[i]));
    // "N points over the line": refuses a reading that is no longer over it, so the section is reworded then.
    const over = (what: string, share: number, line: number): string => {
        if (share <= line) throw new Error(`${what} is no longer over the ${line}% line; the section's reading has to be reworded.`);
        return (share - line).toFixed(1);
    };
    const drift = quoted.session_set_drift_points;
    const days = Math.round((Date.parse(quoted.until) - Date.parse(quoted.since)) / 86_400_000);

    return {
        claim: c.claim,
        evidence: c.evidence as EvidenceLevel,
        source: c.source,
        spec: c.spec as string,
        reproduce: c.reproduce,
        since: quoted.since,
        until: quoted.until,
        days,
        tokenizer: quoted.tokenizer,
        /** The spec's pre-registered bands: under the first, between, at or above the second. */
        thresholds: quoted.thresholds_pct,
        claudeCode,
        /** How far over its line each interactive headline is, in points, to one decimal. */
        marginsOverLine: {
            claudeCode: over('Claude Code interactive', quoted.claude_code_interactive.share_of_recorded_context_pct, highLine),
            hermes: over('Hermes interactive', quoted.hermes_interactive.share_of_recorded_context_pct, lowLine),
        },
        /** The Claude Code headline at passes 3, 4 and the current one, each as "NN.N%". */
        headlineByPass: history,
        /** Pooled shares moved by the last classifier fixes on identical sessions, in points, to two decimals. */
        classifierEffect: {
            recordedContext: quoted.classifier_effect_points.recorded_context.toFixed(2),
            billedPrompt: quoted.classifier_effect_points.billed_prompt.toFixed(2),
        },
        /** "half a point": what a run's session set moves the headline by. */
        sessionSetDrift: drift === 0.5 ? 'half a point' : `${drift} points`,
        /** The report's sentence: "about a fifth of what these sessions were billed for ... about a third of the context". */
        claudeCodeInWords: {
            ofBilled: aboutFraction(claudeCode.fractions.ofBilled),
            ofContext: aboutFraction(claudeCode.fractions.ofContext),
        },
        hermes: row('Hermes interactive', group(explorationHermes, 'hermes/interactive'), quoted.hermes_interactive),
        benchmark: {
            sessions: fmt.format(bench.sessions),
            ofContext: percent('Hermes benchmark harness', bench.exploration_share_billed, quoted.hermes_benchmark.share_of_recorded_context_pct),
        },
        dataFiles: [`${EXPLORATION_DIR}/claude-code.summary.json`, `${EXPLORATION_DIR}/hermes.summary.json`],
    };
})();
