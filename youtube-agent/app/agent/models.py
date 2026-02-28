from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class YouTubeTask(models.Model):
    title = models.CharField(max_length=255)
    query = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.title


class Session(models.Model):
    class Mode(models.TextChoices):
        IMITATE = "imitate", "Imitate"
        OPTIMIZE = "optimize", "Optimize"

    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        FAILED = "failed", "Failed"

    planned_start = models.DateTimeField()
    planned_end = models.DateTimeField()
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_end = models.DateTimeField(null=True, blank=True)
    mode = models.CharField(max_length=16, choices=Mode.choices, default=Mode.IMITATE)
    summary = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PLANNED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Session #{self.pk} ({self.mode}/{self.status})"


class VideoDecision(models.Model):
    class Action(models.TextChoices):
        WATCH = "watch", "Watch"
        SKIP = "skip", "Skip"

    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="video_decisions")
    video_id = models.CharField(max_length=64)
    video_url = models.URLField()
    title = models.CharField(max_length=300)
    duration_seconds = models.PositiveIntegerField()
    action = models.CharField(max_length=8, choices=Action.choices)
    reason = models.TextField(blank=True)
    watched_seconds = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.video_id} ({self.action})"


class InterestProfile(models.Model):
    category_weights = models.JSONField(default=dict, blank=True)
    topic_weights = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"InterestProfile #{self.pk}"


class AgentSettings(models.Model):
    class Mode(models.TextChoices):
        IMITATE = "imitate", "Imitate"
        OPTIMIZE = "optimize", "Optimize"

    session_window_start = models.TimeField(help_text="Daily session window start time")
    session_window_end = models.TimeField(help_text="Daily session window end time")
    shorts_limit = models.PositiveIntegerField(default=10)
    min_duration_seconds = models.PositiveIntegerField(default=60)
    sessions_per_day_min = models.PositiveIntegerField(
        default=2,
        validators=[MinValueValidator(2), MaxValueValidator(3)],
    )
    sessions_per_day_max = models.PositiveIntegerField(
        default=3,
        validators=[MinValueValidator(2), MaxValueValidator(3)],
    )
    mode = models.CharField(max_length=16, choices=Mode.choices, default=Mode.IMITATE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return "Agent Settings"
