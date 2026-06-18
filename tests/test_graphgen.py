"""Tests for the built-in tree-sitter graph backend (neuralmind/graphgen.py).

Loaded directly (not via ``import neuralmind``) so the suite runs without
chromadb — the same dependency-light philosophy as the synapse/eval tests.
Skips cleanly when the tree-sitter parser isn't installed.

    python tests/test_graphgen.py
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent

# Import graphgen.py in isolation (it has no relative imports and pulls in only
# the stdlib + tree-sitter), bypassing the chromadb-heavy package __init__.
_spec = importlib.util.spec_from_file_location(
    "neuralmind_graphgen", _REPO / "neuralmind" / "graphgen.py"
)
assert _spec and _spec.loader
graphgen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(graphgen)

FIXTURE = _REPO / "tests" / "fixtures" / "sample_project"

# The graphify graph.json contract the rest of the stack consumes.
NODE_KEYS = {
    "label",
    "file_type",
    "source_file",
    "source_location",
    "id",
    "community",
    "norm_label",
}
EDGE_KEYS = {
    "relation",
    "context",
    "confidence",
    "source_file",
    "source_location",
    "weight",
    "source",
    "target",
    "confidence_score",
}


class PureHelperTests(unittest.TestCase):
    """The id/module helpers are pure and run without tree-sitter."""

    def test_slug(self) -> None:
        self.assertEqual(graphgen._slug("users/crud.py"), "users_crud_py")
        self.assertEqual(graphgen._slug("create_user()"), "create_user")
        self.assertEqual(graphgen._slug("A.B-c d"), "a_b_c_d")

    def test_module_dotted(self) -> None:
        self.assertEqual(graphgen._module_dotted("users/crud.py"), "users.crud")
        self.assertEqual(graphgen._module_dotted("auth/__init__.py"), "auth")
        self.assertEqual(graphgen._module_dotted("top.py"), "top")


@unittest.skipUnless(graphgen.is_available(), "tree-sitter not installed")
class BuildGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.graph = graphgen.build_graph(FIXTURE)
        cls.nodes = cls.graph["nodes"]
        cls.edges = cls.graph["links"]

    def test_top_level_schema(self) -> None:
        for key in ("directed", "multigraph", "graph", "nodes", "links", "hyperedges"):
            self.assertIn(key, self.graph)
        self.assertFalse(self.graph["directed"])

    def test_node_keys_match_graphify(self) -> None:
        for n in self.nodes:
            self.assertEqual(set(n.keys()), NODE_KEYS, f"bad node keys for {n.get('id')}")

    def test_edge_keys_match_graphify(self) -> None:
        for e in self.edges:
            self.assertEqual(set(e.keys()), EDGE_KEYS, f"bad edge keys for {e}")

    def test_finds_key_symbols(self) -> None:
        labels = {n["label"] for n in self.nodes if n["file_type"] == "code"}
        for want in ("User", "create_user()", "get_user_by_email()", "encode_token()"):
            self.assertIn(want, labels)

    def test_has_code_and_rationale_nodes(self) -> None:
        types = {n["file_type"] for n in self.nodes}
        self.assertIn("code", types)
        self.assertIn("rationale", types)  # docstring-derived layer

    def test_expected_edge_relations_present(self) -> None:
        relations = {e["relation"] for e in self.edges}
        for want in ("contains", "imports_from", "calls", "rationale_for"):
            self.assertIn(want, relations)

    def test_no_dangling_edges(self) -> None:
        ids = {n["id"] for n in self.nodes}
        for e in self.edges:
            self.assertIn(e["source"], ids)
            self.assertIn(e["target"], ids)

    def test_unique_node_ids(self) -> None:
        ids = [n["id"] for n in self.nodes]
        self.assertEqual(len(ids), len(set(ids)))

    def test_communities_dense_and_assigned(self) -> None:
        comms = sorted({n["community"] for n in self.nodes})
        self.assertTrue(all(c >= 0 for c in comms), "every node gets a community")
        # Dense 0..k labelling (no gaps).
        self.assertEqual(comms, list(range(len(comms))))

    def test_deterministic(self) -> None:
        again = graphgen.build_graph(FIXTURE)
        self.assertEqual(again["nodes"], self.nodes)
        self.assertEqual(again["links"], self.edges)

    def test_rationale_edges_point_at_code(self) -> None:
        code_ids = {n["id"] for n in self.nodes if n["file_type"] == "code"}
        rat_ids = {n["id"] for n in self.nodes if n["file_type"] == "rationale"}
        for e in self.edges:
            if e["relation"] == "rationale_for":
                self.assertIn(e["source"], rat_ids)
                self.assertIn(e["target"], code_ids)

    # -- v0.15 retrieval-parity enrichments -------------------------------- #
    # These are what brought the built-in backend to parity with graphify on
    # the faithfulness eval (see evals/parity/run.py); guard them so a future
    # change can't silently regress retrieval quality below the gate.

    def test_emits_document_nodes_from_markdown(self) -> None:
        """README.md → a document file node plus its heading nodes."""
        docs = [n for n in self.nodes if n["file_type"] == "document"]
        self.assertTrue(docs, "markdown should yield document nodes")
        labels = {n["label"] for n in docs}
        self.assertIn("README.md", labels)
        # At least one heading from the fixture README.
        self.assertIn("NeuralMind Benchmark Fixture", labels)

    def test_extracts_module_level_constants(self) -> None:
        """Module constants are first-class code symbols (queryable by name)."""
        labels = {n["label"] for n in self.nodes if n["file_type"] == "code"}
        self.assertIn("SESSION_TTL", labels)
        self.assertIn("REFRESH_TTL", labels)

    def test_extracts_class_fields(self) -> None:
        """Dataclass fields become code symbols (e.g. the User record fields)."""
        labels = {n["label"] for n in self.nodes if n["file_type"] == "code"}
        self.assertIn("password_hash", labels)
        self.assertIn("is_active", labels)

    def test_skips_dunder_assignments(self) -> None:
        labels = {n["label"] for n in self.nodes if n["file_type"] == "code"}
        self.assertFalse(any(lbl.startswith("__") and lbl.endswith("__") for lbl in labels))

    def test_communities_are_per_file(self) -> None:
        """Every node in a file shares one community; clusters are balanced
        (one per source file), not a single collapsed blob."""
        by_file: dict[str, set[int]] = {}
        for n in self.nodes:
            by_file.setdefault(n["source_file"], set()).add(n["community"])
        for src, comms in by_file.items():
            self.assertEqual(len(comms), 1, f"{src} split across communities {comms}")
        n_files = len(by_file)
        n_comms = len({n["community"] for n in self.nodes})
        self.assertEqual(n_comms, n_files)
        # No giant blob: the largest community holds well under half the nodes.
        sizes: dict[int, int] = {}
        for n in self.nodes:
            sizes[n["community"]] = sizes.get(n["community"], 0) + 1
        self.assertLess(max(sizes.values()), len(self.nodes) // 2)

    def test_rationale_captures_docstring_body(self) -> None:
        """Rationale keeps the descriptive body, not just the summary line —
        that's where query-relevant facts live."""
        rats = [n["label"].lower() for n in self.nodes if n["file_type"] == "rationale"]
        blob = " || ".join(rats)
        self.assertIn("looks the user up by email", blob)

    def test_rationale_respects_length_cap(self) -> None:
        for n in self.nodes:
            if n["file_type"] == "rationale":
                self.assertLessEqual(len(n["label"]), graphgen._RATIONALE_MAX_CHARS)


