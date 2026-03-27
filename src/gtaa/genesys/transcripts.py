"""
Download and parse Genesys Speech & Text Analytics transcripts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import httpx
import PureCloudPlatformClientV2 as gc  # type: ignore
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from gtaa.genesys.conversations import ConversationSummary


@dataclass
class TranscriptTurn:
    speaker_role: str        # "agent" | "customer" | "unknown"
    speaker_name: Optional[str]
    text: str
    start_time_ms: Optional[int]
    end_time_ms: Optional[int]


@dataclass
class Transcript:
    conversation_id: str
    communication_id: Optional[str]
    turns: List[TranscriptTurn] = field(default_factory=list)
    raw: dict = field(default_factory=dict)

    def to_plain_text(self) -> str:
        """Flatten transcript turns to plain text for AI processing."""
        lines = []
        for turn in self.turns:
            role = turn.speaker_role.upper()
            name = f" ({turn.speaker_name})" if turn.speaker_name else ""
            lines.append(f"{role}{name}: {turn.text}")
        return "\n".join(lines)

    @property
    def is_empty(self) -> bool:
        return not self.turns


def _is_rate_limit(exc: Exception) -> bool:
    return hasattr(exc, "status") and exc.status == 429


def _parse_transcript_json(data: dict, conversation_id: str, communication_id: Optional[str]) -> Transcript:
    """Parse the transcript JSON from Genesys into a Transcript object."""
    turns: List[TranscriptTurn] = []

    # Genesys transcript format has a "transcripts" array with "phrases"
    transcript_items = data.get("transcripts", [data])

    for item in transcript_items:
        phrases = item.get("phrases", [])
        for phrase in phrases:
            channel = phrase.get("channel", 0)
            # channel 0 = customer, channel 1 = agent (typical Genesys convention)
            speaker_role = "agent" if channel == 1 else "customer"
            speaker_name = phrase.get("participantPurpose") or phrase.get("participantName")
            words = phrase.get("words", [])
            text = " ".join(w.get("word", "") for w in words if w.get("word"))

            if not text.strip():
                continue

            start_ms = int(phrase.get("offsetMs", 0))
            duration_ms = int(phrase.get("durationMs", 0))

            turns.append(
                TranscriptTurn(
                    speaker_role=speaker_role,
                    speaker_name=speaker_name,
                    text=text.strip(),
                    start_time_ms=start_ms,
                    end_time_ms=start_ms + duration_ms if duration_ms else None,
                )
            )

    return Transcript(
        conversation_id=conversation_id,
        communication_id=communication_id,
        turns=turns,
        raw=data,
    )


def get_transcript(
    api_client: gc.ApiClient,
    conversation: ConversationSummary,
) -> Optional[Transcript]:
    """
    Fetch the transcript for a conversation using Speech & Text Analytics API.
    Returns None if no transcript is available.
    """
    speech_api = gc.SpeechTextAnalyticsApi(api_client)

    @retry(
        retry=retry_if_exception(_is_rate_limit),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        stop=stop_after_attempt(5),
    )
    def _get_transcript_urls():
        return speech_api.get_speechandtextanalytics_conversation(conversation.conversation_id)

    try:
        result = _get_transcript_urls()
    except Exception:
        return None

    if not result:
        return None

    # The API returns a list of transcript file URLs
    transcript_urls = getattr(result, "transcript_urls", None)
    if not transcript_urls:
        return None

    # Use first available transcript URL
    transcript_url_obj = transcript_urls[0]
    url = getattr(transcript_url_obj, "url", None)
    communication_id = getattr(transcript_url_obj, "communication_id", None)

    if not url:
        return None

    # Download the transcript JSON from the pre-signed URL
    try:
        response = httpx.get(url, timeout=30, follow_redirects=True)
        response.raise_for_status()
        data = response.json()
    except Exception:
        return None

    return _parse_transcript_json(data, conversation.conversation_id, communication_id)
