"""Rule-based consistency checks: plain code, no AI.

They look at the draft as a whole and warn the PM about combinations that are
technically valid in the tool but probably wrong, the kind of thing a senior PM
would catch on review. They never change the draft; they only warn.

Thresholds are assumptions (documented in the write-up) and would be set by the
firm's investment committee in practice.
"""
from .catalog import MODELS

MAX_SUSTAINABLE_DRAWDOWN = 0.05   # >5% of capital per year starts to erode capital
HIGH_DRAWDOWN = 0.08              # >8% is very likely to deplete the capital
HIGH_FEE = 1.5                    # adviser fee % above which we ask the PM to double-check
MIN_AMOUNT, MAX_AMOUNT = 100_000, 1_000_000_000

_RISK_ORDER = ["Conservative", "Moderately Conservative", "Moderate",
               "Moderately Aggressive", "Aggressive"]
# Risk levels each model is designed for (from the model descriptions in catalog.py).
_MODEL_RISK = {
    "income": {"Conservative", "Moderately Conservative", "Moderate"},
    "balanced": {"Moderately Conservative", "Moderate", "Moderately Aggressive"},
    "global-growth": {"Moderately Aggressive", "Aggressive"},
}


def _v(fields, key):
    return (fields.get(key) or {}).get("value")


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def run_checks(fields: dict) -> list[dict]:
    """Return a list of {level: 'warning'|'info', message, fields: [keys]}."""
    out = []

    def warn(level, message, *keys):
        out.append({"level": level, "message": message, "fields": list(keys)})

    model, currency = _v(fields, "model"), _v(fields, "currency")
    risk, horizon = _v(fields, "riskProfileCategory"), _v(fields, "investmentHorizon")
    amount, income = _num(_v(fields, "totalInvestment")), _num(_v(fields, "incomeValue"))
    fee = _num(_v(fields, "advisorFee"))
    name = MODELS[model]["portfolioName"] if model in MODELS else None

    # 1. Currency doesn't match the model portfolio's currency.
    if model in MODELS and currency and currency != MODELS[model]["currency"]:
        warn("warning", f"The {name} is a {MODELS[model]['currency']} portfolio, but the currency is "
                        f"{currency}. Check the model or the currency.", "model", "currency")

    # 2. Risk level is outside what the model is designed for.
    if model in _MODEL_RISK and risk and risk not in _MODEL_RISK[model]:
        warn("warning", f"A {risk.lower()} risk level is unusual for the {name}. "
                        f"Check the model fits the client's risk profile.", "model", "riskProfileCategory")

    # 3. Income drawdown is high relative to the capital.
    if amount and income:
        rate = income * 12 / amount
        if rate > HIGH_DRAWDOWN:
            warn("warning", f"An income of {income:,.0f} a month is {rate:.1%} of the capital per year, "
                            f"which is likely to deplete it. Confirm the amounts.", "incomeValue", "totalInvestment")
        elif rate > MAX_SUSTAINABLE_DRAWDOWN:
            warn("info", f"An income of {income:,.0f} a month is {rate:.1%} of the capital per year. "
                         f"Above ~5% may erode capital over time; worth discussing with the client.",
                 "incomeValue", "totalInvestment")

    # 4. Income needed, but the model isn't built to pay one.
    if income and model == "global-growth":
        warn("warning", f"The client needs a monthly income, but the {name} is a pure growth portfolio "
                        f"with no income focus.", "model", "incomeValue")

    # 5. Short horizon with a high-risk profile.
    if horizon == "1 year+" and risk in ("Moderately Aggressive", "Aggressive"):
        warn("warning", "A short (1 year+) horizon with an aggressive risk level is a poor fit: there is "
                        "little time to recover from a market fall.", "investmentHorizon", "riskProfileCategory")

    # 6. Replacement without details (needed for disclosure).
    if _v(fields, "isReplacement") is True and not _v(fields, "replacementDetails"):
        warn("info", "This replaces an existing portfolio. Add replacement details for the "
                     "disclosure section.", "replacementDetails")

    # 7. Unusual figures that may be typos.
    if amount is not None and amount > 0 and not (MIN_AMOUNT <= amount <= MAX_AMOUNT):
        warn("warning", f"An investment amount of {amount:,.0f} looks unusual. Check for a missing or "
                        f"extra zero.", "totalInvestment")
    if fee is not None and fee > HIGH_FEE:
        warn("info", f"An adviser fee of {fee}% is above the typical range. Please double-check.",
             "advisorFee")
    return out
