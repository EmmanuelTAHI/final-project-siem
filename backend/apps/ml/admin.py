from django.contrib import admin

from .models import MLModel, Prediction


@admin.register(MLModel)
class MLModelAdmin(admin.ModelAdmin):
    list_display = ("name", "version", "algorithm", "is_active", "trained_at", "training_samples")
    list_filter = ("algorithm", "is_active")
    ordering = ("-created_at",)
    readonly_fields = ("id", "created_at")
    actions = ["activate_model"]

    def activate_model(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Sélectionnez un seul modèle à activer.", level="error")
            return
        model = queryset.first()
        model.activate()
        self.message_user(request, f"Modèle '{model.name} v{model.version}' activé.")
    activate_model.short_description = "Activer le modèle sélectionné"


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = ("log", "model", "is_anomaly", "anomaly_score", "predicted_at")
    list_filter = ("is_anomaly", "model")
    ordering = ("-predicted_at",)
    readonly_fields = ("id", "predicted_at")
