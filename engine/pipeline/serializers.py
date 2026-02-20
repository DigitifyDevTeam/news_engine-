from rest_framework import serializers
from .models import ProcessingRun


class ProcessingRunSerializer(serializers.ModelSerializer):
    progress_percent = serializers.SerializerMethodField()
    progress_message = serializers.SerializerMethodField()
    report_id = serializers.SerializerMethodField()

    class Meta:
        model = ProcessingRun
        fields = [
            "id", "run_type", "status", "started_at", "completed_at",
            "articles_scraped", "signals_extracted", "error_log", "config",
            "progress_phase", "progress_total", "progress_current",
            "progress_percent", "progress_message", "report_id",
            "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_progress_percent(self, obj):
        if obj.progress_total and obj.progress_total > 0:
            pct = int(100 * obj.progress_current / obj.progress_total)
            if obj.status == ProcessingRun.RUN_STATUS_RUNNING and obj.progress_phase == "report":
                return max(pct, 95)
            return min(100, pct)
        if obj.status == ProcessingRun.RUN_STATUS_RUNNING:
            if obj.progress_phase == "report":
                return 95
            return 0
        if obj.status == ProcessingRun.RUN_STATUS_COMPLETED:
            return 100
        return 0

    def get_progress_message(self, obj):
        phase = obj.progress_phase or "pending"
        pct = self.get_progress_percent(obj)
        if phase == "extraction":
            if obj.progress_total:
                return f"Extraction des signaux : {obj.progress_current}/{obj.progress_total} articles ({pct}%)"
            return "Préparation de l'extraction…"
        if phase == "report":
            return "Génération du rapport PDF…"
        if phase == "completed":
            return "Pipeline terminé — rapport prêt"
        if obj.status == ProcessingRun.RUN_STATUS_FAILED:
            return "Échec du pipeline"
        if obj.status == ProcessingRun.RUN_STATUS_RUNNING:
            return f"En cours… {pct}%"
        return ""

    def get_report_id(self, obj):
        return obj.config.get("report_id") if isinstance(obj.config, dict) else None


class PipelineRunTriggerSerializer(serializers.Serializer):
    run_type = serializers.ChoiceField(choices=["scrape", "extract", "report", "full"], default="full")
