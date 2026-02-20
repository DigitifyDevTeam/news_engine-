from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from .models import Signal
from .serializers import SignalSerializer


class SignalViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Signal.objects.select_related("article", "chunk", "processing_run").all()
    serializer_class = SignalSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["category", "article", "processing_run", "is_validated"]
