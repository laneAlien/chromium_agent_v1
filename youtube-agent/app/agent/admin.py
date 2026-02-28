from django.contrib import admin

from .models import YouTubeTask


@admin.register(YouTubeTask)
class YouTubeTaskAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "query", "created_at")
    search_fields = ("title", "query")
