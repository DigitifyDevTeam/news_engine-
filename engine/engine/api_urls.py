"""
API URL routing: registers all viewsets under /api/.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from sources.views import SourceViewSet
from articles.views import ArticleViewSet
from intelligence.views import SignalViewSet
from reports.views import WeeklyReportViewSet
from pipeline.views import ProcessingRunViewSet

router = DefaultRouter()
router.register("sources", SourceViewSet, basename="source")
router.register("articles", ArticleViewSet, basename="article")
router.register("signals", SignalViewSet, basename="signal")
router.register("reports", WeeklyReportViewSet, basename="report")
router.register("pipeline/runs", ProcessingRunViewSet, basename="processingrun")

urlpatterns = [
    path("", include(router.urls)),
]
