from rest_framework import serializers

from .models import Organization


class OrganizationSerializer(serializers.ModelSerializer):
    user_count = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            "id", "name", "slug", "plan", "is_active", "is_platform_internal",
            "user_count", "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_user_count(self, obj):
        return obj.users.count()
