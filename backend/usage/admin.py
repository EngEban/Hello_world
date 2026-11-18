from django.contrib import admin

from .models import FeatureUsagePolicy, UsageCounter


@admin.register(FeatureUsagePolicy)
class FeatureUsagePolicyAdmin(admin.ModelAdmin):
    list_display = ('feature_code', 'label', 'limits_enabled', 'meter_anonymous', 'anonymous_daily_limit', 'admin_bypass', 'updated_at')
    list_filter = ('limits_enabled', 'meter_anonymous', 'admin_bypass')
    search_fields = ('feature_code', 'label')


@admin.register(UsageCounter)
class UsageCounterAdmin(admin.ModelAdmin):
    list_display = ('subject', 'feature_code', 'period', 'period_start', 'count', 'updated_at')
    list_filter = ('feature_code', 'period')
    search_fields = ('subject', 'feature_code')
    readonly_fields = ('subject', 'feature_code', 'period', 'period_start', 'count', 'updated_at')
