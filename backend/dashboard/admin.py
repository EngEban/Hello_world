from django.contrib import admin
from .models import (
    ContactSubmission,
    DashboardActivityLog,
    JobApplication,
    JoinTeamEntry,
    NewsletterSubscriber,
    ResearchOpportunity,
    ServiceDefinition,
    ServiceRequest,
    SiteSettings,
    TeamMember,
)

admin.site.register(ContactSubmission)
admin.site.register(JobApplication)
admin.site.register(NewsletterSubscriber)
admin.site.register(TeamMember)
admin.site.register(SiteSettings)


@admin.register(JoinTeamEntry)
class JoinTeamEntryAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'sort_order', 'action_url', 'updated_at')
    list_filter = ('status', 'icon_key')
    search_fields = ('title', 'description', 'action_url', 'seo_title', 'seo_description')
    prepopulated_fields = {'slug': ('title',)}


@admin.register(DashboardActivityLog)
class DashboardActivityLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'module', 'action', 'actor', 'object_label', 'message')
    list_filter = ('module', 'action', 'created_at')
    search_fields = ('message', 'object_label', 'actor__username', 'actor__email')
    readonly_fields = ('created_at',)


@admin.register(ResearchOpportunity)
class ResearchOpportunityAdmin(admin.ModelAdmin):
    list_display = ('title', 'opportunity_type', 'specialty', 'status', 'deadline', 'is_featured', 'updated_at')
    list_filter = ('status', 'opportunity_type', 'specialty', 'is_featured', 'is_remote')
    search_fields = ('title', 'summary', 'description', 'category', 'organization', 'location')
    prepopulated_fields = {'slug': ('title',)}


@admin.register(ServiceDefinition)
class ServiceDefinitionAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'category', 'assigned_team', 'is_featured', 'updated_at')
    list_filter = ('status', 'category', 'is_featured')
    search_fields = ('title', 'summary', 'description', 'category', 'assigned_team')
    prepopulated_fields = {'slug': ('title',)}


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = ('subject', 'requester_name', 'service', 'status', 'priority', 'assigned_to', 'created_at')
    list_filter = ('status', 'priority', 'service', 'created_at')
    search_fields = ('subject', 'requester_name', 'requester_email', 'message')
