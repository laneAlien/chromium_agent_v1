"""APScheduler integration for periodic agent jobs."""

from __future__ import annotations

import logging
import random
from datetime import date, datetime, time, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from django.db.models import QuerySet
from django.utils import timezone

from .models import AgentSettings, Session
from .services import run_session

logger = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None

DEFAULT_WINDOWS: tuple[tuple[time, time], ...] = (
    (time(hour=9, minute=0), time(hour=12, minute=0)),
    (time(hour=13, minute=0), time(hour=17, minute=0)),
    (time(hour=18, minute=0), time(hour=22, minute=0)),
)


def _get_or_create_settings() -> AgentSettings:
    settings, _ = AgentSettings.objects.get_or_create(
        pk=1,
        defaults={
            "window_one_start": DEFAULT_WINDOWS[0][0],
            "window_one_end": DEFAULT_WINDOWS[0][1],
            "window_two_start": DEFAULT_WINDOWS[1][0],
            "window_two_end": DEFAULT_WINDOWS[1][1],
            "window_three_start": DEFAULT_WINDOWS[2][0],
            "window_three_end": DEFAULT_WINDOWS[2][1],
        },
    )
    return settings


def _window_bounds(settings: AgentSettings) -> tuple[tuple[time, time], ...]:
    windows = (
        (settings.window_one_start, settings.window_one_end),
        (settings.window_two_start, settings.window_two_end),
        (settings.window_three_start, settings.window_three_end),
    )
    return tuple((start, end) for start, end in windows if start < end)


def _random_time_in_window(day: date, start: time, end: time) -> datetime:
    window_start = datetime.combine(day, start)
    window_end = datetime.combine(day, end)
    window_seconds = int((window_end - window_start).total_seconds())
    if window_seconds <= 0:
        return window_start
    return window_start + timedelta(seconds=random.randint(0, window_seconds))


def _pick_daily_run_times(settings: AgentSettings, day: date) -> list[datetime]:
    windows = _window_bounds(settings)
    if not windows:
        return []

    min_sessions = min(settings.sessions_per_day_min, settings.sessions_per_day_max)
    max_sessions = max(settings.sessions_per_day_min, settings.sessions_per_day_max)
    run_count = random.randint(min_sessions, max_sessions)

    selected_windows = random.sample(list(windows), k=min(run_count, len(windows)))
    run_times = [_random_time_in_window(day, start, end) for start, end in selected_windows]

    while len(run_times) < run_count:
        start, end = random.choice(windows)
        run_times.append(_random_time_in_window(day, start, end))

    return sorted(run_times)


def _schedule_session_job(session: Session) -> None:
    if _scheduler is None:
        return

    run_at = timezone.localtime(session.planned_start)
    _scheduler.add_job(
        func=run_session,
        trigger=DateTrigger(run_date=run_at),
        args=[session.id],
        id=f"session-{session.id}",
        replace_existing=True,
        misfire_grace_time=300,
    )


def _planned_sessions_for_day(day: date) -> QuerySet[Session]:
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(day, time.min), tz)
    end = timezone.make_aware(datetime.combine(day, time.max), tz)
    return Session.objects.filter(planned_start__range=(start, end))


def generate_daily_sessions(target_day: date | None = None) -> list[Session]:
    settings = _get_or_create_settings()
    day = target_day or timezone.localdate()

    if _planned_sessions_for_day(day).exists():
        return []

    sessions: list[Session] = []
    duration = timedelta(minutes=45)
    for run_time in _pick_daily_run_times(settings, day):
        tz = timezone.get_current_timezone()
        planned_start = timezone.make_aware(run_time, tz)
        session = Session.objects.create(
            planned_start=planned_start,
            planned_end=planned_start + duration,
            mode=settings.mode,
            status=Session.Status.PLANNED,
            summary="Scheduled by daily planner",
        )
        sessions.append(session)
        _schedule_session_job(session)

    return sessions


def _schedule_daily_planner() -> None:
    if _scheduler is None:
        return

    _scheduler.add_job(
        func=generate_daily_sessions,
        trigger=CronTrigger(hour=0, minute=5),
        id="daily-session-planner",
        replace_existing=True,
    )


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return

    _scheduler = BackgroundScheduler(timezone=timezone.get_current_timezone_name())
    _schedule_daily_planner()
    _scheduler.start()

    planned_today = generate_daily_sessions()
    logger.info("Scheduler initialized (%s new sessions for today)", len(planned_today))