@unittest.skipUnless(graphgen.is_available(), "tree-sitter not installed")
class WriteGraphTests(unittest.TestCase):
    def test_write_graph_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d)
            (proj / "pkg").mkdir()
            (proj / "pkg" / "__init__.py").write_text("")
            (proj / "pkg" / "mod.py").write_text(
                '"""A module."""\n'
                "from pkg.helper import help_fn\n\n"
                "class Base:\n"
                "    pass\n\n"
                "class Thing(Base):\n"
                '    """A thing."""\n'
                "    def go(self):\n"
                "        return help_fn()\n"
            )
            (proj / "pkg" / "helper.py").write_text("def help_fn():\n    return 1\n")

            out = graphgen.write_graph(proj)
            self.assertTrue(out.exists())
            self.assertEqual(out, proj / "graphify-out" / "graph.json")

            g = json.loads(out.read_text())
            labels = {n["label"] for n in g["nodes"]}
            self.assertIn("Thing", labels)
            self.assertIn("go()", labels)
            self.assertIn("help_fn()", labels)

            rels = {e["relation"] for e in g["links"]}
            self.assertIn("inherits", rels)  # Thing(Base)
            self.assertIn("imports_from", rels)  # pkg.helper
            self.assertIn("calls", rels)  # go -> help_fn

    def test_ignores_vcs_and_cache_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d)
            (proj / "real.py").write_text("def f():\n    return 1\n")
            for junk in (".git", "__pycache__", "node_modules"):
                (proj / junk).mkdir()
                (proj / junk / "ignored.py").write_text("def should_not_appear():\n    return 0\n")
            g = graphgen.build_graph(proj)
            labels = {n["label"] for n in g["nodes"]}
            self.assertIn("f()", labels)
            self.assertNotIn("should_not_appear()", labels)


