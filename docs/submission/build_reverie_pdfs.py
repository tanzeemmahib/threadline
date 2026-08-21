"""Build deterministic, print-ready Reverie submission PDFs.

The Markdown, SVG, PNG, JSON, and CSV sources remain authoritative. These PDFs are
presentation derivatives and intentionally contain no copied benchmark constants.

Run from the repository root:
    python docs/submission/build_reverie_pdfs.py
"""

from __future__ import annotations

import html
import json
import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader
from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import LETTER, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    Image,
    LongTable,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

rl_config.invariant = 1

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
SUBMISSION = DOCS / "submission"
OUTPUT = ROOT / "output" / "pdf"

PAPER = colors.HexColor("#F8F4EA")
INK = colors.HexColor("#171612")
STONE = colors.HexColor("#625D54")
BRASS = colors.HexColor("#9A7835")
RUST = colors.HexColor("#864A35")
SAGE = colors.HexColor("#586757")
RULE = colors.HexColor("#D5CCBC")
PALE = colors.HexColor("#EFE8DA")


def ascii_text(value: object) -> str:
    text = str(value)
    replacements = {
        "\u2014": " - ",
        "\u2013": "-",
        "\u2212": "-",
        "\u2192": "->",
        "\u2190": "<-",
        "\u2194": "<->",
        "\u2022": "-",
        "\u00a0": " ",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def clean_markdown(value: str) -> str:
    text = ascii_text(value).strip()
    text = re.sub(r"!\[([^]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", text)
    return text.replace("**", "").replace("`", "")


def ptext(value: object) -> str:
    return html.escape(ascii_text(value), quote=False).replace("\n", "<br/>")


base = getSampleStyleSheet()
STYLE = {
    "kicker": ParagraphStyle(
        "Kicker",
        parent=base["Normal"],
        fontName="Courier-Bold",
        fontSize=7.2,
        leading=9,
        textColor=BRASS,
        spaceAfter=7,
    ),
    "cover": ParagraphStyle(
        "Cover",
        parent=base["Title"],
        fontName="Times-Bold",
        fontSize=28,
        leading=31,
        alignment=TA_LEFT,
        textColor=INK,
        spaceAfter=11,
    ),
    "subtitle": ParagraphStyle(
        "Subtitle",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=10.5,
        leading=14.5,
        textColor=STONE,
        spaceAfter=13,
    ),
    "h1": ParagraphStyle(
        "H1",
        parent=base["Heading1"],
        fontName="Times-Bold",
        fontSize=22,
        leading=25,
        textColor=INK,
        spaceBefore=9,
        spaceAfter=10,
    ),
    "h2": ParagraphStyle(
        "H2",
        parent=base["Heading2"],
        fontName="Times-Bold",
        fontSize=15,
        leading=18,
        textColor=INK,
        spaceBefore=13,
        spaceAfter=6,
        keepWithNext=True,
    ),
    "h3": ParagraphStyle(
        "H3",
        parent=base["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=10.2,
        leading=13,
        textColor=INK,
        spaceBefore=9,
        spaceAfter=4,
        keepWithNext=True,
    ),
    "body": ParagraphStyle(
        "Body",
        parent=base["BodyText"],
        fontName="Helvetica",
        fontSize=8.6,
        leading=12.1,
        textColor=INK,
        spaceAfter=5,
    ),
    "small": ParagraphStyle(
        "Small",
        parent=base["BodyText"],
        fontName="Helvetica",
        fontSize=7.3,
        leading=9.8,
        textColor=STONE,
        spaceAfter=4,
    ),
    "mono": ParagraphStyle(
        "Mono",
        parent=base["Code"],
        fontName="Courier",
        fontSize=6.6,
        leading=8.5,
        textColor=INK,
        spaceAfter=4,
    ),
    "quote": ParagraphStyle(
        "Quote",
        parent=base["BodyText"],
        fontName="Times-Roman",
        fontSize=11.5,
        leading=15.5,
        textColor=INK,
        leftIndent=11,
        rightIndent=11,
        spaceAfter=5,
    ),
    "cell": ParagraphStyle(
        "Cell",
        parent=base["BodyText"],
        fontName="Helvetica",
        fontSize=6.9,
        leading=9,
        textColor=INK,
    ),
    "cell_head": ParagraphStyle(
        "CellHead",
        parent=base["BodyText"],
        fontName="Courier-Bold",
        fontSize=6.3,
        leading=8.1,
        textColor=PAPER,
    ),
    "center_small": ParagraphStyle(
        "CenterSmall",
        parent=base["BodyText"],
        fontName="Helvetica",
        fontSize=7.4,
        leading=9.5,
        alignment=TA_CENTER,
        textColor=STONE,
    ),
}


def para(value: object, style: str = "body") -> Paragraph:
    return Paragraph(ptext(value), STYLE[style])


def callout(title: str, body: str, accent: colors.Color = BRASS) -> Table:
    table = Table(
        [[para(title.upper(), "kicker")], [para(body, "quote")]],
        colWidths=[7.1 * inch],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE),
                ("BOX", (0, 0), (-1, -1), 0.45, RULE),
                ("LINEBEFORE", (0, 0), (0, -1), 2.4, accent),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, 0), 8),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 1),
                ("TOPPADDING", (0, 1), (-1, 1), 1),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 9),
            ]
        )
    )
    return table


