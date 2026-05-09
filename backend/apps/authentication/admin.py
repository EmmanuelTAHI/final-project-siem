from django.contrib import admin

from .models import LinkedAccount, LoginConfirmation, ProviderLoginEvent, SecurityNotification


@admin.register(LinkedAccount)
class LinkedAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "provider", "provider_email", "status", "last_polled_at", "linked_at")
    list_filter = ("provider", "status")
    search_fields = ("user__email", "provider_email", "provider_user_id")
    readonly_fields = ("linked_at", "updated_at", "last_polled_at",
                       "access_token_encrypted", "refresh_token_encrypted")


@admin.register(ProviderLoginEvent)
class ProviderLoginEventAdmin(admin.ModelAdmin):
    list_display = ("linked_account", "event_type", "occurred_at", "ip_address",
                    "browser", "os", "geo_country", "risk_score")
    list_filter = ("event_type", "is_known_device", "is_known_location")
    search_fields = ("linked_account__provider_email", "ip_address", "provider_event_id")
    readonly_fields = ("received_at",)


@admin.register(LoginConfirmation)
class LoginConfirmationAdmin(admin.ModelAdmin):
    list_display = ("user", "linked_account", "status", "ip_address", "geo_country",
                    "created_at", "expires_at", "responded_at")
    list_filter = ("status",)
    search_fields = ("user__email",)
    readonly_fields = ("created_at",)


@admin.register(SecurityNotification)
class SecurityNotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "kind", "level", "title", "is_read", "created_at")
    list_filter = ("kind", "level", "is_read")
    search_fields = ("user__email", "title", "body")
    readonly_fields = ("created_at",)