FIXTURE_TS = _REPO / "tests" / "fixtures" / "sample_project_ts"
FIXTURE_GO = _REPO / "tests" / "fixtures" / "sample_project_go"
FIXTURE_RUST = _REPO / "tests" / "fixtures" / "sample_project_rust"
FIXTURE_JAVA = _REPO / "tests" / "fixtures" / "sample_project_java"


@unittest.skipUnless(
    graphgen.is_available() and graphgen.language_available("typescript"),
    "tree-sitter-typescript not installed",
)
class TypeScriptTests(unittest.TestCase):
    """The TS extractor behind the SUPPORTED_SUFFIXES seam (Item 1)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.graph = graphgen.build_graph(FIXTURE_TS)
        cls.nodes = cls.graph["nodes"]
        cls.edges = cls.graph["links"]

    def test_schema_keys(self) -> None:
        for n in self.nodes:
            self.assertEqual(set(n.keys()), NODE_KEYS, n.get("id"))
        for e in self.edges:
            self.assertEqual(set(e.keys()), EDGE_KEYS, e)

    def test_finds_key_symbols(self) -> None:
        labels = {n["label"] for n in self.nodes if n["file_type"] == "code"}
        for want in ("authenticateUser()", "verifySession()", "encodeToken()", "User"):
            self.assertIn(want, labels)

    def test_jsdoc_becomes_rationale(self) -> None:
        rats = " || ".join(n["label"].lower() for n in self.nodes if n["file_type"] == "rationale")
        self.assertIn("looks the user up by email", rats)

    def test_edge_relations(self) -> None:
        rels = {e["relation"] for e in self.edges}
        for want in ("contains", "imports_from", "calls", "inherits", "rationale_for"):
            self.assertIn(want, rels)

    def test_no_dangling_edges(self) -> None:
        ids = {n["id"] for n in self.nodes}
        for e in self.edges:
            self.assertIn(e["source"], ids)
            self.assertIn(e["target"], ids)

    def test_deterministic(self) -> None:
        again = graphgen.build_graph(FIXTURE_TS)
        self.assertEqual(again["nodes"], self.nodes)


@unittest.skipUnless(
    graphgen.is_available() and graphgen.language_available("go"),
    "tree-sitter-go not installed",
)
class GoTests(unittest.TestCase):
    """The Go extractor behind the SUPPORTED_SUFFIXES seam (Item 1)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.graph = graphgen.build_graph(FIXTURE_GO)
        cls.nodes = cls.graph["nodes"]
        cls.edges = cls.graph["links"]

    def test_finds_key_symbols(self) -> None:
        labels = {n["label"] for n in self.nodes if n["file_type"] == "code"}
        for want in ("AuthenticateUser()", "VerifySession()", "EncodeToken()", "User"):
            self.assertIn(want, labels)

    def test_struct_fields_extracted(self) -> None:
        labels = {n["label"] for n in self.nodes if n["file_type"] == "code"}
        # User struct fields become code symbols.
        self.assertIn("PasswordHash", labels)

    def test_line_comment_becomes_rationale(self) -> None:
        rats = " || ".join(n["label"].lower() for n in self.nodes if n["file_type"] == "rationale")
        self.assertIn("looks the user up by email", rats)

    def test_edge_relations(self) -> None:
        rels = {e["relation"] for e in self.edges}
        for want in ("contains", "imports_from", "calls", "rationale_for"):
            self.assertIn(want, rels)

    def test_no_dangling_edges(self) -> None:
        ids = {n["id"] for n in self.nodes}
        for e in self.edges:
            self.assertIn(e["source"], ids)
            self.assertIn(e["target"], ids)


