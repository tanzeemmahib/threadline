"""Build the two print-ready THREADLINE submission PDFs.

Run from the repository root with the bundled or project Python runtime:
    python docs/submission/build_pdfs.py

The PDFs are presentation derivatives. Markdown and JSON remain authoritative.
"""

from __future__ import annotations

import html
import json
import re
import unicodedata
from functools import partial
from pathlib import Path
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[2]
SUBMISSION = ROOT / "docs" / "submission"

IVORY = colors.HexColor("#F2EBDD")
PAPER = colors.HexColor("#FBF8F1")
GRAPHITE = colors.HexColor("#171612")
CHARCOAL = colors.HexColor("#28251F")
STONE = colors.HexColor("#6B665D")
BRASS = colors.HexColor("#A7833C")
BRASS_LIGHT = colors.HexColor("#D3BB83")
RUST = colors.HexColor("#8B4C35")
SAGE = colors.HexColor("#62715F")
RULE = colors.HexColor("#D8D0C1")


def _register_fonts() -> None:
    font_dir = Path("C:/Windows/Fonts")
    files = {
        "ThreadSans": font_dir / "arial.ttf",
        "ThreadSansBold": font_dir / "arialbd.ttf",
        "ThreadSerif": font_dir / "georgia.ttf",
        "ThreadSerifBold": font_dir / "georgiab.ttf",
        "ThreadMono": font_dir / "consola.ttf",
        "ThreadMonoBold": font_dir / "consolab.ttf",
    }
    for name, path in files.items():
        if path.exists():
            pdfmetrics.registerFont(TTFont(name, str(path)))


_register_fonts()

FONT_SANS = "ThreadSans" if "ThreadSans" in pdfmetrics.getRegisteredFontNames() else "Helvetica"
FONT_SANS_BOLD = "ThreadSansBold" if "ThreadSansBold" in pdfmetrics.getRegisteredFontNames() else "Helvetica-Bold"
FONT_SERIF = "ThreadSerif" if "ThreadSerif" in pdfmetrics.getRegisteredFontNames() else "Times-Roman"
FONT_SERIF_BOLD = "ThreadSerifBold" if "ThreadSerifBold" in pdfmetrics.getRegisteredFontNames() else "Times-Bold"
FONT_MONO = "ThreadMono" if "ThreadMono" in pdfmetrics.getRegisteredFontNames() else "Courier"
FONT_MONO_BOLD = "ThreadMonoBold" if "ThreadMonoBold" in pdfmetrics.getRegisteredFontNames() else "Courier-Bold"


