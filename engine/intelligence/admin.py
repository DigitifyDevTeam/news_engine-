from django.contrib import admin
from .models import Signal, PromptTemplate


@admin.register(Signal)
class SignalAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "article", "relevance_score", "confidence", "is_validated", "created_at")
    list_filter = ("category", "is_validated")
    search_fields = ("title", "description")


@admin.register(PromptTemplate)
class PromptTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "purpose", "created_at", "updated_at")
    search_fields = ("name", "purpose", "body")
