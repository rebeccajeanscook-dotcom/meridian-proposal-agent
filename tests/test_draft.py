"""Tests for the draft logic using a hand-written extraction (no API key needed)."""
from backend import draft


def _f(value, source="notes", evidence="x"):
    return {"value": value, "source": source, "evidence": evidence, "reason": ""}


MISSING = {"value": None, "source": "missing", "evidence": ""}

SPARSE = {  # roughly what Claude returns for 03-notes-sparse.txt
    "clientName": _f("Mrs Lindiwe Petersen"),
    "clientType": _f("Individual"),
    "introGreetTo": _f("client", "inferred"),
    "financialPlanner": MISSING, "clientEmail": MISSING,
    "totalInvestment": MISSING,            # "a few million" must stay missing
    "incomeValue": MISSING,
    "currency": _f("ZAR"),
    "investmentHorizon": MISSING,
    "riskProfileCategory": _f("Moderate", "inferred"),
    "targetReturn": MISSING, "benchmark": MISSING,
    "model": _f("balanced", "inferred"),
    "mandateType": MISSING, "advisorFee": MISSING,
    "isReplacement": MISSING, "replacementDetails": MISSING,
    "modelWording": "Balanced-ish feel",
    "flags": [],
}


def test_sparse_asks_in_priority_order():
    fields, _ = draft.clean_extraction(SPARSE)
    assert draft.pending_questions(fields) == [
        "totalInvestment", "incomeValue", "investmentHorizon", "mandateType", "advisorFee"]


def test_vague_amount_is_not_used():
    raw = {**SPARSE, "totalInvestment": _f("a few million")}
    fields, flags = draft.clean_extraction(raw)
    assert fields["totalInvestment"]["value"] is None
    assert any("Investment amount" in f for f in flags)


def test_answers_skip_and_build():
    fields, _ = draft.clean_extraction(SPARSE)
    fields, err = draft.apply_answer(fields, "totalInvestment", "about R3.5m")
    assert err is None and fields["totalInvestment"] == {
        "value": "3500000", "source": "pm", "evidence": "You answered: about R3.5m", "reason": ""}
    fields, err = draft.apply_answer(fields, "incomeValue", "lots")
    assert err  # unreadable answer is rejected, not guessed
    fields, _ = draft.apply_answer(fields, "incomeValue", None, skip=True)
    fields, _ = draft.apply_answer(fields, "investmentHorizon", None, skip=True)

    p = draft.build_proposal(fields, {"needs": "Mrs Petersen ...", "riskProfile": "Moderate."})
    assert p["applyModel"] == "balanced"
    assert p["strategy"]["keyFigures"] == {"totalInvestment": "3500000"}
    assert "goalAssessment" in p and "keyFigures" not in p["goalAssessment"]
    assert "[TO CONFIRM: monthly income drawdown, investment horizon" in p["needs"]
    assert "investmentHorizon" not in p["objective"]


def test_advisor_needs_planner_and_no_income_is_omitted():
    raw = {**SPARSE, "introGreetTo": _f("advisor"), "incomeValue": _f("0"),
           "isReplacement": _f("true"), "replacementDetails": _f("Replaces an offshore unit trust.")}
    fields, _ = draft.clean_extraction(raw)
    assert draft.pending_questions(fields)[0] == "financialPlanner"
    fields, _ = draft.apply_answer(fields, "financialPlanner", "Marcus Reid")
    p = draft.build_proposal(fields)
    assert p["financialPlanner"] == "Marcus Reid"
    assert "incomeValue" not in p.get("strategy", {}).get("keyFigures", {})
    assert p["replacements"]["isReplacement"] is True


def test_model_from_pm_wording_and_currency_derived():
    raw = {**SPARSE, "model": MISSING, "currency": MISSING, "modelWording": "Reg 28 bespoke model"}
    fields, _ = draft.clean_extraction(raw)
    assert fields["model"]["value"] == "income" and fields["model"]["source"] == "inferred"
    assert fields["currency"] == {**fields["currency"], "value": "ZAR", "source": "inferred"}
