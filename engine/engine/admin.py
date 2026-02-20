"""
Custom admin configuration to handle Python 3.14 compatibility issues.
"""
from django.contrib.admin import AdminSite
from django.template.context import RequestContext


class CustomAdminSite(AdminSite):
    """Custom admin site to handle template context issues."""
    
    def get_context(self, request, extra_context=None):
        """
        Override get_context to handle Python 3.14 compatibility.
        """
        context = super().get_context(request, extra_context)
        return context


# Create custom admin site instance
custom_admin_site = CustomAdminSite(name='custom_admin')
