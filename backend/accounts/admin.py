from django.contrib import admin

from .models import (
    AccountRole,
    AccountNotification,
    BillingWebhookEvent,
    EmailVerificationRequest,
    FeatureEntitlement,
    MembershipProfile,
    SubscriptionPlan,
    UsageLimit,
    UsageRecord,
    UserSubscription,
    UserToolWorkspace,
)


@admin.register(AccountRole)
class AccountRoleAdmin(admin.ModelAdmin):
    list_display = ['code', 'label', 'can_access_dashboard', 'is_super_admin', 'is_active']
    list_filter = ['can_access_dashboard', 'is_super_admin', 'is_active']
    search_fields = ['code', 'label', 'description']


@admin.register(MembershipProfile)
class MembershipProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'effective_tier', 'access_role', 'auth_provider', 'email_verified', 'premium_until']
    list_filter = ['tier', 'access_role', 'auth_provider', 'email_verified']
    search_fields = ['user__username', 'user__email', 'display_name', 'organization']


@admin.register(FeatureEntitlement)
class FeatureEntitlementAdmin(admin.ModelAdmin):
    list_display = ['label', 'code', 'free_enabled', 'premium_enabled', 'is_active']
    list_filter = ['free_enabled', 'premium_enabled', 'is_active']
    search_fields = ['label', 'code', 'description']


@admin.register(UserToolWorkspace)
class UserToolWorkspaceAdmin(admin.ModelAdmin):
    list_display = ['user', 'tool_key', 'updated_at']
    list_filter = ['tool_key', 'updated_at']
    readonly_fields = ['created_at', 'updated_at']
    search_fields = ['user__username', 'user__email', 'tool_key']


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ['code', 'label', 'tier', 'provider', 'billing_interval', 'price_cents', 'currency', 'is_active']
    list_filter = ['tier', 'provider', 'billing_interval', 'is_active', 'is_public']
    search_fields = ['code', 'label', 'description', 'provider_price_id']


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'plan', 'status', 'provider', 'current_period_end', 'cancel_at_period_end']
    list_filter = ['status', 'provider', 'plan']
    search_fields = ['user__username', 'user__email', 'provider_customer_id', 'provider_subscription_id']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(BillingWebhookEvent)
class BillingWebhookEventAdmin(admin.ModelAdmin):
    list_display = ['event_id', 'event_type', 'provider', 'processed_at', 'created_at']
    list_filter = ['provider', 'event_type', 'processed_at']
    search_fields = ['event_id', 'event_type']
    readonly_fields = ['created_at', 'processed_at']


@admin.register(AccountNotification)
class AccountNotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'notification_type', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['title', 'message', 'user__username', 'user__email']
    readonly_fields = ['created_at', 'read_at']


@admin.register(UsageLimit)
class UsageLimitAdmin(admin.ModelAdmin):
    list_display = ['feature_code', 'tier', 'period', 'limit', 'is_active']
    list_filter = ['tier', 'period', 'is_active']
    search_fields = ['feature_code']


@admin.register(UsageRecord)
class UsageRecordAdmin(admin.ModelAdmin):
    list_display = ['user', 'feature_code', 'amount', 'created_at']
    list_filter = ['feature_code', 'created_at']
    search_fields = ['user__username', 'user__email', 'feature_code']
    readonly_fields = ['created_at']


@admin.register(EmailVerificationRequest)
class EmailVerificationRequestAdmin(admin.ModelAdmin):
    list_display = ['email', 'user', 'expires_at', 'used_at', 'created_at']
    list_filter = ['used_at', 'expires_at', 'created_at']
    search_fields = ['email', 'user__username', 'user__email']
    readonly_fields = ['created_at']
