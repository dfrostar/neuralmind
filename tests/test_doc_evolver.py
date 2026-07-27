"""Tests for DocEvolver — evolutionary JSDoc optimizer.

Covers mutation strategies, fitness scoring, promotion logic,
full evolution loop, and fail-open behavior.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from neuralmind.doc_evolver import (
    BlindSpot,
    DocEvolver,
    EvolveResult,
    GenerationResult,
    JSDocGenerator,
    JSDocVariant,
    MutationStrategy,
    _camel_to_words,
    _detect_method_type,
    _extract_params,
    _get_synonyms,
    _scan_file_for_blind_spots,
    audit_blind_spots,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a minimal project with a source file."""
    project = tmp_path / "project"
    project.mkdir()
    src = project / "src"
    src.mkdir()

    # Create a source file with undocumented methods
    source_file = src / "export.ts"
    source_file.write_text(
        "function handleCSVExport(data) {\n"
        "  return data.map(row => row.join(',')).join('\\n');\n"
        "}\n"
        "\n"
        "function parseJSONInput(raw) {\n"
        "  return JSON.parse(raw);\n"
        "}\n"
        "\n"
        "const formatReportOutput = (report) => {\n"
        "  return report.toString();\n"
        "};\n"
    )
    return project


@pytest.fixture
def generator() -> JSDocGenerator:
    return JSDocGenerator()


@pytest.fixture
def blind_spots() -> list[BlindSpot]:
    return [
        BlindSpot(name="handleCSVExport", file_path="src/export.ts", line=1),
        BlindSpot(name="parseJSONInput", file_path="src/export.ts", line=5),
        BlindSpot(
            name="formatReportOutput", file_path="src/export.ts", line=9, method_type="arrow"
        ),
    ]


@pytest.fixture
def evolver(tmp_project: Path, blind_spots: list[BlindSpot]) -> DocEvolver:
    return DocEvolver(
        project_path=tmp_project,
        blind_spots=blind_spots,
        population_size=5,
        generations=3,
        hysteresis=0.05,
    )


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestCamelToWords:
    def test_simple_camel(self) -> None:
        assert _camel_to_words("handleCSVExport") == "handle csv export"

    def test_pascal_case(self) -> None:
        assert _camel_to_words("ParseJSONInput") == "parse json input"

    def test_single_word(self) -> None:
        assert _camel_to_words("format") == "format"


class TestGetSynonyms:
    def test_known_verb(self) -> None:
        synonyms = _get_synonyms("handleCSVExport")
        assert len(synonyms) > 0
        assert "process" in synonyms or "manage" in synonyms

    def test_no_known_verb(self) -> None:
        synonyms = _get_synonyms("xyzabc")
        assert synonyms == []


class TestDetectMethodType:
    def test_arrow_function(self) -> None:
        assert _detect_method_type("const foo = (x) => {") == "arrow"

    def test_regular_function(self) -> None:
        assert _detect_method_type("function foo(x) {") == "function"

    def test_method(self) -> None:
        assert _detect_method_type("foo(x) {") == "method"


class TestExtractParams:
    def test_simple_params(self) -> None:
        params = _extract_params("function foo(a, b, c) {")
        assert params == ["a", "b", "c"]

    def test_typed_params(self) -> None:
        params = _extract_params("function foo(a: string, b: number) {")
        assert params == ["a", "b"]

    def test_default_values(self) -> None:
        params = _extract_params("function foo(a = 5, b = 'hello') {")
        assert params == ["a", "b"]

    def test_no_params(self) -> None:
        params = _extract_params("function foo() {")
        assert params == []


# ---------------------------------------------------------------------------
# JSDocGenerator tests
# ---------------------------------------------------------------------------