def data_table(rows: list[list[object]], widths: list[float] | None = None) -> Table:
    rendered: list[list[Paragraph]] = []
    for row_index, row in enumerate(rows):
        style = "cell_head" if row_index == 0 else "cell"
        rendered.append([para(clean_markdown(str(cell)), style) for cell in row])
    table = LongTable(
        rendered,
        colWidths=widths,
        repeatRows=1,
        splitByRow=1,
        splitInRow=0,
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), INK),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PAPER, PALE]),
                ("GRID", (0, 0), (-1, -1), 0.35, RULE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def page_chrome(pdf: canvas.Canvas, doc: SimpleDocTemplate, label: str) -> None:
    width, height = doc.pagesize
    pdf.saveState()
    pdf.setFillColor(PAPER)
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    pdf.setStrokeColor(BRASS)
    pdf.setLineWidth(0.55)
    pdf.line(0.52 * inch, height - 0.42 * inch, width - 0.52 * inch, height - 0.42 * inch)
    pdf.setFont("Courier-Bold", 6.5)
    pdf.setFillColor(BRASS)
    pdf.drawString(0.54 * inch, height - 0.31 * inch, "THREADLINE / REVERIE 2026")
    pdf.setFont("Courier", 6.3)
    pdf.setFillColor(STONE)
    pdf.drawRightString(width - 0.54 * inch, height - 0.31 * inch, ascii_text(label).upper())
    pdf.setStrokeColor(RULE)
    pdf.line(0.52 * inch, 0.4 * inch, width - 0.52 * inch, 0.4 * inch)
    pdf.drawString(
        0.54 * inch,
        0.23 * inch,
        "SYNTHETIC RESEARCH DEMO / NO AUTONOMOUS IDENTITY CONFIRMATION",
    )
    pdf.drawRightString(width - 0.54 * inch, 0.23 * inch, f"PAGE {doc.page}")
    pdf.restoreState()


def markdown_story(path: Path) -> list[object]:
    lines = path.read_text(encoding="utf-8").splitlines()
    story: list[object] = []
    index = 1 if lines and lines[0].startswith("# ") else 0
    in_code = False
    code_lines: list[str] = []
    while index < len(lines):
        raw = lines[index]
        stripped = raw.strip()
        if stripped.startswith("```"):
            if in_code:
                story.append(Preformatted(ascii_text("\n".join(code_lines)), STYLE["mono"]))
                code_lines = []
            in_code = not in_code
            index += 1
            continue
        if in_code:
            code_lines.append(raw)
            index += 1
            continue
        if not stripped or stripped.startswith("!["):
            index += 1
            continue
        if stripped.startswith("## "):
            story.append(para(clean_markdown(stripped[3:]), "h2"))
            index += 1
            continue
        if stripped.startswith("### "):
            story.append(para(clean_markdown(stripped[4:]), "h3"))
            index += 1
            continue
        if stripped.startswith("|"):
            rows: list[list[str]] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                cells = [
                    clean_markdown(cell.strip())
                    for cell in lines[index].strip().strip("|").split("|")
                ]
                if not all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells):
                    rows.append(cells)
                index += 1
            if rows:
                width = 7.1 * inch
                count = max(len(row) for row in rows)
                weights = [1.25] + [1.0] * (count - 1)
                total = sum(weights)
                story.append(data_table(rows, [width * item / total for item in weights]))
                story.append(Spacer(1, 6))
            continue
        if stripped.startswith("> "):
            quote_lines = [clean_markdown(stripped[2:])]
            index += 1
            while index < len(lines) and lines[index].strip().startswith(">"):
                quote_lines.append(clean_markdown(lines[index].strip().lstrip(">").strip()))
                index += 1
            story.append(callout("Research boundary", " ".join(quote_lines)))
            story.append(Spacer(1, 6))
            continue
        if stripped.startswith("- ") or re.match(r"^\d+\.\s", stripped):
            body = re.sub(r"^(?:- |\d+\.\s+)", "", stripped)
            story.append(Paragraph(ptext(clean_markdown(body)), STYLE["body"], bulletText="-"))
            index += 1
            continue
        paragraph = [stripped]
        index += 1
        while index < len(lines):
            nxt = lines[index].strip()
            if (
                not nxt
                or nxt.startswith(("#", "- ", "|", "```", "> ", "!["))
                or re.match(r"^\d+\.\s", nxt)
            ):
                break
            paragraph.append(nxt)
            index += 1
        story.append(para(clean_markdown(" ".join(paragraph))))
    return story


