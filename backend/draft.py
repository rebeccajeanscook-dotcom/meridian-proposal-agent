"""The draft: a dict of fields, each with a value and where it came from.

    fields = {
      "totalInvestment": {"value": "6200000", "source": "notes",
                          "evidence": "lump sum of about R6.2 million", "reason": ""},
      ...
    }

This module cleans Claude's extraction, decides the next follow-up question,
applies the PM's answers and turns the finished draft into the object the
proposal tool's window.loadProposal() accepts.
"""
import re

from .catalog import FIELD_BY_KEY, FIELDS, MODELS
from .normalise import normalise


def _empty(source="missing"):
    return {"value": None, "source": source, "evidence": "", "reason": ""}


# ── From Claude's raw extraction to a clean draft ──────────────────────────

def clean_extraction(raw: dict) -> tuple[dict, list]:
    fields, flags = {}, list(raw.get("flags") or [])
    for spec in FIELDS:
        key = spec["key"]
        item = raw.get(key) or {}
        source = item.get("source") or "missing"
        raw_value = item.get("value")
        entry = _empty()
        if source != "missing" and raw_value not in (None, ""):
            value = normalise(key, raw_value)
            if value is None:
                flags.append(f"{spec['label']}: couldn't use '{raw_value}' — please confirm.")
            else:
                entry = {"value": value, "source": source if source in ("notes", "inferred") else "inferred",
                         "evidence": item.get("evidence", ""), "reason": item.get("reason", "")}
        entry["raw"] = raw_value  # what Claude returned, kept so the PM can see the conversion
        fields[key] = entry

    # If Claude didn't pick a model but the PM used a known nickname, map it in code.
    wording = (raw.get("modelWording") or "").strip()
    if fields["model"]["value"] is None and wording:
        mid = normalise("model", wording)
        if mid:
            fields["model"] = {"value": mid, "source": "inferred", "evidence": wording,
                               "reason": f"'{wording}' matched the {MODELS[mid]['portfolioName']}."}
    if wording and fields["model"]["value"]:
        fields["model"]["pmWording"] = wording

    apply_derived(fields)
    return fields, flags


def apply_derived(fields: dict) -> None:
    """Fill fields that follow logically from others, labelled as inferred."""
    model = fields.get("model", {}).get("value")
    if model and fields["currency"]["source"] == "missing":
        fields["currency"] = {"value": MODELS[model]["currency"], "source": "inferred",
                              "evidence": "", "reason": f"The {MODELS[model]['portfolioName']} is a {MODELS[model]['currency']} portfolio."}
    if fields["introGreetTo"]["source"] == "missing":
        fields["introGreetTo"] = {"value": "client", "source": "inferred", "evidence": "",
                                  "reason": "Proposals go to the client unless the notes mention their adviser."}
    if fields["isReplacement"]["value"] is None and fields["isReplacement"]["source"] == "missing":
        fields["isReplacement"] = {"value": False, "source": "inferred", "evidence": "",
                                   "reason": "No replacement mentioned in the notes."}


# ── Follow-up questions, one at a time ─────────────────────────────────────

def _needs_answer(fields, key):
    return fields.get(key, {}).get("source") == "missing"


def pending_questions(fields: dict) -> list:
    keys = sorted((f for f in FIELDS if f.get("ask") and _needs_answer(fields, f["key"])),
                  key=lambda f: f["ask"])
    keys = [f["key"] for f in keys]
    if fields.get("introGreetTo", {}).get("value") == "advisor" and _needs_answer(fields, "financialPlanner"):
        keys.insert(0, "financialPlanner")
    return keys


def _options(key):
    if key == "model":
        return [{"value": mid, "label": f"{m['portfolioName']} ({m['currency']})",
                 "hint": m["description"]} for mid, m in MODELS.items()]
    if key == "introGreetTo":
        return [{"value": "client", "label": "The client directly"},
                {"value": "advisor", "label": "Their financial adviser"}]
    spec = FIELD_BY_KEY[key]
    return [{"value": o, "label": o} for o in spec.get("options", [])]


def question_for(key: str, fields: dict) -> dict:
    spec = FIELD_BY_KEY[key]
    context = "This wasn't in your notes."
    if key == "riskProfileCategory" and fields.get("model", {}).get("value"):
        context += f" You've chosen the {MODELS[fields['model']['value']]['portfolioName']}."
    return {
        "key": key,
        "label": spec["label"],
        "text": spec.get("question", f"What is the {spec['label'].lower()}?"),
        "kind": spec["kind"],
        "options": _options(key) if spec["kind"] == "enum" else [],
        "placeholder": spec.get("placeholder", ""),
        "context": context,
    }


