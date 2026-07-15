// Minimal Express app fixture for the `neuralmind gaps` prototype.
// Reproduces the P2003 coverage trap: an endpoint that is "tested" but only
// in mock mode, so the live-Postgres FK path is never exercised.

const express = require('express');
const app = express();
const router = express.Router();

// Live-covered: has a test that runs against the real DB fixture.
app.get('/health', (req, res) => res.json({ ok: true }));

// Mock-only: three tests exist, all guarded by SKIP_PG — the bug's hiding spot.
app.post('/api/sessions', async (req, res) => {
    // createSession(orgId) → prisma.session.create({ org_id }) → FK risk
    res.json({ id: 'x' });
});

// Mock-only: referenced in tests via a template literal `/api/sessions/${id}`.
app.get('/api/sessions/:id', async (req, res) => res.json({ id: req.params.id }));

// Mock-only.
app.get('/.well-known/jwks.json', (req, res) => res.json({ keys: [] }));

// Untested.
router.post('/api/auth/jwk/rotate', async (req, res) => res.json({ rotated: true }));

// Untested.
router.get('/api/costs/avoidance', (req, res) => res.json({ saved: 0 }));

app.use(router);
module.exports = app;