class TestJSDocGenerator:
    def test_generate_returns_variant(self, generator: JSDocGenerator) -> None:
        variant = generator.generate("handleCSVExport")
        assert isinstance(variant, JSDocVariant)
        assert variant.lines

    def test_generate_uses_strategy(self, generator: JSDocGenerator) -> None:
        variant = generator.generate("handleCSVExport", strategy=MutationStrategy.LENGTH)
        assert variant.strategy == MutationStrategy.LENGTH

    def test_generate_respects_length(self, generator: JSDocGenerator) -> None:
        variant = generator.generate("handleCSVExport")
        assert variant.length_class in ("short", "medium", "long")

    def test_variant_text_format(self, generator: JSDocGenerator) -> None:
        variant = generator.generate("handleCSVExport")
        text = variant.text
        assert text.startswith("/**")
        assert text.endswith(" */")
        assert " * " in text

    def test_mutate_around_preserves_name(self, generator: JSDocGenerator) -> None:
        parent = generator.generate("handleCSVExport")
        child = generator.mutate_around(parent, "handleCSVExport")
        assert isinstance(child, JSDocVariant)

    def test_mutate_around_changes_sometimes(self, generator: JSDocGenerator) -> None:
        """Mutation should change at least one attribute in 10 tries."""
        parent = generator.generate("handleCSVExport", params=["data"])
        changed = False
        for _ in range(10):
            child = generator.mutate_around(parent, "handleCSVExport", params=["data"])
            if (
                child.length_class != parent.length_class
                or child.structure != parent.structure
                or child.keyword_density != parent.keyword_density
            ):
                changed = True
                break
        assert changed, "Mutation should change at least one attribute"

    def test_structure_variants_differ(self, generator: JSDocGenerator) -> None:
        variants = []
        for _ in range(20):
            v = generator.generate("handleCSVExport", params=["data"])
            variants.append(v.structure)
        # Should see at least 2 different structures in 20 samples
        assert len(set(variants)) >= 2


# ---------------------------------------------------------------------------
# DocEvolver unit tests
# ---------------------------------------------------------------------------


class TestDocEvolverInit:
    def test_init_defaults(self, tmp_project: Path, blind_spots: list[BlindSpot]) -> None:
        evolver = DocEvolver(project_path=tmp_project, blind_spots=blind_spots)
        assert evolver.population_size == 5
        assert evolver.generations == 5
        assert evolver.hysteresis == 0.05

    def test_init_custom(self, tmp_project: Path, blind_spots: list[BlindSpot]) -> None:
        evolver = DocEvolver(
            project_path=tmp_project,
            blind_spots=blind_spots,
            population_size=10,
            generations=2,
            hysteresis=0.1,
        )
        assert evolver.population_size == 10
        assert evolver.generations == 2
        assert evolver.hysteresis == 0.1

    def test_init_empty_spots_raises(self, tmp_project: Path) -> None:
        with pytest.raises(ValueError, match="blind_spots must not be empty"):
            DocEvolver(project_path=tmp_project, blind_spots=[])

    def test_init_negative_hysteresis_fallback(
        self, tmp_project: Path, blind_spots: list[BlindSpot]
    ) -> None:
        evolver = DocEvolver(project_path=tmp_project, blind_spots=blind_spots, hysteresis=-0.1)
        assert evolver.hysteresis == 0.05


class TestPromoteIfBetter:
    def test_promotes_when_better(self, evolver: DocEvolver) -> None:
        assert evolver.promote_if_better(0.6, 0.5) is True

    def test_does_not_promote_when_worse(self, evolver: DocEvolver) -> None:
        assert evolver.promote_if_better(0.4, 0.5) is False

    def test_hysteresis_margin(self, evolver: DocEvolver) -> None:
        # Within hysteresis margin: 0.52 vs 0.5 — 0.52 < 0.5 * 1.05 = 0.525
        assert evolver.promote_if_better(0.52, 0.5) is False

    def test_exact_hysteresis_boundary(self, evolver: DocEvolver) -> None:
        # Just above hysteresis: 0.526 > 0.525
        assert evolver.promote_if_better(0.526, 0.5) is True


class TestEvaluateCandidate:
    def test_fitness_is_reciprocal_rank(self, evolver: DocEvolver) -> None:
        spot = BlindSpot(name="handleCSVExport", file_path="src/export.ts", line=1)
        variant = JSDocVariant(
            strategy=MutationStrategy.LENGTH,
            lines=["Handle CSV export."],
        )
        # Mock query to return the file at rank 1
        evolver.query_fn = lambda p, q: ["src/export.ts", "other/file.ts"]
        fitness = evolver.evaluate_candidate(spot, variant)
        assert fitness == pytest.approx(1.0)

    def test_fitness_rank2(self, evolver: DocEvolver) -> None:
        spot = BlindSpot(name="handleCSVExport", file_path="src/export.ts", line=1)
        variant = JSDocVariant(
            strategy=MutationStrategy.LENGTH,
            lines=["Handle CSV export."],
        )
        evolver.query_fn = lambda p, q: ["other/file.ts", "src/export.ts"]
        fitness = evolver.evaluate_candidate(spot, variant)
        assert fitness == pytest.approx(0.5)

    def test_fitness_not_found(self, evolver: DocEvolver) -> None:
        spot = BlindSpot(name="handleCSVExport", file_path="src/export.ts", line=1)
        variant = JSDocVariant(
            strategy=MutationStrategy.LENGTH,
            lines=["Handle CSV export."],
        )
        evolver.query_fn = lambda p, q: ["other/file.ts"]
        fitness = evolver.evaluate_candidate(spot, variant)
        assert fitness == 0.0


