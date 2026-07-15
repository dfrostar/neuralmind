// Jest test fixture for the `neuralmind gaps` prototype.
// Mixed coverage on purpose: one endpoint hits the real DB fixture, three are
// mock-only (SKIP_PG-guarded), and two endpoints have no tests at all.

const request = require('supertest');
const app = require('./server');
const { testDb } = require('@/db'); // real-DB fixture import → live-capable file

const SKIP_PG = process.env.SKIP_PG === '1';

describe('health', () => {
    // Live-covered: not skipped, asserts against the real DB fixture.
    it('GET /health checks the database', async () => {
        await testDb.ping();
        const res = await request(app).get('/health');
        expect(res.status).toBe(200);
    });
});

describe('sessions', () => {
    // Mock-only: three cases, all guarded by SKIP_PG — never touch live PG.
    it('POST /api/sessions creates a session (SKIP_PG)', async () => {
        if (SKIP_PG) return;
        const res = await request(app).post('/api/sessions');
        expect(res.status).toBe(200);
    });

    it('POST /api/sessions rejects bad org (SKIP_PG)', async () => {
        if (SKIP_PG) return;
        expect(true).toBe(true);
    });

    it('POST /api/sessions is idempotent (SKIP_PG)', async () => {
        if (SKIP_PG) return;
        expect(true).toBe(true);
    });

    // Mock-only: path referenced via a template literal to exercise normalization.
    it('GET session by id (SKIP_PG)', async () => {
        if (SKIP_PG) return;
        const id = 'abc';
        await request(app).get(`/api/sessions/${id}`);
    });
});

describe('jwks', () => {
    it('GET /.well-known/jwks.json returns keys (SKIP_PG)', async () => {
        if (SKIP_PG) return;
        const res = await request(app).get('/.well-known/jwks.json');
        expect(res.status).toBe(200);
    });
});
