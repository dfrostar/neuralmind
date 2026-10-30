/**
 * Reads the longitudinal performance record at build time: the rows, the
 * machine and project profile, and the monthly narratives, all under
 * `benchmarks/ai9970/`. Parsing and every honest-render gate are in
 * `record.ts`; this module only finds the files.
 *
 * The record is registered in `site/claims.json` (`longitudinal_record`) like
 * every other source of a number on the site, and the path is read from
 * there: moving the record without updating the canon fails the build.
 *
 * Server-only (it reads the filesystem), like `evidence.ts`.
 */
import { readFileSync, readdirSync } from 'node:fs';
import path from 'node:path';
import claims from '../../claims.json';
import type { EvidenceLevel } from '@/components/ui/EvidenceBadge';
import { NARRATIVE_FILE_RE, histories, latestNarrative, parseNarrative, parseRecord, type Narrative } from './record';

export const RECORD = claims.longitudinal_record;

/** Repo root: `next build` and vitest both run from `site/`. */
const REPO_ROOT = path.join(process.cwd(), '..');

export interface Profile {
    machine: { id: string; hardware: string };
    method: string;
    projects: Record<string, { shape: string | null }>;
}

export function loadProfile(file = path.join(REPO_ROOT, RECORD.profile)): Profile {
    return JSON.parse(readFileSync(file, 'utf8')) as Profile;
}

export function loadRecord(file = path.join(REPO_ROOT, RECORD.source)) {
    return parseRecord(readFileSync(file, 'utf8'), RECORD.source);
}

/** Every `YYYY-MM.md` in the narratives directory; `TEMPLATE.md` and the like are skipped. */
export function loadNarratives(dir = path.join(REPO_ROOT, RECORD.narratives)): Narrative[] {
    return readdirSync(dir)
        .filter((name) => NARRATIVE_FILE_RE.test(name))
        .map((name) => parseNarrative(name, readFileSync(path.join(dir, name), 'utf8')));
}

/** Everything /performance and /performance/linkedin.txt render, loaded once per build. */
export function performanceRecord() {
    const rows = loadRecord();
    const profile = loadProfile();
    const projects = histories(rows);
    for (const p of projects) {
        if (!(p.project in profile.projects)) {
            throw new Error(`${RECORD.source} has rows for "${p.project}", which ${RECORD.profile} does not list.`);
        }
    }
    return {
        projects,
        profile,
        narrative: latestNarrative(loadNarratives()),
        evidence: RECORD.evidence as EvidenceLevel,
        /** The newest run the page shows; a withheld row doesn't count. */
        lastRun: projects.flatMap((p) => p.runs.map((r) => r.row.ts)).sort().at(-1) ?? null,
    };
}
