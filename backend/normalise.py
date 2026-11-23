"""Deterministic conversion of loosely written values into the exact formats
the proposal tool accepts. Each parser returns the clean value, or None if it
can't be sure — in which case the field is treated as missing, never guessed.
"""
import re

from .catalog import (
    CLIENT_TYPES, CURRENCIES, GREET_TO, MANDATE_TYPES, MODELS, RISK_CATEGORIES,
)

_MULTIPLIERS = {
    "k": 1_000, "thousand": 1_000,
    "m": 1_000_000, "mil": 1_000_000, "mill": 1_000_000, "million": 1_000_000, "mn": 1_000_000,
    "bn": 1_000_000_000, "b": 1_000_000_000, "billion": 1_000_000_000,
}

_WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "hundred": 100,
}

_NONE_WORDS = {"none", "no", "nil", "zero", "0", "n/a", "na", "not required", "no income"}


def _words_to_number(text: str):
    """Handle simple spoken amounts like 'four and a half million'."""
    t = text.lower()
    half = " and a half" in t
    t = t.replace(" and a half", "")
    m = re.search(r"\b(" + "|".join(_WORD_NUMBERS) + r")\b\s*(thousand|million|billion)?", t)
    if not m:
        return None
    n = _WORD_NUMBERS[m.group(1)] + (0.5 if half else 0)
    return n * _MULTIPLIERS.get(m.group(2) or "", 1)


def parse_money(raw):
    """'R6.2 million' -> '6200000'; 'R28,000' -> '28000'; 'none' -> '0'."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return str(int(round(raw))) if raw >= 0 else None
    text = str(raw).strip().lower()
    if not text:
        return None
    if text in _NONE_WORDS or text.startswith("no ") or text.startswith("none"):
        return "0"
    # Vague amounts are not numbers ("a few million").
    if re.search(r"\b(few|several|some|couple)\b", text):
        return None
    cleaned = re.sub(r"(?<=\d)[ , '](?=\d{3}\b)", "", text)  # 1 200 000 / 1,200,000
    m = re.search(r"(\d+(?:\.\d+)?)\s*(k|thousand|mil|mill|million|mn|m|bn|billion|b)?\b", cleaned)
    if m:
        value = float(m.group(1)) * _MULTIPLIERS.get(m.group(2) or "", 1)
    else:
        value = _words_to_number(text)
        if value is None:
            return None
    return str(int(round(value)))


def parse_percent(raw):
    """'0.60%' -> '0.60'; 'zero point seven five' -> '0.75'."""
    if raw is None:
        return None
    text = str(raw).strip().lower().replace(",", ".")
    m = re.search(r"\d+(?:\.\d+)?", text)
    if m:
        num = float(m.group(0))
    else:
        digits = {"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
                  "six": "6", "seven": "7", "eight": "8", "nine": "9", "point": "."}
        words = re.findall(r"[a-z]+", text)
        s = "".join(digits[w] for w in words if w in digits)
        try:
            num = float(s)
        except ValueError:
            return None
    if re.search(r"\d\s*(bps?|basis points?)\b", text):
        num = num / 100        # 75bps -> 0.75%
    if num < 0 or num > 10:   # an adviser fee above 10% is almost certainly a mistake
        return None
    return f"{num:.2f}"


def parse_horizon(raw):
    """Map a horizon in years to the tool's dropdown buckets."""
    if raw is None:
        return None
    text = str(raw).strip().lower()
    for opt in ("1 year+", "3 years+", "5 years+"):
        if text == opt:
            return opt
    m = re.search(r"(\d+(?:\.\d+)?)", text)
    years = float(m.group(1)) if m else _words_to_number(text)
    if years is None:
        return None  # e.g. 'long-term' alone is not specific enough to decide
    if "month" in text:
        years = years / 12
    if years >= 5:
        return "5 years+"
    if years >= 3:
        return "3 years+"
    if years >= 1:
        return "1 year+"
    return None


