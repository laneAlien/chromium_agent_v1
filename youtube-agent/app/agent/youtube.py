"""YouTube browsing and decision helpers."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import quote_plus

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from .models import AgentSettings, VideoDecision, YouTubeTask

YOUTUBE_HOME_URL = "https://www.youtube.com/"
YOUTUBE_SEARCH_URL = "https://www.youtube.com/results?search_query={query}"


@dataclass
class CandidateVideo:
    video_id: str
    title: str
    video_url: str
    duration_seconds: int
    is_short: bool
    source: str


@dataclass
class DecisionPayload:
    video_id: str
    title: str
    video_url: str
    duration_seconds: int
    action: str
    reason: str
    watched_seconds: int


def build_watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def _safe_video_id(video_url: str) -> str:
    match = re.search(r"[?&]v=([a-zA-Z0-9_-]{6,})", video_url)
    if match:
        return match.group(1)
    short_match = re.search(r"/shorts/([a-zA-Z0-9_-]{6,})", video_url)
    if short_match:
        return short_match.group(1)
    return f"unknown-{abs(hash(video_url))}"


def _parse_duration_to_seconds(raw_duration: str) -> int:
    cleaned = raw_duration.strip().replace(" ", "")
    if not cleaned:
        return 0
    parts = cleaned.split(":")
    if not all(part.isdigit() for part in parts):
        return 0

    total = 0
    for part in parts:
        total = (total * 60) + int(part)
    return total


def _collect_candidates(page, source: str, max_count: int) -> list[CandidateVideo]:
    candidates: list[CandidateVideo] = []
    containers = page.locator("ytd-rich-item-renderer, ytd-video-renderer, ytd-grid-video-renderer")
    count = min(containers.count(), max_count)

    for index in range(count):
        item = containers.nth(index)
        link = item.locator("a#video-title").first
        href = link.get_attribute("href")
        if not href:
            continue

        if href.startswith("/"):
            video_url = f"https://www.youtube.com{href}"
        else:
            video_url = href

        try:
            link_text = link.inner_text(timeout=1000)
        except PlaywrightTimeoutError:
            link_text = ""
        title = (link.get_attribute("title") or link_text or "Untitled video").strip()

        duration_label = ""
        duration_locator = item.locator("span.ytd-thumbnail-overlay-time-status-renderer")
        if duration_locator.count() > 0:
            try:
                duration_label = duration_locator.first.inner_text(timeout=1000).strip()
            except PlaywrightTimeoutError:
                duration_label = ""

        duration_seconds = _parse_duration_to_seconds(duration_label)
        is_short = "/shorts/" in video_url

        candidates.append(
            CandidateVideo(
                video_id=_safe_video_id(video_url),
                title=title,
                video_url=video_url,
                duration_seconds=duration_seconds,
                is_short=is_short,
                source=source,
            )
        )

    return candidates


def _load_targets(page, tasks: Iterable[YouTubeTask]) -> list[CandidateVideo]:
    all_candidates: list[CandidateVideo] = []

    page.goto(YOUTUBE_HOME_URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(1500)
    all_candidates.extend(_collect_candidates(page, source="home_feed", max_count=12))

    for task in tasks:
        query = quote_plus(task.query.strip() or task.title.strip())
        page.goto(YOUTUBE_SEARCH_URL.format(query=query), wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1000)
        all_candidates.extend(_collect_candidates(page, source=f"search:{task.query}", max_count=6))

    deduped: dict[str, CandidateVideo] = {}
    for candidate in all_candidates:
        deduped.setdefault(candidate.video_url, candidate)
    return list(deduped.values())


def run_youtube_flow(settings: AgentSettings) -> list[DecisionPayload]:
    """Run a YouTube-only watch/skip flow and return all decision records."""
    user_data_dir = Path(os.getenv("PLAYWRIGHT_USER_DATA_DIR", "/tmp/playwright-user-data"))
    user_data_dir.mkdir(parents=True, exist_ok=True)

    tasks = list(YouTubeTask.objects.order_by("-created_at")[:10])
    decisions: list[DecisionPayload] = []

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=False,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
            viewport={"width": 1366, "height": 768},
        )

        try:
            page = context.new_page()
            try:
                candidates = _load_targets(page, tasks)
            except PlaywrightTimeoutError:
                candidates = []

            shorts_consumed = 0
            for candidate in candidates:
                reason = ""
                action = VideoDecision.Action.SKIP
                watched_seconds = 0

                if candidate.is_short and shorts_consumed >= settings.shorts_limit:
                    reason = "Skipped short: shorts limit reached"
                elif candidate.duration_seconds and candidate.duration_seconds < settings.min_duration_seconds:
                    reason = "Skipped: below minimum duration"
                else:
                    action = VideoDecision.Action.WATCH
                    reason = f"Watched from {candidate.source}"
                    watched_seconds = candidate.duration_seconds or settings.min_duration_seconds
                    if candidate.is_short:
                        shorts_consumed += 1

                    page.goto(candidate.video_url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(500)

                decisions.append(
                    DecisionPayload(
                        video_id=candidate.video_id,
                        title=candidate.title,
                        video_url=candidate.video_url,
                        duration_seconds=candidate.duration_seconds,
                        action=action,
                        reason=reason,
                        watched_seconds=watched_seconds,
                    )
                )

            if not decisions:
                decisions.append(
                    DecisionPayload(
                        video_id="no-candidates",
                        title="No YouTube candidates found",
                        video_url=YOUTUBE_HOME_URL,
                        duration_seconds=settings.min_duration_seconds,
                        action=VideoDecision.Action.SKIP,
                        reason="No videos discovered from feed/search targets",
                        watched_seconds=0,
                    )
                )
        finally:
            context.close()

    return decisions
