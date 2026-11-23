"""Evaluate the extraction pipeline against expected outputs.

    python -m eval.run_eval                                   # default model, all cases
    python -m eval.run_eval --models claude-haiku-5-5,claude-sonnet-5-5,claude-opus-5-5
    python -m eval.run_eval --runs 3                          # repeat to check consistency
    python -m eval.run_eval --set samples                     # only the 4 challenge samples
    python -m eval.run_eval --verbose                         # print every field

Test cases come from two places, both as  NN-name.txt  +  NN-expected.json :
  - the challenge pack's sample-inputs/  (the 4 given examples)
  - eval/cases/                          (our own edge cases; add more here)

Scoring (structured fields only; prose isn't scored):
  - every field present in the expected JSON must match exactly        -> "field accuracy"
  - every path in "_mustBeMissing" must be absent from the output       -> "invented values"
    (catches the model making up an amount, fee, horizon, model, etc.)
Follow-up questions are all skipped (TO CONFIRM), so this measures the notes alone.

Results are saved to eval/results.csv (one row per case/field/run) for the write-up.
"""
import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from backend import draft, llm  # noqa: E402

CHALLENGE_DIR = Path(os.getenv("CHALLENGE_DIR", ROOT.parent / "meridian-ai-challenge 2"))
SOURCES = {"samples": CHALLENGE_DIR / "sample-inputs", "cases": ROOT / "eval" / "cases"}
OUT = ROOT / "eval" / "outputs"

SCORED = [
    "clientName", "introGreetTo", "financialPlanner", "applyModel",
    "goalAssessment.clientType", "goalAssessment.mandateType", "goalAssessment.currency",
    "strategy.keyFigures.totalInvestment", "strategy.keyFigures.incomeValue",
    "objective.riskProfileCategory", "objective.investmentHorizon", "objective.targetReturn",
    "fees.advisorFee", "replacements.isReplacement",
]


def get(d, path):
    for part in path.split("."):
        if not isinstance(d, dict) or part not in d:
            return None
        d = d[part]
    return d


def load_cases(which):
    cases = []
    for name, folder in SOURCES.items():
        if which not in ("all", name) or not folder.exists():
            continue
        for notes in sorted(folder.glob("*.txt")):
            cid = notes.name.split("-")[0]
            exp = folder / f"{cid}-expected.json"
            if exp.exists():
                cases.append({"id": notes.stem, "notes": notes.read_text(),
                              "expected": json.loads(exp.read_text())})
    return cases


def run_case(case):
    """Run extraction for one case. Returns (proposal, fields, flags, usage)."""
    fields, flags = draft.clean_extraction(llm.extract_facts(case["notes"]))
    for key in draft.pending_questions(fields):
        draft.apply_answer(fields, key, None, skip=True)
    return draft.build_proposal(fields), fields, flags, dict(llm.last_usage)


def score(case, proposal):
    rows = []
    exp = case["expected"]
    for path in SCORED:
        e, g = get(exp, path), get(proposal, path)
        if e is None:
            continue
        rows.append({"check": "match", "field": path, "expected": e, "got": g,
                     "ok": str(e).strip().lower() == str(g).strip().lower()})
    for path in exp.get("_mustBeMissing", []):
        g = get(proposal, path)
        rows.append({"check": "must_be_missing", "field": path, "expected": None, "got": g,
                     "ok": g is None})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=llm.MODEL, help="comma-separated model IDs")
    ap.add_argument("--runs", type=int, default=1, help="repeat each case N times")
    ap.add_argument("--set", default="all", choices=["all", "samples", "cases"])
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    cases = load_cases(args.set)
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"{len(cases)} cases × {len(models)} model(s) × {args.runs} run(s)\n")

    all_rows, summary = [], []
    for model in models:
        llm.MODEL = model
        stats = {"match": [0, 0], "must_be_missing": [0, 0], "seconds": [], "in": 0, "out": 0, "errors": 0}
        print(f"══ {model}")
        for case in cases:
            for run in range(1, args.runs + 1):
                try:
                    proposal, fields, flags, usage = run_case(case)
                except Exception as e:  # noqa: BLE001
                    stats["errors"] += 1
                    print(f"  ✗ {case['id']} (run {run}): ERROR {e}")
                    continue
                stats["seconds"].append(usage.get("seconds", 0))
                stats["in"] += usage.get("input_tokens", 0)
                stats["out"] += usage.get("output_tokens", 0)
                (OUT / f"{model}__{case['id']}__run{run}.json").write_text(json.dumps(
                    {"proposal": proposal, "fields": fields, "flags": flags, "usage": usage}, indent=2))

                rows = score(case, proposal)
                misses = [r for r in rows if not r["ok"]]
                for r in rows:
                    stats[r["check"]][0] += r["ok"]
                    stats[r["check"]][1] += 1
                    all_rows.append({"model": model, "case": case["id"], "run": run, **r})
                mark = "✓" if not misses else "✗"
                print(f"  {mark} {case['id']:34} {len(rows) - len(misses)}/{len(rows)}  ({usage.get('seconds', '?')}s)")
                for r in (rows if args.verbose else misses):
                    label = "should be empty" if r["check"] == "must_be_missing" else f"expected {r['expected']!r}"
                    print(f"      {'·' if r['ok'] else '✗'} {r['field']:38} {label:34} got {r['got']!r}")

        m, mm = stats["match"], stats["must_be_missing"]
        n = len(stats["seconds"]) or 1
        summary.append([model, f"{m[0]}/{m[1]} ({100 * m[0] / max(m[1], 1):.0f}%)",
                        f"{mm[1] - mm[0]} of {mm[1]}", f"{sum(stats['seconds']) / n:.1f}s",
                        f"{stats['in'] // n} / {stats['out'] // n}", stats["errors"]])
        print()

    header = ["model", "field accuracy", "invented values", "avg time", "avg tokens in/out", "errors"]
    widths = [max(len(str(r[i])) for r in summary + [header]) for i in range(len(header))]
    print("SUMMARY")
    for r in [header] + summary:
        print("  " + "  ".join(str(c).ljust(w) for c, w in zip(r, widths)))

    with open(ROOT / "eval" / "results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["model", "case", "run", "check", "field", "expected", "got", "ok"])
        w.writeheader()
        w.writerows(all_rows)
    print(f"\nDetailed results: eval/results.csv   Raw outputs: eval/outputs/")


if __name__ == "__main__":
    t = time.time()
    main()
    print(f"Total time: {time.time() - t:.0f}s")
