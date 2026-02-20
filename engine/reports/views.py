from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from .models import WeeklyReport
from .serializers import WeeklyReportSerializer


class WeeklyReportViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WeeklyReport.objects.all()
    serializer_class = WeeklyReportSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "week_start", "week_end"]
