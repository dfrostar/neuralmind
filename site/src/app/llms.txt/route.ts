import { readFileSync } from 'node:fs';
import path from 'node:path';

// `output: 'export'` requires route handlers to be statically evaluated.
export const dynamic = 'force-static';

/**
 * https://neuralmind.uk/llms.txt — the machine-readable summary models read
 * before they cite us. It 404'd on the apex while docs.neuralmind.uk served
 * one, so the domain people actually link to had none.
 *
 * Served from docs/llms.txt rather than a copy: that file is already scanned
 * by tests/test_docs_claims.py for absolute privacy claims and superseded
 * figures, and a second copy is how the two would drift apart.
 */
export function GET() {
    const body = readFileSync(path.join(process.cwd(), '..', 'docs', 'llms.txt'), 'utf8');
    return new Response(body, {
        headers: { 'Content-Type': 'text/plain; charset=utf-8' },
    });
}
