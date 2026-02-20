from rest_framework import serializers
from .models import Article, ContentChunk


class ContentChunkSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentChunk
        fields = ["id", "index", "text", "token_count"]


class ArticleSerializer(serializers.ModelSerializer):
    chunks = ContentChunkSerializer(many=True, read_only=True)

    class Meta:
        model = Article
        fields = [
            "id", "source", "url", "title", "raw_text", "summary",
            "published_at", "word_count", "language", "processing_status",
            "chunks", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class ArticleListSerializer(serializers.ModelSerializer):
    """Lighter serializer for list views (no raw_text, no chunks)."""
    class Meta:
        model = Article
        fields = [
            "id", "source", "url", "title", "summary", "published_at",
            "word_count", "language", "processing_status", "created_at",
        ]
