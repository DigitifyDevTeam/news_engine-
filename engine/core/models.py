from django.db import models
from django.utils import timezone


class TimestampedModel(models.Model):
    """Abstract base model adding created_at and updated_at."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
    
    def __copy__(self):
        """Fix for Python 3.14 compatibility with Django admin."""
        # Create a simple copy without calling super().__copy__()
        import copy
        return copy.copy(self)