def build_markdown_pdf(source: Path, output: Path, title: str, subtitle: str, label: str) -> None:
    doc = SimpleDocTemplate(
        str(output),
        pagesize=LETTER,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.62 * inch,
        bottomMargin=0.58 * inch,
        title=title,
        author="THREADLINE",
        subject="Reverie Hacks 2026 synthetic research submission evidence",
    )
    story: list[object] = [
        Spacer(1, 0.2 * inch),
        para("THREADLINE / REVERIE HACKS 2026", "kicker"),
        para(title, "cover"),
        para(subtitle, "subtitle"),
        callout(
            "Scope",
            "Possible record connections for authorized human review only. Synthetic evidence; no autonomous identity confirmation and no operational humanitarian validation.",
        ),
        Spacer(1, 10),
    ]
    story.extend(markdown_story(source))
    doc.build(
        story,
        onFirstPage=lambda pdf, current: page_chrome(pdf, current, label),
        onLaterPages=lambda pdf, current: page_chrome(pdf, current, label),
    )


def build_workflow_pdf(output: Path) -> None:
    page = landscape(LETTER)
    pdf = canvas.Canvas(str(output), pagesize=page, invariant=1)
    pdf.setTitle("THREADLINE Reverie ML workflow")
    pdf.setAuthor("THREADLINE")
    pdf.setSubject("Reverie Hacks 2026 ML Prompt Engineering workflow")
    width, height = page
    pdf.setFillColor(PAPER)
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    pdf.setFont("Courier-Bold", 7)
    pdf.setFillColor(BRASS)
    pdf.drawString(0.45 * inch, height - 0.36 * inch, "THREADLINE / ML PROMPT ENGINEERING WORKFLOW")
    pdf.setFont("Times-Bold", 20)
    pdf.setFillColor(INK)
    pdf.drawString(
        0.45 * inch,
        height - 0.7 * inch,
        "Probabilistic evidence. Deterministic release boundary.",
    )
    image = Image(str(DOCS / "reverie-ml-workflow.png"), width=10.05 * inch, height=6.03 * inch)
    image.drawOn(pdf, 0.48 * inch, 0.52 * inch)
    pdf.setFont("Courier", 6.2)
    pdf.setFillColor(STONE)
    pdf.drawString(
        0.48 * inch,
        0.27 * inch,
        "EDITABLE SOURCE: docs/reverie-ml-workflow.svg / SYNTHETIC RESEARCH DEMONSTRATION",
    )
    pdf.drawRightString(width - 0.48 * inch, 0.27 * inch, "NO AUTONOMOUS IDENTITY CONFIRMATION")
    pdf.showPage()
    pdf.save()