_RISK_SYNONYMS = [
    (r"moderate(ly)?[\s-]*(to|-)[\s-]*aggressive|moderately aggressive|mod[\s-]*agg", "Moderately Aggressive"),
    (r"conservative[\s-]*(to|-)[\s-]*moderate|moderately conservative|mod[\s-]*cons", "Moderately Conservative"),
    (r"\baggressive|high risk", "Aggressive"),
    (r"\bconservative|low risk|cautious|risk[\s-]*averse", "Conservative"),
    (r"\bmoderate|balanced|medium", "Moderate"),
]


def parse_risk(raw):
    if raw is None:
        return None
    text = str(raw).strip().lower()
    for opt in RISK_CATEGORIES:
        if text == opt.lower():
            return opt
    for pattern, value in _RISK_SYNONYMS:
        if re.search(pattern, text):
            return value
    return None


def parse_model(raw):
    """Map a model ID or PM shorthand ('Reg 28 bespoke') to a model ID."""
    if raw is None:
        return None
    text = re.sub(r"[^a-z0-9 ]", " ", str(raw).lower())
    text = re.sub(r"\s+", " ", text).strip()
    if text.replace(" ", "-") in MODELS:
        return text.replace(" ", "-")
    best, best_len = None, 0
    for model_id, info in MODELS.items():
        for alias in info["aliases"]:
            if alias in text and len(alias) > best_len:
                best, best_len = model_id, len(alias)
    return best


def _parse_choice(raw, options):
    if raw is None:
        return None
    text = str(raw).strip().lower()
    for opt in options:
        if text == opt.lower() or text.startswith(opt.lower()):
            return opt
    return None


def parse_currency(raw):
    if raw is None:
        return None
    text = str(raw).strip().upper()
    if text in CURRENCIES:
        return text
    if text in ("R", "RAND", "RANDS") or "RAND" in text:
        return "ZAR"
    if "DOLLAR" in text or text == "$":
        return "USD"
    if "POUND" in text or "STERLING" in text or text == "£":
        return "GBP"
    if "EURO" in text or text == "€":
        return "EUR"
    return None


def parse_client_type(raw):
    if raw is None:
        return None
    text = str(raw).lower()
    if "trust" in text:
        return "Trust"
    if any(w in text for w in ("company", "pty", "ltd", "corporate", "business")):
        return "Company"
    if any(w in text for w in ("individual", "person", "joint", "personal")):
        return "Individual"
    return _parse_choice(raw, CLIENT_TYPES)


def parse_greet_to(raw):
    if raw is None:
        return None
    text = str(raw).lower()
    if any(w in text for w in ("advis", "planner", "broker")):
        return "advisor"
    if any(w in text for w in ("client", "direct", "trustee")):
        return "client"
    return _parse_choice(raw, GREET_TO)


def parse_bool(raw):
    if raw is None:
        return None
    if isinstance(raw, bool):
        return raw
    text = str(raw).strip().lower()
    if text in ("true", "yes", "y", "1"):
        return True
    if text in ("false", "no", "n", "0"):
        return False
    return None


def parse_text(raw):
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


PARSERS = {
    "clientName": parse_text,
    "clientEmail": parse_text,
    "clientType": parse_client_type,
    "introGreetTo": parse_greet_to,
    "financialPlanner": parse_text,
    "totalInvestment": parse_money,
    "incomeValue": parse_money,
    "currency": parse_currency,
    "investmentHorizon": parse_horizon,
    "riskProfileCategory": parse_risk,
    "targetReturn": parse_text,
    "benchmark": parse_text,
    "model": parse_model,
    "mandateType": lambda r: _parse_choice(r, MANDATE_TYPES),
    "advisorFee": parse_percent,
    "isReplacement": parse_bool,
    "replacementDetails": parse_text,
}


def normalise(key, raw):
    """Return the tool-ready value for a field, or None if it can't be parsed."""
    parser = PARSERS.get(key, parse_text)
    return parser(raw)
