from rest_framework import serializers
from .models import WeeklyReport


class WeeklyReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeeklyReport
        fields = [
            "id", "week_start", "week_end", "status", "executive_summary",
            "signals_section", "opportunities", "threats", "tools_to_test",
            "project_ideas", "recommended_actions", "kpis", "full_markdown",
            "signal_count", "source_count", "processing_run",
            "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]
