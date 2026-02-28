"""Service-layer helpers for agent business logic."""

from __future__ import annotations

from datetime import time

from django.db import transaction
from django.utils import timezone

from .models import AgentSettings, Session, VideoDecision
from .youtube import run_youtube_flow


def format_search_query(query: str) -> str:
    return query.strip()


def _build_session_summary(decisions: list[VideoDecision], shorts_limit: int) -> str:
    watched = [d for d in decisions if d.action == VideoDecision.Action.WATCH]
    skipped = [d for d in decisions if d.action == VideoDecision.Action.SKIP]

    reason_counts: dict[str, int] = {}
    for decision in decisions:
        reason = decision.reason.strip() or "(no reason)"
        reason_counts[reason] = reason_counts.get(reason, 0) + 1

    watched_shorts = sum(1 for d in watched if "/shorts/" in d.video_url)
    watched_duration_total = sum(d.watched_seconds for d in watched)
    candidate_duration_total = sum(d.duration_seconds for d in decisions)

    reason_lines = [f"- {reason}: {count}" for reason, count in sorted(reason_counts.items())]

    return "\n".join(
        [
            f"Watched: {len(watched)}",
            f"Skipped: {len(skipped)}",
            f"Shorts consumed: {watched_shorts}/{shorts_limit}",
            f"Watched duration total (seconds): {watched_duration_total}",
            f"Candidate duration total (seconds): {candidate_duration_total}",
            "Reasons distribution:",
            *reason_lines,
        ]
    )


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
        decision_payloads = run_youtube_flow(settings)
        saved_decisions: list[VideoDecision] = []
        for decision in decision_payloads:
            saved_decisions.append(
                VideoDecision.objects.create(
                    session=session,
                    video_id=decision.video_id,
                    video_url=decision.video_url,
                    title=decision.title,
                    duration_seconds=decision.duration_seconds,
                    action=decision.action,
                    reason=decision.reason,
                    watched_seconds=decision.watched_seconds,
                )
            )

        session.status = Session.Status.COMPLETED
        session.actual_end = timezone.now()
        session.summary = _build_session_summary(saved_decisions, settings.shorts_limit)
        session.save(update_fields=["status", "actual_end", "summary", "updated_at"])
    except Exception as exc:
        session.status = Session.Status.FAILED
        session.actual_end = timezone.now()
        session.summary = f"Session failed: {exc}"
        session.save(update_fields=["status", "actual_end", "summary", "updated_at"])
        raise

    return session
