"""
SOC Copilot — historique des conversations en langage naturel avec l'IA.
"""
import uuid

from django.db import models


class CopilotConversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="copilot_conversations",
    )
    user = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, related_name="copilot_conversations",
    )
    title = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title or f"Conversation {self.id}"


class CopilotMessage(models.Model):
    ROLE_CHOICES = [("user", "Utilisateur"), ("assistant", "Assistant")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        CopilotConversation, on_delete=models.CASCADE, related_name="messages",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    tool_calls = models.JSONField(default=list, blank=True, help_text="Outils invoqués par l'IA pour répondre.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"[{self.role}] {self.content[:60]}"
