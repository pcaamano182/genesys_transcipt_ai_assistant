"""
Batch orchestration: fetch transcripts and process them concurrently with Gemini.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Iterator, List, Optional

import PureCloudPlatformClientV2 as gc  # type: ignore

from gtaa.config.settings import ProcessingSettings
from gtaa.genesys.conversations import ConversationSummary
from gtaa.genesys.transcripts import get_transcript
from gtaa.processor.gemini import AnalysisResult, GeminiProcessor


def process_conversations(
    api_client: gc.ApiClient,
    conversations: List[ConversationSummary],
    gemini: GeminiProcessor,
    user_prompt: str,
    settings: ProcessingSettings,
    progress_callback: Optional[Callable[[int, int, AnalysisResult], None]] = None,
) -> Iterator[AnalysisResult]:
    """
    For each conversation: download transcript + analyze with Gemini.
    Uses ThreadPoolExecutor for concurrency.
    Yields AnalysisResult as they complete.
    """
    total = len(conversations)
    completed = 0

    def _process_one(conversation: ConversationSummary) -> AnalysisResult:
        transcript = get_transcript(api_client, conversation)
        if transcript is None:
            from gtaa.genesys.transcripts import Transcript
            transcript = Transcript(
                conversation_id=conversation.conversation_id,
                communication_id=None,
                turns=[],
            )
        return gemini.analyze(
            conversation=conversation,
            transcript=transcript,
            user_prompt=user_prompt,
            max_transcript_chars=settings.max_transcript_chars,
        )

    with ThreadPoolExecutor(max_workers=settings.max_workers) as executor:
        futures = {executor.submit(_process_one, conv): conv for conv in conversations}

        for future in as_completed(futures):
            completed += 1
            try:
                result = future.result()
            except Exception as e:
                conv = futures[future]
                result = AnalysisResult(
                    conversation_id=conv.conversation_id,
                    start_time=conv.start_time,
                    end_time=conv.end_time,
                    duration_seconds=conv.duration_ms // 1000,
                    queue_id=conv.queue_id,
                    queue_name=conv.queue_name,
                    participants=conv.participants,
                    transcript_text="",
                    analysis=f"Processing error: {str(e)}",
                    prompt_used=user_prompt,
                    error=str(e),
                )

            if progress_callback:
                progress_callback(completed, total, result)

            yield result
