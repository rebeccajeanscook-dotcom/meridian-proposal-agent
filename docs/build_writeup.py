"""Builds the take-home write-up PDF (Rebecca Cook, Meridian Proposal Assistant)."""
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Flowable, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

F = "/usr/share/fonts/truetype/crosextra/"
pdfmetrics.registerFont(TTFont("Body", F + "Carlito-Regular.ttf"))
pdfmetrics.registerFont(TTFont("Body-Bold", F + "Carlito-Bold.ttf"))
pdfmetrics.registerFont(TTFont("Body-Italic", F + "Carlito-Italic.ttf"))
pdfmetrics.registerFont(TTFont("Body-BoldItalic", F + "Carlito-BoldItalic.ttf"))
pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-Bold", italic="Body-Italic",
                              boldItalic="Body-BoldItalic")

OBSIDIAN = colors.HexColor("#1b2733")
GUNMETAL = colors.HexColor("#353f41")
MUTED = colors.HexColor("#6b7275")
SEA = colors.HexColor("#24435c")
HONEY = colors.HexColor("#ddb347")
SAGE = colors.HexColor("#98a88b")
OCHRE = colors.HexColor("#aa5b3b")
IVORY = colors.HexColor("#fffcf3")
LINE = colors.HexColor("#d9dcd6")
TINT = colors.HexColor("#f4f5f2")

PM_C, AI_C, RULE_C, TOOL_C = colors.HexColor("#f6e7bd"), colors.HexColor("#d5e0ea"), \
    colors.HexColor("#e1e8da"), colors.HexColor("#e6e1e2")

body = ParagraphStyle("body", fontName="Body", fontSize=11, leading=14.5, textColor=GUNMETAL,
                      spaceAfter=5)
small = ParagraphStyle("small", parent=body, fontSize=9.5, leading=12, spaceAfter=0)
cell = ParagraphStyle("cell", parent=body, fontSize=10, leading=12.5, spaceAfter=0)
cellb = ParagraphStyle("cellb", parent=cell, fontName="Body-Bold", textColor=OBSIDIAN)
h1 = ParagraphStyle("h1", parent=body, fontName="Body-Bold", fontSize=16, leading=20,
                    textColor=OBSIDIAN, spaceBefore=10, spaceAfter=6)
h2 = ParagraphStyle("h2", parent=body, fontName="Body-Bold", fontSize=12.5, leading=16,
                    textColor=SEA, spaceBefore=6, spaceAfter=3)
bullet = ParagraphStyle("bullet", parent=body, leftIndent=12, bulletIndent=2, spaceAfter=2.5)
note = ParagraphStyle("note", parent=body, fontSize=10, leading=13, textColor=MUTED)


def P(t, s=body):
    return Paragraph(t, s)


def bullets(items, style=bullet):
    return [Paragraph(i, style, bulletText="•") for i in items]


