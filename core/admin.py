from django.contrib import admin

from .models import (
    AuditLog,
    CookiePreference,
    Department,
    Notification,
    Policy,
    PolicyConsent,
    Role,
    RoleAssignment,
    UserProfile,
)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'is_internal', 'is_active', 'sort_order')
    list_filter = ('is_internal', 'is_active')
    search_fields = ('code', 'name')


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'kind', 'parent', 'is_active')
    list_filter = ('kind', 'is_active')
    search_fields = ('code', 'name')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'department', 'approval_status', 'is_demo_account', 'must_change_password', 'updated_at')
    list_filter = ('approval_status', 'is_demo_account', 'must_change_password')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')


@admin.register(RoleAssignment)
class RoleAssignmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'department', 'is_approved', 'approved_at')
    list_filter = ('role', 'is_approved')
    search_fields = ('user__username', 'department__name', 'role__name')
    filter_horizontal = ('assigned_areas',)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'kind', 'is_read', 'created_at')
    list_filter = ('kind', 'is_read')
    search_fields = ('user__username', 'title', 'message')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'actor', 'action', 'object_type', 'object_id')
    list_filter = ('action', 'object_type')
    search_fields = ('actor__username', 'action', 'object_id')
    readonly_fields = ('created_at',)


@admin.register(Policy)
class PolicyAdmin(admin.ModelAdmin):
    list_display = ('title', 'policy_type', 'version', 'status', 'is_required', 'effective_date', 'updated_at')
    list_filter = ('policy_type', 'status', 'is_required')
    search_fields = ('title', 'slug', 'version')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(PolicyConsent)
class PolicyConsentAdmin(admin.ModelAdmin):
    list_display = ('user', 'policy', 'version', 'status', 'accepted_at', 'withdrawn_at', 'updated_at')
    list_filter = ('policy__policy_type', 'status')
    search_fields = ('user__username', 'user__email', 'policy__title', 'version')
    readonly_fields = ('accepted_at', 'created_at', 'updated_at')


@admin.register(CookiePreference)
class CookiePreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'essential_cookies_accepted', 'optional_cookies', 'updated_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at')
