"""
Vertex AI / Generative Language API integration for transcript analysis.

Supports two backends (auto-detected):
  1. Vertex AI publisher models (aiplatform.googleapis.com)
  2. Generative Language API (generativelanguage.googleapis.com)

The processor tries both endpoints and uses whichever responds first.
All calls go through REST (httpx) — no SDK dependency for generation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Tuple

import httpx
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

_FALLBACK_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.5-flash-preview-05-20",
    "gemini-2.0-flash-001",
    "gemini-1.5-flash-002",
    "gemini-1.5-pro-002",
]

# Vertex AI regions to try if the configured one doesn't have models
_FALLBACK_REGIONS = [
    "us-central1",
    "us-east4",
    "us-west1",
    "europe-west1",
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


# ---------------------------------------------------------------------------
# REST-based generation (no SDK dependency)
# ---------------------------------------------------------------------------

def _get_access_token(credentials) -> str:
    """Refresh and return the access token from service account credentials."""
    from google.auth.transport.requests import Request  # type: ignore
    if not credentials.token or credentials.expired:
        credentials.refresh(Request())
    return credentials.token


def _build_vertex_url(model: str, project: str, location: str) -> str:
    return (
        f"https://{location}-aiplatform.googleapis.com/v1/"
        f"projects/{project}/locations/{location}/"
        f"publishers/google/models/{model}:generateContent"
    )


def _build_genai_url(model: str) -> str:
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _build_request_body(
    prompt: str,
    system_instruction: str = _DEFAULT_SYSTEM_PROMPT,
    temperature: float = 0.2,
    max_output_tokens: int = 2048,
) -> dict:
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
        },
    }
    if system_instruction:
        body["systemInstruction"] = {"parts": [{"text": system_instruction}]}
    return body


def _parse_response(data: dict) -> str:
    """Extract generated text from the API response."""
    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError(f"No candidates in response: {json.dumps(data)[:300]}")
    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        raise RuntimeError(f"No parts in response: {json.dumps(data)[:300]}")
    return parts[0].get("text", "")


def _discover_endpoint(
    configured_model: str,
    project_id: str,
    configured_location: str,
    credentials,
) -> Tuple[str, str]:
    """
    Try to find a working endpoint + model combination.
    Returns (url_template, model_name) where url_template is either 'vertex' or 'genai'.

    Tries:
      1. Vertex AI in configured region
      2. Vertex AI in fallback regions
      3. Generative Language API (generativelanguage.googleapis.com)
    """
    token = _get_access_token(credentials)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    test_body = {
        "contents": [{"role": "user", "parts": [{"text": "Say OK"}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 5},
    }

    candidates = [configured_model] + [m for m in _FALLBACK_MODELS if m != configured_model]

    # --- Try Vertex AI (configured region first, then fallbacks) ---
    regions = [configured_location] + [r for r in _FALLBACK_REGIONS if r != configured_location]

    for region in regions:
        for model_name in candidates:
            url = _build_vertex_url(model_name, project_id, region)
            try:
                r = httpx.post(url, headers=headers, json=test_body, timeout=15)
                if r.status_code == 200:
                    print(f"    OK: Vertex AI / {region} / {model_name}")
                    return f"vertex:{region}", model_name
                # Only log first model per region to avoid noise
                if model_name == candidates[0]:
                    try:
                        msg = r.json().get("error", {}).get("message", "")[:80]
                    except Exception:
                        msg = r.text[:80]
                    print(f"    Vertex AI / {region}: HTTP {r.status_code} - {msg}")
            except httpx.TimeoutException:
                if model_name == candidates[0]:
                    print(f"    Vertex AI / {region}: timeout")
                break  # If the region times out, skip remaining models for this region
            except Exception:
                break

    # --- Try Generative Language API ---
    print("    Trying Generative Language API (generativelanguage.googleapis.com)...")
    for model_name in candidates:
        url = _build_genai_url(model_name)
        try:
            r = httpx.post(url, headers=headers, json=test_body, timeout=15)
            if r.status_code == 200:
                print(f"    OK: Generative Language API / {model_name}")
                return "genai", model_name
            try:
                msg = r.json().get("error", {}).get("message", "")[:80]
            except Exception:
                msg = r.text[:80]
            print(f"    GenAI / {model_name}: HTTP {r.status_code} - {msg}")
        except Exception as e:
            print(f"    GenAI / {model_name}: {type(e).__name__}")

    raise RuntimeError(
        f"No working Gemini endpoint found.\n"
        f"Models tried: {', '.join(candidates)}\n"
        f"Regions tried: {', '.join(regions)}\n"
        "Also tried: generativelanguage.googleapis.com\n\n"
        "Check that at least ONE of these APIs is enabled in your GCP project:\n"
        "  - Vertex AI API (for aiplatform.googleapis.com)\n"
        "  - Generative Language API (for generativelanguage.googleapis.com)\n"
        "And that the service account has the appropriate role."
    )


# ---------------------------------------------------------------------------
# Processor
# ---------------------------------------------------------------------------

class GeminiProcessor:
    def __init__(self, settings: GoogleSettings, credentials=None):
        self.settings = settings
        self._credentials = credentials
        self._backend: Optional[str] = None       # "vertex:{region}" or "genai"
        self._model_name: Optional[str] = None
        self._discovered = False

    def _ensure_discovery(self):
        """Run endpoint discovery once."""
        if self._discovered:
            return
        self._discovered = True

        if self._credentials is None:
            # No credentials — fall back to configured model name (SDK-based)
            self._model_name = self.settings.model
            self._backend = f"vertex:{self.settings.location}"
            return

        print(f"  Discovering available Gemini endpoint...")
        self._backend, self._model_name = _discover_endpoint(
            configured_model=self.settings.model,
            project_id=self.settings.project_id,
            configured_location=self.settings.location,
            credentials=self._credentials,
        )
        print(f"  Using: {self._backend} / {self._model_name}")

    def _generate_rest(self, prompt: str, system_instruction: str = _DEFAULT_SYSTEM_PROMPT) -> str:
        """Call Gemini via REST API."""
        self._ensure_discovery()

        token = _get_access_token(self._credentials)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        body = _build_request_body(prompt, system_instruction)

        if self._backend.startswith("vertex:"):
            region = self._backend.split(":", 1)[1]
            url = _build_vertex_url(self._model_name, self.settings.project_id, region)
        else:
            url = _build_genai_url(self._model_name)

        r = httpx.post(url, headers=headers, json=body, timeout=120)

        if r.status_code != 200:
            try:
                msg = r.json().get("error", {}).get("message", r.text[:200])
            except Exception:
                msg = r.text[:200]
            raise RuntimeError(f"Gemini API error (HTTP {r.status_code}): {msg}")

        return _parse_response(r.json())

    @retry(
        wait=wait_exponential(multiplier=2, min=2, max=60),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def _call_gemini(self, prompt: str) -> str:
        return self._generate_rest(prompt)

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
