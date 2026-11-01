import EvidenceBadge, { type EvidenceLevel } from '@/components/ui/EvidenceBadge';
import Stat, { StatGrid } from '@/components/ui/Stat';
import type { ProjectHistory } from '@/lib/record';
import { rateView, ratioView } from '@/lib/record';
import { RateValue, RatioValue, fmtInt } from './Gated';

/**
 * One project at a glance: what the repo is, how big its index is, how it was
 * measured and on what, and its latest published run through the same gates
 * as the table. Anything the record doesn't carry reads "not recorded".
 */
function Fact({ label, children }: { label: string; children: React.ReactNode }) {
    return (
        <div className="grid grid-cols-[7rem_1fr] gap-3 py-2 border-b border-carbon-border last:border-b-0">
            <dt className="label pt-0.5">{label}</dt>
            <dd className="text-body text-sm">{children}</dd>
        </div>
    );
}

const notRecorded = <span className="text-faint">not recorded</span>;

export default function ProfileCard({
    history,
    shape,
    hardware,
    method,
    evidence,
}: {
    history: ProjectHistory;
    shape: string | null;
    hardware: string;
    method: string;
    evidence: EvidenceLevel;
}) {
    const latest = history.runs.at(-1)?.row;
    return (
        <article className="panel rounded-card p-6 flex flex-col min-w-0" data-project={history.project}>
            <header className="flex flex-wrap items-center justify-between gap-3 mb-4">
                <h3 className="font-display text-title-sm font-semibold text-white">{history.project}</h3>
                <EvidenceBadge level={evidence} />
            </header>
            <dl className="mb-5">
                <Fact label="Repo shape">{shape ?? notRecorded}</Fact>
                <Fact label="Index size">
                    {latest?.nodes != null ? `${fmtInt(latest.nodes)} nodes` : notRecorded}
                    {latest?.synapse_edges != null && ` · ${fmtInt(latest.synapse_edges)} synapse edges`}
                </Fact>
                <Fact label="Method">{method}</Fact>
                <Fact label="Hardware">{hardware}</Fact>
                <Fact label="Latest run">
                    {latest ? (
                        <>
                            {latest.ts.slice(0, 10)}
                            {latest.version ? ` · ${latest.version}` : ' · version not recorded'}
                            {latest.median_query_s != null && ` · median query ${latest.median_query_s.toFixed(3)} s`}
                        </>
                    ) : (
                        <span className="text-faint">none published</span>
                    )}
                </Fact>
            </dl>
            {latest && (
                <StatGrid className="grid-cols-3 mt-auto">
                    <Stat label="hit@1" value={<RateValue view={rateView(latest.hit_at_1, latest.gold_n)} />} />
                    <Stat label="hit@5" value={<RateValue view={rateView(latest.hit_at_5, latest.gold_n)} />} />
                    <Stat label="vs indexed code" value={<RatioValue view={ratioView(latest)} />} />
                </StatGrid>
            )}
        </article>
    );
}
