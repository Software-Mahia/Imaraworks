from rest_framework import serializers

from .models import AuditLog


class AuditEntrySerializer(serializers.ModelSerializer):
    """One entry in a request's history."""

    actor_username = serializers.CharField(source='actor.username', read_only=True)

    class Meta:
        model = AuditLog
        fields = ['id', 'action', 'actor_username', 'details', 'timestamp']


class AuditLogSerializer(AuditEntrySerializer):
    """One entry in the whole log: the same as history, plus which request."""

    class Meta(AuditEntrySerializer.Meta):
        fields = AuditEntrySerializer.Meta.fields + ['request']