def ascii_text(value: object) -> str:
    text = str(value)
    replacements = {
        "\u2014": " - ",
        "\u2013": "-",
        "\u2212": "-",
        "\u2192": "->",
        "\u2190": "<-",
        "\u2022": "-",
        "\u00a0": " ",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\ufffd": "-",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def clean_markdown(value: str) -> str:
    text = ascii_text(value).strip()
    text = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", text)
    text = text.replace("**", "").replace("`", "")
    return text


def ptext(value: object) -> str:
    return html.escape(ascii_text(value), quote=False).replace("\n", "<br/>")


styles = getSampleStyleSheet()
STYLE = {
    "kicker": ParagraphStyle(
        "Kicker",
        fontName=FONT_MONO_BOLD,
        fontSize=7.3,
        leading=9,
        textColor=BRASS,
        tracking=1.5,
        spaceAfter=8,
    ),
    "cover": ParagraphStyle(
        "Cover",
        fontName=FONT_SERIF_BOLD,
        fontSize=31,
        leading=35,
        textColor=GRAPHITE,
        spaceAfter=12,
    ),
    "subtitle": ParagraphStyle(
        "Subtitle",
        fontName=FONT_SANS,
        fontSize=11,
        leading=16,
        textColor=STONE,
        spaceAfter=14,
    ),
    "h1": ParagraphStyle(
        "H1",
        fontName=FONT_SERIF_BOLD,
        fontSize=24,
        leading=28,
        textColor=GRAPHITE,
        spaceBefore=8,
        spaceAfter=12,
    ),
    "h2": ParagraphStyle(
        "H2",
        fontName=FONT_SERIF_BOLD,
        fontSize=16,
        leading=20,
        textColor=GRAPHITE,
        spaceBefore=15,
        spaceAfter=7,
        keepWithNext=True,
    ),
    "h3": ParagraphStyle(
        "H3",
        fontName=FONT_SANS_BOLD,
        fontSize=10.2,
        leading=13,
        textColor=CHARCOAL,
        spaceBefore=10,
        spaceAfter=5,
        keepWithNext=True,
    ),
    "body": ParagraphStyle(
        "Body",
        fontName=FONT_SANS,
        fontSize=8.7,
        leading=12.4,
        textColor=CHARCOAL,
        spaceAfter=6,
    ),
    "small": ParagraphStyle(
        "Small",
        fontName=FONT_SANS,
        fontSize=7.5,
        leading=10.5,
        textColor=STONE,
        spaceAfter=4,
    ),
    "mono": ParagraphStyle(
        "Mono",
        fontName=FONT_MONO,
        fontSize=7,
        leading=9.2,
        textColor=CHARCOAL,
        spaceAfter=5,
    ),
    "quote": ParagraphStyle(
        "Quote",
        fontName=FONT_SERIF,
        fontSize=12.5,
        leading=17,
        textColor=GRAPHITE,
        leftIndent=13,
        rightIndent=13,
        spaceAfter=5,
    ),
    "cell": ParagraphStyle(
        "Cell",
        fontName=FONT_SANS,
        fontSize=7.1,
        leading=9.4,
        textColor=CHARCOAL,
    ),
    "cell_head": ParagraphStyle(
        "CellHead",
        fontName=FONT_MONO_BOLD,
        fontSize=6.6,
        leading=8.4,
        textColor=IVORY,
    ),
    "cell_mono": ParagraphStyle(
        "CellMono",
        fontName=FONT_MONO,
        fontSize=6.7,
        leading=8.5,
        textColor=CHARCOAL,
    ),
}


def para(text: object, style: str = "body") -> Paragraph:
    return Paragraph(ptext(text), STYLE[style])


def callout(title: str, body: str, accent: colors.Color = BRASS) -> Table:
    data = [[para(title.upper(), "kicker")], [para(body, "quote")]]
    table = Table(data, colWidths=[7.25 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F4EFE5")),
                ("BOX", (0, 0), (-1, -1), 0.6, RULE),
                ("LINEBEFORE", (0, 0), (0, -1), 3, accent),
                ("LEFTPADDING", (0, 0), (-1, -1), 13),
                ("RIGHTPADDING", (0, 0), (-1, -1), 13),
                ("TOPPADDING", (0, 0), (-1, 0), 9),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
                ("TOPPADDING", (0, 1), (-1, 1), 2),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 11),
            ]
        )
    )
    return table


