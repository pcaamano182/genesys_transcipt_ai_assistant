"""
Vertex AI Gemini integration for transcript analysis.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from gtaa.config.settings import GoogleSettings
from gtaa.genesys.conversations import ConversationSummary
from gtaa.genesys.transcripts import Transcript

_DEFAULT_SYSTEM_PROMPT = """\
You are an expert call center analyst. Analyze the following call transcript and respond to the user's request.
Be concise, structured, and focus on actionable insights.
If the transcript is empty or unintelligible, respond with: "No transcript available."
"""

_MAX_CHARS_PER_CHUNK = 80_000  # ~20k tokens, safe for Gemini 1.5 Pro


@dataclass
class AnalysisResult:
    conversation_id: str
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    duration_seconds: int
    queue_id: Optional[str]
    queue_name: Optional[str]
    participants: list
    transcript_text: str
    analysis: str
    prompt_used: str
    metadata: dict = field(default_factory=dict)
    error: Optional[str] = None

    @property
    def duration_formatted(self) -> str:
        m, s = divmod(self.duration_seconds, 60)
        return f"{m:02d}:{s:02d}"


def _build_prompt(user_prompt: str, transcript_text: str, conversation: ConversationSummary) -> str:
    metadata_block = (
        f"Conversation ID: {conversation.conversation_id}\n"
        f"Start: {conversation.start_time}\n"
        f"Duration: {conversation.duration_ms // 1000}s\n"
        f"Queue: {conversation.queue_name or conversation.queue_id or 'N/A'}\n"
    )
    return (
        f"## Conversation Metadata\n{metadata_block}\n"
        f"## Transcript\n{transcript_text}\n\n"
        f"## Task\n{user_prompt}"
    )


def _chunk_transcript(text: str, max_chars: int = _MAX_CHARS_PER_CHUNK) -> list[str]:
    """Split a long transcript into overlapping chunks."""
    if len(text) <= max_chars:
        return [text]
    chunks = []
    overlap = max_chars // 10
    start = 0
    while start < len(text):
        end = start + max_chars
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


class GeminiProcessor:
    def __init__(self, settings: GoogleSettings):
        self.settings = settings
        self._model = None

    def _get_model(self):
        if self._model is None:
            from vertexai.generative_models import GenerativeModel, GenerationConfig  # type: ignore
            self._model = GenerativeModel(
                model_name=self.settings.model,
                system_instruction=_DEFAULT_SYSTEM_PROMPT,
            )
        return self._model

    @retry(
        wait=wait_exponential(multiplier=2, min=2, max=60),
        stop=stop_after_attempt(4),
    )
    def _call_gemini(self, prompt: str) -> str:
        from vertexai.generative_models import GenerationConfig  # type: ignore
        model = self._get_model()
        response = model.generate_content(
            prompt,
            generation_config=GenerationConfig(
                temperature=0.2,
                max_output_tokens=2048,
            ),
        )
        return response.text

    def analyze(
        self,
        conversation: ConversationSummary,
        transcript: Transcript,
        user_prompt: str,
        max_transcript_chars: int = _MAX_CHARS_PER_CHUNK,
    ) -> AnalysisResult:
        """Analyze a single transcript with Gemini. Returns AnalysisResult."""
        transcript_text = transcript.to_plain_text() if not transcript.is_empty else ""
        duration_seconds = conversation.duration_ms // 1000

        if transcript.is_empty:
            return AnalysisResult(
                conversation_id=conversation.conversation_id,
                start_time=conversation.start_time,
                end_time=conversation.end_time,
                duration_seconds=duration_seconds,
                queue_id=conversation.queue_id,
                queue_name=conversation.queue_name,
                participants=conversation.participants,
                transcript_text="",
                analysis="No transcript available for this conversation.",
                prompt_used=user_prompt,
                error="empty_transcript",
            )

        # Truncate or chunk if too long
        if len(transcript_text) > max_transcript_chars:
            transcript_text = transcript_text[:max_transcript_chars] + "\n[TRANSCRIPT TRUNCATED]"

        prompt = _build_prompt(user_prompt, transcript_text, conversation)

        try:
            analysis = self._call_gemini(prompt)
            error = None
        except Exception as e:
            analysis = f"Error during analysis: {str(e)}"
            error = str(e)

        return AnalysisResult(
            conversation_id=conversation.conversation_id,
            start_time=conversation.start_time,
            end_time=conversation.end_time,
            duration_seconds=duration_seconds,
            queue_id=conversation.queue_id,
            queue_name=conversation.queue_name,
            participants=conversation.participants,
            transcript_text=transcript_text,
            analysis=analysis,
            prompt_used=user_prompt,
            error=error,
        )
