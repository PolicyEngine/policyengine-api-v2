"""Tests for budget-window batch result helpers."""

import pytest

from src.modal.budget_window_results import (
    build_budget_window_result,
    sum_single_year_outputs,
    validate_single_year_output,
)
from tests.fixtures.budget_window_outputs import (
    FULL_SINGLE_YEAR_MACRO_OUTPUT_KEYS,
    make_single_year_macro_output,
)


def test_validate_single_year_output_preserves_full_macro_output():
    child_result = make_single_year_macro_output(
        tax_revenue_impact=100,
        state_tax_revenue_impact=40,
        benefit_spending_impact=20,
        budgetary_impact=80,
    )

    output = validate_single_year_output(
        simulation_year="2026",
        child_result=child_result,
    )

    dumped = output.model_dump(mode="json")
    assert FULL_SINGLE_YEAR_MACRO_OUTPUT_KEYS <= dumped.keys()
    assert dumped["budget"]["tax_revenue_impact"] == 100
    assert dumped["budget"]["state_tax_revenue_impact"] == 40
    assert dumped["detailed_budget"]["income_tax"]["difference"] == 10
    assert dumped["decile"]["average"]["1"] == 100
    assert dumped["decile_impacts"] == [
        {"decile": 1, "absolute_change": 100.0, "relative_change": 0.01}
    ]
    assert dumped["program_statistics"][0]["program_name"] == "income_tax"
    assert "annualImpacts" not in dumped


def test_validate_single_year_output_preserves_extra_worker_fields():
    child_result = make_single_year_macro_output(
        tax_revenue_impact=100,
        state_tax_revenue_impact=40,
        benefit_spending_impact=20,
        budgetary_impact=80,
    )
    child_result["worker_specific_section"] = {"value": "preserved"}
    child_result["budget"]["worker_specific_budget_metric"] = 123

    output = validate_single_year_output(
        simulation_year="2026",
        child_result=child_result,
    )

    dumped = output.model_dump(mode="json")
    assert dumped["worker_specific_section"] == {"value": "preserved"}
    assert dumped["budget"]["worker_specific_budget_metric"] == 123


def test_validate_single_year_output_defaults_state_tax_for_uk_child_result():
    """UK worker results omit ``state_tax_revenue_impact`` because the UK
    microsimulation has no devolved fiscal layer. The canonical output keeps a
    stable shape by treating that component as zero."""

    output = validate_single_year_output(
        simulation_year="2026",
        child_result=make_single_year_macro_output(
            tax_revenue_impact=250,
            state_tax_revenue_impact=None,
            benefit_spending_impact=40,
            budgetary_impact=210,
        ),
    )

    assert output.budget.tax_revenue_impact == 250
    assert output.budget.state_tax_revenue_impact == 0
    assert output.budget.budgetary_impact == 210


def test_validate_single_year_output_rejects_malformed_child_result():
    with pytest.raises(
        ValueError,
        match="Malformed budget-window child result: missing numeric budget.tax_revenue_impact",
    ):
        validate_single_year_output(
            simulation_year="2026",
            child_result=make_single_year_macro_output(
                tax_revenue_impact=100,
                state_tax_revenue_impact=40,
                benefit_spending_impact=20,
                budgetary_impact=80,
            )
            | {"budget": {"state_tax_revenue_impact": 40}},
        )


def test_validate_single_year_output_rejects_non_object_child_result():
    with pytest.raises(
        ValueError,
        match="Malformed budget-window child result: expected object for 2026",
    ):
        validate_single_year_output(
            simulation_year="2026",
            child_result="not-an-object",
        )


def test_validate_single_year_output_rejects_non_object_budget():
    child_result = make_single_year_macro_output(
        tax_revenue_impact=100,
        state_tax_revenue_impact=40,
        benefit_spending_impact=20,
        budgetary_impact=80,
    )
    child_result["budget"] = "not-an-object"

    with pytest.raises(
        ValueError,
        match="Malformed budget-window child result: missing budget object",
    ):
        validate_single_year_output(
            simulation_year="2026",
            child_result=child_result,
        )