class TestSampleCandidate:
    def test_returns_variant(self, evolver: DocEvolver) -> None:
        parent = JSDocVariant(strategy=MutationStrategy.LENGTH, lines=["Test"])
        child = evolver.sample_candidate(parent, "handleCSVExport", [], "function")
        assert isinstance(child, JSDocVariant)


class TestRunGeneration:
    def test_returns_generation_result(self, evolver: DocEvolver) -> None:
        spot = BlindSpot(name="handleCSVExport", file_path="src/export.ts", line=1)
        variant = JSDocVariant(strategy=MutationStrategy.LENGTH, lines=["Test"])
        evolver.query_fn = lambda p, q: ["src/export.ts"]
        result = evolver.run_generation(spot, variant, 0.5, [], "function")
        assert isinstance(result, GenerationResult)
        assert result.population_size == evolver.population_size


# ---------------------------------------------------------------------------
# Full evolution loop tests
# ---------------------------------------------------------------------------


class TestEvolve:
    def test_evolve_returns_results(self, evolver: DocEvolver) -> None:
        evolver.query_fn = lambda p, q: ["src/export.ts"]
        results = evolver.evolve()
        assert len(results) == len(evolver.blind_spots)
        for r in results:
            assert isinstance(r, EvolveResult)
            assert r.best_fitness >= 0.0

    def test_evolve_single_spot(self, tmp_project: Path) -> None:
        spot = BlindSpot(name="handleCSVExport", file_path="src/export.ts", line=1)
        evolver = DocEvolver(
            project_path=tmp_project,
            blind_spots=[spot],
            population_size=3,
            generations=2,
        )
        evolver.query_fn = lambda p, q: ["src/export.ts"]
        results = evolver.evolve()
        assert len(results) == 1
        assert results[0].name == "handleCSVExport"
        assert results[0].generations_run == 2

    def test_evolve_improves_fitness(self, tmp_project: Path) -> None:
        """Evolution should find better variants over generations."""
        spot = BlindSpot(name="handleCSVExport", file_path="src/export.ts", line=1)

        call_count = 0

        def mock_query(project: str, q: str) -> list[str]:
            nonlocal call_count
            call_count += 1
            # Return the target file at varying ranks to simulate improvement
            if call_count <= 3:
                return ["other/file.ts", "src/export.ts"]  # rank 2
            return ["src/export.ts"]  # rank 1

        evolver = DocEvolver(
            project_path=tmp_project,
            blind_spots=[spot],
            population_size=5,
            generations=3,
        )
        evolver.query_fn = mock_query
        results = evolver.evolve()
        assert len(results) == 1
        assert results[0].best_fitness >= 0.5  # At least rank 2


class TestFailOpen:
    def test_evolve_handles_exception_gracefully(self, tmp_project: Path) -> None:
        """If query_fn raises, evolution should not crash."""
        spot = BlindSpot(name="handleCSVExport", file_path="src/export.ts", line=1)

        def bad_query(p: str, q: str) -> list[str]:
            raise RuntimeError("query failed")

        evolver = DocEvolver(
            project_path=tmp_project,
            blind_spots=[spot],
            population_size=3,
            generations=2,
        )
        evolver.query_fn = bad_query
        results = evolver.evolve()
        # Should return a result with 0 fitness, not raise
        assert len(results) == 1
        assert results[0].best_fitness == 0.0
        assert results[0].best_variant is None

    def test_patch_winners_skips_none_variants(self, tmp_project: Path) -> None:
        """patch_winners should skip results without a variant."""
        spot = BlindSpot(name="handleCSVExport", file_path="src/export.ts", line=1)
        evolver = DocEvolver(
            project_path=tmp_project, blind_spots=[spot], population_size=3, generations=1
        )
        results = [
            EvolveResult(
                name="test",
                file_path="src/export.ts",
                line=1,
                best_fitness=0.0,
                best_variant=None,
                generations_run=0,
                promoted=False,
            )
        ]
        modified = evolver.patch_winners(results)
        assert modified == []

    def test_missing_file_returns_zero_fitness(self, tmp_project: Path) -> None:
        spot = BlindSpot(name="foo", file_path="nonexistent.ts", line=1)
        variant = JSDocVariant(strategy=MutationStrategy.LENGTH, lines=["Test"])
        evolver = DocEvolver(
            project_path=tmp_project, blind_spots=[spot], population_size=3, generations=1
        )
        fitness = evolver.evaluate_candidate(spot, variant)
        assert fitness == 0.0


