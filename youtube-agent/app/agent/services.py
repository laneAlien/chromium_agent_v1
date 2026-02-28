"""Service-layer helpers for agent business logic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time

from django.db import transaction
from django.utils import timezone

from .models import AgentSettings, Session, VideoDecision, YouTubeTask
from .youtube import build_watch_url


@dataclass
class DecisionPayload:
    video_id: str
    title: str
    duration_seconds: int
    action: str
    reason: str
    watched_seconds: int


def format_search_query(query: str) -> str:
    return query.strip()


def _build_decisions(settings: AgentSettings) -> list[DecisionPayload]:
    tasks = list(YouTubeTask.objects.order_by("-created_at")[: settings.shorts_limit])
    decisions: list[DecisionPayload] = []
    for index, task in enumerate(tasks):
        duration = settings.min_duration_seconds + (index * 15)
        watch = index % 2 == 0
        decisions.append(
            DecisionPayload(
                video_id=f"task-{task.id}",
                title=task.title,
                duration_seconds=duration,
                action=VideoDecision.Action.WATCH if watch else VideoDecision.Action.SKIP,
                reason="Matches current profile" if watch else "Lower relevance score",
                watched_seconds=duration if watch else 0,
            )
        )

    if decisions:
        return decisions

    # Keep lifecycle traces and persistence even when no tasks exist.
    return [
        DecisionPayload(
            video_id="fallback-1",
            title="Fallback recommendation",
            duration_seconds=settings.min_duration_seconds,
            action=VideoDecision.Action.WATCH,
            reason="No queued tasks; using fallback recommendation",
            watched_seconds=settings.min_duration_seconds,
        )
    ]


@transaction.atomic
def run_session(session_id: int) -> Session:
    """Orchestrate one session and persist lifecycle + all video decisions."""
    session = Session.objects.select_for_update().get(pk=session_id)
    session.status = Session.Status.RUNNING
    session.actual_start = timezone.now()
    session.summary = "Session started"
    session.save(update_fields=["status", "actual_start", "summary", "updated_at"])

    settings, _ = AgentSettings.objects.get_or_create(
        pk=1,
        defaults={
            "window_one_start": time(hour=9, minute=0),
            "window_one_end": time(hour=12, minute=0),
            "window_two_start": time(hour=13, minute=0),
            "window_two_end": time(hour=17, minute=0),
            "window_three_start": time(hour=18, minute=0),
            "window_three_end": time(hour=22, minute=0),
        },
    )

    try:
        decisions = _build_decisions(settings)
        for decision in decisions:
            VideoDecision.objects.create(
                session=session,
                video_id=decision.video_id,
                video_url=build_watch_url(decision.video_id),
                title=decision.title,
                duration_seconds=decision.duration_seconds,
                action=decision.action,
                reason=decision.reason,
                watched_seconds=decision.watched_seconds,
            )

        session.status = Session.Status.COMPLETED
        session.actual_end = timezone.now()
        session.summary = f"Processed {len(decisions)} videos"
        session.save(update_fields=["status", "actual_end", "summary", "updated_at"])
    except Exception as exc:
        session.status = Session.Status.FAILED
        session.actual_end = timezone.now()
        session.summary = f"Session failed: {exc}"
        session.save(update_fields=["status", "actual_end", "summary", "updated_at"])
        raise

    return session
