from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from .models import Article
from .serializers import ArticleSerializer, ArticleListSerializer


class ArticleViewSet(viewsets.ModelViewSet):
    queryset = Article.objects.select_related("source").prefetch_related("chunks").all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["source", "processing_status", "language"]

    def get_serializer_class(self):
        if self.action == "list":
            return ArticleListSerializer
        return ArticleSerializer
