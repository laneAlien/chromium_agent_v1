from django.contrib import admin

from .models import AgentSettings, InterestProfile, Session, VideoDecision, YouTubeTask


@admin.register(YouTubeTask)
class YouTubeTaskAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "query", "created_at")
    search_fields = ("title", "query")


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "mode",
        "status",
        "planned_start",
        "planned_end",
        "actual_start",
        "actual_end",
        "updated_at",
    )
    list_filter = ("mode", "status", "planned_start", "created_at")
    search_fields = ("summary",)


@admin.register(VideoDecision)
class VideoDecisionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "session",
        "video_id",
        "title",
        "action",
        "duration_seconds",
        "watched_seconds",
        "created_at",
    )
    list_filter = ("action", "created_at", "session__mode", "session__status")
    search_fields = ("video_id", "video_url", "title", "reason")


@admin.register(InterestProfile)
class InterestProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "updated_at")
    list_filter = ("created_at", "updated_at")


@admin.register(AgentSettings)
class AgentSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "session_window_start",
        "session_window_end",
        "shorts_limit",
        "min_duration_seconds",
        "sessions_per_day_min",
        "sessions_per_day_max",
        "mode",
        "updated_at",
    )
    list_filter = ("mode", "updated_at")