def table(rows, widths, header=True, zebra=True):
    data = [[P(c, cellb if (header and r == 0) else cell) if isinstance(c, str) else c for c in row]
            for r, row in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    st = [("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
          ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
          ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5)]
    if header:
        st += [("BACKGROUND", (0, 0), (-1, 0), TINT), ("LINEBELOW", (0, 0), (-1, 0), 0.8, SEA)]
    t.setStyle(TableStyle(st))
    return t


# ── Stage diagram ───────────────────────────────────────────────────────────
STAGES = [
    ("PM", PM_C, "1. Capture", "The PM records a voice note, uploads one, or pastes meeting notes."),
    ("AI", AI_C, "2. Transcribe", "Speech is turned into text on the PM's own laptop (Whisper). The PM can fix any misheard words."),
    ("AI", AI_C, "3. Read the notes", "Claude fills in every proposal field and records where each value came from, with the exact quote."),
    ("RULES", RULE_C, "4. Check and tidy", "Plain code converts values into the tool's exact formats, refuses vague figures, and warns about combinations that look wrong."),
    ("PM", PM_C, "5. Fill the gaps", "For key facts that are still missing, the PM is asked one question at a time, or can mark them 'to confirm'."),
    ("PM", PM_C, "6. Review", "The PM sees every value, its source and any warnings, and can change anything."),
    ("AI", AI_C, "7. Write the wording", "Claude drafts the client-needs and risk paragraphs using only the confirmed facts. The PM can edit them."),
    ("TOOL", TOOL_C, "8. Load the proposal", "The draft opens in Meridian's existing proposal tool, unchanged, ready to finish and export."),
]
WHO = {"PM": "Portfolio Manager", "AI": "AI", "RULES": "Rules (code)", "TOOL": "Existing tool"}


class StageDiagram(Flowable):
    def __init__(self, width):
        super().__init__()
        self.width = width
        self.box_h, self.gap = 13.5 * mm, 4.2 * mm
        self.height = len(STAGES) * (self.box_h + self.gap) + 12 * mm

    def draw(self):
        c = self.canv
        # legend
        x = 0
        for key, col in (("PM", PM_C), ("AI", AI_C), ("RULES", RULE_C), ("TOOL", TOOL_C)):
            c.setFillColor(col); c.setStrokeColor(LINE)
            c.roundRect(x, self.height - 6 * mm, 4.5 * mm, 4.5 * mm, 1, fill=1, stroke=1)
            c.setFillColor(GUNMETAL); c.setFont("Body", 9.5)
            c.drawString(x + 6.5 * mm, self.height - 4.9 * mm, WHO[key])
            x += 6.5 * mm + c.stringWidth(WHO[key], "Body", 9.5) + 8 * mm
        y = self.height - 12 * mm
        label_w = 45 * mm
        for i, (who, col, title, text) in enumerate(STAGES):
            y -= self.box_h
            c.setFillColor(col); c.setStrokeColor(colors.white)
            c.roundRect(0, y, self.width, self.box_h, 3, fill=1, stroke=0)
            c.setFillColor(OBSIDIAN); c.setFont("Body-Bold", 11)
            c.drawString(4 * mm, y + self.box_h - 5.6 * mm, title)
            c.setFillColor(MUTED); c.setFont("Body", 8.5)
            c.drawString(4 * mm, y + 2.8 * mm, WHO[who])
            p = Paragraph(text, ParagraphStyle("d", parent=small, fontSize=10, leading=12.2))
            w, h = p.wrap(self.width - label_w - 6 * mm, self.box_h)
            p.drawOn(c, label_w, y + (self.box_h - h) / 2)
            if i < len(STAGES) - 1:
                cx = 20 * mm
                c.setStrokeColor(SEA); c.setFillColor(SEA); c.setLineWidth(1.2)
                c.line(cx, y - 0.6 * mm, cx, y - self.gap + 1.6 * mm)
                pth = c.beginPath()
                pth.moveTo(cx - 1.5 * mm, y - self.gap + 2 * mm)
                pth.lineTo(cx + 1.5 * mm, y - self.gap + 2 * mm)
                pth.lineTo(cx, y - self.gap + 0.4 * mm)
                pth.close()
                c.drawPath(pth, fill=1, stroke=0)
            y -= self.gap


# ── Page furniture ──────────────────────────────────────────────────────────
def cover(c, doc):
    w, h = A4
    c.setFillColor(OBSIDIAN); c.rect(0, h - 105 * mm, w, 105 * mm, fill=1, stroke=0)
    c.setFillColor(HONEY); c.rect(25 * mm, h - 107 * mm, 40 * mm, 2 * mm, fill=1, stroke=0)
    c.setFillColor(HONEY); c.setFont("Body-Bold", 10.5)
    c.drawString(25 * mm, h - 40 * mm, "OLD MUTUAL  ·  JUNIOR AI ENGINEER TAKE-HOME")
    c.setFillColor(IVORY); c.setFont("Body-Bold", 30)
    c.drawString(25 * mm, h - 58 * mm, "Meridian Proposal Assistant")
    c.setFont("Body", 15)
    c.drawString(25 * mm, h - 69 * mm, "From meeting notes and voice notes to a draft proposal")
    c.setFillColor(OBSIDIAN); c.setFont("Body-Bold", 18)
    c.drawString(25 * mm, h - 130 * mm, "Rebecca Cook")
    c.setFillColor(MUTED); c.setFont("Body", 12)
    c.drawString(25 * mm, h - 138 * mm, "Write-up: design, assumptions and next steps")
    c.drawString(25 * mm, h - 145 * mm, "24 November 2026")


def later(c, doc):
    w, h = A4
    c.setStrokeColor(LINE); c.setLineWidth(0.5)
    c.line(20 * mm, 14 * mm, w - 20 * mm, 14 * mm)
    c.setFillColor(MUTED); c.setFont("Body", 8.5)
    c.drawString(20 * mm, 9.5 * mm, "Meridian Proposal Assistant  ·  Rebecca Cook")
    c.drawRightString(w - 20 * mm, 9.5 * mm, str(doc.page))


# ── Content ─────────────────────────────────────────────────────────────────
def build(path):
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=20 * mm,
                            title="Meridian Proposal Assistant: write-up", author="Rebecca Cook")
    W = A4[0] - 40 * mm
    s = []

    # Cover page: summary box under the header
    s.append(Spacer(1, 140 * mm))
    summary = Table([[P(
        "<b>In short.</b> Portfolio Managers lose time typing meeting notes into the proposal tool. "
        "I built the <b>pre-processing stages that feed into the existing proposal tool</b>: a PM "
        "speaks or pastes their notes, the assistant turns them into a draft proposal, asks only about "
        "what is missing, shows where every value came from, and loads the result into the tool for "
        "the PM to finish. The PM stays in control at every step, and the tool itself is unchanged.",
        ParagraphStyle("s", parent=body, fontSize=11.5, leading=15.5))]], colWidths=[W - 10 * mm])
    summary.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), IVORY),
                                 ("LINEBEFORE", (0, 0), (0, -1), 3, HONEY),
                                 ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                                 ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))
    s.append(summary)
    s.append(Spacer(1, 8 * mm))
    s.append(P("<b>What is included in the submission</b>", h2))
    s += bullets([
        "A working app (code and README) that runs on a laptop and opens the proposal tool with the draft loaded.",
        "Automated tests for the rules, and an evaluation on 12 example notes to measure accuracy.",
        "This write-up: how it works, why I used AI where I did, the assumptions to confirm, and next steps.",
    ])
    s.append(PageBreak())

    # 1. What I built
    s.append(P("1. What I built and how it works", h1))
    s.append(P(
        "I focused on the part of the process that costs PMs the most time: getting from a meeting to "
        "a first draft. The assistant sits <b>in front of</b> Meridian's proposal tool, does the "
        "preparation work, and hands over a finished draft through the tool's own loading function. "
        "Nothing inside the tool was changed, so it can be adopted without touching the existing system."))
    s.append(P("The draft moves through eight simple stages. Each one is done by the PM, by AI, or "
               "by plain rules written in code:"))
    s.append(Spacer(1, 2 * mm))
    s.append(StageDiagram(W))
    s.append(P("The colours show a deliberate split of work: <b>AI reads and writes</b>, <b>rules check</b>, "
               "and <b>the PM decides</b>.", note))

    # 2. Why an LLM
    s.append(KeepTogether([P("2. Why I used a large language model (LLM)", h1),
                           P("PM notes are written for the PM, not for a computer. The same fact arrives in many forms:"),
                           table([
        ["What the PM wrote or said", "What the tool needs"],
        ["“lump sum of about R6.2 million”, “call it four and a half million”", "6200000 / 4500000"],
        ["“Reg 28 bespoke model”, “flexible bespoke portfolio”", "Income model / Balanced model"],
        ["“moderate to aggressive”, “not a gambler but wants growth”", "Moderately Aggressive / a suggested level to check"],
        ["“two million, no sorry, two point five”", "2500000 (the corrected figure)"],
    ], [W * 0.62, W * 0.38])]))
    s.append(Spacer(1, 3 * mm))
    s += bullets([
        "<b>A fixed form or keyword search breaks on this variety.</b> It would need a rule for every way "
        "of saying every thing, and would still fail on voice notes full of “um” and self-corrections.",
        "<b>An LLM reads notes the way a colleague would.</b> It understands context, shorthand and "
        "corrections, and can quote the exact words it relied on, so the PM can check it.",
        "<b>But I did not let the AI have the final say.</b> It is used only for reading and writing. "
        "Plain code then checks every value, never accepts a vague figure, and flags risky combinations. "
        "The PM confirms anything uncertain before the draft is used.",
        "<b>The model is forced to answer in a fixed structure</b> (a set list of fields), so the app never "
        "has to guess how to read the AI's reply.",
    ])

    # 3. Safeguards
    s.append(P("3. How the PM stays in control", h1))
    s.append(P("Because this is financial advice, I treated trust as the main design goal:"))
    s += bullets([
        "<b>Every value shows its source</b>: <i>from your notes</i> (with the quote), <i>inferred, please "
        "check</i> (with the reason), <i>confirmed by you</i>, or <i>to confirm</i>.",
        "<b>No invented numbers.</b> Amounts, income and fees are only used if the notes state them. "
        "In testing, the AI invented 0 values across all the “trap” cases designed to tempt it.",
        "<b>Missing facts become questions</b>, asked one at a time, or are marked "
        "[TO CONFIRM] in the proposal so nothing goes out silently incomplete.",
        "<b>Consistency checks</b> written in code warn about combinations that are valid but probably "
        "wrong (see section 5), the kind of thing a senior PM would catch.",
        "<b>Nothing is loaded until the PM clicks</b>, and everything stays editable in the tool afterwards.",
        "<b>Voice stays private</b>: recordings are transcribed on the laptop and never leave it.",
    ])

    # 4. Testing and model choice
    s.append(P("4. Testing and choice of AI model", h1))
    s.append(P(
        "I tested 3 Claude models on the 4 example notes plus 8 harder ones I wrote (annual income, "
        "self-corrections, US dollars, notes with no numbers, shorthand, an unknown fund, pounds), "
        "checking every field against the expected answer:"))
    s.append(KeepTogether([table([
        ["Model", "Fields correct", "Invented values", "Time per draft", "Cost per draft*"],
        ["Claude Haiku 5.5 (chosen)", "107 / 107 (100%)", "0", "~6 seconds", "~$0.001"],
        ["Claude Sonnet 5.5 (3 runs)", "318 / 321 (99%)", "0", "~11 seconds", "~$0.015"],
        ["Claude Opus 5.5", "107 / 107 (100%)", "0", "~12 seconds", "~$0.037"],
    ], [W * 0.29, W * 0.2, W * 0.16, W * 0.17, W * 0.18]), P("*Reading step only, at list prices per million tokens of $0.10/$0.50 (Haiku), $2/$10 (Sonnet) "
               "and $4/$20 (Opus) for input/output, with about 2,500 tokens in and 1,000–1,400 out per draft.",
               note)]))
    s += bullets([
        "<b>Choice: Haiku.</b> It matched the most expensive model on accuracy, was about twice as fast as "
        "Sonnet, and costs roughly a tenth of a US cent per draft. Even at thousands of proposals a month the "
        "AI cost is negligible next to the PM time saved.",
        "<b>Sonnet's three misses</b> were all on one note: it treated “about R6.2 million” as too vague and "
        "left it blank. Cautious rather than wrong-and-confident, but still a miss; I clarified the "
        "instructions so approximate-but-specific amounts count as stated.",
        "<b>Caveat:</b> 12 notes is a small test set, and Haiku and Opus were run once each. Before any real "
        "use I would test on a much larger set of real (anonymised) notes, repeat runs to check consistency, "
        "and compare models from other providers as well.",
    ])

    # 5. Assumptions
    s.append(P("5. Assumptions for Old Mutual to confirm", h1))
    s.append(P("I had no contact person for questions, so I made these assumptions and built them into the "
               "tool. Each one is easy to change."))
    s.append(P("Reading the notes", h2))
    s.append(table([
        ["Assumption", "What the assistant does"],
        ["Who the proposal is addressed to", "The client, unless the notes mention their financial adviser."],
        ["Approximate vs vague amounts", "“About R6.2m” is used (and flagged); “a few million” is never turned into a number."],
        ["Income stated per year", "Divided by 12 to give the monthly income the tool expects."],
        ["“No income needed”", "Left out of the proposal rather than shown as R0."],
        ["Horizons longer than 5 years", "Shown as “5 years+”, the highest option in the tool."],
        ["Currency not stated", "Taken from the chosen model portfolio (and labelled as inferred)."],
        ["Replacement not mentioned", "Assumed not to replace an existing portfolio (labelled as inferred)."],
        ["Titles (Mr / Mrs / Dr)", "Only used if the notes use one."],
        ["Joint clients", "The proposal goes under the person the PM names; the partner is mentioned in the text."],
    ], [W * 0.34, W * 0.66]))
    s.append(P("Model portfolios", h2))
    s.append(table([
        ["Assumption", "What the assistant does"],
        ["PM nicknames for portfolios", "“Flexible bespoke” = Balanced, “Reg 28” = Income, “global equity” = Global Growth."],
        ["A fund name that matches none of the three", "Never forced onto a model; the PM is asked instead."],
        ["Which risk levels suit which model", "Income: Conservative to Moderate. Balanced: Moderately Conservative to Moderately Aggressive. Global Growth: Moderately Aggressive and Aggressive."],
    ], [W * 0.34, W * 0.66]))
    s.append(P("Warning thresholds (for the investment committee to set)", h2))
    s.append(table([
        ["Check", "Threshold I assumed"],
        ["Income drawdown too high", "Note above 5% of capital per year; warning above 8%."],
        ["Adviser fee unusually high", "Above 1.5% per year."],
        ["Amount looks like a typo", "Below R100 000 or above R1 billion."],
        ["Other warnings (no threshold)", "Currency differs from the model's currency; income needed on a pure-growth model; "
                                          "a 1-year horizon with an aggressive risk level; a replacement with no details."],
    ], [W * 0.34, W * 0.66]))

    # 6. Limitations
    s.append(P("6. Limitations", h1))
    s += bullets([
        "Runs on one laptop for one user; it is not hosted, so a PM cannot yet use it from their phone in the car.",
        "Nothing is saved between sessions, and each “load” creates a new draft in the tool rather than updating the last one.",
        "English notes only. Speech recognition can mishear names and figures, which is why the PM checks the transcript first.",
        "One proposal per meeting; the tool's three model portfolios are the only ones it knows.",
        "Tested on 12 fictional notes, which is enough to show the approach works, not enough to prove it at scale.",
    ])

    # 7. With more time
    s.append(P("7. What I would add with more time: an AI agent", h1))
    s.append(P(
        "Because of the time available, I chose not to build a conversational AI agent. I would add one next. "
        "It would sit beside the review table (stage 6) as a chat box the PM can type or talk to."))
    s += bullets([
        "<b>What it would do:</b> take corrections in plain language, such as “make it R4.5m, she wants R30k a "
        "month, and switch her to moderate”, and update several fields at once. It could also explain any value "
        "(“why did you pick Balanced?”) and describe or compare the model portfolios.",
        "<b>How it would stay safe:</b> the agent could only change the draft through the same checked actions a PM "
        "uses by hand. Every change would appear in the table marked as made through chat, and the "
        "consistency checks would still run. It could never load or send a proposal on its own.",
        "<b>Value:</b> hands-free corrections for PMs on the move, fewer clicks, and a natural next step towards "
        "the brief's idea of a PM simply talking the proposal into existence.",
        "<b>Cost:</b> roughly 7,000 tokens per PM message, about $0.001 per message on Haiku. Further out, an agent "
        "could also suggest a model from the risk profile, but that starts to become advice and would need "
        "compliance sign-off first.",
    ])

    # 8. Production + questions
    s.append(P("8. Before real use, and questions for Old Mutual", h1))
    s += bullets([
        "<b>Client data and the AI provider.</b> Client notes are personal information under POPIA. Which AI "
        "providers are approved, and should calls go through Old Mutual's own cloud account (for example AWS, "
        "Azure or Google) so data stays in a contracted environment?",
        "<b>API keys.</b> In this demo the key sits in a local file. In production it would be an "
        "organisation-owned key held in a secrets manager, with spending limits, usage monitoring and an "
        "audit log of every request.",
        "<b>Hosting and sign-in.</b> Where should the assistant run, and should PMs sign in with their "
        "company accounts? This is also what would make mobile use possible.",
        "<b>Rules and thresholds.</b> Who should own and approve the assumptions in section 5?",
        "<b>The proposal tool.</b> A small change in the tool, letting a loaded draft replace the "
        "previous one, would avoid duplicate drafts.",
    ])
    s.append(Spacer(1, 3 * mm))
    s.append(P("All client names and figures used in development and testing are fictional.", note))

    doc.build(s, onFirstPage=cover, onLaterPages=later)


if __name__ == "__main__":
    build("/home/claude/writeup/Meridian_Proposal_Assistant_Writeup_Rebecca_Cook.pdf")
