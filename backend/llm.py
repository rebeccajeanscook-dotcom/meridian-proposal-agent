"""Claude calls: (1) extract proposal facts from notes with provenance,
(2) write the prose sections once the facts are settled.

Both use structured outputs (output_config.format = json_schema), so Claude's
reply is guaranteed to be valid JSON matching our schema.
"""
import json
import os
import time

import anthropic

from .catalog import (
    CLIENT_TYPES, CURRENCIES, FIELDS, HORIZONS, MANDATE_TYPES, MODELS, RISK_CATEGORIES,
)

# Haiku 5.5 scored 100% on our 12 test cases at ~1/16 of Sonnet's cost and ~40% faster
# (see eval/ and the write-up). Override with CLAUDE_MODEL in .env.
MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-5-5")

_client = None


def client():
    global _client
    if _client is None:
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY is not set. Add it to the .env file.")
        # Keys that aren't scoped to a single workspace must name the workspace on
        # every request (anthropic-workspace-id header). Workspace-scoped keys don't need it.
        workspace = os.getenv("ANTHROPIC_WORKSPACE_ID", "").strip()
        headers = {"anthropic-workspace-id": workspace} if workspace else None
        _client = anthropic.Anthropic(default_headers=headers)
    return _client


last_usage = {}


def _json_call(system: str, user: str, schema: dict, max_tokens: int) -> dict:
    """One Claude call whose reply must match `schema`."""
    started = time.time()
    resp = client().messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": schema}},
    )
    last_usage.update(seconds=round(time.time() - started, 1),
                      input_tokens=resp.usage.input_tokens, output_tokens=resp.usage.output_tokens)
    if resp.stop_reason == "max_tokens":
        raise RuntimeError("Claude's reply was cut off (max_tokens). Try shorter notes.")
    text = "".join(b.text for b in resp.content if b.type == "text")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Claude returned something that isn't valid JSON: {e}")


def _model_catalogue() -> str:
    lines = []
    for mid, m in MODELS.items():
        lines.append(
            f"- id `{mid}`: {m['portfolioName']} ({m['currency']}). {m['description']} "
            f"Allocation: {m['allocation']}. PMs may call it: {', '.join(m['aliases'])}."
        )
    return "\n".join(lines)


# ── 1. Extraction ──────────────────────────────────────────────────────────

_FIELD_HINTS = {
    "clientName": "Name as it should appear on the proposal. Include a title (Mr/Mrs/Dr) ONLY if the notes use it; never add one. For joint clients use the person the notes say to put it under.",
    "clientEmail": "Only if written in the notes.",
    "clientType": f"One of {CLIENT_TYPES}. Joint individuals are 'Individual'.",
    "introGreetTo": "'client' if addressed to the client/trustees directly, 'advisor' if it goes to their financial adviser.",
    "financialPlanner": "The client's external financial adviser's name, if mentioned.",
    "totalInvestment": "Amount to invest as plain digits (e.g. '6200000'). An approximate but specific amount ('about R6.2 million', 'call it 4.5m') IS stated: use it with source 'notes' and mention it in flags. Only a vague amount with no number ('a few million', 'in the millions') is missing — never estimate one.",
    "incomeValue": "MONTHLY income drawdown as plain digits ('roughly R28,000 a month' -> '28000', source 'notes'). If the notes say no income is needed, value '0' with source 'notes'. If an annual figure is given, divide by 12. If income is wanted but no figure is given, it is missing.",
    "currency": f"One of {CURRENCIES}.",
    "investmentHorizon": f"One of {HORIZONS}. Map years: >=5 -> '5 years+', 3-5 -> '3 years+', 1-3 -> '1 year+'. 'Long-term' with no number is missing.",
    "riskProfileCategory": f"One of {RISK_CATEGORIES}.",
    "targetReturn": "e.g. 'CPI + 5%', only if stated.",
    "benchmark": "Benchmark description, only if a specific one is stated.",
    "model": f"One of {list(MODELS)}. Map the PM's shorthand using the catalogue.",
    "mandateType": f"One of {MANDATE_TYPES}.",
    "advisorFee": "Adviser fee % as a plain number string (e.g. '0.75').",
    "isReplacement": "'true' if this replaces an existing portfolio, 'false' if the notes say it does not.",
    "replacementDetails": "One sentence describing what is being replaced, if applicable.",
}


