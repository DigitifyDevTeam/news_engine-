from django.contrib import admin
from .models import Article, ContentChunk


# Completely disable Article admin to avoid Python 3.14 template issues
# Use custom view at /admin/articles/custom/ instead

# Temporarily disable ContentChunk admin to debug
# @admin.register(ContentChunk)
# class ContentChunkAdmin(admin.ModelAdmin):
#     list_display = ("article", "index", "token_count")
#     readonly_fields = ("created_at", "updated_at")
#     ordering = ("article", "index")
