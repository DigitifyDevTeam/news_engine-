from django.contrib import admin
from .models import ProcessingRun


@admin.register(ProcessingRun)
class ProcessingRunAdmin(admin.ModelAdmin):
    list_display = ("id", "run_type", "status", "started_at", "completed_at", "articles_scraped", "signals_extracted")
    list_filter = ("run_type", "status")
    readonly_fields = ("started_at", "completed_at", "created_at", "updated_at", "error_log")