def _extraction_schema():
    """Kept deliberately small: one list of field items rather than 17 nested objects,
    because structured outputs compile the schema into a grammar with a size limit.
    Per-field instructions live in the system prompt instead."""
    item = {
        "type": "object",
        "properties": {
            "key": {"type": "string", "enum": [f["key"] for f in FIELDS]},
            "value": {"type": "string"},
            "source": {"type": "string", "enum": ["notes", "inferred", "missing"]},
            "evidence": {"type": "string"},
            "reason": {"type": "string"},
        },
        "required": ["key", "value", "source", "evidence", "reason"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "fields": {"type": "array", "items": item},
            "modelWording": {"type": "string"},
            "flags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["fields", "modelWording", "flags"],
        "additionalProperties": False,
    }


def _field_guide() -> str:
    return "\n".join(f"- {f['key']}: {_FIELD_HINTS.get(f['key'], '')}" for f in FIELDS)


_EXTRACT_SYSTEM = f"""You help Portfolio Managers (PMs) at Meridian Private Clients turn their
meeting notes or voice-note transcripts into a draft investment proposal.

Your job is extraction, not advice. Record what the notes say. Rules:
- Never invent numbers (amounts, income, fees). If a figure is vague or absent, mark it missing.
- Use 'inferred' only for a reasonable reading of the notes the PM should check (e.g. mapping
  'not a gambler but wants growth' to a risk level, or the PM's portfolio nickname to a model).
  Always say why in 'reason'.
- Quote the notes verbatim in 'evidence' so the PM can see where each value came from.
- Voice transcripts contain fillers and self-corrections; use the PM's final intent.
- Use the exact option values given for dropdown fields.

Output format: return one item in "fields" for EVERY field key below, each with
  value    – the value in the format described (empty string if missing)
  source   – "notes" (explicitly stated), "inferred" (a reasonable reading the PM must check) or "missing"
  evidence – a short verbatim quote from the notes (empty if missing)
  reason   – for inferred values, one short sentence on why (otherwise empty)
"modelWording" is the PM's own words for the portfolio, verbatim (empty if none).
"flags" lists short notes for the PM about ambiguities or anything that doesn't fit the tool
(e.g. a joint client, or a portfolio name that doesn't match a model).

Fields:
{_field_guide()}

The firm's model portfolios:
{_model_catalogue()}
"""


def extract_facts(notes: str) -> dict:
    """Return {field_key: {value, source, evidence, reason}, 'modelWording': str, 'flags': [..]}."""
    data = _json_call(_EXTRACT_SYSTEM, f"PM notes:\n<notes>\n{notes}\n</notes>",
                      _extraction_schema(), max_tokens=4000)
    out = {"modelWording": data.get("modelWording", ""), "flags": data.get("flags", [])}
    for item in data.get("fields", []):
        key = item.pop("key", None)
        if key:
            if item.get("value") == "":  # empty string means "no value"
                item["value"] = None
            out[key] = item
    return out  # any field Claude left out is treated as missing downstream


# ── 2. Narrative ───────────────────────────────────────────────────────────

_NARRATIVE_SCHEMA = {
    "type": "object",
    "properties": {
        "needs": {"type": "string",
                  "description": "Client needs & objectives: one paragraph, third person, formal (e.g. 'Mr Whitfield, aged 63, has recently retired...'). Use only the facts given."},
        "riskProfile": {"type": "string",
                        "description": "Risk profile: 1-3 sentences starting with the risk level in plain words (e.g. 'Moderate-to-aggressive. ...')."},
    },
    "required": ["needs", "riskProfile"],
    "additionalProperties": False,
}

_NARRATIVE_SYSTEM = """You write the prose sections of a Meridian Private Clients investment
proposal from confirmed facts and the PM's original notes. Formal, warm, concise, South African
English. Do not add facts, figures or recommendations that are not in the facts or notes. If a
key fact is marked TO CONFIRM, write around it neutrally (e.g. 'the investment amount is to be
confirmed') rather than guessing. Do not include the [TO CONFIRM] list itself; it is appended
separately."""


def write_narrative(notes: str, facts: dict) -> dict:
    return _json_call(
        _NARRATIVE_SYSTEM,
        f"Confirmed facts (JSON):\n{json.dumps(facts, indent=2)}\n\nPM notes:\n<notes>\n{notes}\n</notes>",
        _NARRATIVE_SCHEMA, max_tokens=1500)
