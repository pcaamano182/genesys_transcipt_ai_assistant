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

_MAX_CHARS_PER_CHUNK = 80_000

# Models to try in order of preference
_FALLBACK_MODELS = [
    "gemini-2.5-flash-preview-05-20",
    "gemini-2.0-flash-001",
    "gemini-2.0-flash",
    "gemini-1.5-flash-002",
    "gemini-1.5-pro-002",
]


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


def _discover_model_rest(configured_model: str, project_id: str, location: str, credentials) -> str:
    """
    Test model availability by sending a minimal generateContent request via REST.
    No SDK retries, no loops — one POST per candidate, 15s timeout.
    Returns the first model that responds successfully.
    """
    import httpx
    from google.auth.transport.requests import Request  # type: ignore

    if not credentials.token or credentials.expired:
        credentials.refresh(Request())

    headers = {
        "Authorization": f"Bearer {credentials.token}",
        "Content-Type": "application/json",
    }
    # Minimal request body — just ask the model to say "ok"
    body = {
        "contents": [{"role": "user", "parts": [{"text": "Say OK"}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 5},
    }

    candidates = [configured_model] + [m for m in _FALLBACK_MODELS if m != configured_model]

    for model_name in candidates:
        url = (
            f"https://{location}-aiplatform.googleapis.com/v1/"
            f"projects/{project_id}/locations/{location}/"
            f"publishers/google/models/{model_name}:generateContent"
        )
        try:
            r = httpx.post(url, headers=headers, json=body, timeout=15)
            if r.status_code == 200:
                return model_name
            # Show why it failed
            error_msg = ""
            try:
                error_msg = r.json().get("error", {}).get("message", r.text[:100])
            except Exception:
                error_msg = r.text[:100]
            print(f"    {model_name}: HTTP {r.status_code} - {error_msg}")
        except Exception as e:
            print(f"    {model_name}: {type(e).__name__}: {e}")

    raise RuntimeError(
        f"No Gemini model available in project '{project_id}' / location '{location}'.\n"
        f"Tried: {', '.join(candidates)}\n"
        "Check that:\n"
        "  1. Vertex AI API is enabled in your GCP project\n"
        "  2. The service account has the 'Vertex AI User' role\n"
        "  3. The location/region is correct"
    )


class GeminiProcessor:
    def __init__(self, settings: GoogleSettings, credentials=None):
        self.settings = settings
        self._credentials = credentials
        self._model = None
        self._resolved_model_name: Optional[str] = None

    def _get_model(self):
        if self._model is None:
            from vertexai.generative_models import GenerativeModel  # type: ignore

            if self._resolved_model_name is None and self._credentials is not None:
                print(f"  Checking model availability ({self.settings.model})...")
                self._resolved_model_name = _discover_model_rest(
                    configured_model=self.settings.model,
                    project_id=self.settings.project_id,
                    location=self.settings.location,
                    credentials=self._credentials,
                )
                if self._resolved_model_name != self.settings.model:
                    print(f"  Model '{self.settings.model}' not available, using: {self._resolved_model_name}")
                else:
                    print(f"  Model OK: {self._resolved_model_name}")
            elif self._resolved_model_name is None:
                # No credentials for discovery, use configured model directly
                self._resolved_model_name = self.settings.model

            self._model = GenerativeModel(
                model_name=self._resolved_model_name,
                system_instruction=_DEFAULT_SYSTEM_PROMPT,
            )
        return self._model

    @retry(
        wait=wait_exponential(multiplier=2, min=2, max=60),
        stop=stop_after_attempt(4),
        reraise=True,
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

        # Truncate if too long
        if len(transcript_text) > max_transcript_chars:
            transcript_text = transcript_text[:max_transcript_chars] + "\n[TRANSCRIPT TRUNCATED]"

        prompt = _build_prompt(user_prompt, transcript_text, conversation)

        try:
            analysis = self._call_gemini(prompt)
            error = None
        except Exception as e:
            err_type = type(e).__name__
            err_detail = str(e)
            if hasattr(e, 'message'):
                err_detail = e.message
            if hasattr(e, 'code'):
                err_detail = f"HTTP {e.code}: {err_detail}"
            analysis = f"Error during analysis ({err_type}): {err_detail}"
            error = f"{err_type}: {err_detail}"

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
