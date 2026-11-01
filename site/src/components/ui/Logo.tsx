/**
 * The mark: an engram.
 *
 * The mark before this one drew a hub node with three weighted edges, which
 * was the product, but it was also the default picture of every graph and AI
 * tool: a molecule of dots and lines. This one draws what the synapse layer
 * keeps instead: an activation pattern on a 4 by 4 grid of cells.
 *
 * The two full columns are two files your agent used together; the two
 * diagonal cells are the association NeuralMind learned between them, in
 * amber because amber on this site means a person, and the association was
 * learned from how a person works. Cells that fire together wire together, and
 * the lit cells spell the N. The six cells that never fired stay drawn, in the
 * rule colour, so the grid reads as a memory rather than a letter.
 *
 * `public/icon.svg`, `favicon.ico` and `apple-touch-icon.png` draw the same
 * grid on a graphite tile; change them together.
 */

const CELL = 5;
const GAP = 2;
const at = (i: number) => i * (CELL + GAP);

// [column, row] of the lit cells: the two files, then the learned edge.
const FILES = [0, 3].flatMap((c) => [0, 1, 2, 3].map((r) => [c, r] as const));
const EDGE = [
    [1, 1],
    [2, 2],
] as const;
const QUIET = [
    [1, 0],
    [2, 0],
    [2, 1],
    [1, 2],
    [1, 3],
    [2, 3],
] as const;

export default function Logo({ className = 'w-[1.625rem] h-[1.625rem]' }: { className?: string }) {
    const cell = ([c, r]: readonly [number, number], fill: string) => (
        <rect key={`${c}-${r}`} x={at(c)} y={at(r)} width={CELL} height={CELL} rx={1} className={fill} />
    );
    return (
        <svg viewBox="0 0 26 26" className={className} aria-hidden="true">
            {QUIET.map((p) => cell(p, 'fill-carbon-line'))}
            {FILES.map((p) => cell(p, 'fill-ink'))}
            {EDGE.map((p) => cell(p, 'fill-electric'))}
        </svg>
    );
}
