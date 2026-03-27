"""
Query Genesys Cloud conversations with filters.
Uses Analytics API: POST /api/v2/analytics/conversations/details/query
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Iterator, List, Optional

import PureCloudPlatformClientV2 as gc  # type: ignore
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from gtaa.config.settings import GenesysSettings


@dataclass
class ConversationFilter:
    start_date: date
    end_date: date
    queue_ids: List[str] = field(default_factory=list)
    user_ids: List[str] = field(default_factory=list)
    division_ids: List[str] = field(default_factory=list)
    min_duration_seconds: Optional[int] = None


@dataclass
class ConversationSummary:
    conversation_id: str
    start_time: datetime
    end_time: Optional[datetime]
    duration_ms: int
    participants: List[dict]
    queue_id: Optional[str]
    queue_name: Optional[str]


def _is_rate_limit(exc: Exception) -> bool:
    return hasattr(exc, "status") and exc.status == 429


def _build_query_body(filters: ConversationFilter, page: int, page_size: int) -> gc.ConversationQuery:
    """Build the analytics query body from user filters."""
    # Format: YYYY-MM-DDTHH:MM:SS.000Z/YYYY-MM-DDTHH:MM:SS.000Z
    start_dt = datetime.combine(filters.start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_dt = datetime.combine(filters.end_date, datetime.max.time().replace(microsecond=0)).replace(tzinfo=timezone.utc)
    interval = f"{start_dt.strftime('%Y-%m-%dT%H:%M:%S.000Z')}/{end_dt.strftime('%Y-%m-%dT%H:%M:%S.000Z')}"

    segment_filters = [
        gc.SegmentDetailQueryFilter(
            type="and",
            predicates=[
                gc.SegmentDetailQueryPredicate(
                    type="dimension",
                    dimension="mediaType",
                    operator="matches",
                    value="voice",
                )
            ],
        )
    ]

    conversation_filters = []

    if filters.queue_ids:
        conversation_filters.append(
            gc.ConversationDetailQueryFilter(
                type="or",
                predicates=[
                    gc.ConversationDetailQueryPredicate(
                        type="dimension",
                        dimension="queueId",
                        operator="matches",
                        value=qid,
                    )
                    for qid in filters.queue_ids
                ],
            )
        )

    if filters.division_ids:
        conversation_filters.append(
            gc.ConversationDetailQueryFilter(
                type="or",
                predicates=[
                    gc.ConversationDetailQueryPredicate(
                        type="dimension",
                        dimension="divisionId",
                        operator="matches",
                        value=did,
                    )
                    for did in filters.division_ids
                ],
            )
        )

    query = gc.ConversationQuery(
        interval=interval,
        order="asc",
        order_by="conversationStart",
        segment_filters=segment_filters,
        conversation_filters=conversation_filters if conversation_filters else None,
        paging=gc.PagingSpec(page_size=page_size, page_number=page),
    )

    return query


def query_conversations(
    api_client: gc.ApiClient,
    filters: ConversationFilter,
    settings: GenesysSettings,
) -> Iterator[ConversationSummary]:
    """
    Iterate over all conversations matching the filters, handling pagination.
    Yields ConversationSummary objects.
    """
    analytics_api = gc.ConversationsApi(api_client)
    page = 1
    total_yielded = 0

    while True:
        query_body = _build_query_body(filters, page, settings.page_size)

        @retry(
            retry=retry_if_exception(_is_rate_limit),
            wait=wait_exponential(multiplier=2, min=2, max=30),
            stop=stop_after_attempt(5),
        )
        def _execute():
            return analytics_api.post_analytics_conversations_details_query(query_body)

        result = _execute()

        if not result or not result.conversations:
            break

        for conv in result.conversations:
            participants = []
            queue_id = None
            queue_name = None

            if conv.participants:
                for p in conv.participants:
                    p_info = {
                        "participant_id": p.participant_id,
                        "participant_name": getattr(p, "participant_name", None),
                        "purpose": getattr(p, "purpose", None),
                        "user_id": getattr(p, "user_id", None),
                    }
                    participants.append(p_info)
                    if p_info["purpose"] == "acd" and p.sessions:
                        for s in p.sessions:
                            if getattr(s, "queue_id", None):
                                queue_id = s.queue_id
                                break

            start_time = conv.conversation_start
            end_time = getattr(conv, "conversation_end", None)

            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            if isinstance(end_time, str):
                end_time = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

            duration_ms = getattr(conv, "conversation_metrics", None)
            if duration_ms:
                duration_ms = getattr(duration_ms, "duration_ms", 0) or 0
            else:
                if start_time and end_time:
                    duration_ms = int((end_time - start_time).total_seconds() * 1000)
                else:
                    duration_ms = 0

            if filters.min_duration_seconds and duration_ms < filters.min_duration_seconds * 1000:
                continue

            yield ConversationSummary(
                conversation_id=conv.conversation_id,
                start_time=start_time,
                end_time=end_time,
                duration_ms=duration_ms,
                participants=participants,
                queue_id=queue_id,
                queue_name=queue_name,
            )
            total_yielded += 1

        # Check if there are more pages
        total_hits = getattr(result, "total_hits", None)
        if total_hits is not None and total_yielded >= total_hits:
            break
        if len(result.conversations) < settings.page_size:
            break

        page += 1
