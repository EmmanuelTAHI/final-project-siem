from rest_framework import serializers
from .models import HuntingQuery, HuntingResult


class HuntingQuerySerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True, default="")

    class Meta:
        model = HuntingQuery
        fields = [
            "id", "name", "description", "query_params", "mitre_tactic", "mitre_technique",
            "last_run_at", "last_results_count", "run_count", "is_scheduled",
            "created_by", "created_by_name", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "last_run_at", "last_results_count", "run_count", "created_by"]
        extra_kwargs = {
            "description": {"required": False, "allow_blank": True},
            "mitre_tactic": {"required": False, "allow_blank": True},
            "mitre_technique": {"required": False, "allow_blank": True},
            "query_params": {"required": False},
            "is_scheduled": {"required": False},
        }

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["created_by"] = request.user
        validated_data.setdefault("query_params", {})
        return super().create(validated_data)
