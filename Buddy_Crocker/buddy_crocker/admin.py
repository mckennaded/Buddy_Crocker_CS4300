"""
admin.py allows admin access to the included models
"""
from django.contrib import admin, messages
from .models import Allergen, Recipe, Ingredient, Pantry, Profile, ScanRateLimit

admin.site.register([Allergen, Recipe, Ingredient, Pantry, Profile])

# Register ScanRateLimit model
@admin.register(ScanRateLimit)
class ScanRateLimitAdmin(admin.ModelAdmin):
    """Admin interface for ScanRateLimit model."""

    list_display = ['user', 'timestamp', 'ip_address']
    list_filter = ['timestamp', 'user']
    search_fields = ['user__username', 'ip_address']
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        """Disable manual creation of scan records."""
        return False

    actions = ['cleanup_old_scans']

    @admin.action(description='Clean up scans older than 7 days')
    def cleanup_old_scans(self, request, _queryset):
        """Admin action to clean up old scan records."""
        deleted_count = ScanRateLimit.cleanup_old_records(days=7)
        messages.success(
            request,
            f'Successfully deleted {deleted_count} old scan record(s).'
        )
