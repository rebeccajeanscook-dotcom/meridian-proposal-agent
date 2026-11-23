"""The firm's reference data: model portfolios, dropdown options and the
proposal fields the assistant works with.

Everything the AI is allowed to choose from lives here, so it can be checked
in code rather than trusted from the model's output.
"""

# ── Model portfolios (mirrors STRATEGIES in challenge-generator.html) ──────
MODELS = {
    "balanced": {
        "portfolioName": "Meridian Balanced Portfolio",
        "currency": "ZAR",
        "allocation": "30% SA equity, 35% international equity, 25% SA fixed interest, 10% cash",
        "description": (
            "Multi-asset, flexible/bespoke growth portfolio in rand with a meaningful offshore "
            "allocation. Suits moderate to moderately aggressive investors who want growth "
            "with some diversification, and clients with an undecided 'balanced' feel."
        ),
        # Shorthand PMs use in their notes for this model.
        "aliases": [
            "balanced", "flexible", "flexible bespoke", "flexible bespoke portfolio",
            "flex mod etf", "3yg flex mod etf", "multi-asset", "bespoke flexible",
        ],
    },
    "global-growth": {
        "portfolioName": "Meridian Global Growth Portfolio",
        "currency": "USD",
        "allocation": "90% international equity, 10% cash",
        "description": (
            "Offshore, US-dollar, pure global equity portfolio for long-term capital growth. "
            "Suits aggressive investors with no income need and no local exposure."
        ),
        "aliases": [
            "global growth", "global equity", "global equity model", "offshore equity",
            "offshore growth",
        ],
    },
    "income": {
        "portfolioName": "Meridian Income Portfolio",
        "currency": "ZAR",
        "allocation": "50% SA fixed interest, 20% SA equity, 20% international equity, 10% cash",
        "description": (
            "Rand, income-oriented, predominantly local portfolio (Regulation 28 style) that "
            "funds a regular monthly drawdown. Suits conservative to moderately conservative "
            "investors and retirees prioritising capital preservation."
        ),
        "aliases": [
            "income", "reg 28", "reg 28 bespoke", "reg 28 bespoke model", "reg 28 etf",
            "3yg reg 28 etf", "ct coastal income", "retirement income",
        ],
    },
}

# ── Dropdown options in the proposal tool ──────────────────────────────────
HORIZONS = ["1 year+", "3 years+", "5 years+"]
RISK_CATEGORIES = [
    "Conservative",
    "Moderately Conservative",
    "Moderate",
    "Moderately Aggressive",
    "Aggressive",
]
CURRENCIES = ["ZAR", "USD", "GBP", "EUR"]
CLIENT_TYPES = ["Individual", "Trust", "Company"]
MANDATE_TYPES = ["Discretionary", "Advisory"]
GREET_TO = ["client", "advisor"]

# ── Proposal fields the assistant extracts, asks about and reviews ─────────
# kind: text | money | percent | enum | bool | prose
# ask:  order in which missing fields are asked about (None = never asked)
FIELDS = [
    {"key": "clientName", "label": "Client name", "group": "Client", "kind": "text", "ask": 1,
     "question": "Who is this proposal for? (client name as it should appear)"},
    {"key": "clientEmail", "label": "Client email", "group": "Client", "kind": "text", "ask": None},
    {"key": "clientType", "label": "Client type", "group": "Client", "kind": "enum",
     "options": CLIENT_TYPES, "ask": 9,
     "question": "Is the client an individual, a trust or a company?"},
    {"key": "introGreetTo", "label": "Address proposal to", "group": "Client", "kind": "enum",
     "options": GREET_TO, "ask": 8,
     "question": "Should the proposal be addressed to the client directly, or to their financial adviser?"},
    {"key": "financialPlanner", "label": "Client's financial adviser", "group": "Client",
     "kind": "text", "ask": None,
     "question": "What is the name of the client's financial adviser?"},
    {"key": "totalInvestment", "label": "Investment amount", "group": "Investment",
     "kind": "money", "ask": 2,
     "question": "How much is the client investing?",
     "placeholder": "e.g. R5m, 2 500 000, USD 1.2m"},
    {"key": "incomeValue", "label": "Monthly income drawdown", "group": "Investment",
     "kind": "money", "ask": 3,
     "question": "Does the client need a monthly income from the portfolio? If so, how much per month?",
     "placeholder": "e.g. R25 000, or 'none'"},
    {"key": "currency", "label": "Currency", "group": "Investment", "kind": "enum",
     "options": CURRENCIES, "ask": 7,
     "question": "Which currency is the investment in?"},
    {"key": "investmentHorizon", "label": "Investment horizon", "group": "Objective",
     "kind": "enum", "options": HORIZONS, "ask": 4,
     "question": "What is the client's investment time horizon?"},
    {"key": "riskProfileCategory", "label": "Risk level", "group": "Objective", "kind": "enum",
     "options": RISK_CATEGORIES, "ask": 5,
     "question": "Which risk level fits the client?"},
    {"key": "targetReturn", "label": "Target return", "group": "Objective", "kind": "text",
     "ask": None, "placeholder": "e.g. CPI + 5%"},
    {"key": "benchmark", "label": "Benchmark", "group": "Objective", "kind": "text", "ask": None},
    {"key": "model", "label": "Model portfolio", "group": "Portfolio", "kind": "enum",
     "options": list(MODELS.keys()), "ask": 6,
     "question": "Which model portfolio should the proposal use?"},
    {"key": "mandateType", "label": "Mandate type", "group": "Portfolio", "kind": "enum",
     "options": MANDATE_TYPES, "ask": 10,
     "question": "What type of mandate is this?"},
    {"key": "advisorFee", "label": "Adviser fee (% p.a.)", "group": "Fees & other",
     "kind": "percent", "ask": 11,
     "question": "What adviser fee applies (% per year)?", "placeholder": "e.g. 0.75"},
    {"key": "isReplacement", "label": "Replaces an existing portfolio", "group": "Fees & other",
     "kind": "bool", "ask": None},
    {"key": "replacementDetails", "label": "Replacement details", "group": "Fees & other",
     "kind": "text", "ask": None},
]

FIELD_BY_KEY = {f["key"]: f for f in FIELDS}

# AI-written prose sections, drafted after the facts are settled.
NARRATIVE_FIELDS = [
    {"key": "needs", "label": "Client needs & objectives", "group": "Narrative", "kind": "prose"},
    {"key": "riskProfile", "label": "Risk profile (prose)", "group": "Narrative", "kind": "prose"},
]

# Provenance labels shown to the PM.
SOURCES = {
    "notes": "From your notes",
    "inferred": "Inferred — please check",
    "missing": "Missing",
    "pm": "Confirmed by you",
    "to_confirm": "To confirm",
    "ai_drafted": "AI-drafted text",
}
