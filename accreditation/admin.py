from django.contrib import admin

from .models import (
    AccreditationArea,
    AccreditationCycle,
    AccreditationLevel,
    AccreditationSubArea,
    AreaAssignment,
    EvidenceComment,
    EvidenceFile,
    EvidenceRequirement,
    EvidenceReview,
    EvidenceSubmission,
    EvidenceVersion,
)


@admin.register(AccreditationCycle)
class AccreditationCycleAdmin(admin.ModelAdmin):
    list_display = ('name', 'academic_year', 'status', 'is_active', 'created_at')
    list_filter = ('status', 'is_active')
    search_fields = ('name', 'academic_year')


@admin.register(AccreditationLevel)
class AccreditationLevelAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'cycle', 'status_label', 'sort_order')
    list_filter = ('cycle',)
    search_fields = ('code', 'name')


@admin.register(AccreditationArea)
class AccreditationAreaAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'level', 'sort_order')
    list_filter = ('level',)
    search_fields = ('code', 'name', 'slug')


@admin.register(AccreditationSubArea)
class AccreditationSubAreaAdmin(admin.ModelAdmin):
    list_display = ('code', 'title', 'area', 'sort_order')
    list_filter = ('area__level', 'area')
    search_fields = ('code', 'title')


@admin.register(EvidenceRequirement)
class EvidenceRequirementAdmin(admin.ModelAdmin):
    list_display = ('code', 'title', 'area', 'subarea', 'deadline', 'is_required', 'sort_order')
    list_filter = ('area__level', 'area', 'is_required')
    search_fields = ('code', 'title', 'required_description')


@admin.register(AreaAssignment)
class AreaAssignmentAdmin(admin.ModelAdmin):
    list_display = ('area', 'department', 'deadline', 'assigned_by', 'updated_at')
    list_filter = ('area__level', 'area', 'department')
    search_fields = ('area__code', 'area__name', 'department__name', 'assigned_by__username')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(EvidenceSubmission)
class EvidenceSubmissionAdmin(admin.ModelAdmin):
    list_display = ('requirement', 'department', 'program_head', 'status', 'current_reviewer', 'last_updated')
    list_filter = ('status', 'requirement__area__level', 'department')
    search_fields = ('requirement__code', 'requirement__title', 'department__name', 'program_head__username')
    readonly_fields = ('created_at', 'last_updated', 'submitted_at', 'closed_at')


@admin.register(EvidenceVersion)
class EvidenceVersionAdmin(admin.ModelAdmin):
    list_display = ('submission', 'version_number', 'submitted_by', 'created_at')
    search_fields = ('submission__requirement__code', 'submitted_by__username')
    readonly_fields = ('created_at',)


@admin.register(EvidenceFile)
class EvidenceFileAdmin(admin.ModelAdmin):
    list_display = ('original_name', 'version', 'uploaded_by', 'created_at')
    search_fields = ('original_name', 'link_url', 'uploaded_by__username')


@admin.register(EvidenceReview)
class EvidenceReviewAdmin(admin.ModelAdmin):
    list_display = ('submission', 'reviewer', 'reviewer_role', 'decision', 'from_status', 'to_status', 'created_at')
    list_filter = ('decision', 'reviewer_role', 'from_status', 'to_status')
    search_fields = ('submission__requirement__code', 'reviewer__username', 'remarks')
    readonly_fields = ('created_at',)


@admin.register(EvidenceComment)
class EvidenceCommentAdmin(admin.ModelAdmin):
    list_display = ('submission', 'author', 'created_at')
    search_fields = ('submission__requirement__code', 'author__username', 'body')
    readonly_fields = ('created_at',)