def test_validate_single_year_output_wraps_model_shape_errors():
    child_result = make_single_year_macro_output(
        tax_revenue_impact=100,
        state_tax_revenue_impact=40,
        benefit_spending_impact=20,
        budgetary_impact=80,
    )
    child_result["decile"] = "not-an-object"

    with pytest.raises(
        ValueError,
        match="Malformed budget-window child result for 2026",
    ):
        validate_single_year_output(
            simulation_year="2026",
            child_result=child_result,
        )


def test_validate_single_year_output_rejects_malformed_state_tax_value():
    child_result = make_single_year_macro_output(
        tax_revenue_impact=100,
        state_tax_revenue_impact=40,
        benefit_spending_impact=20,
        budgetary_impact=80,
    )
    child_result["budget"]["state_tax_revenue_impact"] = "bad"

    with pytest.raises(
        ValueError,
        match="Malformed budget-window child result: missing numeric budget.state_tax_revenue_impact",
    ):
        validate_single_year_output(
            simulation_year="2026",
            child_result=child_result,
        )


def test_sum_single_year_outputs_avoids_binary_float_drift():
    """0.1 + 0.2 + 0.3 = 0.6 exactly when accumulated in Decimal."""

    outputs_by_year = {
        "2026": validate_single_year_output(
            simulation_year="2026",
            child_result=make_single_year_macro_output(
                tax_revenue_impact=0.1,
                state_tax_revenue_impact=0,
                benefit_spending_impact=0,
                budgetary_impact=0,
            ),
        ),
        "2027": validate_single_year_output(
            simulation_year="2027",
            child_result=make_single_year_macro_output(
                tax_revenue_impact=0.2,
                state_tax_revenue_impact=0,
                benefit_spending_impact=0,
                budgetary_impact=0,
            ),
        ),
        "2028": validate_single_year_output(
            simulation_year="2028",
            child_result=make_single_year_macro_output(
                tax_revenue_impact=0.3,
                state_tax_revenue_impact=0,
                benefit_spending_impact=0,
                budgetary_impact=0,
            ),
        ),
    }

    totals = sum_single_year_outputs(
        outputs_by_year=outputs_by_year,
        years=["2026", "2027", "2028"],
    )

    assert totals.taxRevenueImpact == 0.6


def test_build_budget_window_result_sums_totals_and_keeps_outputs_by_year():
    outputs_by_year = {
        "2026": validate_single_year_output(
            simulation_year="2026",
            child_result=make_single_year_macro_output(
                tax_revenue_impact=10,
                state_tax_revenue_impact=3,
                benefit_spending_impact=5,
                budgetary_impact=15,
            ),
        ),
        "2027": validate_single_year_output(
            simulation_year="2027",
            child_result=make_single_year_macro_output(
                tax_revenue_impact=11,
                state_tax_revenue_impact=3,
                benefit_spending_impact=6,
                budgetary_impact=17,
            ),
        ),
    }

    result = build_budget_window_result(
        start_year="2026",
        window_size=2,
        outputs_by_year=outputs_by_year,
    )

    assert result.years == ["2026", "2027"]
    assert result.endYear == "2027"
    assert result.outputsByYear["2026"].budget.tax_revenue_impact == 10
    assert result.totals.taxRevenueImpact == 21
    assert result.totals.budgetaryImpact == 32
    assert not hasattr(result.totals, "year")


def test_build_budget_window_result_rejects_missing_year_outputs():
    outputs_by_year = {
        "2026": validate_single_year_output(
            simulation_year="2026",
            child_result=make_single_year_macro_output(
                tax_revenue_impact=10,
                state_tax_revenue_impact=3,
                benefit_spending_impact=5,
                budgetary_impact=15,
            ),
        ),
    }

    with pytest.raises(
        ValueError,
        match="Cannot build budget-window result: missing outputs for 2027",
    ):
        build_budget_window_result(
            start_year="2026",
            window_size=2,
            outputs_by_year=outputs_by_year,
        )
