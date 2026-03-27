from __future__ import annotations

from pathlib import Path
from typing import List

from gtaa.processor.gemini import AnalysisResult


def write_pdf(results: List[AnalysisResult], output_path: Path) -> Path:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    h2_style = styles["Heading2"]
    normal_style = styles["Normal"]
    meta_style = ParagraphStyle("meta", parent=normal_style, fontSize=9, textColor=colors.grey)
    analysis_style = ParagraphStyle("analysis", parent=normal_style, fontSize=10, leading=14)

    story = []
    story.append(Paragraph("Genesys Transcript Analysis Report", title_style))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(f"Total conversations analyzed: {len(results)}", meta_style))
    story.append(Spacer(1, 1 * cm))

    for i, r in enumerate(results, 1):
        story.append(Paragraph(f"{i}. Conversation: {r.conversation_id}", h2_style))

        meta_rows = [
            ["Start", r.start_time.strftime("%Y-%m-%d %H:%M:%S UTC") if r.start_time else "N/A"],
            ["Duration", r.duration_formatted],
            ["Queue", r.queue_name or r.queue_id or "N/A"],
        ]
        if r.error:
            meta_rows.append(["Error", r.error])

        meta_table = Table(meta_rows, colWidths=[3 * cm, 12 * cm])
        meta_table.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 0.3 * cm))

        story.append(Paragraph("<b>Analysis:</b>", normal_style))
        # Escape HTML special chars for ReportLab
        analysis_text = (r.analysis
                         .replace("&", "&amp;")
                         .replace("<", "&lt;")
                         .replace(">", "&gt;")
                         .replace("\n", "<br/>"))
        story.append(Paragraph(analysis_text, analysis_style))
        story.append(Spacer(1, 0.8 * cm))

        if i < len(results):
            story.append(PageBreak())

    doc.build(story)
    return output_path
