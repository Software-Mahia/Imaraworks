from rest_framework import serializers

from .models import AuditLog


class AuditEntrySerializer(serializers.ModelSerializer):
    """One entry in a request's history."""

    actor_username = serializers.CharField(source='actor.username', read_only=True)

    class Meta:
        model = AuditLog
        fields = ['id', 'action', 'actor_username', 'details', 'timestamp']


class AuditLogSerializer(AuditEntrySerializer):
    """One entry in the whole log, for ADMIN: who did what, when, to which request.

    Leaves out `details` (amounts, vendors, rejection reasons): admins have no
    access to payment data (agreed on #2). The fields are listed one by one, so
    a field added to AuditLog later stays hidden until someone adds it here.
    """

    class Meta(AuditEntrySerializer.Meta):
        fields = ['id', 'action', 'actor_username', 'timestamp', 'request']
