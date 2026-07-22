"""
Serializers pour les règles de corrélation.
"""
from rest_framework import serializers

from .models import CorrelationRule, RuleMatch


class CorrelationRuleSerializer(serializers.ModelSerializer):
    created_by_email = serializers.CharField(
        source="created_by.email", read_only=True, allow_null=True
    )
    matches_count = serializers.SerializerMethodField()
    alert_count = serializers.SerializerMethodField()
    rule_type = serializers.SerializerMethodField()
    last_triggered = serializers.SerializerMethodField()

    class Meta:
        model = CorrelationRule
        fields = [
            "id",
            "name",
            "description",
            "is_active",
            "severity",
            "rule_type",
            "condition_logic",
            "alert_title_template",
            "mitre_tactic",
            "mitre_technique",
            "compliance_controls",
            "created_by",
            "created_by_email",
            "created_at",
            "updated_at",
            "matches_count",
            "alert_count",
            "last_triggered",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_matches_count(self, obj):
        return obj.matches.count()

    def get_alert_count(self, obj):
        return obj.matches.count()

    def get_rule_type(self, obj):
        cl = obj.condition_logic or {}
        return cl.get("type", "threshold")

    def get_last_triggered(self, obj):
        last = obj.matches.order_by("-matched_at").values_list("matched_at", flat=True).first()
        return last.isoformat() if last else None


class CorrelationRuleCreateSerializer(serializers.ModelSerializer):
    """
    Accepte aussi `rule_type` au niveau racine — il est injecté automatiquement
    dans `condition_logic.type` pour rester compatible avec le moteur de
    corrélation (qui attend `type` dans la config JSON).
    """

    rule_type = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = CorrelationRule
        fields = [
            "name",
            "description",
            "is_active",
            "severity",
            "rule_type",
            "condition_logic",
            "alert_title_template",
            "mitre_tactic",
            "mitre_technique",
            "compliance_controls",
        ]
        extra_kwargs = {
            "alert_title_template": {"required": False, "allow_blank": True},
            "description": {"required": False, "allow_blank": True},
            "mitre_tactic": {"required": False, "allow_null": True, "allow_blank": True},
            "mitre_technique": {"required": False, "allow_null": True, "allow_blank": True},
            "compliance_controls": {"required": False},
        }

    def to_internal_value(self, data):
        result = super().to_internal_value(data)
        rule_type = result.pop("rule_type", None) or data.get("rule_type")
        cond = result.get("condition_logic") or {}
        if not isinstance(cond, dict):
            cond = {}
        if rule_type and not cond.get("type"):
            cond["type"] = rule_type
        result["condition_logic"] = cond
        return result

    def validate_condition_logic(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "condition_logic doit être un objet JSON."
            )
        return value

    def validate(self, attrs):
        cond = attrs.get("condition_logic") or {}
        if not cond.get("type"):
            raise serializers.ValidationError({
                "rule_type": "Le type de règle est requis (threshold, impossible_travel, time_based, sequence...)."
            })
        # Génère un alert_title_template par défaut si absent
        if not attrs.get("alert_title_template"):
            name = attrs.get("name") or self.instance.name if self.instance else "Règle"
            attrs["alert_title_template"] = f"[{name}] détection sur {{user_email}} ({{source_ip}})"
        return attrs


class RuleMatchSerializer(serializers.ModelSerializer):
    rule_name = serializers.CharField(source="rule.name", read_only=True)

    class Meta:
        model = RuleMatch
        fields = ["id", "rule", "rule_name", "alert", "matched_at"]
        read_only_fields = fields
