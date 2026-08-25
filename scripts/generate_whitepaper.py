
"""Script to generate the institutional FSKU White Paper PDF.

Styled with a dark financial terminal theme:
- Deep black/obsidian background (#08090D)
- Crisp white & silver typography (#FFFFFF, #E2E8F0, #94A3B8)
- Prominent 'NATIVX' logo in the upper-right corner of every page
- Mathematical formulas, structured comparison tables, and architectural details.
"""

from __future__ import annotations
import os
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to compute and draw page numbers cleanly."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count: int):
        width, height = letter
        self.saveState()
        self.setFont("Helvetica-Bold", 7.5)
        self.setFillColor(colors.HexColor("#919191"))
        self.drawRightString(width - 40, 28, f"Page {self._pageNumber} of {page_count}")
        self.restoreState()

def draw_page_decorations(canvas_obj, doc):
    """Draws background, header rule, NATIVX logo, and footer on each page before flowables."""
    width, height = letter
    canvas_obj.saveState()

    canvas_obj.setFillColor(colors.HexColor("#131313"))
    canvas_obj.rect(0, 0, width, height, fill=1, stroke=0)

    canvas_obj.setStrokeColor(colors.HexColor("#474747"))
    canvas_obj.setLineWidth(0.8)
    canvas_obj.line(40, height - 44, width - 40, height - 44)

    canvas_obj.setFont("Helvetica-Bold", 7.5)
    canvas_obj.setFillColor(colors.HexColor("#919191"))
    canvas_obj.drawString(40, height - 34, "FSKU · GPU COMPUTE BENCHMARK & FORWARD CURVE METHODOLOGY")

    badge_w, badge_h = 72, 18
    badge_x = width - 40 - badge_w
    badge_y = height - 40
    canvas_obj.setFillColor(colors.HexColor("#1B1B1B"))
    canvas_obj.setStrokeColor(colors.HexColor("#474747"))
    canvas_obj.setLineWidth(0.75)
    canvas_obj.roundRect(badge_x, badge_y, badge_w, badge_h, 3, fill=1, stroke=1)

    canvas_obj.setFont("Helvetica-Bold", 9.5)
    canvas_obj.setFillColor(colors.HexColor("#FFFFFF"))
    canvas_obj.drawRightString(width - 48, height - 34, "NATIVX")

    canvas_obj.setStrokeColor(colors.HexColor("#474747"))
    canvas_obj.setLineWidth(0.8)
    canvas_obj.line(40, 42, width - 40, 42)

    canvas_obj.setFont("Helvetica", 7.5)
    canvas_obj.setFillColor(colors.HexColor("#919191"))
    canvas_obj.drawString(40, 28, "Published by NativX (nativx.net) · Apache License 2.0 · Open Source & Transparent")

    canvas_obj.restoreState()

