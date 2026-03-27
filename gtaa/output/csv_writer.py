from __future__ import annotations

import csv
from pathlib import Path
from typing import List

from gtaa.processor.gemini import AnalysisResult

_COLUMNS = [
    "conversation_id",
    "start_time",
    "end_time",
    "duration_seconds",
    "duration_formatted",
    "queue_id",
    "queue_name",
    "analysis",
    "error",
]


def write_csv(results: List[AnalysisResult], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            writer.writerow({
                "conversation_id": r.conversation_id,
                "start_time": r.start_time.isoformat() if r.start_time else "",
                "end_time": r.end_time.isoformat() if r.end_time else "",
                "duration_seconds": r.duration_seconds,
                "duration_formatted": r.duration_formatted,
                "queue_id": r.queue_id or "",
                "queue_name": r.queue_name or "",
                "analysis": r.analysis,
                "error": r.error or "",
            })
    return output_path
