import os
import sys

from django.apps import AppConfig

_scheduler_started = False
_MANAGEMENT_COMMANDS_TO_SKIP = {"makemigrations", "migrate", "collectstatic", "shell", "test"}


class AgentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "agent"

    def ready(self):
        global _scheduler_started
        if _scheduler_started:
            return

        if os.environ.get("DJANGO_ENABLE_AGENT_SCHEDULER", "1") in {"0", "false", "False"}:
            return

        if len(sys.argv) > 1 and sys.argv[1] in _MANAGEMENT_COMMANDS_TO_SKIP:
            return

        if os.environ.get("RUN_MAIN") not in {None, "true"}:
            return

        from .scheduler import start_scheduler

        start_scheduler()
        _scheduler_started = True
