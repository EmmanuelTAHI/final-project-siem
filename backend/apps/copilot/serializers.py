from rest_framework import serializers

from .models import CopilotConversation, CopilotMessage


class CopilotMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = CopilotMessage
        fields = ["id", "role", "content", "tool_calls", "created_at"]


class CopilotConversationSerializer(serializers.ModelSerializer):
    messages = CopilotMessageSerializer(many=True, read_only=True)

    class Meta:
        model = CopilotConversation
        fields = ["id", "title", "created_at", "updated_at", "messages"]


class CopilotConversationBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = CopilotConversation
        fields = ["id", "title", "created_at", "updated_at"]
