import { performanceRecord } from '@/lib/performance';

// `output: 'export'` requires route handlers to be statically evaluated.
export const dynamic = 'force-static';

/**
 * https://neuralmind.uk/performance/linkedin.txt — block B of the latest
 * month's narrative, verbatim, so the post can be copied in one go. Blocks A
 * and C render on /performance; block D is dropped by the parser and never
 * reaches either. Empty when the month has no block B.
 */
export function GET() {
    const body = performanceRecord().narrative?.linkedin ?? '';
    return new Response(body ? `${body}\n` : '', {
        headers: { 'Content-Type': 'text/plain; charset=utf-8' },
    });
}