def data_table(rows: list[list[object]], widths: list[float] | None = None) -> Table:
    rendered: list[list[Paragraph]] = []
    for r_index, row in enumerate(rows):
        style = "cell_head" if r_index == 0 else "cell"
        rendered.append([para(clean_markdown(str(cell)), style) for cell in row])
    table = Table(rendered, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), GRAPHITE),
                ("TEXTCOLOR", (0, 0), (-1, 0), IVORY),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PAPER, colors.HexColor("#F3EEE4")]),
                ("GRID", (0, 0), (-1, -1), 0.35, RULE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def page_background(canvas, doc) -> None:
    canvas.saveState()
    width, height = LETTER
    canvas.setFillColor(PAPER)
    canvas.rect(0, 0, width, height, fill=1, stroke=0)
    canvas.restoreState()


def draw_chrome(canvas, label: str, page_number: int) -> None:
    canvas.saveState()
    width, height = LETTER
    canvas.setStrokeColor(BRASS)
    canvas.setLineWidth(0.6)
    canvas.line(0.54 * inch, height - 0.43 * inch, width - 0.54 * inch, height - 0.43 * inch)
    canvas.setFont(FONT_MONO_BOLD, 6.8)
    canvas.setFillColor(BRASS)
    canvas.drawString(0.56 * inch, height - 0.32 * inch, "THREADLINE / SUBMISSION EVIDENCE")
    canvas.setFont(FONT_MONO, 6.6)
    canvas.setFillColor(STONE)
    canvas.drawRightString(width - 0.56 * inch, height - 0.32 * inch, ascii_text(label).upper())
    canvas.setStrokeColor(RULE)
    canvas.line(0.54 * inch, 0.42 * inch, width - 0.54 * inch, 0.42 * inch)
    canvas.setFont(FONT_MONO, 6.3)
    canvas.setFillColor(STONE)
    canvas.drawString(0.56 * inch, 0.25 * inch, "SYNTHETIC RESEARCH DEMONSTRATION / NO AUTONOMOUS IDENTITY CONFIRMATION")
    canvas.drawRightString(width - 0.56 * inch, 0.25 * inch, f"PAGE {page_number}")
    canvas.restoreState()


class ChromeCanvas(pdfcanvas.Canvas):
    """Overlay consistent header/footer chrome after every page is composed."""

    def __init__(self, *args, label: str, **kwargs):
        super().__init__(*args, **kwargs)
        self._chrome_label = label
        self._page_states: list[dict] = []

    def showPage(self) -> None:  # noqa: N802 - ReportLab API
        self._page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        for state in self._page_states:
            self.__dict__.update(state)
            draw_chrome(self, self._chrome_label, self._pageNumber)
            super().showPage()
        super().save()


def markdown_flow(path: Path, *, skip_title: bool = True) -> list:
    lines = path.read_text(encoding="utf-8").splitlines()
    story: list = []
    index = 0
    in_code = False
    code_lines: list[str] = []
    if skip_title and lines and lines[0].startswith("# "):
        index = 1

    while index < len(lines):
        raw = lines[index]
        stripped = raw.strip()
        if stripped.startswith("```"):
            if in_code:
                story.append(Preformatted(ascii_text("\n".join(code_lines)), STYLE["mono"]))
                code_lines = []
                in_code = False
            else:
                in_code = True
            index += 1
            continue
        if in_code:
            code_lines.append(raw)
            index += 1
            continue
        if not stripped:
            index += 1
            continue
        if stripped.startswith("## "):
            if stripped == "## 01 - Incident configuration":
                story.append(PageBreak())
            story.append(Paragraph(ptext(clean_markdown(stripped[3:])), STYLE["h2"]))
            index += 1
            continue
        if stripped.startswith("### "):
            story.append(Paragraph(ptext(clean_markdown(stripped[4:])), STYLE["h3"]))
            index += 1
            continue
        if stripped.startswith("|") and "|" in stripped[1:]:
            table_rows: list[list[str]] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                cells = [clean_markdown(cell.strip()) for cell in lines[index].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells):
                    table_rows.append(cells)
                index += 1
            if table_rows:
                available = 7.25 * inch
                count = max(len(row) for row in table_rows)
                weights = [1.0] * count
                if count >= 2:
                    weights[0] = 1.35
                total = sum(weights)
                story.append(data_table(table_rows, [available * weight / total for weight in weights]))
                story.append(Spacer(1, 7))
            continue
        if stripped.startswith("- ") or re.match(r"^\d+\.\s", stripped):
            body = re.sub(r"^(?:- |\d+\.\s+)", "", stripped)
            story.append(Paragraph(ptext(clean_markdown(body)), STYLE["body"], bulletText="-"))
            index += 1
            continue
        if stripped.startswith("> "):
            story.append(callout("Research boundary", clean_markdown(stripped[2:])))
            story.append(Spacer(1, 7))
            index += 1
            continue

        paragraph_lines = [stripped]
        index += 1
        while index < len(lines):
            nxt = lines[index].strip()
            if not nxt or nxt.startswith(("#", "- ", "|", "```", "> ")) or re.match(r"^\d+\.\s", nxt):
                break
            paragraph_lines.append(nxt)
            index += 1
        story.append(para(clean_markdown(" ".join(paragraph_lines))))
    return story


def document(path: Path, label: str) -> SimpleDocTemplate:
    return SimpleDocTemplate(
        str(path),
        pagesize=LETTER,
        rightMargin=0.63 * inch,
        leftMargin=0.63 * inch,
        topMargin=0.62 * inch,
        bottomMargin=0.58 * inch,
        title=label,
        author="THREADLINE",
        subject="Synthetic research demonstration submission evidence",
    )


def build_workflow_pdf() -> Path:
    out = SUBMISSION / "workflow-node-documentation.pdf"
    doc = document(out, "Workflow node documentation")
    story: list = [
        Spacer(1, 0.22 * inch),
        para("THREADLINE / WORKFLOW REFERENCE", "kicker"),
        para("Evidence in. Boundaries out.", "cover"),
        para(
            "A printable description of all twelve workflow nodes, five connected-provider LLM stages, deterministic validation boundaries, release rules, failure behavior, and known limitations.",
            "subtitle",
        ),
        callout(
            "Scope",
            "Possible record connections for authorized human review. The system preserves evidence and uncertainty; it never confirms identity.",
        ),
        Spacer(1, 14),
        Image(str(SUBMISSION / "threadline-workflow.png"), width=7.25 * inch, height=4.43 * inch),
        Spacer(1, 9),
        para(
            "Editable source: threadline-workflow.svg. The privacy gate is intentionally shown after the five model stages because the current implementation protects the reviewer-facing packet, not provider ingress.",
            "small",
        ),
        PageBreak(),
        para("THREADLINE / MODEL AND PROVIDER BOUNDARY", "kicker"),
        HRFlowable(width="100%", thickness=0.6, color=BRASS),
        Spacer(1, 4),
    ]
    story.extend(markdown_flow(SUBMISSION / "workflow-node-documentation.md"))
    story.extend(
        [
            Spacer(1, 10),
            HRFlowable(width="100%", thickness=0.6, color=BRASS),
            Spacer(1, 8),
            para("Authoritative sources", "h3"),
            para(
                "Workflow details are derived from the repository's workflow registry, node implementations, prompts, schemas, evidence-contract service, audit service, and deterministic submission artifacts. This PDF is a presentation derivative; use the Markdown and machine-readable files for audit.",
                "small",
            ),
        ]
    )
    doc.build(
        story,
        onFirstPage=page_background,
        onLaterPages=page_background,
        canvasmaker=partial(ChromeCanvas, label="workflow / nodes"),
    )
    return out


def metric(system: dict, metric_id: str) -> dict:
    return next(item for item in system["metrics"] if item["metric_id"] == metric_id)


def outcome_label(system: dict) -> str:
    classification = system.get("classification", "Not recorded")
    if system.get("system_id") == "threadline":
        status = system.get("workflow", {}).get("contract_release_status", "Not recorded")
        return f"{classification}; aggregate {status}"
    return classification


def build_comparison_pdf() -> Path:
    results = json.loads((SUBMISSION / "results.json").read_text(encoding="utf-8"))
    ablation = json.loads((SUBMISSION / "ablation-counterfactual.json").read_text(encoding="utf-8"))
    benchmark = results["deterministic_benchmark"]
    judge = results["judge_case_comparison"]
    live = results["archived_live_prompt_v2"]
    out = SUBMISSION / "comparison-samples.pdf"
    doc = document(out, "Comparison and samples")

    story: list = [
        Spacer(1, 0.23 * inch),
        para("THREADLINE / JUDGE EVIDENCE", "kicker"),
        para("An answer is not a conclusion.", "cover"),
        para(
            "Same synthetic records. Same deterministic mock model. Different workflow. The one-call fixtures return a plausible candidate; THREADLINE preserves the rival contradiction and withholds aggregate release.",
            "subtitle",
        ),
        callout(
            "Answer first",
            "The baseline produced an answer. THREADLINE produced an auditable boundary around what the evidence can support.",
        ),
        Spacer(1, 13),
        para("What this packet proves", "h2"),
        data_table(
            [
                ["Evidence track", "What is measured", "What is not claimed"],
                ["Deterministic 21-case replay", "Fixed workflow behavior with identical case input", "Live-model quality or field safety"],
                ["Archived Prompt V2 live run", "One provider extraction run plus deterministic policy", "Same-model baseline comparison or repeated-run stability"],
            ],
            [1.55 * inch, 2.65 * inch, 3.05 * inch],
        ),
        Spacer(1, 12),
        para("Safety objective", "h2"),
        para(
            "False merges are treated as the central safety concern. Missed possible connections, dangerous unsupported connections, and correctly withheld cases remain distinct outcomes rather than being collapsed into a single flattering score.",
        ),
        para(
            f"Artifact {results['artifact_id']} / benchmark {benchmark['benchmark_id']} / synthetic cases only / working tree dirty at generation: {results['code_state']['working_tree_dirty']}",
            "mono",
        ),
        PageBreak(),
        para("CASE / SAME INPUT", "kicker"),
        para("One plausible connection. One material rival.", "h1"),
        para(
            f"Case {judge['case']['case_id']} supplies the same {judge['case']['input_manifest']['record_count']} records to every compared system. Shared input SHA-256: {judge['case']['input_manifest']['input_sha256']}.",
            "small",
        ),
    ]

    record_rows = [["Source record", "Exact synthetic source text"]]
    for record in judge["case"]["records"]:
        record_rows.append([f"{record['record_id']}\n{record['source_type']}", record["text"]])
    story.append(data_table(record_rows, [1.45 * inch, 5.8 * inch]))
    story.extend(
        [
            Spacer(1, 10),
            para("Observed deterministic outputs", "h2"),
            data_table(
                [["System", "Candidate records", "Structured outcome"]]
                + [
                    [system["system_name"], ", ".join(system.get("candidate_record_ids", [])), outcome_label(system)]
                    for system in judge["systems"].values()
                ],
                [1.8 * inch, 2.1 * inch, 3.35 * inch],
            ),
            Spacer(1, 9),
            callout("Safe conclusion", judge["safe_conclusion"], RUST),
            PageBreak(),
            para("DETERMINISTIC COMPARISON", "kicker"),
            para("Coverage and restraint remain visible together.", "h1"),
            para(benchmark["evaluation_label"], "small"),
        ]
    )

    metric_rows = [["System", "Candidate recall", "False-link rate", "Correct abstention"]]
    for system in benchmark["systems"]:
        recall = metric(system, "candidate_recall_at_k")
        false_link = metric(system, "false_link_rate")
        abstain = metric(system, "correct_abstention_rate")
        metric_rows.append(
            [
                system["system_name"],
                f"{recall['numerator']}/{recall['denominator']} ({recall['value']:.3f}%)",
                f"{false_link['numerator']}/{false_link['denominator']} ({false_link['value']:.3f}%)",
                f"{abstain['numerator']}/{abstain['denominator']} ({abstain['value']:.3f}%)",
            ]
        )
    story.append(data_table(metric_rows, [2.05 * inch, 1.75 * inch, 1.75 * inch, 1.7 * inch]))
    story.extend(
        [
            Spacer(1, 10),
            para("Interpretation", "h2"),
            para(
                "The generic and structured one-call fixtures returned a positive review candidate in all eight different-identity cases. Full THREADLINE returned none and abstained on the one deliberately ambiguous case. These are fixture-and-rule outcomes, not estimates of live-model performance.",
            ),
            para("Ablations retained without spin", "h2"),
        ]
    )
    ablation_rows = [["Configuration", "Disabled", "Primary or case-level effect"]]
    for config in ablation["benchmark_ablations"]["configurations"]:
        changed = ", ".join(sorted(config.get("changed_metrics", {}).keys())) or "None"
        affected = len(config.get("affected_case_ids", []))
        ablation_rows.append(
            [config["configuration_id"], ", ".join(config.get("disabled_nodes", [])) or "None", f"Changed metrics: {changed}; affected cases: {affected}"]
        )
    story.append(data_table(ablation_rows, [1.5 * inch, 1.55 * inch, 4.2 * inch]))
    counter = ablation["source_counterfactual"]
    story.extend(
        [
            Spacer(1, 9),
            callout(
                "Source-removal counterfactual",
                f"Removing {counter.get('removed_record_id', 'the recorded source')} changed aggregate contract status from {counter.get('baseline_contract_status', 'withheld')} to {counter.get('counterfactual_contract_status', 'released')}. This changes what the contract permits; it does not prove identity.",
                RUST,
            ),
            para(
                "Evidence-contract-node removal is Not measured because the contract is not an independently disableable benchmark node in the current implementation.",
                "small",
            ),
            PageBreak(),
            para("ARCHIVED LIVE-PROVIDER EVIDENCE", "kicker"),
            para("One measured extraction run, reported separately.", "h1"),
            para(live["evaluation_label"], "small"),
        ]
    )
    q = live["extraction_quality"]
    d = live["decision_metrics"]
    op = live["operational"]
    story.append(
        data_table(
            [
                ["Measure", "Archived Prompt V2 result"],
                ["Provider / model", f"{live['provider']} / {live['model']}"],
                ["Prompt / temperature", f"{live['prompt_version']} / {live['temperature']}"],
                ["Successful extractions", f"{q['records_ok']}/{q['records_total']}"],
                ["Extraction TP / FP / FN", f"{q['total_tp']} / {q['total_fp']} / {q['total_fn']}"],
                ["Extraction precision / recall / F1", f"{q['micro_precision']:.4f} / {q['micro_recall']:.4f} / {q['micro_f1']:.4f}"],
                ["Candidate retrieval", f"{live['retrieval']['n']}/{live['retrieval']['d']}"],
                [
                    "Released proposals / false merges / false non-links",
                    f"{d['true_link_count']} / {d['false_merge_count']} of 8 different-identity pairs / {d['false_non_match_count']}",
                ],
                ["Median latency", f"{op['median_latency_ms']:,.0f} ms across {op['successful_records']} successful calls"],
                ["p95 latency", f"{op['p95_latency_ms']:,.0f} ms; {op['p95_method']}"],
                ["Tokens / attempts", f"{op['total_tokens_successful_records']:,} / {op['total_attempts']}"],
                ["Approximate API cost", op["approximate_api_cost"]],
            ],
            [3.0 * inch, 4.25 * inch],
        )
    )
    story.extend(
        [
            Spacer(1, 10),
            para("What remains unknown", "h2"),
        ]
    )
    for limitation in live["limitations"]:
        story.append(Paragraph(ptext(limitation), STYLE["body"], bulletText="-"))
    story.extend(
        [
            Paragraph(ptext("Approximate cost is not reconstructed because the archive does not pin separate input/output token counts and a dated provider price table."), STYLE["body"], bulletText="-"),
            Paragraph(ptext("The archived run did not record an exact git commit or dirty-tree patch; the current commit is not retroactively assigned."), STYLE["body"], bulletText="-"),
            Spacer(1, 7),
            HRFlowable(width="100%", thickness=0.6, color=BRASS),
            Spacer(1, 8),
            para("Reproduce and inspect", "h2"),
            para("Offline judge path: scripts/run-v1-demo.ps1", "mono"),
            para("Submission evidence: cd backend; ./.venv/Scripts/python.exe scripts/build_submission_evidence.py", "mono"),
            para("Auditable sources: results.json, results.csv, raw-outputs.json, ablation-counterfactual.json, benchmark-report.md", "small"),
            callout(
                "Final boundary",
                "All cases and identities are fictional. This research prototype is not validated for operational humanitarian use and cannot establish a person's identity.",
            ),
        ]
    )
    doc.build(
        story,
        onFirstPage=page_background,
        onLaterPages=page_background,
        canvasmaker=partial(ChromeCanvas, label="comparison / samples"),
    )
    return out


def main() -> None:
    required = [
        SUBMISSION / "results.json",
        SUBMISSION / "ablation-counterfactual.json",
        SUBMISSION / "workflow-node-documentation.md",
        SUBMISSION / "threadline-workflow.png",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise SystemExit("Missing required source artifacts:\n" + "\n".join(missing))
    outputs: Iterable[Path] = (build_workflow_pdf(), build_comparison_pdf())
    for output in outputs:
        print(f"Wrote {output.relative_to(ROOT)} ({output.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
