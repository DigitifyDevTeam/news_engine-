import logging

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from core.exceptions import ScrapingError
from .models import Source
from .serializers import SourceSerializer
from .tasks import scrape_source
from .services import ScrapingService

logger = logging.getLogger(__name__)


def _is_broker_unavailable(exc):
    """True if the exception is Redis/Celery broker connection failure."""
    msg = str(exc).lower()
    return (
        "connection" in msg
        or "redis" in msg
        or "10061" in msg
        or "refused" in msg
        or "operationalerror" in type(exc).__name__.lower()
    )


class SourceViewSet(viewsets.ModelViewSet):
    queryset = Source.objects.all()
    serializer_class = SourceSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["source_type", "scrape_strategy", "is_active"]

    @action(detail=True, methods=["post"], url_path="scrape")
    def scrape(self, request, pk=None):
        """
        Scrape this source. Uses Celery if Redis is available; otherwise runs
        synchronously so the UI works without a worker. Returns 200 with
        articles_count when run sync, 202 with task_id when queued.
        """
        source = self.get_object()

        try:
            result = scrape_source.delay(source.pk)
            return Response(
                {"task_id": str(result.id), "source_id": source.pk, "queued": True},
                status=status.HTTP_202_ACCEPTED,
            )
        except Exception as e:
            if not _is_broker_unavailable(e):
                logger.exception("Scrape task enqueue failed: %s", e)
                return Response(
                    {"error": str(e), "detail": "Could not queue scrape task."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            # Fallback: run scrape synchronously (no Redis/Celery required)
            try:
                service = ScrapingService()
                articles = service.scrape_source(source)
                return Response(
                    {
                        "source_id": source.pk,
                        "articles_count": len(articles),
                        "queued": False,
                        "message": f"Scraped {len(articles)} article(s).",
                    },
                    status=status.HTTP_200_OK,
                )
            except ScrapingError as e:
                return Response(
                    {"error": str(e), "detail": "Scraping failed."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            except Exception as e:
                logger.exception("Sync scrape failed: %s", e)
                return Response(
                    {"error": str(e), "detail": "Scraping failed."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