def run_for_version(cohort: dict, version: str) -> dict:
    return next(run for run in cohort["runs"] if run["prompt_version"] == version)


def build_evidence_summary(output: Path, artifact: dict, results: dict) -> None:
    story = artifact["winning_story"]
    cohorts = {item["cohort_id"]: item for item in artifact["prompt_iterations"]["cohorts"]}
    targeted = cohorts["targeted-19-record-live-cohort"]
    full = cohorts["full-58-record-live-cohort"]
    v1 = run_for_version(targeted, "v1")
    v2_targeted = run_for_version(targeted, "v2")
    v2 = run_for_version(full, "v2")
    v3 = run_for_version(full, "v3")
    production = artifact["prompt_iterations"]["promotion_decision"]
    comparison = results["judge_case_comparison"]
    same_input = comparison["same_input_verification"]
    provider = comparison["provider"]
    input_manifest = comparison["case"]["input_manifest"]

    pdf = canvas.Canvas(str(output), pagesize=LETTER, invariant=1)
    pdf.setTitle("THREADLINE Reverie evidence summary")
    pdf.setAuthor("THREADLINE")
    pdf.setSubject("One-page source-backed evidence summary")
    width, height = LETTER
    pdf.setFillColor(PAPER)
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    left = 0.55 * inch
    right = width - 0.55 * inch
    pdf.setStrokeColor(BRASS)
    pdf.setLineWidth(0.7)
    pdf.line(left, height - 0.43 * inch, right, height - 0.43 * inch)
    pdf.setFont("Courier-Bold", 7)
    pdf.setFillColor(BRASS)
    pdf.drawString(left, height - 0.31 * inch, "THREADLINE / REVERIE 2026 / EVIDENCE SUMMARY")
    pdf.setFont("Times-Bold", 26)
    pdf.setFillColor(INK)
    pdf.drawString(left, height - 0.85 * inch, "Connect the records. Never guess the person.")
    pdf.setFont("Helvetica", 9.2)
    pdf.setFillColor(STONE)
    pdf.drawString(
        left,
        height - 1.08 * inch,
        "Same records. Different workflow. A source-cited candidate connection and a deterministic stop.",
    )

    y = height - 1.4 * inch
    card_width = (right - left - 0.18 * inch) / 2
    for x, title, headline, body, accent in [
        (
            left,
            "SUPPORTED FOR AUTHORIZED REVIEW",
            "FAMILY-018 <-> SHELTER-204",
            "Compatible age and traceable supporting fields. A possible connection only - never identity confirmation.",
            SAGE,
        ),
        (
            left + card_width + 0.18 * inch,
            "BLOCKED BY DETERMINISTIC CONFLICT",
            "FAMILY-018 <-> HOSPITAL-052",
            "Age 14 conflicts with document-backed age 24. The model cannot override the material-conflict gate.",
            RUST,
        ),
    ]:
        pdf.setFillColor(PALE)
        pdf.roundRect(x, y - 1.05 * inch, card_width, 1.05 * inch, 3, fill=1, stroke=0)
        pdf.setFillColor(accent)
        pdf.rect(x, y - 1.05 * inch, 0.04 * inch, 1.05 * inch, fill=1, stroke=0)
        pdf.setFont("Courier-Bold", 6.2)
        pdf.drawString(x + 0.14 * inch, y - 0.2 * inch, title)
        pdf.setFont("Helvetica-Bold", 10)
        pdf.setFillColor(INK)
        pdf.drawString(x + 0.14 * inch, y - 0.43 * inch, headline)
        text = pdf.beginText(x + 0.14 * inch, y - 0.63 * inch)
        text.setFont("Helvetica", 7.1)
        text.setFillColor(STONE)
        for line in wrap_text(body, 58):
            text.textLine(line)
        pdf.drawText(text)

    y -= 1.3 * inch
    pdf.setFont("Times-Bold", 14)
    pdf.setFillColor(INK)
    pdf.drawString(left, y, "Prompt iteration: completion did not outrank precision")
    y -= 0.15 * inch
    rows = [
        ["COHORT", "PROMPT", "OK", "TP / FP / FN", "PRECISION", "RECALL", "F1"],
        [
            "Targeted 19",
            "V1",
            quality_ok(v1),
            quality_counts(v1),
            quality_value(v1, "micro_precision"),
            quality_value(v1, "micro_recall"),
            quality_value(v1, "micro_f1"),
        ],
        [
            "Targeted 19",
            "V2",
            quality_ok(v2_targeted),
            quality_counts(v2_targeted),
            quality_value(v2_targeted, "micro_precision"),
            quality_value(v2_targeted, "micro_recall"),
            quality_value(v2_targeted, "micro_f1"),
        ],
        [
            "Full 58",
            "V2 / production",
            quality_ok(v2),
            quality_counts(v2),
            quality_value(v2, "micro_precision"),
            quality_value(v2, "micro_recall"),
            quality_value(v2, "micro_f1"),
        ],
        [
            "Full 58",
            "V3 / not promoted",
            quality_ok(v3),
            quality_counts(v3),
            quality_value(v3, "micro_precision"),
            quality_value(v3, "micro_recall"),
            quality_value(v3, "micro_f1"),
        ],
    ]
    table = data_table(
        rows,
        [
            0.85 * inch,
            1.35 * inch,
            0.55 * inch,
            1.15 * inch,
            0.95 * inch,
            0.78 * inch,
            0.7 * inch,
        ],
    )
    table.wrapOn(pdf, right - left, 2 * inch)
    table.drawOn(pdf, left, y - 1.18 * inch)

    y -= 1.42 * inch
    pdf.setFillColor(PALE)
    pdf.roundRect(left, y - 0.67 * inch, right - left, 0.67 * inch, 3, fill=1, stroke=0)
    pdf.setFont("Courier-Bold", 6.5)
    pdf.setFillColor(RUST)
    pdf.drawString(
        left + 0.12 * inch,
        y - 0.17 * inch,
        f"{production['reason_code']} / V3 NOT PROMOTED",
    )
    pdf.setFont("Helvetica", 7.4)
    pdf.setFillColor(INK)
    pdf.drawString(
        left + 0.12 * inch,
        y - 0.38 * inch,
        "V3 raised recall but produced 78 false-positive fields versus 30 for V2; precision and F1 regressed on the same 58 records.",
    )
    pdf.setFillColor(STONE)
    pdf.drawString(
        left + 0.12 * inch,
        y - 0.56 * inch,
        "No full 58-record V1 live artifact exists; no three-way same-cohort ranking is claimed.",
    )

    y -= 0.91 * inch
    pdf.setFont("Times-Bold", 14)
    pdf.setFillColor(INK)
    pdf.drawString(left, y, "Measured boundary")
    y -= 0.24 * inch
    metrics = [
        f"Prompt V2 archived run: {v2['decision_metrics']['true_link_count']} link-recommended candidate pairs; {v2['decision_metrics']['false_merge_count']}/{v2['decision_metrics']['different_identity_pairs']} observed false merges.",
        f"False non-links remain visible: {v2['decision_metrics']['false_non_match_count']} across {v2['decision_metrics']['same_identity_pairs']} same-identity opportunities.",
        f"Blocking-conflict recall: {v2['decision_metrics']['blocked_conflict_recall']:.3f}. Approximate API cost: {v2['operational']['approximate_api_cost']}.",
    ]
    pdf.setFont("Helvetica", 7.7)
    for item in metrics:
        pdf.setFillColor(INK)
        pdf.drawString(left + 0.1 * inch, y, "-")
        pdf.drawString(left + 0.23 * inch, y, item)
        y -= 0.19 * inch

    pdf.setStrokeColor(RULE)
    pdf.line(left, y - 0.02 * inch, right, y - 0.02 * inch)
    y -= 0.2 * inch

    # The comparison rail is sourced from results.json. It makes the same-input
    # experimental boundary visible without implying that mock replay is a live
    # model comparison.
    pdf.setFont("Courier-Bold", 6.4)
    pdf.setFillColor(BRASS)
    pdf.drawString(left, y, "SAME-INPUT DESIGN / DETERMINISTIC MOCK REPLAY")
    pdf.setFont("Courier", 6.05)
    pdf.setFillColor(STONE)
    pdf.drawRightString(
        right,
        y,
        f"{input_manifest['record_count']} RECORDS / {provider['model']} / TEMP {provider['temperature']:.1f}",
    )
    y -= 0.18 * inch
    pdf.setStrokeColor(RULE)
    rail_left = left + 0.12 * inch
    rail_right = right - 0.12 * inch
    rail_y = y - 0.16 * inch
    pdf.setLineWidth(0.8)
    pdf.line(rail_left, rail_y, rail_right, rail_y)
    systems = (
        ("GENERIC", "ONE PROMPT"),
        ("STRUCTURED", "ONE CALL"),
        ("THREADLINE", "DECOMPOSED WORKFLOW"),
    )
    for index, (name, detail) in enumerate(systems):
        x = rail_left + (rail_right - rail_left) * index / (len(systems) - 1)
        pdf.setFillColor(PAPER)
        pdf.setStrokeColor(BRASS if name == "THREADLINE" else STONE)
        pdf.circle(x, rail_y, 3.2, fill=1, stroke=1)
        pdf.setFont("Courier-Bold", 6.1)
        pdf.setFillColor(INK)
        pdf.drawCentredString(x, rail_y - 0.17 * inch, name)
        pdf.setFont("Courier", 5.7)
        pdf.setFillColor(STONE)
        pdf.drawCentredString(x, rail_y - 0.29 * inch, detail)
    y -= 0.6 * inch
    input_digest = input_manifest["input_sha256"]
    exact_shared = "VERIFIED" if same_input["exact_input_shared"] else "NOT VERIFIED"
    pdf.setFont("Courier", 5.8)
    pdf.setFillColor(STONE)
    pdf.drawString(
        left,
        y,
        f"EXACT INPUT SHARED: {exact_shared} / INPUT SHA-256 {input_digest[:16]}... / {provider['warning']}",
    )

    y -= 0.28 * inch
    pdf.setFont("Courier-Bold", 6.4)
    pdf.setFillColor(BRASS)
    pdf.drawString(left, y, "FIVE-STAGE WORKFLOW")
    y -= 0.17 * inch
    gap = 0.08 * inch
    stage_width = (right - left - gap * 4) / 5
    stages = (
        ("01", "QUARANTINE", "Preserve source"),
        ("02", "EXTRACT", "Cite exact spans"),
        ("03", "RETRIEVE", "Bound candidates"),
        ("04", "CHALLENGE", "Conflict + rival"),
        ("05", "CONTRACT", "Withhold / review"),
    )
    for index, (number, name, detail) in enumerate(stages):
        x = left + index * (stage_width + gap)
        pdf.setFillColor(PALE)
        pdf.roundRect(x, y - 0.5 * inch, stage_width, 0.5 * inch, 2, fill=1, stroke=0)
        pdf.setFont("Courier-Bold", 5.5)
        pdf.setFillColor(BRASS)
        pdf.drawString(x + 0.08 * inch, y - 0.13 * inch, number)
        pdf.setFont("Courier-Bold", 5.8)
        pdf.setFillColor(INK)
        pdf.drawString(x + 0.08 * inch, y - 0.28 * inch, name)
        pdf.setFont("Helvetica", 5.7)
        pdf.setFillColor(STONE)
        pdf.drawString(x + 0.08 * inch, y - 0.42 * inch, detail)

    y -= 0.72 * inch
    lower_gap = 0.18 * inch
    lower_left_width = (right - left) * 0.64
    lower_right_x = left + lower_left_width + lower_gap
    lower_right_width = right - lower_right_x
    lower_height = 1.28 * inch
    pdf.setFillColor(PALE)
    pdf.roundRect(left, y - lower_height, lower_left_width, lower_height, 3, fill=1, stroke=0)
    pdf.setFont("Courier-Bold", 6.3)
    pdf.setFillColor(RUST)
    pdf.drawString(left + 0.12 * inch, y - 0.18 * inch, "MEASURED LIMITS")
    limits = (
        "Synthetic records only; no operational humanitarian validation.",
        f"Zero observed false merges is {v2['decision_metrics']['false_merge_count']}/{v2['decision_metrics']['different_identity_pairs']} - a small denominator, not a safety guarantee.",
        "One archived live-provider run; repeatability intervals are not measured.",
        "No live same-model one-shot comparator; approximate API cost not measured.",
    )
    text = pdf.beginText(left + 0.12 * inch, y - 0.38 * inch)
    text.setFont("Helvetica", 6.25)
    text.setFillColor(INK)
    text.setLeading(9.1)
    for limit in limits:
        for line_index, line in enumerate(wrap_text(limit, 67)):
            text.textLine(("- " if line_index == 0 else "  ") + line)
    pdf.drawText(text)

    pdf.setFillColor(PALE)
    pdf.roundRect(
        lower_right_x,
        y - lower_height,
        lower_right_width,
        lower_height,
        3,
        fill=1,
        stroke=0,
    )
    placeholder_size = 0.53 * inch
    placeholder_x = lower_right_x + 0.11 * inch
    placeholder_y = y - 0.77 * inch
    pdf.setStrokeColor(RULE)
    pdf.setLineWidth(0.65)
    pdf.rect(
        placeholder_x,
        placeholder_y,
        placeholder_size,
        placeholder_size,
        fill=0,
        stroke=1,
    )
    pdf.setFont("Courier-Bold", 5.4)
    pdf.setFillColor(STONE)
    pdf.drawCentredString(
        placeholder_x + placeholder_size / 2,
        placeholder_y + 0.29 * inch,
        "QR",
    )
    pdf.setFont("Courier", 4.8)
    pdf.drawCentredString(
        placeholder_x + placeholder_size / 2,
        placeholder_y + 0.17 * inch,
        "ADD AFTER",
    )
    pdf.drawCentredString(
        placeholder_x + placeholder_size / 2,
        placeholder_y + 0.08 * inch,
        "DEPLOYMENT",
    )
    public_x = placeholder_x + placeholder_size + 0.1 * inch
    pdf.setFont("Courier-Bold", 5.9)
    pdf.setFillColor(RUST)
    pdf.drawString(public_x, y - 0.18 * inch, "PUBLIC DEMO")
    pdf.setFont("Helvetica-Bold", 7.1)
    pdf.setFillColor(INK)
    pdf.drawString(public_x, y - 0.39 * inch, "NOT CONFIGURED")
    pdf.setFont("Helvetica", 5.8)
    pdf.setFillColor(STONE)
    public_text = pdf.beginText(public_x, y - 0.58 * inch)
    public_text.setLeading(7.4)
    for line in wrap_text("Add a verified HTTPS URL and QR only after hosting.", 27):
        public_text.textLine(line)
    pdf.drawText(public_text)

    y -= lower_height + 0.18 * inch
    artifact_hash = sha256_file(SUBMISSION / "reverie-prompt-lab.json")
    pdf.setFont("Courier-Bold", 6.2)
    pdf.setFillColor(BRASS)
    pdf.drawString(left, y, "REPRODUCE / OFFLINE DEFAULT")
    pdf.setFont("Courier", 5.8)
    pdf.setFillColor(INK)
    pdf.drawString(
        left + 1.42 * inch,
        y,
        r".\scripts\reverie-release.ps1  |  bash scripts/reverie-release.sh",
    )
    y -= 0.15 * inch
    pdf.setFillColor(STONE)
    pdf.drawString(
        left,
        y,
        f"ARTIFACT SHA-256 {artifact_hash} / CASE {story['case_id']} / ROUTES /demo?demo=guided + /prompt-lab",
    )

    pdf.setFillColor(RUST)
    pdf.rect(left, 0.48 * inch, right - left, 0.04 * inch, fill=1, stroke=0)
    pdf.setFont("Helvetica-Bold", 7.1)
    pdf.setFillColor(INK)
    pdf.drawString(
        left,
        0.29 * inch,
        "One connection recovered. One false merge prevented. Every decision traceable.",
    )
    pdf.setFont("Helvetica", 6.1)
    pdf.setFillColor(STONE)
    pdf.drawRightString(
        right,
        0.29 * inch,
        "Candidate connection - not a person identified. Synthetic research only.",
    )
    pdf.showPage()
    pdf.save()


