from django.db import models
from django.core.exceptions import ValidationError
from core.models import TimestampedModel
from core.utils import normalize_text

STATUS_PENDING = "pending"
STATUS_CHUNKED = "chunked"
STATUS_EXTRACTED = "extracted"
STATUS_FAILED = "failed"
PROCESSING_STATUS_CHOICES = [
    (STATUS_PENDING, "Pending"),
    (STATUS_CHUNKED, "Chunked"),
    (STATUS_EXTRACTED, "Extracted"),
    (STATUS_FAILED, "Failed"),
]


class Article(TimestampedModel):
    """Raw scraped content, normalized and stored. No raw HTML."""

    STATUS_PENDING = STATUS_PENDING
    STATUS_CHUNKED = STATUS_CHUNKED
    STATUS_EXTRACTED = STATUS_EXTRACTED
    STATUS_FAILED = STATUS_FAILED

    source = models.ForeignKey(
        "sources.Source", on_delete=models.CASCADE, related_name="articles"
    )
    url = models.URLField(unique=True)
    title = models.CharField(max_length=512)
    raw_text = models.TextField()
    summary = models.TextField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    word_count = models.PositiveIntegerField(default=0)
    language = models.CharField(max_length=10, default="fr")
    processing_status = models.CharField(
        max_length=20,
        choices=PROCESSING_STATUS_CHOICES,
        default=STATUS_PENDING,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["title"]),
            models.Index(fields=["source", "created_at"]),
        ]

    def __str__(self):
        return self.title[:60] + ("..." if len(self.title) > 60 else "")
    
    def clean(self):
        """Validate and normalize title before saving."""
        if self.title:
            # Normalize title for better duplicate detection
            self.title = normalize_text(self.title).strip()
            
            # Check for duplicates by title and source (case-insensitive)
            if self.source:
                existing_duplicates = Article.objects.filter(
                    title__iexact=self.title,
                    source=self.source
                ).exclude(pk=self.pk)
                
                if existing_duplicates.exists():
                    raise ValidationError(
                        f"Article with title '{self.title}' already exists from source '{self.source.name}'. "
                        f"Duplicate IDs: {[a.pk for a in existing_duplicates]}"
                    )
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    @classmethod
    def find_duplicates_by_title(cls, title, threshold=0.85):
        """
        Find articles with similar titles using fuzzy matching.
        Returns a queryset of potential duplicates.
        """
        from difflib import SequenceMatcher
        
        normalized_title = normalize_text(title).strip()
        duplicates = []
        
        # Get all articles and compare titles
        for article in cls.objects.all():
            if article.pk == getattr(cls, '_current_pk', None):
                continue
                
            similarity = SequenceMatcher(
                None, 
                normalized_title.lower(), 
                article.title.lower()
            ).ratio()
            
            if similarity >= threshold:
                duplicates.append(article)
        
        return duplicates
    
    @classmethod
    def remove_duplicates_by_title(cls, threshold=0.85, keep_newest=True):
        """
        Remove duplicate articles based on title similarity.
        
        Args:
            threshold: Similarity threshold (0.0-1.0)
            keep_newest: If True, keep newest article; if False, keep oldest
        
        Returns:
            dict: Statistics about removal operation
        """
        from difflib import SequenceMatcher
        from collections import defaultdict
        
        # Group articles by similar titles
        title_groups = defaultdict(list)
        processed = set()
        
        articles = cls.objects.all().order_by('-created_at' if keep_newest else 'created_at')
        
        for i, article in enumerate(articles):
            if article.pk in processed:
                continue
                
            # Find similar articles
            similar_articles = [article]
            for other_article in articles[i+1:]:
                if other_article.pk in processed:
                    continue
                    
                similarity = SequenceMatcher(
                    None,
                    article.title.lower(),
                    other_article.title.lower()
                ).ratio()
                
                if similarity >= threshold:
                    similar_articles.append(other_article)
                    processed.add(other_article.pk)
            
            if len(similar_articles) > 1:
                title_groups[article.title] = similar_articles
            processed.add(article.pk)
        
        # Remove duplicates, keeping the specified one
        removed_count = 0
        removed_ids = []
        
        for title, articles_list in title_groups.items():
            if len(articles_list) > 1:
                # Keep first article (newest or oldest based on parameter)
                keep_article = articles_list[0]
                remove_articles = articles_list[1:]
                
                for article in remove_articles:
                    removed_ids.append(article.pk)
                    article.delete()
                    removed_count += 1
                
                print(f"Kept: {keep_article.title[:50]}... (ID: {keep_article.pk})")
                print(f"Removed {len(remove_articles)} duplicates")
        
        return {
            'groups_found': len(title_groups),
            'articles_removed': removed_count,
            'removed_ids': removed_ids
        }


class ContentChunk(TimestampedModel):
    """Tokenized text slice sent to the LLM."""

    article = models.ForeignKey(
        Article, on_delete=models.CASCADE, related_name="chunks"
    )
    index = models.PositiveIntegerField()
    text = models.TextField()
    token_count = models.PositiveIntegerField()

    class Meta:
        ordering = ["article", "index"]
        unique_together = [["article", "index"]]

    def __str__(self):
        return f"Chunk {self.index} of {self.article_id}"
