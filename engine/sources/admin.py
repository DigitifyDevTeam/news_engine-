from django.contrib import admin
from .models import Source


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ("name", "url", "source_type", "scrape_strategy", "is_active", "last_scraped_at")
    list_filter = ("source_type", "scrape_strategy", "is_active")
    search_fields = ("name", "url")
    readonly_fields = ("last_scraped_at", "created_at", "updated_at")
