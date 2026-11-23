"""FastAPI app: serves the assistant UI, the unchanged proposal tool, and the API.

Run from the project folder:  uvicorn backend.main:app --reload
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

from . import draft, llm, transcribe  # noqa: E402  (after .env is loaded)
from .checks import run_checks  # noqa: E402
from .catalog import FIELDS, MODELS, NARRATIVE_FIELDS, SOURCES  # noqa: E402

CHALLENGE_DIR = Path(os.getenv("CHALLENGE_DIR", ROOT.parent / "meridian-ai-challenge 2")).resolve()
TOOL_HTML = CHALLENGE_DIR / "challenge-generator.html"
SAMPLES_DIR = CHALLENGE_DIR / "sample-inputs"

app = FastAPI(title="Meridian Proposal Assistant")


# ── Pages ──────────────────────────────────────────────────────────────────

@app.get("/")
def index():
    return FileResponse(ROOT / "frontend" / "index.html")


@app.get("/tool")
def tool():
    """The proposal tool, served unchanged from the challenge pack (same origin as the UI,
    so the UI can call window.loadProposal inside its iframe)."""
    if not TOOL_HTML.exists():
        raise HTTPException(404, f"Proposal tool not found at {TOOL_HTML}. Set CHALLENGE_DIR in .env.")
    return FileResponse(TOOL_HTML)


app.mount("/static", StaticFiles(directory=ROOT / "frontend"), name="static")


# ── API ────────────────────────────────────────────────────────────────────

class NotesIn(BaseModel):
    notes: str


class AnswerIn(BaseModel):
    fields: dict
    key: str
    answer: str | bool | None = None
    skip: bool = False


class DraftIn(BaseModel):
    fields: dict
    notes: str = ""
    narrative: dict | None = None


@app.get("/api/health")
def health():
    return {"claude": bool(os.getenv("ANTHROPIC_API_KEY")), "model": llm.MODEL,
            "workspace": bool(os.getenv("ANTHROPIC_WORKSPACE_ID")),
            "whisper": transcribe.available(), "tool": TOOL_HTML.exists()}


@app.get("/api/schema")
def schema():
    return {"fields": FIELDS, "narrativeFields": NARRATIVE_FIELDS, "sources": SOURCES,
            "models": {k: {"portfolioName": v["portfolioName"], "currency": v["currency"]}
                       for k, v in MODELS.items()}}


@app.get("/api/samples")
def samples():
    if not SAMPLES_DIR.exists():
        return []
    return [{"id": p.stem, "name": p.stem.split("-", 1)[1].replace("-", " ").replace("notes ", "").capitalize(),
             "text": p.read_text(encoding="utf-8")}
            for p in sorted(SAMPLES_DIR.glob("*.txt"))]


@app.post("/api/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    if not transcribe.available():
        raise HTTPException(501, "Voice transcription isn't installed. Run: pip install faster-whisper")
    data = await file.read()
    if not data:
        raise HTTPException(400, "The audio file is empty.")
    try:
        return {"text": transcribe.transcribe(data, file.filename)}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"Couldn't transcribe that file: {e}")


def _with_next(fields, extra=None):
    question, remaining = draft.next_question(fields)
    return {"fields": fields, "question": question, "remaining": remaining,
            "toConfirm": draft.to_confirm_list(fields), "checks": run_checks(fields),
            **(extra or {})}


@app.post("/api/extract")
def extract(body: NotesIn):
    if not body.notes.strip():
        raise HTTPException(400, "Add some notes first.")
    try:
        raw = llm.extract_facts(body.notes)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Claude call failed: {e}")
    fields, flags = draft.clean_extraction(raw)
    return _with_next(fields, {"flags": flags, "raw": raw})


@app.post("/api/answer")
def answer(body: AnswerIn):
    fields, error = draft.apply_answer(body.fields, body.key, body.answer, body.skip)
    return _with_next(fields, {"error": error})


@app.post("/api/narrative")
def narrative(body: DraftIn):
    try:
        text = llm.write_narrative(body.notes, draft.facts_for_narrative(body.fields))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Claude call failed: {e}")
    return {"narrative": text, "toConfirm": draft.to_confirm_list(body.fields)}


@app.post("/api/proposal")
def proposal(body: DraftIn):
    return {"proposal": draft.build_proposal(body.fields, body.narrative),
            "checks": run_checks(body.fields)}
