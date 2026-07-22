from rest_framework import serializers
from .models import BlockedIP, Playbook, PlaybookExecution


class BlockedIPSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlockedIP
        fields = ["id", "ip_address", "reason", "source", "is_active", "expires_at", "created_at"]
        read_only_fields = ["id", "created_at"]


class PlaybookSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True, default="")

    class Meta:
        model = Playbook
        fields = [
            "id", "name", "description", "trigger_type", "trigger_conditions",
            "actions", "is_active", "execution_count", "created_by", "created_by_name",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "execution_count", "created_by", "created_at", "updated_at"]

    def create(self, validated_data):
        request_user = self.context["request"].user
        validated_data["created_by"] = request_user
        validated_data["organization"] = request_user.organization
        return super().create(validated_data)


class PlaybookExecutionSerializer(serializers.ModelSerializer):
    playbook_name = serializers.CharField(source="playbook.name", read_only=True)
    alert_title = serializers.CharField(source="alert.title", read_only=True, default="")
    duration_seconds = serializers.FloatField(read_only=True)

    class Meta:
        model = PlaybookExecution
        fields = [
            "id", "playbook", "playbook_name", "alert", "alert_title",
            "status", "actions_taken", "error_message", "triggered_by",
            "started_at", "finished_at", "duration_seconds",
        ]
        read_only_fields = ["id", "started_at", "finished_at"]
