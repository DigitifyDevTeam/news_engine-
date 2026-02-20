from rest_framework import serializers
from .models import Signal


class SignalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Signal
        fields = [
            "id", "article", "chunk", "processing_run", "category", "title",
            "description", "relevance_score", "confidence", "entities",
            "is_validated", "raw_llm_output", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]
