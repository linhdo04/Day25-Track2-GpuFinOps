import pytest

from finops import pricing
from missions import m2_inference_levers


def test_cache_economics_break_even_and_validation():
    assert pricing.cache_break_even_reads(1.25, 0.10) == pytest.approx(1.25 / 0.90)
    assert not pricing.cache_is_worth_it(1, 1.25, 0.10)
    assert pricing.cache_is_worth_it(2, 1.25, 0.10)
    with pytest.raises(ValueError):
        pricing.cache_break_even_reads(1.25, 1.0)


def test_reasoning_budget_is_measured_and_actionable():
    result = m2_inference_levers.run(verbose=False)
    reasoning = result["reasoning"]
    assert reasoning["requests"] > 0
    assert reasoning["cost_daily"] > 0
    assert reasoning["wh_daily"] > 0
    assert reasoning["cap_savings_daily"] > 0
    assert reasoning["cap_wh_savings_daily"] > 0
