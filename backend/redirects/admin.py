from django.contrib import admin

from .models import Redirect, WordPressImportRecord


@admin.register(Redirect)
class RedirectAdmin(admin.ModelAdmin):
    list_display = ['old_path', 'new_url', 'status_code', 'is_prefix', 'is_active', 'source', 'hits', 'last_hit_at']
    list_filter = ['is_active', 'is_prefix', 'source', 'status_code']
    search_fields = ['old_path', 'new_url', 'note']
    readonly_fields = ['hits', 'last_hit_at', 'created_at', 'updated_at']


@admin.register(WordPressImportRecord)
class WordPressImportRecordAdmin(admin.ModelAdmin):
    list_display = ['entity', 'wordpress_id', 'object_id', 'source_format', 'last_imported_at']
    list_filter = ['entity', 'source_format']
    search_fields = ['=wordpress_id', '=object_id']

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