def next_question(fields: dict):
    pending = pending_questions(fields)
    if not pending:
        return None, 0
    return question_for(pending[0], fields), len(pending)


def apply_answer(fields: dict, key: str, answer, skip: bool = False):
    """Returns (fields, error). On skip, the field is marked TO CONFIRM."""
    if key not in FIELD_BY_KEY:
        return fields, f"Unknown field '{key}'."
    if skip:
        fields[key] = _empty("to_confirm")
        return fields, None
    value = normalise(key, answer)
    if value is None:
        hint = FIELD_BY_KEY[key].get("placeholder")
        return fields, f"Sorry, I couldn't read that as a {FIELD_BY_KEY[key]['label'].lower()}." + (
            f" Try something like: {hint}." if hint else "")
    fields[key] = {"value": value, "source": "pm", "evidence": f"You answered: {answer}", "reason": ""}
    apply_derived(fields)
    return fields, None


# ── Draft → proposal-tool object ───────────────────────────────────────────

def _val(fields, key):
    return fields.get(key, {}).get("value")


def to_confirm_list(fields: dict) -> list:
    keys = [k for k, f in fields.items()
            if f.get("source") in ("to_confirm", "missing")
            and (FIELD_BY_KEY.get(k, {}).get("ask") or k == "financialPlanner")]
    if _val(fields, "introGreetTo") != "advisor" and "financialPlanner" in keys:
        keys.remove("financialPlanner")
    return [re.sub(r"\s*\(.*?\)", "", FIELD_BY_KEY[k]["label"]).lower() for k in keys]


def facts_for_narrative(fields: dict) -> dict:
    out = {}
    for spec in FIELDS:
        v = _val(fields, spec["key"])
        src = fields.get(spec["key"], {}).get("source")
        if spec["key"] == "model" and v:
            v = MODELS[v]["portfolioName"]
        if spec["key"] == "incomeValue" and v == "0":
            v = "No income required"
        out[spec["label"]] = "TO CONFIRM" if src in ("missing", "to_confirm") else v
    return out


def build_proposal(fields: dict, narrative: dict | None = None) -> dict:
    """Build the object passed to window.loadProposal() in the proposal tool."""
    narrative = narrative or {}
    p: dict = {"status": "draft"}

    if _val(fields, "model"):
        p["applyModel"] = _val(fields, "model")
    for key in ("clientName", "clientEmail", "introGreetTo"):
        if _val(fields, key):
            p[key] = _val(fields, key)
    if _val(fields, "introGreetTo") == "advisor" and _val(fields, "financialPlanner"):
        p["financialPlanner"] = _val(fields, "financialPlanner")

    needs = (narrative.get("needs") or "").strip()
    pending = to_confirm_list(fields)
    if pending:
        needs = (needs + "\n\n" if needs else "") + f"[TO CONFIRM: {', '.join(pending)}.]"
    if needs:
        p["needs"] = needs

    ga = {k: _val(fields, k) for k in ("clientType", "mandateType", "currency") if _val(fields, k)}
    if ga:
        p["goalAssessment"] = ga

    # Amounts MUST live under strategy.keyFigures — the tool ignores them elsewhere.
    kf = {}
    if _val(fields, "totalInvestment"):
        kf["totalInvestment"] = _val(fields, "totalInvestment")
    if _val(fields, "incomeValue") and _val(fields, "incomeValue") != "0":
        kf["incomeValue"] = _val(fields, "incomeValue")
    if kf:
        p["strategy"] = {"keyFigures": kf}

    obj = {k: _val(fields, k) for k in ("targetReturn", "benchmark", "riskProfileCategory",
                                         "investmentHorizon") if _val(fields, k)}
    if narrative.get("riskProfile"):
        obj["riskProfile"] = narrative["riskProfile"].strip()
    if obj:
        p["objective"] = obj

    if _val(fields, "advisorFee"):
        p["fees"] = {"advisorFee": _val(fields, "advisorFee")}

    if _val(fields, "isReplacement") is True:
        p["replacements"] = {"isReplacement": True,
                             "details": _val(fields, "replacementDetails") or ""}
    return p
