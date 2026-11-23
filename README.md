# Meridian Proposal Assistant

Turns a Portfolio Manager's meeting notes or voice note into a draft investment proposal in
Meridian's existing proposal tool. The PM confirms anything missing and reviews every value first.

```
notes / voice note
   │  Whisper (local speech-to-text, audio never leaves the machine)
   ▼
Claude: extract every field + where it came from (structured JSON output)
   ▼
Python rules: convert to the tool's exact formats, reject vague values ("a few million")
   ▼
Follow-up questions, one at a time, for key fields still missing (or mark TO CONFIRM)
   ▼
Review table + consistency checks (rule-based warnings)   ◄── PM edits anything
   ▼
Claude: write the prose sections from the confirmed facts only
   ▼
window.loadProposal(...) in the unchanged proposal tool
```

The proposal tool (`challenge-generator.html`) is used **unchanged**. The app serves it at `/tool` and
fills it through its own `loadProposal` entry point.

**Write-up:** a separate PDF (*Meridian_Proposal_Assistant_Writeup_Rebecca_Cook.pdf*), submitted alongside
this code, covers the design, why an LLM was used, testing and model choice, the assumptions to confirm,
limitations and next steps.

## Run it

You need Python 3.10 or newer (built and tested on 3.13) and an Anthropic API key.

```bash
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # then paste your ANTHROPIC_API_KEY into .env
uvicorn backend.main:app --reload
```

Then open **http://localhost:8000**.

- **Challenge pack location:** the app expects the challenge pack in a sibling folder called
  `meridian-ai-challenge 2/`. The submitted zip already has this layout, so unzip and run from
  `meridian-proposal-agent/`. If the pack is elsewhere, set `CHALLENGE_DIR` in `.env`.
- **Workspace ID:** if your key isn't tied to one workspace, the API asks for an
  `anthropic-workspace-id`. Set `ANTHROPIC_WORKSPACE_ID` in `.env`.
- **Model:** the default is `claude-haiku-5-5`, chosen from the evaluation below. Set `CLAUDE_MODEL`
  to change it.
- **Voice:** the first transcription downloads the Whisper speech model (~460 MB for `small`).
  After that it works offline.

## Using it

The page shows the pipeline as six numbered stages, top to bottom:

1. **Input.** Paste notes, load a sample, **record** a voice note in the browser, or **upload** an
   audio file (m4a, mp3, wav, webm). Check the transcript, then *Run extraction*.
2. **Claude extraction (raw).** The exact JSON Claude returned, plus flags for the PM.
3. **Follow-up questions.** Key fields that are still missing are asked one at a time. Each can be
   marked *TO CONFIRM*.
4. **Fields after rules & review.** For every field you see what Claude returned, the value the tool
   will get, its source (*from notes / inferred / confirmed by you / to confirm*), and the supporting
   quote or reason. Consistency warnings appear above the table. Any value can be edited.
5. **Proposal text.** The *needs* and *risk profile* paragraphs are AI-drafted and editable.
6. **Output.** The exact object passed to `window.loadProposal()`.
   *Open in proposal tool* loads it in a new tab.

## Consistency checks

These are plain code, not AI. They only warn; they never change the draft:

- the currency doesn't match the model portfolio's currency
- the risk level is outside the range the model is designed for
- the income drawdown is above 5% (note) or 8% (warning) of capital per year
- income is needed but the model is pure growth
- a short horizon is combined with an aggressive risk level
- the proposal is a replacement but has no replacement details
- an amount or fee looks like a typo

## Tests and evaluation

```bash
pytest -q                                   # rules, draft logic, checks (no API key needed)
python -m eval.run_eval                     # 12 cases on the default model
python -m eval.run_eval --models claude-haiku-5-5,claude-sonnet-5-5,claude-opus-5-5 --runs 3
```

Cases come from the challenge pack's `sample-inputs/` (4) and `eval/cases/` (8 edge cases:
- annual income
- self-corrections
- company/USD client addressed to an adviser
- a hallucination trap
- shorthand and basis-point fees
- an unknown portfolio name
- a GBP client
- terse notes

The eval scores each structured field against the expected output, and counts
**invented values**: fields that must stay empty because the notes don't contain them.
Results go to `eval/results.csv` and `eval/outputs/`.

## Project layout

```
backend/
  main.py        FastAPI app: serves the UI, the unchanged tool (/tool) and the API
  llm.py         Claude calls: structured extraction + proposal text
  catalog.py     model portfolios, PM nicknames, dropdown options, field definitions
  normalise.py   rules: "R6.2m" -> "6200000", "15+ years" -> "5 years+", "Reg 28 bespoke" -> income
  draft.py       provenance, follow-up questions, building the loadProposal() object
  checks.py      rule-based consistency warnings
  transcribe.py  local Whisper speech-to-text
frontend/        plain HTML/CSS/JS
tests/           pytest unit tests
eval/            evaluation script and test cases
```

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/transcribe` | audio file → transcript |
| POST | `/api/extract` | notes → fields with provenance, checks and first question |
| POST | `/api/answer` | answer, skip or edit a field → updated fields, checks and next question |
| POST | `/api/narrative` | fields + notes → AI-drafted *needs* and *risk profile* |
| POST | `/api/proposal` | fields + text → the object for `window.loadProposal()` + checks |

All client data in this project is fictional.