def build_pdf(filename: str):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=54,
        bottomMargin=52,
    )

    styles = getSampleStyleSheet()

    style_title = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#FFFFFF"),
        spaceAfter=3,
    )

    style_subtitle = ParagraphStyle(
        "DocSubTitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#919191"),
        spaceAfter=10,
    )

    style_meta = ParagraphStyle(
        "DocMeta",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=10.5,
        textColor=colors.HexColor("#38BDF8"),
        spaceAfter=10,
    )

    style_h1 = ParagraphStyle(
        "Heading1_Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#38EF7D"),
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True,
    )

    style_h2 = ParagraphStyle(
        "Heading2_Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#38BDF8"),
        spaceBefore=8,
        spaceAfter=3,
        keepWithNext=True,
    )

    style_body = ParagraphStyle(
        "Body_Custom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11.5,
        textColor=colors.HexColor("#E2E2E2"),
        spaceAfter=5,
    )

    style_bullet = ParagraphStyle(
        "Bullet_Custom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11.5,
        textColor=colors.HexColor("#E2E2E2"),
        leftIndent=10,
        spaceAfter=3,
    )

    style_formula = ParagraphStyle(
        "Formula_Custom",
        parent=styles["Normal"],
        fontName="Courier-Bold",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#96EBF7"),
        alignment=1,
    )

    style_table_cell = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.2,
        leading=9.5,
        textColor=colors.HexColor("#E2E2E2"),
    )

    style_table_header = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.2,
        leading=9.5,
        textColor=colors.HexColor("#919191"),
    )

    story = []

    story.append(Paragraph("FSKU: Open GPU Compute Indexing & Forward Curves", style_title))
    story.append(Paragraph("A Transparent, Public Methodology for Normalized Spot Benchmarks, Price Dispersion, and Model-Implied Forward Term Structures", style_subtitle))
    story.append(Paragraph("BUILT BY: NATIVX (<font color='#FFFFFF'>nativx.net</font>) &nbsp;|&nbsp; LICENSE: Apache 2.0 &nbsp;|&nbsp; STATUS: Open Public Reference Benchmark", style_meta))
    story.append(HRFlowable(width="100%", thickness=0.75, color=colors.HexColor("#474747"), spaceBefore=0, spaceAfter=8))

    story.append(Paragraph("1. Executive Summary & Market Problem", style_h1))
    story.append(Paragraph(
        "As accelerated compute becomes the foundational capital expenditure of modern artificial intelligence, "
        "market participants require transparent, liquid, and mathematically reproducible benchmarks. Historically, "
        "GPU cloud pricing has remained opaque, dominated by unlisted negotiated rates, disparate multi-GPU chassis configurations, "
        "and fragmented pricing terms across hyperscalers (AWS, GCP, Azure) and specialized neoclouds (CoreWeave, RunPod, Lambda Labs).",
        style_body
    ))
    story.append(Paragraph(
        "Commercial data providers have historically responded to this opacity by selling paywalled, proprietary indices. "
        "However, closed-box pricing indices create severe institutional hazards: methodology opacity, unverifiable source feeds, "
        "and conflation between surface-level quotes and executed trades. <b>FSKU</b> solves this by establishing a 100% open-source, "
        "reproducible benchmark pipeline: <i>Public Data In &rarr; Normalized $/GPU-hr &rarr; SKU Spot Index &rarr; Historical Benchmark &rarr; Implied Forward Curve</i>.",
        style_body
    ))

    story.append(Paragraph("2. Unit Normalization Architecture", style_h1))
    story.append(Paragraph(
        "Cloud compute is sold across heterogeneous server topographies: single-GPU instances, 8-GPU HGX clusters, and multi-node reservations. "
        "To establish true like-for-like comparability across providers without introducing arbitrary subjective modifiers, FSKU applies "
        "strict mathematical <b>Unit Normalization</b>:",
        style_body
    ))

    f1_data = [[Paragraph("Normalized Rate ($/GPU-hour) = Published Hourly Server Rate / Published Physical GPU Count", style_formula)]]
    t_f1 = Table(f1_data, colWidths=[530])
    t_f1.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#181818")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#474747")),
        ('PADDING', (0,0), (-1,-1), 5),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ]))
    story.append(t_f1)
    story.append(Spacer(1, 5))

    story.append(Paragraph(
        "<b>Normalization Boundaries:</b> Normalized rates establish unit parity ($/GPU-hr) rather than full economic identity. "
        "No opaque synthetic multipliers are added for CPU allocations, system RAM, NVMe scratch disks, or egress terms. "
        "Every normalized rate is explicitly categorized by its primary <b>Contract Basis</b>: <i>On-demand</i>, <i>Spot</i>, <i>Capacity Block</i>, or <i>Retail API</i>.",
        style_body
    ))

    story.append(Paragraph("3. Benchmark Index Construction Methodologies", style_h1))
    story.append(Paragraph(
        "To protect benchmarks against extreme upper-tail retail quotes or promotional spot distortions, FSKU evaluates six statistical aggregation formulas:",
        style_body
    ))

    methodology_rows = [
        [Paragraph("Methodology", style_table_header), Paragraph("Formula / Specification", style_table_header), Paragraph("Institutional Application & Purpose", style_table_header)],
        [
            Paragraph("<b>Robust Median (Default)</b>", style_table_cell),
            Paragraph("<font face='Courier'>S_0 = Median(P_1, P_2, ..., P_n)</font>", style_table_cell),
            Paragraph("Default anchor. Highly resilient against extreme upper-tail enterprise retail API quotes.", style_table_cell)
        ],
        [
            Paragraph("<b>10% / 20% Trimmed Mean</b>", style_table_cell),
            Paragraph("<font face='Courier'>Mean(P[k : N-k]), k = floor(N * p)</font>", style_table_cell),
            Paragraph("Symmetrically removes highest and lowest outliers to produce an insulated arithmetic mean.", style_table_cell)
        ],
        [
            Paragraph("<b>Provider-Balanced</b>", style_table_cell),
            Paragraph("<font face='Courier'>Mean(Median_Provider(P))</font>", style_table_cell),
            Paragraph("Equal-weights each provider first before averaging, eliminating provider quote-density bias.", style_table_cell)
        ],
        [
            Paragraph("<b>GPU-Count Weighted</b>", style_table_cell),
            Paragraph("<font face='Courier'>Sum(Total_Rate) / Sum(GPU_Count)</font>", style_table_cell),
            Paragraph("Weights index by physical cluster scale (e.g. 8-GPU HGX cluster price vs 1-GPU PCIe price).", style_table_cell)
        ],
        [
            Paragraph("<b>Simple Arithmetic Mean</b>", style_table_cell),
            Paragraph("<font face='Courier'>1/N * Sum(P_i)</font>", style_table_cell),
            Paragraph("Baseline reference. Highly vulnerable to upward skew in distributed retail cloud markets.", style_table_cell)
        ],
    ]
    t_meth = Table(methodology_rows, colWidths=[115, 165, 250])
    t_meth.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#181818")),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#141414")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#474747")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#262626")),
        ('PADDING', (0,0), (-1,-1), 4.5),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t_meth)
    story.append(Spacer(1, 8))

    story.append(Paragraph("4. Matched-Provider Technological Deflation (d)", style_h1))
    story.append(Paragraph(
        "A critical flaw in naive compute forward pricing is assuming historical hardware retains static rental value. "
        "In reality, rapid silicon architecture iteration causes steady rental price deflation across older chip generations. "
        "To infer pure hardware deflation (<font color='#38BDF8'><b>d</b></font>) without contaminating the estimate with provider markup variations, "
        "FSKU calculates rental ratios strictly across <b>matched provider pairs</b> offering consecutive GPU architectures (e.g. A100 &rarr; H100, H100 &rarr; H200, H100 &rarr; B200):",
        style_body
    ))

    f2_data = [[Paragraph("Annual Technological Deflation (d) = 1 - ( P_older / P_newer ) ^ ( 12 / Cadence_Months )", style_formula)]]
    t_f2 = Table(f2_data, colWidths=[530])
    t_f2.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#181818")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#474747")),
        ('PADDING', (0,0), (-1,-1), 5),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ]))
    story.append(t_f2)
    story.append(Spacer(1, 5))

    story.append(Paragraph("5. Model-Implied Forward Term Structure Formulation", style_h1))
    story.append(Paragraph(
        "Forward curves in FSKU are explicitly model-implied term structures calculated dynamically from current cash spot anchors, "
        "inferred technological deflation (<font color='#38BDF8'><b>d</b></font>), and a configurable annual carry & scarcity factor (<font color='#38EF7D'><b>c</b></font>):",
        style_body
    ))

    f3_data = [[Paragraph("F(T) = S_0 * [ (1 + c) * (1 - d) ] ^ T &nbsp;&nbsp;|&nbsp;&nbsp; where T = m / 12 (delivery horizon in years)", style_formula)]]
    t_f3 = Table(f3_data, colWidths=[530])
    t_f3.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#181818")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#474747")),
        ('PADDING', (0,0), (-1,-1), 5),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ]))
    story.append(t_f3)
    story.append(Spacer(1, 5))

    story.append(Paragraph(
        "<b>Term Structure Dynamics:</b> When annual tech deflation (<font face='Courier'>d ≈ 18%</font>) exceeds annual scarcity/carry (<font face='Courier'>c = 5%</font>), "
        "the forward curve displays natural backwardation (decay roll), reflecting the empirical reality of chip aging. "
        "Interquartile ranges (Q25 & Q75) provide clear confidence bands across 1M, 3M, 6M, 12M, 24M, 36M, 48M, and 60M delivery tenors.",
        style_body
    ))

    story.append(Paragraph("6. Methodology Sensitivity & Source Ablation Resilience", style_h1))
    story.append(Paragraph(
        "Institutional indices must withstand source volatility and provider dropouts. FSKU incorporates two real-time diagnostic engines:",
        style_body
    ))
    story.append(Paragraph(
        "&bull; <b>Methodology Sensitivity:</b> Computes the maximum divergence spread across all six weighting formulas to quantify outlier vulnerability.",
        style_bullet
    ))
    story.append(Paragraph(
        "&bull; <b>Source Ablation:</b> Systematically drops each provider from the dataset and calculates the resulting index delta (<font face='Courier'>Delta %</font>) to reveal single-source concentration risk.",
        style_bullet
    ))

    story.append(Paragraph("Empirical Snapshot: Benchmark Indices Across Key Accelerator SKUs", style_h2))
    empirical_rows = [
        [Paragraph("GPU SKU", style_table_header), Paragraph("VRAM", style_table_header), Paragraph("Spot Index", style_table_header), Paragraph("10% Trimmed", style_table_header), Paragraph("Provider-Bal.", style_table_header), Paragraph("12M Forward", style_table_header), Paragraph("36M Forward", style_table_header), Paragraph("Status", style_table_header)],
        [Paragraph("<b>H100 SXM</b>", style_table_cell), Paragraph("80 GB", style_table_cell), Paragraph("<b>$2.49</b>", style_table_cell), Paragraph("$3.26", style_table_cell), Paragraph("$3.16", style_table_cell), Paragraph("$2.15", style_table_cell), Paragraph("$1.60", style_table_cell), Paragraph("<font color='#38EF7D'>ACTIVE</font>", style_table_cell)],
        [Paragraph("<b>H200</b>", style_table_cell), Paragraph("141 GB", style_table_cell), Paragraph("<b>$6.30</b>", style_table_cell), Paragraph("$7.23", style_table_cell), Paragraph("$7.93", style_table_cell), Paragraph("$5.44", style_table_cell), Paragraph("$4.06", style_table_cell), Paragraph("<font color='#38EF7D'>ACTIVE</font>", style_table_cell)],
        [Paragraph("<b>B200</b>", style_table_cell), Paragraph("180 GB", style_table_cell), Paragraph("<b>$5.98</b>", style_table_cell), Paragraph("$6.28", style_table_cell), Paragraph("$6.21", style_table_cell), Paragraph("$5.16", style_table_cell), Paragraph("$3.85", style_table_cell), Paragraph("<font color='#38BDF8'>EMERGING</font>", style_table_cell)],
        [Paragraph("<b>B300</b>", style_table_cell), Paragraph("288 GB", style_table_cell), Paragraph("<b>$5.71</b>", style_table_cell), Paragraph("$5.71", style_table_cell), Paragraph("$5.71", style_table_cell), Paragraph("$4.93", style_table_cell), Paragraph("$3.68", style_table_cell), Paragraph("<font color='#38BDF8'>EMERGING</font>", style_table_cell)],
        [Paragraph("<b>A100 SXM</b>", style_table_cell), Paragraph("80 GB", style_table_cell), Paragraph("<b>$1.29</b>", style_table_cell), Paragraph("$1.32", style_table_cell), Paragraph("$1.34", style_table_cell), Paragraph("$1.11", style_table_cell), Paragraph("$0.83", style_table_cell), Paragraph("<font color='#38EF7D'>ACTIVE</font>", style_table_cell)],
        [Paragraph("<b>MI300X</b>", style_table_cell), Paragraph("192 GB", style_table_cell), Paragraph("<b>$2.40</b>", style_table_cell), Paragraph("$2.40", style_table_cell), Paragraph("$2.40", style_table_cell), Paragraph("$2.07", style_table_cell), Paragraph("$1.55", style_table_cell), Paragraph("<font color='#F59E0B'>INDICATIVE</font>", style_table_cell)],
    ]
    t_emp = Table(empirical_rows, colWidths=[75, 45, 65, 65, 75, 70, 70, 65])
    t_emp.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#181818")),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#141414")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#474747")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#262626")),
        ('PADDING', (0,0), (-1,-1), 4),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t_emp)
    story.append(Spacer(1, 8))

    story.append(Paragraph("7. Software Architecture & Open Governance", style_h1))
    story.append(Paragraph(
        "FSKU is engineered as a zero-dependency, high-throughput compute intelligence platform in Python 3.10+ with:",
        style_body
    ))
    story.append(Paragraph("&bull; <b>Embedded NoSQL Storage (FSKUDb):</b> Thread-safe document collections with atomic persistence and SHA-256 snapshot audits.", style_bullet))
    story.append(Paragraph("&bull; <b>Resync Engine:</b> Asynchronous multi-provider polling adapters with automated diff detection.", style_bullet))
    story.append(Paragraph("&bull; <b>FastAPI REST Server & Rich CLI:</b> High-performance JSON endpoints, CSV streaming exports, and terminal visualization.", style_bullet))
    story.append(Paragraph("&bull; <b>Apache 2.0 License:</b> Permissive, patent-protected open-source licensing to ensure universal enterprise and research adoption.", style_bullet))

    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=0.75, color=colors.HexColor("#474747"), spaceBefore=2, spaceAfter=6))
    story.append(Paragraph(
        "<b>Repository & Reference Code:</b> <font color='#38BDF8'>https://github.com/nativ-x/fsku</font> &nbsp;|&nbsp; "
        "<b>Built by:</b> NATIVX (<font color='#FFFFFF'>nativx.net</font>) &nbsp;|&nbsp; "
        "<b>Inquiries:</b> <font color='#FFFFFF'>research@nativx.net</font>",
        style_meta
    ))

    doc.build(story, canvasmaker=NumberedCanvas, onFirstPage=draw_page_decorations, onLaterPages=draw_page_decorations)
    print(f"Successfully generated FSKU White Paper PDF: {filename}")

if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent.parent / "docs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_pdf = str(out_dir / "FSKU_White_Paper.pdf")
    build_pdf(out_pdf)
