"""Tests for gates/rubrics.py"""

import pytest
from gates.rubrics import RUBRICS

EXPECTED_GATES = {"plan", "research", "outline", "content", "editorial", "formatting", "assembly"}


class TestRubricsStructure:
    def test_all_expected_gates_present(self):
        assert EXPECTED_GATES == set(RUBRICS.keys())

    @pytest.mark.parametrize("gate_key", sorted(EXPECTED_GATES))
    def test_weights_sum_to_one(self, gate_key):
        rubric = RUBRICS[gate_key]
        total = sum(dim["weight"] for dim in rubric)
        assert total == pytest.approx(1.0, abs=1e-9), (
            f"Rubric '{gate_key}' weights sum to {total}, expected 1.0"
        )

    @pytest.mark.parametrize("gate_key", sorted(EXPECTED_GATES))
    def test_each_dimension_has_required_fields(self, gate_key):
        for dim in RUBRICS[gate_key]:
            assert "name" in dim, f"{gate_key}: missing 'name'"
            assert "weight" in dim, f"{gate_key}: missing 'weight'"
            assert "measures" in dim, f"{gate_key}: missing 'measures'"
            assert "critical" in dim, f"{gate_key}: missing 'critical'"

    @pytest.mark.parametrize("gate_key", sorted(EXPECTED_GATES))
    def test_weights_are_positive(self, gate_key):
        for dim in RUBRICS[gate_key]:
            assert dim["weight"] > 0, (
                f"{gate_key}/{dim['name']}: weight must be > 0"
            )

    @pytest.mark.parametrize("gate_key", sorted(EXPECTED_GATES))
    def test_weights_are_at_most_one(self, gate_key):
        for dim in RUBRICS[gate_key]:
            assert dim["weight"] <= 1.0, (
                f"{gate_key}/{dim['name']}: weight {dim['weight']} exceeds 1.0"
            )

    @pytest.mark.parametrize("gate_key", sorted(EXPECTED_GATES))
    def test_names_are_unique_within_rubric(self, gate_key):
        names = [dim["name"] for dim in RUBRICS[gate_key]]
        assert len(names) == len(set(names)), (
            f"{gate_key}: duplicate dimension names: {names}"
        )

    @pytest.mark.parametrize("gate_key", sorted(EXPECTED_GATES))
    def test_measures_are_non_empty_strings(self, gate_key):
        for dim in RUBRICS[gate_key]:
            assert isinstance(dim["measures"], str)
            assert len(dim["measures"]) > 0

    @pytest.mark.parametrize("gate_key", sorted(EXPECTED_GATES))
    def test_critical_is_bool(self, gate_key):
        for dim in RUBRICS[gate_key]:
            assert isinstance(dim["critical"], bool), (
                f"{gate_key}/{dim['name']}: 'critical' must be bool"
            )

    @pytest.mark.parametrize("gate_key", sorted(EXPECTED_GATES))
    def test_at_least_two_dimensions(self, gate_key):
        assert len(RUBRICS[gate_key]) >= 2, (
            f"{gate_key}: must have at least 2 dimensions"
        )


class TestRubricContent:
    def test_research_has_source_coverage_dimension(self):
        names = [d["name"] for d in RUBRICS["research"]]
        assert any("source" in n.lower() or "coverage" in n.lower() for n in names)

    def test_assembly_completeness_is_highest_weight(self):
        dims = RUBRICS["assembly"]
        completeness = next(d for d in dims if "completeness" in d["name"].lower())
        max_weight = max(d["weight"] for d in dims)
        assert completeness["weight"] == pytest.approx(max_weight)

    def test_critical_dimensions_exist_in_content_gate(self):
        critical = [d for d in RUBRICS["content"] if d["critical"]]
        assert len(critical) >= 1

    def test_plan_gate_spec_coverage_is_critical(self):
        plan_dims = RUBRICS["plan"]
        critical_names = [d["name"] for d in plan_dims if d["critical"]]
        assert any("spec" in n.lower() or "coverage" in n.lower() for n in critical_names)