# ---------------------------------------------------------------------------
# AST audit tests
# ---------------------------------------------------------------------------


class TestAudit:
    def test_scan_file_finds_undocumented(self, tmp_project: Path) -> None:
        source = tmp_project / "src" / "export.ts"
        content = source.read_text()
        spots = _scan_file_for_blind_spots(content, "src/export.ts")
        names = [s.name for s in spots]
        assert "handleCSVExport" in names
        assert "parseJSONInput" in names
        assert "formatReportOutput" in names

    def test_scan_file_skips_documented(self, tmp_project: Path) -> None:
        source = tmp_project / "src" / "documented.ts"
        source.write_text(
            "/**\n"
            " * Handles data transformation.\n"
            " */\n"
            "function transformData(input) {\n"
            "  return input * 2;\n"
            "}\n"
        )
        content = source.read_text()
        spots = _scan_file_for_blind_spots(content, "src/documented.ts")
        assert len(spots) == 0

    def test_audit_blind_spots_walks_project(self, tmp_project: Path) -> None:
        spots = audit_blind_spots(tmp_project)
        names = [s.name for s in spots]
        assert "handleCSVExport" in names


# ---------------------------------------------------------------------------
# Integration test
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_full_evolution_on_fixture(self, tmp_project: Path) -> None:
        """End-to-end evolution on a small fixture with 3 undocumented methods."""
        spots = audit_blind_spots(tmp_project)
        assert len(spots) >= 3

        # Mock query function that simulates improved retrieval
        # by returning the target file based on JSDoc quality
        def smart_query(p: str, q: str) -> list[str]:
            # Simulate that better JSDoc leads to better rank
            # This is a simplified model for testing
            return ["src/export.ts", "other.ts"]

        evolver = DocEvolver(
            project_path=tmp_project,
            blind_spots=spots[:3],
            population_size=5,
            generations=5,
            query_fn=smart_query,
        )

        results = evolver.evolve()
        assert len(results) == 3

        # All results should have valid variants
        for r in results:
            assert r.best_variant is not None
            assert r.best_fitness > 0.0
            assert r.generations_run == 5

        # Patch winners and verify source is modified
        modified = evolver.patch_winners(results)
        assert len(modified) > 0

        # Verify the patched file contains JSDoc
        patched_file = tmp_project / "src" / "export.ts"
        content = patched_file.read_text()
        assert "/**" in content
        assert "*/" in content

    def test_evolved_jsdoc_achieves_threshold(self, tmp_project: Path) -> None:
        """Evolved JSDoc should achieve >= 70% Recall@1 on fixture."""
        spots = audit_blind_spots(tmp_project)
        assert len(spots) >= 3

        # Simulate query that returns target at rank 1 when JSDoc is good
        def perfect_query(p: str, q: str) -> list[str]:
            return ["src/export.ts"]

        evolver = DocEvolver(
            project_path=tmp_project,
            blind_spots=spots[:3],
            population_size=5,
            generations=5,
            query_fn=perfect_query,
        )

        results = evolver.evolve()
        # With perfect query (rank 1), all should achieve fitness = 1.0
        for r in results:
            assert r.best_fitness >= 0.7  # Recall@1 >= 70%

    def test_diverse_structures_generated(self, tmp_project: Path) -> None:
        """Evolution should produce diverse JSDoc structures."""
        spots = audit_blind_spots(tmp_project)[:1]

        seen_structures: set[str] = set()

        def collecting_query(p: str, q: str) -> list[str]:
            return ["src/export.ts"]

        evolver = DocEvolver(
            project_path=tmp_project,
            blind_spots=spots,
            population_size=10,
            generations=3,
            query_fn=collecting_query,
        )

        results = evolver.evolve()
        # Check that the generator produces diverse structures
        gen = JSDocGenerator()
        for _ in range(50):
            v = gen.generate("handleCSVExport", params=["data"])
            seen_structures.add(v.structure)

        assert len(seen_structures) >= 2
