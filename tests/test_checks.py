"""Tests for the rule-based consistency checks (no API key needed)."""
from backend.checks import run_checks


def draft(**values):
    return {k: {"value": v, "source": "notes"} for k, v in values.items()}


def messages(fields):
    return " | ".join(c["message"] for c in run_checks(fields))


def test_clean_draft_has_no_warnings():
    # Sample 01 (Whitfield): R6.2m, R28k/month (5.4%) -> only an info note on drawdown.
    checks = run_checks(draft(model="income", currency="ZAR", riskProfileCategory="Moderately Conservative",
                              investmentHorizon="5 years+", totalInvestment="6200000", incomeValue="28000",
                              advisorFee="0.60", isReplacement=False))
    assert [c["level"] for c in checks] == ["info"]
    assert "5.4%" in checks[0]["message"]


def test_currency_mismatch():
    assert "GBP" in messages(draft(model="balanced", currency="GBP"))


def test_risk_vs_model():
    assert "unusual for the Meridian Income Portfolio" in messages(
        draft(model="income", riskProfileCategory="Aggressive"))
    assert messages(draft(model="balanced", riskProfileCategory="Moderate")) == ""


def test_high_drawdown_and_growth_model_income():
    m = messages(draft(model="global-growth", currency="USD", totalInvestment="1000000", incomeValue="10000"))
    assert "12.0% of the capital" in m and "pure growth portfolio" in m


def test_short_horizon_aggressive():
    assert "1 year+" in messages(draft(investmentHorizon="1 year+", riskProfileCategory="Aggressive"))


def test_replacement_and_typos():
    m = messages(draft(isReplacement=True, totalInvestment="62000", advisorFee="2.5"))
    assert "replacement details" in m and "missing or extra zero" in m and "2.5%" in m


def test_missing_values_are_ignored():
    assert run_checks(draft(model=None, currency=None, totalInvestment=None, incomeValue=None)) == []
