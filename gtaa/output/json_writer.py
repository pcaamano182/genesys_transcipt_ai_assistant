from __future__ import annotations

import json
from pathlib import Path
from typing import List

from gtaa.processor.gemini import AnalysisResult


def write_json(results: List[AnalysisResult], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = []
    for r in results:
        data.append({
            "conversation_id": r.conversation_id,
            "start_time": r.start_time.isoformat() if r.start_time else None,
            "end_time": r.end_time.isoformat() if r.end_time else None,
            "duration_seconds": r.duration_seconds,
            "queue_id": r.queue_id,
            "queue_name": r.queue_name,
            "transcript_text": r.transcript_text,
            "analysis": r.analysis,
            "prompt_used": r.prompt_used,
            "error": r.error,
            "metadata": r.metadata,
        })
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return output_path
