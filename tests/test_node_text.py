"""The text a graph node is embedded as (neuralmind.node_text). Stdlib-only."""

from __future__ import annotations

from types import SimpleNamespace

from neuralmind.node_text import GraphContext, context_for, module_of, node_text

NODES = [
    {
        "id": "sessions_py",
        "label": "sessions.py",
        "file_type": "code",
        "source_file": "sessions.py",
    },
    {
        "id": "sessions_py__session_cls",
        "label": "Session",
        "file_type": "code",
        "source_file": "sessions.py",
        "source_location": "L355",
        "community": 3,
    },
    {
        "id": "sessions_py__session_send_fn",
        "label": "send()",
        "file_type": "code",
        "source_file": "sessions.py",
        "source_location": "L673",
        "community": 3,
    },
    {
        "id": "sessions_py__session_send_fn__rationale",
        "label": "Send a given PreparedRequest.",
        "file_type": "rationale",
        "source_file": "sessions.py",
        "source_location": "L674",
    },
    {
        "id": "readme_md__usage_h",
        "label": "Usage",
        "file_type": "document",
        "source_file": "README.md",
    },
]
EDGES = [
    {"relation": "contains", "source": "sessions_py", "target": "sessions_py__session_cls"},
    {
        "relation": "contains",
        "source": "sessions_py__session_cls",
        "target": "sessions_py__session_send_fn",
    },
    {
        "relation": "rationale_for",
        "source": "sessions_py__session_send_fn__rationale",
        "target": "sessions_py__session_send_fn",
    },
]


def _by_id(node_id):
    return next(n for n in NODES if n["id"] == node_id)


def test_method_embeds_with_its_class_module_and_docstring():
    ctx = GraphContext(NODES, EDGES)
    text = node_text(_by_id("sessions_py__session_send_fn"), ctx)
    assert text == "Session.send()\nIn module sessions\nSend a given PreparedRequest."


def test_no_line_or_cluster_numbers_so_moving_code_keeps_the_text():
    ctx = GraphContext(NODES, EDGES)
    node = dict(_by_id("sessions_py__session_send_fn"))
    before = node_text(node, ctx)
    node.update(source_location="L900", community=7)
    assert node_text(node, ctx) == before
    assert "L673" not in before and "Community" not in before


def test_a_file_is_not_a_class():
    ctx = GraphContext(NODES, EDGES)
    # The file contains the class; the class's text must not read "sessions.py.Session".
    assert node_text(_by_id("sessions_py__session_cls"), ctx).splitlines()[0] == "Session"


def test_docstring_node_is_the_docstring_alone():
    ctx = GraphContext(NODES, EDGES)
    node = _by_id("sessions_py__session_send_fn__rationale")
    assert node_text(node, ctx) == "Send a given PreparedRequest."


def test_document_node_keeps_the_entity_line_the_orphan_sweep_reads():
    assert node_text(_by_id("readme_md__usage_h")) == "Entity: Usage\nFile: README.md"


def test_module_of_nested_paths_and_windows_separators():
    assert module_of("src/requests/models.py") == "src.requests.models"
    assert module_of("pkg\\mod.ts") == "pkg.mod"
    assert module_of("Makefile") == "Makefile"


def test_redacts_when_enabled(monkeypatch):
    key = "sk-ant-api03-" + "A" * 93 + "AA"
    node = {"id": "cfg_py__key", "label": f"KEY = {key}", "file_type": "code"}
    monkeypatch.setenv("NEURALMIND_REDACT_SECRETS", "1")
    assert key not in node_text(node)


def test_context_is_cached_per_graph_and_rebuilt_when_it_changes():
    backend = SimpleNamespace(nodes=NODES, edges=EDGES)
    first = context_for(backend)
    assert context_for(backend) is first
    backend.edges = list(EDGES)  # a reloaded graph
    assert context_for(backend) is not first


def test_works_on_a_bare_instance_without_a_graph():
    # The redaction tests call _node_to_text on an uninitialised backend.
    assert node_text({"label": "x()", "file_type": "code"}, context_for(object())) == "x()"
