import threading

from django.conf import settings
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import ProcessingRun
from .serializers import ProcessingRunSerializer, PipelineRunTriggerSerializer
from .tasks import (
    run_full_pipeline,
    run_scraping_pipeline,
    run_extraction_pipeline,
    run_report_generation,
)


class ProcessingRunViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ProcessingRun.objects.all()
    serializer_class = ProcessingRunSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["run_type", "status"]

    @action(detail=False, methods=["post"], url_path="run")
    def trigger_run(self, request):
        """Manually trigger a pipeline run. POST with body: {"run_type": "full"|"scrape"|"extract"|"report"}."""
        try:
            data = request.data if hasattr(request, "data") else {}
            ser = PipelineRunTriggerSerializer(data=data)
            ser.is_valid(raise_exception=True)
            run_type = ser.validated_data.get("run_type", "full")

            if run_type == "full":
                # Create run so we can return processing_run_id for progress polling
                run = ProcessingRun.objects.create(
                    run_type=ProcessingRun.RUN_TYPE_FULL,
                    status=ProcessingRun.RUN_STATUS_RUNNING,
                    started_at=timezone.now(),
                    progress_phase="extraction",
                )
                if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
                    def run_in_background():
                        run_full_pipeline(run_id=run.id)

                    thread = threading.Thread(target=run_in_background, daemon=True)
                    thread.start()
                    return Response(
                        {"task_id": "background", "run_type": run_type, "processing_run_id": run.id},
                        status=status.HTTP_202_ACCEPTED,
                    )
                result = run_full_pipeline.delay(run_id=run.id)
                return Response(
                    {"task_id": str(result.id), "run_type": run_type, "processing_run_id": run.id},
                    status=status.HTTP_202_ACCEPTED,
                )
            elif run_type == "scrape":
                result = run_scraping_pipeline.delay()
            elif run_type == "extract":
                result = run_extraction_pipeline.delay()
            elif run_type == "report":
                result = run_report_generation.delay()
            else:
                return Response({"error": "invalid run_type"}, status=status.HTTP_400_BAD_REQUEST)

            return Response(
                {"task_id": str(result.id), "run_type": run_type},
                status=status.HTTP_202_ACCEPTED,
            )
        except Exception as e:
            return Response(
                {"error": f"Pipeline trigger failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
