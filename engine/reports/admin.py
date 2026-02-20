from django.contrib import admin
from .models import WeeklyReport


@admin.register(WeeklyReport)
class WeeklyReportAdmin(admin.ModelAdmin):
    list_display = ("week_start", "week_end", "status", "signal_count", "source_count", "created_at")
    list_filter = ("status",)
    readonly_fields = ("created_at", "updated_at")
