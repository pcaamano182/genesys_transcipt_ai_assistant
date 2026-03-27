from __future__ import annotations

from pathlib import Path
from typing import List

from gtaa.processor.gemini import AnalysisResult


def write_outputs(
    results: List[AnalysisResult],
    formats: List[str],
    output_dir: str,
    base_filename: str,
) -> List[Path]:
    """Write results to all requested formats. Returns list of created file paths."""
    from gtaa.output.csv_writer import write_csv
    from gtaa.output.json_writer import write_json
    from gtaa.output.excel_writer import write_excel
    from gtaa.output.pdf_writer import write_pdf

    out_dir = Path(output_dir)
    writers = {
        "csv": (write_csv, ".csv"),
        "json": (write_json, ".json"),
        "excel": (write_excel, ".xlsx"),
        "pdf": (write_pdf, ".pdf"),
    }
    created = []
    for fmt in formats:
        fmt = fmt.lower()
        if fmt not in writers:
            continue
        writer_fn, ext = writers[fmt]
        path = out_dir / f"{base_filename}{ext}"
        created.append(writer_fn(results, path))
    return created