@unittest.skipUnless(
    graphgen.is_available() and graphgen.language_available("rust"),
    "tree-sitter-rust not installed",
)
class RustTests(unittest.TestCase):
    """The Rust extractor behind the SUPPORTED_SUFFIXES seam.

    This is the *independent* correctness oracle for the Rust gold graph: it
    asserts a hand-listed set of expected symbols, edges, and rationale rather
    than comparing to a generated baseline, so a broken extractor fails here
    even though the parity gate's gold is generated from the extractor itself.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.graph = graphgen.build_graph(FIXTURE_RUST)
        cls.nodes = cls.graph["nodes"]
        cls.edges = cls.graph["links"]
        cls.code_labels = {n["label"] for n in cls.nodes if n["file_type"] == "code"}

    def test_schema_keys(self) -> None:
        for n in self.nodes:
            self.assertEqual(set(n.keys()), NODE_KEYS, n.get("id"))
        for e in self.edges:
            self.assertEqual(set(e.keys()), EDGE_KEYS, e)

    def test_finds_functions_and_methods(self) -> None:
        # free functions, impl methods, and an internal (private) helper.
        for want in (
            "get_connection()",  # impl method
            "ensure_schema()",  # free fn
            "encode_token()",
            "sign()",  # private fn
            "authenticate_user()",
            "charge_customer()",  # impl method
            "build_routes()",
        ):
            self.assertIn(want, self.code_labels)

    def test_finds_types(self) -> None:
        # struct, trait, and enum all become `code` type nodes.
        for want in ("Connection", "DataStore", "User", "StripeClient", "Method", "Route"):
            self.assertIn(want, self.code_labels)

    def test_struct_fields_extracted(self) -> None:
        for want in ("url", "api_key", "amount_cents", "email"):
            self.assertIn(want, self.code_labels)

    def test_enum_variants_extracted(self) -> None:
        for want in ("Get", "Post", "Delete"):
            self.assertIn(want, self.code_labels)

    def test_doc_comment_becomes_rationale(self) -> None:
        rats = " || ".join(n["label"].lower() for n in self.nodes if n["file_type"] == "rationale")
        self.assertIn("authentication hot path", rats)

    def test_impl_trait_becomes_inherits(self) -> None:
        label = {n["id"]: n["label"] for n in self.nodes}
        inherits = {
            (label[e["source"]], label[e["target"]])
            for e in self.edges
            if e["relation"] == "inherits"
        }
        self.assertIn(("Connection", "DataStore"), inherits)

    def test_use_becomes_imports_from(self) -> None:
        files = {n["id"]: n["source_file"] for n in self.nodes}
        import_pairs = {
            (files.get(e["source"]), files.get(e["target"]))
            for e in self.edges
            if e["relation"] == "imports_from"
        }
        self.assertIn(("src/users/crud.rs", "src/db/connection.rs"), import_pairs)
        self.assertIn(("src/auth/handlers.rs", "src/users/crud.rs"), import_pairs)

    def test_cross_file_call_resolved(self) -> None:
        label = {n["id"]: n["label"] for n in self.nodes}
        calls = {
            (label[e["source"]], label[e["target"]]) for e in self.edges if e["relation"] == "calls"
        }
        # authenticate_user() calls get_user_by_email() in another module.
        self.assertIn(("authenticate_user()", "get_user_by_email()"), calls)

    def test_edge_relations(self) -> None:
        rels = {e["relation"] for e in self.edges}
        for want in ("contains", "imports_from", "calls", "inherits", "rationale_for"):
            self.assertIn(want, rels)

    def test_no_dangling_edges(self) -> None:
        ids = {n["id"] for n in self.nodes}
        for e in self.edges:
            self.assertIn(e["source"], ids)
            self.assertIn(e["target"], ids)

    def test_deterministic(self) -> None:
        again = graphgen.build_graph(FIXTURE_RUST)
        self.assertEqual(again["nodes"], self.nodes)

    def test_matches_committed_gold(self) -> None:
        """The built-in extractor's symbol set must match the committed gold
        (the parity gate's regression baseline)."""
        import json

        gold = json.loads(
            (FIXTURE_RUST / "graphify-out" / "graph.json").read_text(encoding="utf-8")
        )
        gold_syms = {n["label"].rstrip("()") for n in gold["nodes"] if n["file_type"] == "code"}
        built_syms = {lbl.rstrip("()") for lbl in self.code_labels}
        self.assertEqual(gold_syms, built_syms)


@unittest.skipUnless(
    graphgen.is_available() and graphgen.language_available("java"),
    "tree-sitter-java not installed",
)
class JavaTests(unittest.TestCase):
    """The Java extractor behind the SUPPORTED_SUFFIXES seam — the independent
    correctness oracle for the Java gold (hand-listed expected symbols/edges)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.graph = graphgen.build_graph(FIXTURE_JAVA)
        cls.nodes = cls.graph["nodes"]
        cls.edges = cls.graph["links"]
        cls.code_labels = {n["label"] for n in cls.nodes if n["file_type"] == "code"}

    def test_schema_keys(self) -> None:
        for n in self.nodes:
            self.assertEqual(set(n.keys()), NODE_KEYS, n.get("id"))
        for e in self.edges:
            self.assertEqual(set(e.keys()), EDGE_KEYS, e)

    def test_finds_methods_and_constructors(self) -> None:
        for want in (
            "getConnection()",  # static method
            "ensureSchema()",
            "encodeToken()",
            "sign()",  # private method
            "authenticateUser()",
            "chargeCustomer()",
            "StripeClient()",  # constructor
        ):
            self.assertIn(want, self.code_labels)

    def test_finds_types(self) -> None:
        # class, interface, and enum all become `code` type nodes.
        for want in ("Connection", "DataStore", "User", "StripeClient", "Method", "Route"):
            self.assertIn(want, self.code_labels)

    def test_fields_and_enum_constants_extracted(self) -> None:
        for want in ("url", "apiKey", "amountCents", "email", "GET", "POST", "DELETE"):
            self.assertIn(want, self.code_labels)

    def test_javadoc_becomes_rationale(self) -> None:
        rats = " || ".join(n["label"].lower() for n in self.nodes if n["file_type"] == "rationale")
        self.assertIn("authentication hot path", rats)

    def test_implements_becomes_inherits(self) -> None:
        label = {n["id"]: n["label"] for n in self.nodes}
        inherits = {
            (label[e["source"]], label[e["target"]])
            for e in self.edges
            if e["relation"] == "inherits"
        }
        self.assertIn(("Connection", "DataStore"), inherits)

    def test_import_becomes_imports_from(self) -> None:
        files = {n["id"]: n["source_file"] for n in self.nodes}
        pairs = {
            (files.get(e["source"]), files.get(e["target"]))
            for e in self.edges
            if e["relation"] == "imports_from"
        }
        base = "src/main/java/com/example"
        self.assertIn((f"{base}/users/Crud.java", f"{base}/db/Connection.java"), pairs)
        self.assertIn((f"{base}/api/Routes.java", f"{base}/auth/Handlers.java"), pairs)

    def test_cross_file_call_resolved(self) -> None:
        label = {n["id"]: n["label"] for n in self.nodes}
        calls = {
            (label[e["source"]], label[e["target"]]) for e in self.edges if e["relation"] == "calls"
        }
        self.assertIn(("authenticateUser()", "getUserByEmail()"), calls)

    def test_edge_relations(self) -> None:
        rels = {e["relation"] for e in self.edges}
        for want in ("contains", "imports_from", "calls", "inherits", "rationale_for"):
            self.assertIn(want, rels)

    def test_no_dangling_edges(self) -> None:
        ids = {n["id"] for n in self.nodes}
        for e in self.edges:
            self.assertIn(e["source"], ids)
            self.assertIn(e["target"], ids)

    def test_deterministic(self) -> None:
        again = graphgen.build_graph(FIXTURE_JAVA)
        self.assertEqual(again["nodes"], self.nodes)

    def test_matches_committed_gold(self) -> None:
        import json

        gold = json.loads(
            (FIXTURE_JAVA / "graphify-out" / "graph.json").read_text(encoding="utf-8")
        )
        gold_syms = {n["label"].rstrip("()") for n in gold["nodes"] if n["file_type"] == "code"}
        built_syms = {lbl.rstrip("()") for lbl in self.code_labels}
        self.assertEqual(gold_syms, built_syms)


@unittest.skipUnless(graphgen.is_available(), "tree-sitter not installed")
class IncrementalUpdateTests(unittest.TestCase):
    """`update_files` re-parses only changed files (Item 3)."""

    def _project(self, d: Path) -> Path:
        proj = d / "proj"
        (proj / "pkg").mkdir(parents=True)
        (proj / "pkg" / "__init__.py").write_text("")
        (proj / "pkg" / "a.py").write_text(
            '"""Module a."""\n\n\nSOME_CONST = 1\n\n\ndef alpha():\n    return 1\n'
        )
        (proj / "pkg" / "b.py").write_text(
            '"""Module b."""\n\nfrom pkg.a import alpha\n\n\ndef beta():\n    return alpha()\n'
        )
        return proj

    def test_edit_keeps_other_files_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            proj = self._project(Path(d))
            graph = graphgen.build_graph(proj)
            before = {n["id"]: n for n in graph["nodes"] if n["source_file"] != "pkg/a.py"}

            (proj / "pkg" / "a.py").write_text(
                '"""Module a."""\n\n\nSOME_CONST = 1\n\n\ndef alpha():\n    return 1\n\n\n'
                'def gamma():\n    """New fn."""\n    return 3\n'
            )
            graph, stats = graphgen.update_files(proj, graph, ["pkg/a.py"])

            after = {n["id"]: n for n in graph["nodes"] if n["source_file"] != "pkg/a.py"}
            self.assertEqual(before, after, "unchanged files must stay byte-identical")
            self.assertEqual(stats.files_reparsed, 1)
            labels = {n["label"] for n in graph["nodes"] if n["source_file"] == "pkg/a.py"}
            self.assertIn("gamma()", labels)
            ids = {n["id"] for n in graph["nodes"]}
            self.assertFalse(
                any(e["source"] not in ids or e["target"] not in ids for e in graph["links"])
            )

    def test_incremental_matches_full_rebuild_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            proj = self._project(Path(d))
            graph = graphgen.build_graph(proj)
            (proj / "pkg" / "a.py").write_text(
                '"""Module a."""\n\n\ndef alpha():\n    return 1\n\n\ndef delta():\n    return 4\n'
            )
            inc, _ = graphgen.update_files(proj, graph, ["pkg/a.py"])
            full = graphgen.build_graph(proj)
            self.assertEqual(
                {n["label"] for n in inc["nodes"] if n["file_type"] == "code"},
                {n["label"] for n in full["nodes"] if n["file_type"] == "code"},
            )

    def test_remove_file_drops_nodes_and_prunes_edges(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            proj = self._project(Path(d))
            graph = graphgen.build_graph(proj)
            (proj / "pkg" / "a.py").unlink()
            graph, stats = graphgen.update_files(proj, graph, [], removed=["pkg/a.py"])
            self.assertEqual(stats.files_removed, 1)
            self.assertFalse(any(n["source_file"] == "pkg/a.py" for n in graph["nodes"]))
            ids = {n["id"] for n in graph["nodes"]}
            # b's import/call edges into a are pruned (no dangling edges).
            self.assertFalse(
                any(e["source"] not in ids or e["target"] not in ids for e in graph["links"])
            )

    def test_noop_when_nothing_changed(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            proj = self._project(Path(d))
            graph = graphgen.build_graph(proj)
            snapshot = {n["id"]: dict(n) for n in graph["nodes"]}
            graph, stats = graphgen.update_files(proj, graph, [])
            self.assertEqual(stats.files_reparsed, 0)
            self.assertEqual({n["id"]: n for n in graph["nodes"]}, snapshot)

    def test_unchanged_communities_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            proj = self._project(Path(d))
            graph = graphgen.build_graph(proj)
            b_comm = next(n["community"] for n in graph["nodes"] if n["source_file"] == "pkg/b.py")
            (proj / "pkg" / "a.py").write_text('"""Module a."""\n\n\ndef alpha():\n    return 99\n')
            graph, _ = graphgen.update_files(proj, graph, ["pkg/a.py"])
            b_comm_after = next(
                n["community"] for n in graph["nodes"] if n["source_file"] == "pkg/b.py"
            )
            self.assertEqual(b_comm, b_comm_after)


class LanguageSeamTests(unittest.TestCase):
    """The suffix→language registry is the only thing a new grammar touches."""

    def test_supported_suffixes(self) -> None:
        for suf in (".py", ".ts", ".tsx", ".go", ".rs", ".java"):
            self.assertIn(suf, graphgen.SUPPORTED_SUFFIXES)

    def test_every_suffix_has_an_extractor(self) -> None:
        langs = set(graphgen._SUFFIX_LANG.values())
        self.assertTrue(langs <= set(graphgen._EXTRACTORS))


if __name__ == "__main__":
    unittest.main(verbosity=2)
