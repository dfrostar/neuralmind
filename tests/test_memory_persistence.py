"""End-to-end proof that the query-event memory log persists.

Catches regressions where a refactor silently breaks event logging to
``.neuralmind/memory/query_events.jsonl`` — the substrate the synapse
layer and any future learning consumes.

We don't assert a specific numerical uplift (too noisy on a small
fixture). We assert the **mechanism** — the event log grows with one
durable line per query — which is what an end user depends on.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "sample_project"
GRAPH_JSON = FIXTURE_DIR / "graphify-out" / "graph.json"

SEED_QUERIES = [
    "How does the JWT token get signed?",
    "Where is password hashing done?",
    "How do I charge a customer?",
    "What happens if a Stripe charge fails?",
    "How do I issue a partial refund?",
]


@pytest.fixture(scope="module", autouse=True)
def require_fixture_graph():
    if not GRAPH_JSON.exists():
        pytest.skip(
            f"Fixture graph missing at {GRAPH_JSON}. "
            "Run `graphify update tests/fixtures/sample_project` first."
        )


@pytest.fixture
def clean_project_memory():
    """Wipe project-local memory before and after the test."""
    mem_dir = FIXTURE_DIR / ".neuralmind"
    if mem_dir.exists():
        shutil.rmtree(mem_dir)
    yield mem_dir
    if mem_dir.exists():
        shutil.rmtree(mem_dir)


def test_query_events_are_persisted(clean_project_memory):
    """Every query should append one line to the project event log."""
    from neuralmind import NeuralMind, memory

    memory.write_consent_sentinel(True)
    nm = NeuralMind(str(FIXTURE_DIR))

    for q in SEED_QUERIES:
        nm.query(q)

    events_file = memory.project_query_events_file(FIXTURE_DIR)
    assert events_file.exists(), (
        f"Expected {events_file} to exist after queries. "
        "log_query_event may have been short-circuited or the memory dir path changed."
    )

    lines = [ln for ln in events_file.read_text().splitlines() if ln.strip()]
    assert len(lines) == len(SEED_QUERIES), (
        f"Expected {len(SEED_QUERIES)} events, got {len(lines)}. "
        "Events are being dropped — check is_memory_logging_enabled and log_query_event."
    )

    # Each line should be a valid JSON event carrying the query text.
    for ln in lines:
        event = json.loads(ln)
        assert "question" in event or "query" in event, f"event missing question/query: {event}"
