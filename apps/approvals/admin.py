from django.contrib import admin
from .models import Approval


@admin.register(Approval)
class ApprovalAdmin(admin.ModelAdmin):
    """Read-only: approvals are history. Only change_amount() may mark one
    superseded, and it writes an audit entry when it does."""

    list_display = ('created_at', 'request', 'approver', 'level', 'decision', 'superseded')
    list_filter = ('decision', 'level', 'superseded')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
