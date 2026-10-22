/**
 * Real `neuralmind query` output, shown on the homepage beside ripgrep's
 * result for the same public-benchmark query (requests / timeout-exception).
 *
 * Captured 2026-10-21 by building psf/requests at the benchmark's pinned
 * commit (0e322af877, tag v2.32.3) and asking the benchmark's question:
 *
 *   git clone --depth 1 --branch v2.32.3 https://github.com/psf/requests
 *   cd requests/src/requests && neuralmind build .
 *   neuralmind query . "the exception raised when a request times out"
 *
 * The full output is 67 lines. This is an excerpt: the first lines of the
 * "Relevant Code Areas" block verbatim, and the cuts marked `…` (the project
 * map, the rest of the block and the eight search results). The token line
 * drops the reduction ratio the CLI prints after the count, which divides by
 * its own estimate and isn't a figure site/claims.json lists. The token
 * count is the CLI's (~4 characters per token), not the benchmark's tiktoken
 * count, so it differs slightly from the benchmark row quoted beside it.
 */
export const QUERY_REPO = 'requests';
export const QUERY_ID = 'timeout-exception';
export const QUERY_TEXT = 'the exception raised when a request times out';

export const QUERY_EXCERPT: { text: string; tone?: 'head' | 'hit' | 'cut' }[] = [
    { text: `$ neuralmind query . "${QUERY_TEXT}"`, tone: 'head' },
    { text: 'Tokens: 649' },
    { text: '…', tone: 'cut' },
    { text: '## Relevant Code Areas' },
    { text: '### Cluster 2 (relevance: 4.42)' },
    { text: '- Initialize RequestException with `request` and `response` objects. (rationale) — exceptions.py', tone: 'hit' },
    { text: '- The request timed out while trying to connect to the remote server. Requests that produced this error are safe to retry. (rationale) — exceptions.py', tone: 'hit' },
    { text: '- Timeout (code) — exceptions.py', tone: 'hit' },
    { text: '- ConnectTimeout (code) — exceptions.py', tone: 'hit' },
    { text: '- requests.exceptions ~~~~~~~~~~~~~~~~~~~ This module contains the set of Requests\' exceptions. (rationale) — exceptions.py', tone: 'hit' },
    { text: '- ReadTimeout (code) — exceptions.py', tone: 'hit' },
    { text: '…', tone: 'cut' },
];
