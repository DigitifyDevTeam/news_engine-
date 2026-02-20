from rest_framework import serializers
from .models import Source


class SourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Source
        fields = [
            "id", "name", "url", "source_type", "scrape_strategy",
            "frequency_minutes", "is_active", "css_selector",
            "last_scraped_at", "config", "created_at", "updated_at",
        ]
        read_only_fields = ["last_scraped_at", "created_at", "updated_at"]
