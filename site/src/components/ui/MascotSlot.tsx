import { existsSync } from 'node:fs';
import { join } from 'node:path';
import Mascot from './Mascot';

/**
 * Where The Pair appears, if it exists yet.
 *
 * The mascot is built in VRoid Studio outside this repo's code
 * (site/mascot/SPEC.md). This checks at build time for its export at
 * `site/public/mascot/pair.vrm` and renders nothing until the file is
 * there, so dropping the file in and rebuilding is the whole integration.
 * Without it the page has no mascot markup and never fetches three.js; the
 * only cost is the component's own ~2 kB, which Next ships with the page
 * either way. An optional `pair.png` beside it is shown while the model
 * loads.
 */

const VRM = '/mascot/pair.vrm';
const POSTER = '/mascot/pair.png';

const published = (path: string) => existsSync(join(process.cwd(), 'public', path));

export default function MascotSlot({ className = '' }: { className?: string }) {
    if (!published(VRM)) return null;
    return <Mascot src={VRM} poster={published(POSTER) ? POSTER : undefined} className={className} />;
}
