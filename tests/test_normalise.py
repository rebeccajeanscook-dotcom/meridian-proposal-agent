"""Unit tests for the deterministic rules (no API key needed)."""
import pytest

from backend.normalise import (
    parse_client_type, parse_currency, parse_greet_to, parse_horizon, parse_model,
    parse_money, parse_percent, parse_risk,
)


@pytest.mark.parametrize("raw, expected", [
    ("R6.2 million", "6200000"),
    ("about R6.2m", "6200000"),
    ("USD 1.2m", "1200000"),
    ("R28,000", "28000"),
    ("R28 000 a month", "28000"),
    ("28k", "28000"),
    ("four and a half million rand", "4500000"),
    ("4.5 million", "4500000"),
    (8500000, "8500000"),
    ("none", "0"),
    ("no income needed", "0"),
    ("a few million", None),
    ("", None),
    (None, None),
])
def test_money(raw, expected):
    assert parse_money(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("0.60%", "0.60"), ("0.5", "0.50"), ("75bps", "0.75"), ("60 basis points", "0.60"), ("zero point seven five", "0.75"),
    ("75", None), ("abc", None),
])
def test_percent(raw, expected):
    assert parse_percent(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("15+ years", "5 years+"), ("10 years plus", "5 years+"), ("ten years", "5 years+"),
    ("3-4 years", "3 years+"), ("18 months", "1 year+"), ("5 years+", "5 years+"),
    ("long term", None), ("6 months", None),
])
def test_horizon(raw, expected):
    assert parse_horizon(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("moderate to aggressive", "Moderately Aggressive"),
    ("conservative to moderate", "Moderately Conservative"),
    ("Aggressive", "Aggressive"),
    ("risk-averse", "Conservative"),
    ("balanced", "Moderate"),
    ("wants growth", None),
])
def test_risk(raw, expected):
    assert parse_risk(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("Reg 28 bespoke model", "income"),
    ("the global equity model", "global-growth"),
    ("flexible bespoke portfolio", "balanced"),
    ("global-growth", "global-growth"),
    ("income", "income"),
    ("something new", None),
])
def test_model(raw, expected):
    assert parse_model(raw) == expected


def test_misc_enums():
    assert parse_currency("rand") == "ZAR"
    assert parse_currency("usd") == "USD"
    assert parse_client_type("The Sithole Family Trust") == "Trust"
    assert parse_client_type("joint, under Johannes") == "Individual"
    assert parse_greet_to("their financial advisor") == "advisor"
    assert parse_greet_to("client") == "client"
