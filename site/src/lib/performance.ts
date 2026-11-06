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
import {
    INTEGRITY_NOTES,
    NARRATIVE_FILE_RE,
    histories,
    isIntegrityFileName,
    isIntegrityHeading,
    latestNarrative,
    latestTs,
    parseNarrative,
    parseRecord,
    type Narrative,
} from './record';

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

function* walk(dir: string): Generator<string> {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) yield* walk(full);
        else yield full;
    }
}

/**
 * Fail the build on integrity notes anywhere in the record, not only in the
 * narratives it reads: a file named for them under the record's directory,
 * or an integrity heading in any narrative file, `TEMPLATE.md` included.
 * Everything committed there is public on GitHub whether or not a page
 * renders it.
 */
export function assertNoIntegrityNotes(
    recordDir = path.join(REPO_ROOT, path.dirname(RECORD.source)),
    narrativesDir = path.join(REPO_ROOT, RECORD.narratives),
) {
    const problems: string[] = [];
    for (const file of walk(recordDir)) {
        if (isIntegrityFileName(path.basename(file))) problems.push(`${path.relative(recordDir, file)}: named for integrity notes`);
    }
    for (const name of readdirSync(narrativesDir).filter((n) => n.endsWith('.md'))) {
        readFileSync(path.join(narrativesDir, name), 'utf8')
            .split('\n')
            .forEach((line, i) => {
                if (isIntegrityHeading(line)) problems.push(`${name}:${i + 1}: an integrity heading`);
            });
    }
    if (problems.length) {
        throw new Error(
            `Integrity notes are not committed to this public repo; keep them in ${INTEGRITY_NOTES}:\n  ${problems.join('\n  ')}`,
        );
    }
}

/** Everything /performance and /performance/linkedin.txt render, loaded once per build. */
export function performanceRecord() {
    assertNoIntegrityNotes();
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
        lastRun: latestTs(projects.flatMap((p) => p.runs.map((r) => r.row.ts))),
    };
}
