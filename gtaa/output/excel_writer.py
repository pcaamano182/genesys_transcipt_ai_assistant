from __future__ import annotations

from pathlib import Path
from typing import List

from gtaa.processor.gemini import AnalysisResult


def write_excel(results: List[AnalysisResult], output_path: Path) -> Path:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "Analysis Results"

    headers = [
        "Conversation ID", "Start Time", "End Time", "Duration",
        "Queue ID", "Queue Name", "Analysis", "Error"
    ]
    header_fill = PatternFill("solid", fgColor="1F4E79")
    header_font = Font(bold=True, color="FFFFFF")

    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for row_idx, r in enumerate(results, 2):
        ws.cell(row=row_idx, column=1, value=r.conversation_id)
        ws.cell(row=row_idx, column=2, value=r.start_time.isoformat() if r.start_time else "")
        ws.cell(row=row_idx, column=3, value=r.end_time.isoformat() if r.end_time else "")
        ws.cell(row=row_idx, column=4, value=r.duration_formatted)
        ws.cell(row=row_idx, column=5, value=r.queue_id or "")
        ws.cell(row=row_idx, column=6, value=r.queue_name or "")
        analysis_cell = ws.cell(row=row_idx, column=7, value=r.analysis)
        analysis_cell.alignment = Alignment(wrap_text=True)
        ws.cell(row=row_idx, column=8, value=r.error or "")

    # Auto-size columns (capped)
    col_widths = [36, 22, 22, 12, 36, 24, 80, 30]
    for col_idx, width in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    ws.row_dimensions[1].height = 20
    ws.freeze_panes = "A2"

    wb.save(output_path)
    return output_path