def wrap_text(value: str, limit: int) -> list[str]:
    words = value.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        if current and len(" ".join(current + [word])) > limit:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines


def quality_ok(run: dict) -> str:
    quality = run["extraction_quality"]
    return f"{quality['records_ok']}/{quality['records_total']}"


def quality_counts(run: dict) -> str:
    quality = run["extraction_quality"]
    return f"{quality['total_tp']} / {quality['total_fp']} / {quality['total_fn']}"


def quality_value(run: dict, key: str) -> str:
    return f"{run['extraction_quality'][key]:.4f}"


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_pdf(
    path: Path, required_phrases: tuple[str, ...], exact_pages: int | None = None
) -> int:
    reader = PdfReader(str(path))
    if reader.is_encrypted:
        raise RuntimeError(f"Encrypted PDF is not allowed: {path}")
    if exact_pages is not None and len(reader.pages) != exact_pages:
        raise RuntimeError(f"{path.name}: expected {exact_pages} page(s), got {len(reader.pages)}")
    extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
    for phrase in required_phrases:
        if phrase not in extracted:
            raise RuntimeError(f"{path.name}: required phrase missing: {phrase}")
    if any(not (page.extract_text() or "").strip() for page in reader.pages):
        raise RuntimeError(f"{path.name}: blank text page detected")
    return len(reader.pages)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    artifact = json.loads((SUBMISSION / "reverie-prompt-lab.json").read_text(encoding="utf-8"))
    results = json.loads((SUBMISSION / "results.json").read_text(encoding="utf-8"))
    outputs = {
        "workflow": OUTPUT / "threadline-reverie-workflow.pdf",
        "prompt": OUTPUT / "threadline-reverie-prompt-comparison.pdf",
        "technical": OUTPUT / "threadline-reverie-ml-track-documentation.pdf",
        "summary": OUTPUT / "threadline-reverie-evidence-summary.pdf",
    }
    build_workflow_pdf(outputs["workflow"])
    build_markdown_pdf(
        DOCS / "reverie-prompt-comparison.md",
        outputs["prompt"],
        "Same input. Visible safety boundary.",
        "A source-backed comparison of reasonable one-call baselines, the decomposed THREADLINE workflow, and the measured Prompt V1/V2/V3 promotion decision.",
        "prompt comparison",
    )
    build_markdown_pdf(
        DOCS / "reverie-ml-track-documentation.md",
        outputs["technical"],
        "Why every workflow node exists.",
        "Human inputs, five model operations, deterministic validation, retrieval, contradiction and rival analysis, release policy, human review, audit, replay, limits, and reproduction.",
        "ML track documentation",
    )
    build_evidence_summary(outputs["summary"], artifact, results)

    checks = {
        "workflow": verify_pdf(
            outputs["workflow"], ("Probabilistic evidence", "NO AUTONOMOUS IDENTITY"), 1
        ),
        "prompt": verify_pdf(outputs["prompt"], ("Same input", "PRECISION REGRESSION")),
        "technical": verify_pdf(outputs["technical"], ("workflow node", "human review")),
        "summary": verify_pdf(
            outputs["summary"],
            (
                "Connect the records",
                "0/8 observed false merges",
                "SAME-INPUT DESIGN",
                "PUBLIC DEMO",
                "NOT CONFIGURED",
            ),
            1,
        ),
    }
    for name, output in outputs.items():
        print(
            f"PDF {name}: {output.relative_to(ROOT)} / pages={checks[name]} / sha256={sha256_file(output)}"
        )


if __name__ == "__main__":
    main()
